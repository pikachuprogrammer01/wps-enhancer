# WPS Enhancer — Agent 开发任务清单

## 任务概览

| 编号 | 文件 | 前置任务 |
|------|------|---------|
| Task 01 | 项目骨架（目录 + 空文件） | 无 |
| Task 02 | `core/exceptions.py` | 无 |
| Task 03 | `core/logger.py` | 01 |
| Task 04 | `core/file_io/base.py` | 02 |
| Task 05 | `core/file_io/xlsx_handler.py` | 04 |
| Task 06 | `core/file_io/xls_handler.py` | 04 |
| Task 07 | `features/phone_export/config.py` | 01 |
| Task 08 | `features/phone_export/processor.py` | 04, 07 |
| Task 09 | `ui/components/file_picker.py` | 01 |
| Task 10 | `ui/components/status_bar.py` | 01 |
| Task 11 | `features/phone_export/panel.py` | 02, 03, 04, 07, 08, 09, 10 |
| Task 12 | `features/phone_export/__init__.py` | 11 |
| Task 13 | `ui/main_window.py` | 12 |
| Task 14 | `main.py` | 13 |

---

## Task 01 — 项目骨架初始化

**前置任务**：无
**必读文档**：CLAUDE.md → SPEC.md

### 目标
创建项目所需的全部目录结构、空 `__init__.py` 文件和 `requirements.txt`，不包含任何业务逻辑。

### 要创建的目录
```
wps_enhancer/
├── core/
│   └── file_io/
├── features/
│   └── phone_export/
├── ui/
│   └── components/
└── logs/           ← 不创建，程序启动时自动创建，此处仅创建 .gitkeep
```

### 要创建的文件

**1. requirements.txt**
```
PyQt6==6.11.0
openpyxl==3.1.5
xlrd==2.0.2
xlwt==1.3.0
pyinstaller==6.21.0
```

**2. 空 `__init__.py`（仅写一行注释说明所属模块，内容留空）**
- `core/__init__.py`
- `core/file_io/__init__.py`
- `features/__init__.py`
- `features/phone_export/__init__.py`（注意：Task 12 会正式实现此文件，此处保持空白）
- `ui/__init__.py`
- `ui/components/__init__.py`

**3. `logs/.gitkeep`**（空文件，仅用于 git 追踪空目录）

### 禁止行为
- 禁止在任何文件中写入任何业务逻辑或 import 语句
- 禁止创建 TASKS.md 中未列出的文件

### 验收标准
- `requirements.txt` 版本号与 SPEC.md 完全一致
- 所有 `__init__.py` 文件内容为空或仅包含一行注释
- 目录结构与 CLAUDE.md 中目录职责表完全对应

---

## Task 02 — core/exceptions.py

**前置任务**：无
**必读文档**：CLAUDE.md → CLAUDE-detailed.md（第四节「异常使用规范」）

### 目标
定义项目全局统一的异常体系，只定义不捕获。

### 要实现的内容

实现以下 5 个异常类，均继承自 `WpsEnhancerError`：

| 类名 | 说明 |
|------|------|
| `WpsEnhancerError` | 基类，继承自 `Exception` |
| `FileReadError` | 文件无法读取（格式损坏 / 权限不足 / 不支持的格式） |
| `ColumnNotFoundError` | 配置的列名在 Sheet headers 中不存在 |
| `DataProcessError` | 数据处理过程中的意外异常 |
| `FileWriteError` | 输出文件写入失败 |

每个异常类：
- 接收 `message: str` 参数
- 调用 `super().__init__(message)`
- 包含一行注释说明触发场景

### 禁止行为
- 禁止在此文件中 import 任何项目内部模块
- 禁止在此文件中 catch 任何异常
- 禁止添加 CLAUDE-detailed.md 异常继承结构之外的异常类

### 验收标准
- 所有类均可正常实例化：`FileReadError("test message")`
- `isinstance(FileReadError("x"), WpsEnhancerError)` 返回 True
- 文件不超过 40 行

