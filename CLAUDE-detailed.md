# WPS Enhancer — 详细规范

## 一、所有 dataclass 定义

模块间传递数据**只能**使用以下结构，禁止裸字典。所有结构使用 `@dataclass` 装饰器定义。

### TemplateColumn / Template / BuiltinColumn — `core/template/config.py`

```python
@dataclass
class TemplateColumn:
    """模板中的一列。"""
    key: str                # 语义键（稳定标识：name/phone/company/website/custom_<n>）
    name: str               # 列显示名（导出表头）
    enabled: bool = True    # 导出时是否包含

@dataclass
class Template:
    """一个模板 = 名称 + 列集合。"""
    name: str
    columns: List[TemplateColumn]

@dataclass
class BuiltinColumn:
    """内置列（语义字段），可增删改查。"""
    key: str                # 语义键（创建时分配，不再修改）
    label: str              # 显示名（用户可改）
    aliases: List[str]      # 匹配别名（用户可维护）
```

### ColumnMatch — `core/template/matcher.py`

```python
@dataclass
class ColumnMatch:
    """单个模板列的匹配结果。"""
    template_col: TemplateColumn
    source_col: Optional[str]   # 匹配到的源表列名；未匹配为 None
    status: str                 # "manual" | "exact" | "alias" | "none"
```

### MappingConfig — `features/contacts_import/config.py`

```python
@dataclass
class MappingConfig:
    """导入配置：选中的模板 + 列匹配结果。"""
    template: Template
    matches: List[ColumnMatch]
```

### ExportRow — `features/contacts_import/processor.py`

```python
@dataclass
class ExportRow:
    """单条导出数据行（一个手机号占一行；无手机映射时一源行一行）。"""
    values: List[str]           # 与模板 enabled 列一一对应的值列表
    phone_valid: bool           # 该行手机号是否通过校验（未启用校验或空号恒为 True）
    source_row_index: int       # 对应源表数据行号，从 1 开始计数，表头行不计
    merge_span: int = 1         # 同一源行拆分出的行数（1=无拆分）
    is_first_of_split: bool = False  # 拆分组首行（姓名合并起始行）
```

### PreviewData — `features/contacts_import/processor.py`

```python
@dataclass
class PreviewData:
    """数据转换的完整预览结果。"""
    rows: List[ExportRow]
    invalid_count: int          # phone_valid=False 的行数（未启用校验时恒为 0）
    invalid_summary: List[str]  # 每条格式："第 {source_row_index} 行：{phone} 不是合法手机号"
```

### SheetData — `core/file_io/base.py`

```python
@dataclass
class SheetData:
    sheet_name: str             # 来源 Sheet 名称（csv 时为文件名）
    headers: List[str]          # 第一行列名列表，顺序与文件一致
    rows: List[Dict[str, str]]  # 每行数据，格式为 {列名: 值}，值均转为字符串
    declaration_skipped: bool = False  # 是否跳过了首行声明（企查查导出）
```

约定：`rows` 中的字典键与 `headers` 中的值完全一致，值统一转换为 `str`（含空字符串，不使用 `None`）。

### WriteRequest — `core/file_io/base.py`（重构：脱离 25 列模板硬编码）

```python
@dataclass
class WriteRequest:
    """写入输出文件所需的所有信息（通用列结构）。"""
    file_path: str
    headers: List[str]              # 输出表头（= 模板 enabled 列名）
    data_rows: List[List[str]]      # 每行与 headers 一一对应
    merge_ranges: List[MergeRange]  # 仅 xlsx/xls 使用（phone_merge=true 时）
    cell_styles: Dict[Tuple[int, int], CellStyle]  # 仅 xlsx/xls 使用（标红）
    field_keys: Optional[List[str]] = None   # 与 headers 对应的语义 key（vcf 必需）
    encoding: str = "utf-8"         # csv/txt 使用（csv 实际编码由设置决定）
    separator: str = " "            # txt 使用（行内分隔符）
    vcf_fields: Optional[List[str]] = None   # vcf 导出字段（None=全部）
    vcf_name_prefix: str = "vcf_"            # vcf 姓名前缀（纯文本）
    vcf_name_suffix: str = ""                # vcf 姓名后缀
```

