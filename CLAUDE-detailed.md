# WPS Enhancer — 详细规范

## 一、所有 dataclass 定义

模块间传递数据**只能**使用以下结构，禁止裸字典。所有结构使用 `@dataclass` 装饰器定义。

### ColumnMapping — `features/phone_export/config.py`

```python
@dataclass
class ColumnMapping:
    source_name_col: str = "法定代表人"   # 源表姓名列名
    source_phone_col: str = "有效手机号"  # 源表手机号列名
    target_name_col: str = "姓"          # 目标表姓名列名
    target_phone_col: str = "家庭手机"   # 目标表手机号列名
    target_name_index: int = 0          # 姓名在 25 列模板中的索引
    target_phone_index: int = 4         # 手机号在 25 列模板中的索引
```

MVP 阶段四个字段均使用默认值，不允许通过 UI 修改。

### SheetData — `core/file_io/base.py`

```python
@dataclass
class SheetData:
    sheet_name: str             # 来源 Sheet 名称
    headers: List[str]          # 第一行列名列表，顺序与文件一致
    rows: List[Dict[str, str]]  # 每行数据，格式为 {列名: 值}，值均转为字符串
```

约定：`rows` 中的字典键与 `headers` 中的值完全一致，值统一转换为 `str`（含空字符串，不使用 `None`）。

### ExportRow — `features/phone_export/processor.py`

```python
@dataclass
class ExportRow:
    name: str              # 姓名（可为空字符串）
    phone: str             # 单个手机号，已拆分，可为空字符串
    merge_span: int        # 该姓名对应的合并总行数（≥1）
    is_name_cell: bool     # 是否是写入姓名的首行（合并起始行）
    phone_valid: bool      # 手机号是否通过校验，空值固定为 True
    source_row_index: int  # 对应源表原始数据行号，从 1 开始计数，表头行不计
```

`source_row_index` 说明：同一源行拆分出的多条 `ExportRow` 共享相同的 `source_row_index`。

### PreviewData — `features/phone_export/processor.py`

```python
@dataclass
class PreviewData:
    rows: List[ExportRow]         # 全量转换结果
    invalid_count: int            # phone_valid=False 的 ExportRow 总数量
    invalid_summary: List[str]    # 每条格式："第 {source_row_index} 行：{phone} 不是合法手机号"
```

---

## 二、模块职责边界

| 模块 | 允许做 | 明确禁止 |
|------|--------|---------|
| `processor.py` | 接收数据、返回数据、抛出自定义异常 | 读写文件、调用任何 UI 组件、打印日志 |
| `file_io/` | 读写文件、格式检测、单元格样式写入 | 包含业务逻辑、做数据转换、抛出非 File 类异常 |
| `panel.py` | 收集用户输入、展示结果、捕获异常、记录日志 | 直接操作文件、直接处理数据逻辑 |
| `config.py` | 定义 dataclass 和默认值 | 任何逻辑运算和条件判断 |
| `exceptions.py` | 定义异常类 | 捕获任何异常 |
| `logger.py` | 提供日志记录接口 | 包含业务逻辑 |

---

## 三、文件 IO 使用模式

### 格式检测规则（在 `core/file_io/` 中实现）

| 文件扩展名 | 使用的 Handler |
|-----------|---------------|
| `.xlsx` | `XlsxHandler`（基于 openpyxl） |
| `.xls` | `XlsHandler`（基于 xlrd / xlwt） |
| 其他 | 抛出 `FileReadError` |

### Reader 抽象接口（`core/file_io/base.py`）

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `get_sheet_names` | `file_path: str` | `List[str]` | 读取文件中所有 Sheet 名称 |
| `read_sheet` | `file_path: str, sheet_name: str` | `SheetData` | 读取指定 Sheet 的表头和数据行 |

### Writer 抽象接口（`core/file_io/base.py`）

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `write_export` | `file_path: str, rows: List[ExportRow], mapping: ColumnMapping` | `None` | 写入导出数据，含合并单元格和背景色标记 |

### 重要约定

- `xlrd 2.0.2` **只能**读取 `.xls`，禁止用它读取 `.xlsx`
- `xlwt 1.3.0` 最大支持 65,536 行 × 256 列，本项目上限 5,000 行，安全
- `xlwt` 已停止维护（2019 年），禁止寻找或引入替代库，当前版本在本项目场景内可用
- `features/` 中的任何模块禁止直接 import openpyxl、xlrd 或 xlwt

---

## 四、异常使用规范

### 异常继承结构（`core/exceptions.py`）

```
WpsEnhancerError（基类）
├── FileReadError        文件无法读取（格式损坏 / 权限不足 / 不支持的格式）
├── ColumnNotFoundError  配置的列名在 Sheet headers 中不存在
├── DataProcessError     数据处理过程中的意外异常（如 Sheet 为空）
└── FileWriteError       输出文件写入失败（路径无权限 / 磁盘空间不足）
```

### 各异常的触发层与捕获层

| 异常类 | 应在哪里抛出 | 应在哪里捕获 |
|--------|------------|------------|
| `FileReadError` | `file_io/` | `panel.py` |
| `ColumnNotFoundError` | `processor.py` | `panel.py` |
| `DataProcessError` | `processor.py` | `panel.py` |
| `FileWriteError` | `file_io/` | `panel.py` |