---

## Task 03 — core/logger.py

**前置任务**：01
**必读文档**：CLAUDE.md → CLAUDE-detailed.md（第五节「日志规范」）

### 目标
提供统一的日志记录接口，所有模块通过此文件获取 logger，禁止直接使用标准库 `logging`。

### 要实现的内容

实现以下 1 个公开函数：

**`get_logger(module_name: str) -> logging.Logger`**
- 功能说明：根据模块名返回配置好的 logger
- 日志文件路径：`logs/wps_enhancer_<YYYYMMDD>.log`（每天自动切换）
- 若 `logs/` 目录不存在，自动创建
- 日志格式：`%(asctime)s | %(levelname)-7s | %(name)s | %(message)s`
  - `asctime` 格式：`%Y-%m-%d %H:%M:%S`
- Handler 配置：同时输出到文件（`TimedRotatingFileHandler`，按天切换）和控制台（`StreamHandler`）
- 同一 `module_name` 多次调用返回同一个 logger（利用 logging 模块的缓存机制）

### 禁止行为
- 禁止在此文件中硬编码日志文件路径字符串，路径必须通过代码构造
- 禁止在此文件中捕获任何异常
- 禁止直接实例化 `logging.Logger`，通过 `logging.getLogger(module_name)` 获取

### 验收标准
- 调用 `get_logger("test")` 后，`logs/` 目录自动创建
- 连续两次调用 `get_logger("test")` 返回同一对象（`is` 判断为 True）
- 日志文件命名符合 `wps_enhancer_YYYYMMDD.log` 格式

---

## Task 04 — core/file_io/base.py

**前置任务**：02
**必读文档**：CLAUDE.md → CLAUDE-detailed.md（第三节「文件 IO 使用模式」+ 第一节 SheetData）

### 目标
定义文件读写层的所有数据结构、抽象基类和工厂函数，是整个文件 IO 层的唯一权威接口。

### 要实现的内容

**数据结构（dataclass）**

1. **`SheetData`**
   - `sheet_name: str`
   - `headers: List[str]`
   - `rows: List[Dict[str, str]]`

2. **`CellStyle`**
   - `background_color: Optional[str] = None`（hex 颜色，如 `"#FF0000"`，None 表示无样式）

3. **`MergeRange`**
   - `row_start: int`（从数据区第 0 行开始，不含表头行）
   - `row_end: int`（包含，与 row_start 相同表示不合并）
   - `col_index: int`（0 索引）

4. **`WriteRequest`**
   - `file_path: str`
   - `headers: List[str]`
   - `data_rows: List[List[str]]`（`data_rows[row_idx][col_idx]` = 值）
   - `merge_ranges: List[MergeRange]`
   - `cell_styles: Dict[Tuple[int, int], CellStyle]`（key 为 `(row_idx, col_idx)`，0 索引，从数据区开始）

**抽象基类**

5. **`BaseReader`**（`ABC`）
   - `get_sheet_names(file_path: str) -> List[str]`：抽象方法，读取所有 Sheet 名称
   - `read_sheet(file_path: str, sheet_name: str) -> SheetData`：抽象方法，读取指定 Sheet

6. **`BaseWriter`**（`ABC`）
   - `write_export(request: WriteRequest) -> None`：抽象方法，执行写入

**工厂函数**

7. **`get_reader(file_path: str) -> BaseReader`**
   - `.xlsx` 扩展名 → 返回 `XlsxHandler` 实例（从 `xlsx_handler` 模块延迟导入）
   - `.xls` 扩展名 → 返回 `XlsHandler` 实例（从 `xls_handler` 模块延迟导入）
   - 其他扩展名 → 抛出 `FileReadError`（message 含文件路径和扩展名）

8. **`get_writer(file_path: str) -> BaseWriter`**
   - 规则同 `get_reader`，但返回对应格式的 Writer