### AppSettings — `core/settings.py`

```python
@dataclass
class AppSettings:
    """全局设置（settings.json 的权威结构）。"""
    builtin_columns: List[BuiltinColumn]          # 内置列（可增删改查，持久化）
    phone_validate: bool = True                   # 是否校验手机号
    phone_highlight: bool = True                  # 非法手机号标红
    phone_merge: bool = False                     # 姓名跨行合并（仅 xlsx/xls）
    csv_encoding: str = "utf-8-bom"              # utf-8-bom/utf-8/gbk/utf-16/unicode
    txt_encoding: str = "utf-8-bom"              # txt 输出编码（同 csv 可选值）
    txt_separator: str = " "                      # 空格/tab/逗号/顿号/|/自定义
    phone_separators: List[str] = [逗号,分号,顿号,空格,换行,|]  # 同一姓名多手机号分隔符
    vcf_fields: List[str] = [name,phone,company,website]  # vcf 导出字段
    vcf_name_prefix: str = "vcf_"                # vcf 姓名前缀（纯文本，默认 vcf_）
    vcf_name_suffix: str = ""                    # vcf 姓名后缀
    vcf_timestamp: bool = True                   # 是否在姓名上附加年月日时间戳
    vcf_timestamp_position: str = "prefix"       # 时间戳位置：prefix=姓名前 / suffix=姓名后
    declaration_detect: bool = True   # 声明行检测（自动跳过首行声明）
    declaration_keywords: List[str] = [企查查,天眼查,...]  # 声明关键词（可编辑）
    log_debug: bool = False           # 详细日志开关（AOP）
```

### CellStyle / MergeRange — `core/file_io/base.py`（不变）

```python
@dataclass
class CellStyle:
    background_color: Optional[str] = None

@dataclass
class MergeRange:
    row_start: int   # 数据区 0 索引，不含表头行
    row_end: int
    col_index: int
```

---

## 二、模块职责边界

| 模块 | 允许做 | 明确禁止 |
|------|--------|---------|
| `processor.py` | 接收数据、返回数据、抛出自定义异常 | 读写文件、调用任何 UI 组件、打印日志、读取全局设置（设置通过参数传入） |
| `file_io/` | 读写文件、格式检测、单元格样式写入 | 包含业务逻辑、做数据转换、抛出非 File 类异常 |
| `template/matcher.py` | 纯函数列匹配 | 读写文件、访问全局状态、打印日志 |
| `template/store.py` | 模板文件 JSON 读写、目录扫描 | 包含业务逻辑 |
| `template/manager.py` | 模板 CRUD 编排、命名规则 | 直接操作 UI |
| `core/settings.py` | settings.json 唯一读写入口 | 包含业务逻辑 |
| `panel.py` | 收集用户输入、展示结果、捕获异常、记录日志 | 直接操作文件、直接处理数据逻辑 |
| `config.py` | 定义 dataclass 和默认值 | 任何逻辑运算和条件判断 |
| `exceptions.py` | 定义异常类 | 捕获任何异常 |
| `logger.py` | 提供日志记录接口 | 包含业务逻辑 |

---

## 三、文件 IO 使用模式

### 格式检测规则（在 `core/file_io/` 中实现）

| 文件扩展名 | 读取 | 写入 |
|-----------|------|------|
| `.xlsx` | `XlsxReader`（openpyxl） | `XlsxWriter`（openpyxl） |
| `.xls` | `XlsReader`（xlrd） | `XlsWriter`（xlwt） |
| `.csv` | `CsvReader`（标准库 csv，编码自动探测） | `CsvWriter`（编码按设置） |
| `.vcf` | ❌ | `VcfWriter`（vCard 3.0，字段按设置） |
| `.txt` | ❌ | `TxtWriter`（分隔符按设置） |
| 其他 | 抛出 `FileReadError` | 抛出 `FileWriteError`（不支持写入的格式） |