### 捕获后必须执行的两件事

1. 调用 `logger` 记录 `ERROR` 级别日志（含完整异常信息）
2. 展示错误弹窗给用户（弹窗内容对应异常 message）

捕获后**终止**当前操作，不执行后续步骤。

### 异常 message 格式要求

异常的 `message` 必须包含足够的上下文，不允许使用泛化描述：

| 异常类 | message 示例 |
|--------|-------------|
| `ColumnNotFoundError` | `"列 '有效手机号' 在 Sheet 'Sheet1' 中不存在，当前列名为：['姓名', '电话', ...]"` |
| `FileReadError` | `"无法读取文件 'data.xls'：[Errno 13] Permission denied"` |
| `FileWriteError` | `"无法写入文件 'output.xlsx'：磁盘空间不足"` |

---

## 五、日志规范

### 日志文件

| 项目 | 规格 |
|------|------|
| 路径 | `logs/wps_enhancer_<YYYYMMDD>.log` |
| 策略 | 每天一个文件，自动按日期切换 |
| 编码 | UTF-8 |

### 日志级别使用规则

| 级别 | 使用场景 |
|------|---------|
| `INFO` | 正常操作节点（文件读取成功、导出完成、用户选择 Sheet 等） |
| `WARNING` | 非致命问题（手机号格式异常但用户选择忽略并继续） |
| `ERROR` | 捕获到自定义异常，操作中断 |

### 日志格式

每条日志必须包含以下字段，格式固定：

```
<YYYY-MM-DD HH:MM:SS> | <LEVEL> | <module_name> | <message>
```

示例：

```
2026-06-25 14:30:01 | ERROR   | phone_export.panel | ColumnNotFoundError: 列 '有效手机号' 在 Sheet 'Sheet1' 中不存在，当前列名为：['姓名', '电话']
2026-06-25 14:31:05 | INFO    | phone_export.panel | 导出完成，共 42 行，输出至 /Users/xx/data_20260625143105.xls
2026-06-25 14:29:50 | WARNING | phone_export.panel | 用户选择忽略 3 个格式异常的手机号并继续导出
```

---

## 六、编码规范（含正误示例）

### 规则 1：函数单一职责，超 20 行必须拆分

❌ 错误：一个函数同时读文件、校验列名、处理数据、写日志
✅ 正确：`read_sheet()` 只读文件，`validate_columns()` 只校验列名，各自独立调用

### 规则 2：依赖通过参数传入，不读全局变量

❌ 错误：函数内部直接访问模块级变量 `DEFAULT_MAPPING.source_name_col`
✅ 正确：函数签名明确声明 `def process(data: SheetData, mapping: ColumnMapping) -> PreviewData`

### 规则 3：dataclass 传递，不用裸字典

❌ 错误：`return {"name": "张三", "phone": "138...", "valid": True}`
✅ 正确：`return ExportRow(name="张三", phone="138...", merge_span=1, is_name_cell=True, phone_valid=True, source_row_index=1)`

### 规则 4：processor 层必须是纯函数

❌ 错误：`processor.py` 中调用 `open()`、`openpyxl.load_workbook()` 等文件操作
✅ 正确：所有数据通过参数传入，函数只做计算和转换，返回新的数据结构

### 规则 5：失败抛异常，不用 return None

❌ 错误：`if col not in headers: return None`
✅ 正确：`if col not in headers: raise ColumnNotFoundError(f"列 '{col}' 不存在，当前列名：{headers}")`

### 规则 6：完整类型注解

❌ 错误：`def validate(data, mapping):`
✅ 正确：`def validate(data: SheetData, mapping: ColumnMapping) -> None:`

### 规则 7：一行注释说明职责

❌ 错误：无注释，或注释描述的是实现细节而非职责
✅ 正确：`"""校验 mapping 中配置的列名是否存在于 SheetData 的 headers 中。"""`

---

## 七、新增 feature 的步骤

在 `features/` 下新增功能子包时，必须严格遵循以下顺序和约定：

### 必须包含的文件

| 文件 | 职责 |
|------|------|
| `__init__.py` | 暴露 `FEATURE_NAME: str` 和 `Panel`（QWidget 子类）两个名称 |
| `config.py` | 该功能相关的 dataclass 定义和配置默认值，无任何逻辑 |
| `processor.py` | 纯业务逻辑，无 IO，无 UI |
| `panel.py` | 该功能的 UI 面板，继承 `QWidget`，类名为 `<FeatureName>Panel` |
| `SPEC.md` | 该功能的完整行为规格，先于代码存在 |

### 自动发现机制

`ui/main_window.py` 在启动时扫描 `features/` 下的所有子包，通过 `__init__.py` 中暴露的 `FEATURE_NAME` 和 `Panel` 自动将面板添加到主窗口。**新增功能无需修改 `main_window.py` 以外的任何现有文件。**

### 新增步骤顺序

1. 创建子包目录 `features/<feature_name>/`
2. 先写 `SPEC.md`，明确所有行为规格后再开始实现
3. 按照 `config.py` → `processor.py` → `panel.py` 的顺序实现
4. 最后更新项目级 `SPEC.md` 的功能清单