注意：工厂函数中使用**延迟 import**（在函数内部 import），避免循环依赖。

### 禁止行为
- 禁止在此文件中 import openpyxl、xlrd 或 xlwt
- 禁止在抽象基类中包含任何业务逻辑
- 禁止在数据结构中使用 `Optional` 以外的 Union 类型
- `WriteRequest` 的 `cell_styles` key 必须使用 `Tuple[int, int]`，禁止用字符串

### 验收标准
- 所有 dataclass 可正常实例化
- `BaseReader` 和 `BaseWriter` 均无法直接实例化（ABC 约束）
- `get_reader("test.xlsx")` 不抛出异常（即使文件不存在，工厂函数本身只做路由）
- `get_reader("test.csv")` 抛出 `FileReadError`

---

## Task 05 — core/file_io/xlsx_handler.py

**前置任务**：04
**必读文档**：CLAUDE.md → CLAUDE-detailed.md（第三节「文件 IO 使用模式」）

### 目标
实现 xlsx 格式的读写 Handler，使用 openpyxl。

### 要实现的内容

**`XlsxReader(BaseReader)`**

1. **`get_sheet_names(file_path: str) -> List[str]`**
   - 说明：用 openpyxl 打开文件，返回所有 Sheet 名称列表
   - 失败时抛出 `FileReadError`（message 含文件路径 + 原始错误）
   - 打开文件时使用 `read_only=True, data_only=True`

2. **`read_sheet(file_path: str, sheet_name: str) -> SheetData`**
   - 说明：读取指定 Sheet，第一行作为 headers，其余行转换为 `Dict[str, str]`
   - 所有单元格值转换为 `str`（None 转为空字符串 `""`）
   - 失败时抛出 `FileReadError`

**`XlsxWriter(BaseWriter)`**

3. **`write_export(request: WriteRequest) -> None`**
   - 说明：创建新 workbook，写入表头、数据、合并单元格、背景色
   - 写入表头（第 1 行）
   - 逐行写入 `request.data_rows`（从第 2 行开始）
   - 处理 `request.merge_ranges`：
     - 调用 `sheet.merge_cells(start_row, start_column, end_row, end_column)`
     - openpyxl 的行列均为 **1 索引**，需要将 `MergeRange` 中的 0 索引转换
     - 数据区偏移：MergeRange 的行 0 = 文件第 2 行（表头占第 1 行）
   - 处理 `request.cell_styles`：
     - `CellStyle.background_color` 不为 None 时，设置 `PatternFill(fill_type="solid", fgColor=<去掉#前缀的颜色>)`
   - 保存到 `request.file_path`
   - 失败时抛出 `FileWriteError`

### 禁止行为
- 禁止 import xlrd 或 xlwt
- 禁止在此文件中包含任何业务逻辑（如手机号校验）
- 合并单元格后，被合并的非首行单元格禁止写入任何值

### 验收标准
- `get_sheet_names` 能正确读取一个有多个 Sheet 的 xlsx 文件
- `read_sheet` 能正确处理含空单元格的 xlsx（空单元格转为 `""`）
- `write_export` 生成的文件能被 openpyxl 正常打开并验证合并范围

---

## Task 06 — core/file_io/xls_handler.py

**前置任务**：04
**必读文档**：CLAUDE.md → CLAUDE-detailed.md（第三节「文件 IO 使用模式」）

### 目标
实现 xls 格式的读写 Handler，读取用 xlrd，写入用 xlwt。

### 要实现的内容

**`XlsReader(BaseReader)`**

1. **`get_sheet_names(file_path: str) -> List[str]`**
   - 用 `xlrd.open_workbook(file_path)` 打开，返回 `workbook.sheet_names()`
   - 失败时抛出 `FileReadError`