### Reader 抽象接口（`core/file_io/base.py`）

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `get_sheet_names` | `file_path: str` | `List[str]` | 读取文件中所有 Sheet 名称（csv 返回 `[文件名]`） |
| `read_sheet` | `file_path: str, sheet_name: str, skip_declaration: bool = False` | `SheetData` | 读取指定 Sheet 的表头和数据行；`skip_declaration=True` 时按企查查规则剔除首行声明（`SheetData.declaration_skipped` 标记） |

### Writer 抽象接口（`core/file_io/base.py`）

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `write_export` | `request: WriteRequest` | `None` | 写入导出数据；xlsx/xls 含合并单元格和背景色，csv 按 `encoding` 编码，txt 按 `separator` 分隔且首行表头，vcf 按 `field_keys`+`vcf_fields` 输出 vCard 字段 |

### 重要约定

- `xlrd 2.0.2` **只能**读取 `.xls`，禁止用它读取 `.xlsx`
- `xlwt 1.3.0` 最大支持 65,536 行 × 256 列，本项目上限 5,000 行，安全
- `xlwt` 已停止维护（2019 年），禁止寻找或引入替代库
- `features/` 中的任何模块禁止直接 import openpyxl、xlrd 或 xlwt
- `core/settings.py` 是 `settings.json` 的唯一读写入口，`features/` 禁止直接读写该文件
- 模板文件（`template/*.json`）唯一读写入口是 `core/template/store.py`

---

## 四、异常使用规范

### 异常继承结构（`core/exceptions.py`）

```
WpsEnhancerError（基类）
├── FileReadError        文件无法读取（格式损坏 / 权限不足 / 不支持的格式）
├── ColumnNotFoundError  配置的列名在 Sheet headers 中不存在
├── DataProcessError     数据处理过程中的意外异常（如 Sheet 为空）
├── FileWriteError       输出文件写入失败（路径无权限 / 磁盘空间不足）
└── TemplateError        模板操作失败（空名 / 非法字符 / 目录不可写）
```

### 各异常的触发层与捕获层

| 异常类 | 应在哪里抛出 | 应在哪里捕获 |
|--------|------------|------------|
| `FileReadError` | `file_io/`、`template/store.py` | `panel.py` |
| `ColumnNotFoundError` | `processor.py` | `panel.py` |
| `DataProcessError` | `processor.py` | `panel.py` |
| `FileWriteError` | `file_io/` | `panel.py` |
| `TemplateError` | `template/manager.py`、`template/store.py` | `panel.py`（或设置界面所在 UI 层） |

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
| `TemplateError` | `"模板名不能为空"` / `"无法写入模板目录：权限不足"` |

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
| `DEBUG` | **AOP 自动记录**（`log_call` 装饰器产生的进入/退出/耗时日志），受 `app_settings.log_debug` 开关控制；业务代码不手动写 DEBUG |
| `INFO` | 正常操作节点（文件读取成功、模板应用成功、导出完成等），业务代码手动记录 |
| `WARNING` | 非致命问题（列未匹配但用户确认继续、企查查声明行被跳过等） |
| `ERROR` | 异常（`log_call` 自动记录 + panel 捕获处手动记录） |

### 日志格式

每条日志必须包含以下字段，格式固定：

```
<YYYY-MM-DD HH:MM:SS> | <LEVEL> | <module_name> | <message>
```

示例：

```
2026-08-08 14:30:01 | ERROR   | contacts_import.panel | ColumnNotFoundError: 列 '有效手机号' 在 Sheet 'Sheet1' 中不存在，当前列名为：['姓名', '电话']
2026-08-08 14:31:05 | INFO    | contacts_import.panel | 导出成功，共 42 行，输出至 /Users/xx/data_20260808143105.xls
2026-08-08 14:30:02 | DEBUG   | contacts_import.processor | build_preview_data() 开始，参数: data(5000 行) config(模板=企业通讯录)
2026-08-08 14:30:03 | DEBUG   | contacts_import.processor | build_preview_data() 完成，耗时 12ms
2026-08-08 14:29:50 | WARNING | contacts_import.panel | 已检测到并跳过企查查导出声明行
```

### AOP 日志（`core/logger.py` 的 `log_call` 装饰器）

项目采用**装饰器织入**实现 AOP 日志：对关键函数添加 `@log_call`，自动记录调用生命周期，业务代码零侵入。