2. **`read_sheet(file_path: str, sheet_name: str) -> SheetData`**
   - 用 xlrd 读取指定 Sheet
   - 第 0 行作为 headers（`sheet.row_values(0)`）
   - 其余行转换为 `Dict[str, str]`，key 为 header，value 调用 `str()` 转换
   - xlrd 数字型单元格（如 `1.0`）转换时，若值为整数则去掉小数点（`"1"` 而非 `"1.0"`）
   - 空单元格统一转为 `""`
   - 失败时抛出 `FileReadError`

**`XlsWriter(BaseWriter)`**

3. **`write_export(request: WriteRequest) -> None`**
   - 用 `xlwt.Workbook(encoding="utf-8")` 创建新 workbook
   - 写入表头（第 0 行，xlwt 0 索引）
   - 逐行写入 `request.data_rows`（从第 1 行开始）
   - 处理 `request.merge_ranges`：
     - 调用 `sheet.merge(r1, r2, c1, c2)`，所有参数为 0 索引
     - 数据区偏移：MergeRange 的行 0 = xlwt 第 1 行（表头占第 0 行）
     - 合并后只向起始单元格写入值
   - 处理 `request.cell_styles`：
     - 创建 `xlwt.XFStyle`，设置 `Pattern` 的 `pattern` 为 `Pattern.SOLID_PATTERN`
     - `fore_colour` 使用 xlwt 的预定义颜色索引
     - `#FF0000`（红色）对应 xlwt 颜色索引 `2`（`xlwt.Style.colour_map` 中的 `red`）
   - 保存到 `request.file_path`
   - 失败时抛出 `FileWriteError`

### xlwt 数字单元格处理（重要）
xlrd 读取数字型单元格时 `cell.ctype == 2`，值为 float。转换规则：
```
value = sheet.cell_value(row, col)
if sheet.cell_type(row, col) == 2:  # XL_CELL_NUMBER
    value = int(value) if value == int(value) else value
str_value = str(value) if value != "" else ""
```

### 禁止行为
- 禁止 import openpyxl
- xlwt 颜色只支持有限的预定义颜色，禁止尝试使用任意 hex 颜色
- 禁止在此文件中包含任何业务逻辑

### 验收标准
- `read_sheet` 读取含数字的 xls 文件时，整数 `1.0` 转为 `"1"` 而非 `"1.0"`
- `write_export` 生成的 xls 文件可被 xlrd 正常打开

---

## Task 07 — features/phone_export/config.py

**前置任务**：01
**必读文档**：CLAUDE.md → CLAUDE-detailed.md（第一节 ColumnMapping） → features/phone_export/SPEC.md（第二节「列映射配置」）

### 目标
定义 `ColumnMapping` dataclass，存储列映射的 MVP 默认值，无任何逻辑。

### 要实现的内容

**`ColumnMapping`（dataclass）**

| 字段 | 类型 | 默认值 |
|------|------|--------|
| `source_name_col` | `str` | `"法定代表人"` |
| `source_phone_col` | `str` | `"有效手机号"` |
| `target_name_col` | `str` | `"姓名"` |
| `target_phone_col` | `str` | `"家庭手机"` |

每个字段附一行注释说明含义。

### 禁止行为
- 禁止在此文件中包含任何函数或方法
- 禁止使用 `field()` 的 `validator` 或任何校验逻辑
- 禁止 import 除 `dataclasses` 之外的任何模块

### 验收标准
- `ColumnMapping()` 可无参数实例化，四个字段均有正确默认值
- 文件不超过 20 行

---

## Task 08 — features/phone_export/processor.py

**前置任务**：04, 07
**必读文档**：CLAUDE.md → CLAUDE-detailed.md（全部） → features/phone_export/SPEC.md（第三至五节）

### 目标
实现 `phone_export` 功能的全部纯业务逻辑，无 IO，无 UI。

### 要实现的数据结构

**`ExportRow`（dataclass）** — 按 CLAUDE-detailed.md 第一节定义实现，字段和类型完全一致。

**`PreviewData`（dataclass）** — 按 CLAUDE-detailed.md 第一节定义实现，字段和类型完全一致。

### 要实现的函数（按依赖顺序）

**1. `validate_phone(phone: str) -> bool`**
- 说明：校验单个手机号是否合法，不修改输入（调用方负责 strip）
- 规则按 features/phone_export/SPEC.md 第五节严格实现
- 空字符串 `""` 返回 `True`（此函数不处理空值，但须保证行为一致）

**2. `split_phones(raw_phone: str) -> List[str]`**
- 说明：将原始手机号字符串分割为有效段列表
- 按 `;` 分割，每段 `strip()`，过滤掉空字符串
- 若过滤后列表为空，返回 `[]`（空列表，不返回含空字符串的列表）

**3. `validate_columns(data: SheetData, mapping: ColumnMapping) -> None`**
- 说明：校验 mapping 中配置的源列名是否存在于 SheetData.headers
- 校验 `source_name_col` 和 `source_phone_col` 均存在
- 任一不存在 → 抛出 `ColumnNotFoundError`
- ColumnNotFoundError 的 message 格式：`"列 '{col}' 在 Sheet '{sheet_name}' 中不存在，当前列名为：{headers}"`

**4. `build_export_rows(name: str, phones: List[str], row_index: int) -> List[ExportRow]`**
- 说明：根据姓名和手机号列表，构建对应的 ExportRow 列表
- `phones` 为空列表时：返回 1 条 `phone="", phone_valid=True, merge_span=1, is_name_cell=True`
- `phones` 非空时：
  - 共生成 `len(phones)` 条 ExportRow
  - 所有条的 `merge_span = len(phones)`
  - 第 0 条 `is_name_cell=True`，其余为 `False`
  - 每条的 `phone_valid = validate_phone(phone.strip())`

**5. `build_preview_data(data: SheetData, mapping: ColumnMapping) -> PreviewData`**
- 说明：主入口，将 SheetData 转换为 PreviewData
- 先调用 `validate_columns`（可能抛出 ColumnNotFoundError，不捕获，向上传播）
- 若 `data.rows` 为空，返回 `PreviewData(rows=[], invalid_count=0, invalid_summary=[])`
- 逐行处理：取 source_name_col 和 source_phone_col 的值 → split_phones → build_export_rows
- 汇总所有 `phone_valid=False` 的 ExportRow，构建 invalid_summary（格式见 SPEC.md 第五节末尾）
- 意外异常包装为 `DataProcessError` 后抛出

**6. `build_write_request(preview: PreviewData, mapping: ColumnMapping, output_path: str) -> WriteRequest`**
- 说明：将 PreviewData 转换为 WriteRequest，供 file_io 层使用
- `headers = [mapping.target_name_col, mapping.target_phone_col]`
- `data_rows`：每条 ExportRow 生成 `[name if is_name_cell else "", phone]`
- `merge_ranges`：遍历 ExportRow，找到所有 `is_name_cell=True` 且 `merge_span > 1` 的行
  - `MergeRange(row_start=当前数据行idx, row_end=当前数据行idx + merge_span - 1, col_index=0)`
- `cell_styles`：对所有 `phone_valid=False` 的 ExportRow 按其在 data_rows 中的行索引
  - `{(row_idx, 1): CellStyle(background_color="#FF0000")}`

### 禁止行为
- 禁止在此文件中 import openpyxl、xlrd、xlwt 或任何 UI 组件
- 禁止在此文件中调用 `open()`、`print()` 或任何 IO 操作
- 禁止捕获 `ColumnNotFoundError`（让它传播到 panel.py）
- `build_export_rows` 禁止直接调用 `validate_phone` 以外的外部函数

### 验收标准
- `validate_phone("+8613800000000")` 返回 `True`
- `validate_phone("13800000000")` 返回 `True`
- `validate_phone("12800000000")` 返回 `False`（第 2 位不在 3-9 范围）
- `validate_phone("1380000000")` 返回 `False`（10 位）
- `split_phones("138;139 ; ; 137")` 返回 `["138", "139", "137"]`
- `split_phones("")` 返回 `[]`
- `validate_columns` 传入缺失列时抛出 `ColumnNotFoundError`