```python
def log_call(
    module: str,
    *,
    level: int = logging.DEBUG,
    log_args: bool = True,
    log_result: bool = False,
    mask_keys: Optional[Set[str]] = None,
    max_arg_len: int = 200,
) -> Callable:
    """AOP 装饰器：自动记录函数进入、退出、耗时与异常。"""
```

| 参数 | 默认 | 说明 |
|------|------|------|
| `module` | — | 日志模块名（如 `"contacts_import.processor"`） |
| `level` | `DEBUG` | 进入/退出日志级别（异常始终记 `ERROR`） |
| `log_args` | `True` | 是否记录参数摘要 |
| `log_result` | `False` | 是否记录返回值摘要（默认关，防大对象刷屏） |
| `mask_keys` | `None` | 脱敏键集合（匹配 dict 键名与 kwargs 键名，值替换为 `***`） |
| `max_arg_len` | `200` | 单个参数摘要最大字符数，超出截断加 `…` |

**自动记录行为**：

1. 进入：`{func_name}() 开始，参数: {摘要}`（`log_args=True` 时）
2. 退出：`{func_name}() 完成，耗时 {N}ms`（可选 `，结果: {摘要}`）
3. 异常：`{func_name}() 抛出异常: {TypeName}: {message}` + 完整 traceback，级别 `ERROR`（无论开关）
4. 耗时计算与参数序列化**仅在日志级别允许时执行**（避免性能损耗）
5. 参数摘要规则：`str` 截断；`list/tuple/dict` 显示长度（如 `(5000 项)`）；`SheetData` 显示 `(N 行)`；`Template` 显示 `(模板名)`；`None` 显示 `None`；自定义对象显示类型名

### AOP 织入范围（强制）

| 模块 | 织入函数 | 说明 |
|------|---------|------|
| `core/file_io/*` | `get_sheet_names`、`read_sheet`、`write_export` | 记录文件路径、耗时、异常 |
| `core/template/store.py` | `save`、`load`、`list_templates` | 模板文件 IO |
| `core/template/matcher.py` | `match_columns` | 纯函数，入参摘要 |
| `features/contacts_import/processor.py` | 全部公开函数 | 纯函数，入参/异常 |
| `features/contacts_import/panel.py` | 事件入口（`_on_file_selected` 等） | 异常自动记录 |

`log_debug` 设置关闭时，DEBUG 级别不输出，AOP 进入/退出日志不可见，但 **ERROR 异常日志始终输出**（保证排查底线）。

### 全局开关

`app_settings.log_debug: bool = False`（设置界面「日志」分组可切换）。为排查问题开启后，重启不生效的设置为即时生效（`log_call` 每次调用时读取开关）。

---

## 六、编码规范（含正误示例）

### 规则 1：函数单一职责，超 20 行必须拆分

❌ 错误：一个函数同时读文件、校验列名、处理数据、写日志
✅ 正确：`read_sheet()` 只读文件，`validate_columns()` 只校验列名，各自独立调用

### 规则 2：依赖通过参数传入，不读全局变量

❌ 错误：函数内部直接访问模块级设置或 `core/settings` 的全局实例
✅ 正确：函数签名明确声明 `def process(data: SheetData, config: MappingConfig, settings: AppSettings) -> PreviewData`

### 规则 3：dataclass 传递，不用裸字典

❌ 错误：`return {"name": "张三", "phone": "138...", "valid": True}`
✅ 正确：`return ExportRow(values=[...], phone_valid=True, source_row_index=1)`

### 规则 4：processor 层必须是纯函数

❌ 错误：`processor.py` 中调用 `open()`、`openpyxl.load_workbook()` 等文件操作，或读取 `settings.json`
✅ 正确：所有数据（含设置）通过参数传入，函数只做计算和转换，返回新的数据结构

### 规则 5：失败抛异常，不用 return None

❌ 错误：`if col not in headers: return None`
✅ 正确：`if col not in headers: raise ColumnNotFoundError(f"列 '{col}' 不存在，当前列名：{headers}")`

### 规则 6：完整类型注解

❌ 错误：`def validate(data, mapping):`
✅ 正确：`def validate(data: SheetData, mapping: MappingConfig) -> None:`

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