---

## Task 09 — ui/components/file_picker.py

**前置任务**：01
**必读文档**：CLAUDE.md

### 目标
实现文件选择器 Widget，仅负责展示路径和触发文件选择，不包含任何业务逻辑。

### 要实现的内容

**`FilePicker(QWidget)`**

构造函数参数：
- `label: str`（显示在选择框左侧的标签文字）
- `file_filter: str`（文件对话框的过滤规则，默认 `"Excel 文件 (*.xls *.xlsx)"`）
- `parent: Optional[QWidget] = None`

UI 构成（水平布局）：
- `QLabel`（显示 `label` 参数）
- `QLineEdit`（只读，显示当前选择的文件路径，初始为空）
- `QPushButton`（文字为「浏览...」）

信号：
- `file_selected = pyqtSignal(str)`（用户选择文件后发出，参数为文件绝对路径）

方法：
- `_on_browse_clicked(self) -> None`：点击「浏览...」时调用 `QFileDialog.getOpenFileName`，用户确认后更新 QLineEdit 并发出 `file_selected` 信号
- `get_file_path(self) -> str`：返回当前选择的文件路径（未选时返回空字符串）
- `clear(self) -> None`：清空当前路径

### 禁止行为
- 禁止在此 Widget 中 import 任何项目内部业务模块
- 禁止在此 Widget 中做文件格式校验（格式校验由 file_io 层负责）

### 验收标准
- Widget 可独立实例化并展示（无依赖）
- 点击「浏览...」按钮后弹出文件选择对话框
- 用户选择文件后 `file_selected` 信号被发出，`get_file_path()` 返回正确路径

---

## Task 10 — ui/components/status_bar.py

**前置任务**：01
**必读文档**：CLAUDE.md

### 目标
实现底部状态栏 Widget，显示操作状态和消息，不包含任何业务逻辑。

### 要实现的内容

**`StatusBar(QWidget)`**

UI 构成（水平布局）：
- `QLabel`（显示状态消息，默认文字为空，初始隐藏）

公开方法（每个方法只做两件事：设置文字 + 设置颜色样式）：
- `show_info(self, message: str) -> None`：深灰色文字
- `show_success(self, message: str) -> None`：绿色文字
- `show_error(self, message: str) -> None`：红色文字
- `show_warning(self, message: str) -> None`：橙色文字
- `clear(self) -> None`：清空文字，隐藏 label

### 禁止行为
- 禁止在此 Widget 中 import 任何项目内部业务模块
- 禁止在此 Widget 中包含任何非 UI 逻辑

### 验收标准
- Widget 可独立实例化
- 调用各方法后 label 文字和颜色正确变化

---

## Task 11 — features/phone_export/panel.py

**前置任务**：02, 03, 04, 07, 08, 09, 10
**必读文档**：CLAUDE.md → CLAUDE-detailed.md（全部） → features/phone_export/SPEC.md（全部）

### 目标
实现 `phone_export` 功能的完整 UI 面板，负责业务流程的编排、异常捕获、日志记录和用户交互。

### UI 布局结构

```
PhoneExportPanel (QWidget, 垂直布局)
├── 文件选择区 (QGroupBox)
│   ├── FilePicker（标签：「源文件」）
│   └── Sheet 选择下拉框 (QComboBox, 初始禁用)
│
├── 预览区 (QGroupBox，初始隐藏)
│   ├── 汇总标签 (QLabel)
│   ├── 警告区 (QWidget, 红色背景，仅 invalid_count>0 时可见)
│   │   └── 警告内容 (QLabel, 滚动展示 invalid_summary)
│   ├── 预览表格 (QTableWidget, 2列, 初始展示 30 行)
│   └── 展开/收起按钮 (QPushButton, 总行数>30 时可见)
│
└── 操作区 (水平布局, 右对齐)
    ├── StatusBar
    └── 操作按钮 (QPushButton, 初始禁用)
```

### 要实现的方法

**初始化**
- `__init__(self, parent=None)`：初始化所有 UI 组件，连接所有信号槽，设置初始状态
- `_setup_ui(self) -> None`：纯 UI 布局代码，不包含逻辑

**数据加载**
- `_on_file_selected(self, file_path: str) -> None`
  - 调用 `get_reader(file_path).get_sheet_names(file_path)` 获取 Sheet 列表
  - 成功：填充 Sheet 下拉框，启用下拉框，记录 INFO 日志
  - 失败（FileReadError）：调用 `_handle_error`

- `_on_sheet_changed(self, sheet_name: str) -> None`
  - 若 sheet_name 为空则返回
  - 获取当前文件路径，调用 `get_reader(file_path).read_sheet(file_path, sheet_name)` 获取 SheetData
  - 成功：调用 `build_preview_data(data, ColumnMapping())` 获取 PreviewData，再调用 `_display_preview`
  - 失败（FileReadError / ColumnNotFoundError / DataProcessError）：调用 `_handle_error`

**预览展示**
- `_display_preview(self, preview: PreviewData) -> None`
  - 更新汇总标签（文案按 SPEC.md 第六节「预览面板」表格）
  - 若 `invalid_count > 0`：显示警告区，填充 invalid_summary 内容，按钮文字改为「忽略并继续导出」
  - 若 `invalid_count == 0`：隐藏警告区，按钮文字改为「确认导出」
  - 填充预览表格前 30 行（若总行数 > 30，显示展开按钮）
  - `phone_valid=False` 的单元格设置红色背景
  - 显示预览区，启用操作按钮
  - 将 `preview` 对象保存到 `self._preview_data`（供导出时使用）

- `_toggle_preview_rows(self) -> None`
  - 展开：显示全部行，按钮文字改为「收起」
  - 收起：只显示前 30 行，按钮文字改为「展开查看全部 {N} 行」

**导出流程**
- `_on_export_clicked(self) -> None`
  - 构造默认输出路径（源文件目录 + 源文件名_yyyyMMddHHmmss + 原扩展名）
  - 调用 `QFileDialog.getSaveFileName` 让用户确认路径
  - 用户取消：直接返回
  - 用户确认：调用 `_write_file(output_path)`

- `_write_file(self, output_path: str) -> None`
  - 调用 `build_write_request(self._preview_data, ColumnMapping(), output_path)` 获取 WriteRequest
  - 调用 `get_writer(output_path).write_export(request)` 执行写入
  - 成功：调用 `_handle_success(output_path)`，记录 INFO 日志
  - 失败（FileWriteError）：调用 `_handle_error`

**错误与成功处理**
- `_handle_error(self, error: WpsEnhancerError) -> None`
  - 记录 ERROR 日志（含完整 error message）
  - 调用 `status_bar.show_error(str(error))`
  - 弹出 `QMessageBox.critical` 对话框

- `_handle_success(self, output_path: str) -> None`
  - 记录 INFO 日志
  - 调用 `status_bar.show_success(f"导出成功，文件已保存至：{output_path}")`

### 禁止行为
- 禁止在此文件中直接 import openpyxl、xlrd 或 xlwt
- 禁止在 `_display_preview` 以外的方法中操作 QTableWidget 的内容
- 禁止在 `_on_sheet_changed` 之外直接调用 `build_preview_data`
- 禁止捕获 `Exception` 基类，只捕获 `WpsEnhancerError` 及其具体子类
- `self._preview_data` 在 `_display_preview` 之前禁止被其他方法访问

### 验收标准
- 选择有效 xlsx 文件后 Sheet 下拉框正确填充
- 选择 Sheet 后预览区出现，前 30 行显示，超出 30 行时展开按钮出现
- `phone_valid=False` 的单元格显示红色背景
- 点击导出按钮后文件保存对话框弹出，默认名称符合规格
- 文件写入成功后状态栏显示成功信息
- 任意步骤出错后只展示错误弹窗，不崩溃

---

## Task 12 — features/phone_export/__init__.py

**前置任务**：11
**必读文档**：CLAUDE.md → CLAUDE-detailed.md（第七节「新增 feature 的步骤」）

### 目标
通过 `__init__.py` 将 `PhoneExportPanel` 和功能名称暴露给主窗口自动发现机制。

### 要实现的内容

```python
FEATURE_NAME: str = "手机号导出"

from .panel import PhoneExportPanel as Panel
```

仅两行有效内容，不引入任何其他代码。

### 验收标准
- `from features.phone_export import FEATURE_NAME, Panel` 可正常执行
- `FEATURE_NAME == "手机号导出"`
- `Panel` 是 `PhoneExportPanel` 类本身

---

## Task 13 — ui/main_window.py

**前置任务**：12
**必读文档**：CLAUDE.md → SPEC.md（第三节「功能扩展模型」→ 自动发现机制）

### 目标
实现主窗口，自动扫描 `features/` 目录下的所有功能子包并以标签页形式加载。

### 要实现的内容

**`MainWindow(QMainWindow)`**

- `__init__(self, parent=None)`
  - 设置窗口标题：`"WPS Enhancer"`
  - 设置最小尺寸（宽 900，高 600）
  - 调用 `_load_features()`
  - 调用 `_setup_ui()`

- `_load_features(self) -> None`
  - 扫描 `features/` 目录下所有直接子目录
  - 对每个子目录，尝试以 `features.<子目录名>` 为模块名 import
  - 若 import 成功且模块有 `FEATURE_NAME` 和 `Panel` 属性，则将其加入 `self._features: List[Tuple[str, Type[QWidget]]]`
  - 若 import 失败，记录 WARNING 日志后跳过，不中断启动

- `_setup_ui(self) -> None`
  - 创建 `QTabWidget`
  - 遍历 `self._features`，为每个 `(FEATURE_NAME, Panel)` 创建 `Panel()` 实例并以 `FEATURE_NAME` 为标签添加到 Tab
  - 将 `QTabWidget` 设为 central widget
  - 若 `self._features` 为空，显示提示标签「未找到任何功能模块」

### 禁止行为
- 禁止硬编码任何功能模块名（必须通过目录扫描动态发现）
- 禁止在此文件中 import 任何具体的 feature 模块（动态 import 通过 `importlib.import_module` 实现）
- 禁止在 `_load_features` 中捕获 `Exception` 基类以外的异常（允许宽泛捕获以保证启动不崩溃）

### 验收标准
- 在 `features/` 下有 `phone_export` 子包时，主窗口自动出现「手机号导出」标签页
- 新增一个合法的 feature 子包后，无需修改 `main_window.py` 即可出现新标签页
- 某个 feature import 失败时，其余 feature 正常加载，主窗口正常启动

---

## Task 14 — main.py

**前置任务**：13
**必读文档**：CLAUDE.md

### 目标
实现唯一入口文件，只负责创建应用实例、显示主窗口和启动事件循环。

### 要实现的内容

实现 `main()` 函数，包含以下 4 行核心逻辑：
1. 创建 `QApplication(sys.argv)`
2. 创建 `MainWindow()`
3. 调用 `window.show()`
4. 调用 `sys.exit(app.exec())`

在 `if __name__ == "__main__":` 块中调用 `main()`。

### 禁止行为
- 禁止在此文件中 import 任何 feature 模块
- 禁止在此文件中包含任何业务逻辑
- 文件不超过 20 行

### 验收标准
- 运行 `python main.py` 后主窗口弹出
- 窗口关闭后进程正常退出，返回码为 0
