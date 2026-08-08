# 模板系统设计文档

> 状态：设计稿（等待用户审查后进入编码）
> 关联文档：`features/contacts_import/SPEC.md`、`CLAUDE-detailed.md`

## 一、定位与目标

模板系统是**公共基础设施**（`core/template/`），不属于任何具体功能模块。

目标：

1. **模板持久化**：模板由模板系统生成独立文件存放本地 `<应用目录>/template/` 文件夹，模板名由用户输入，文件名 = 模板名。程序启动时扫描该目录，读取所有模板并展示。
2. **无缝扩展**：后续任何新功能都可以复用 `TemplateManager` 和列匹配引擎，无需修改模板系统本身。新功能只需：读取模板 → 匹配源表列 → 生成新表格。
3. **列匹配**：凭借「模板的列定义 + 内置列别名」与源表列名做自动匹配，支持用户手动调整覆盖。

## 二、目录结构

```
core/template/
├── __init__.py      # 暴露 TemplateManager、Template、TemplateColumn
├── config.py        # dataclass 定义 + 默认值（无任何逻辑）
├── store.py         # 模板文件 JSON 存取、模板列表扫描（文件 IO）
├── matcher.py       # 列匹配引擎（纯函数）
└── manager.py       # TemplateManager：模板 CRUD 编排（依赖通过参数传入）
```

职责边界遵循项目铁律：`config.py` 无逻辑；`matcher.py` 纯函数；`store.py` 只做文件读写（异常抛 `FileReadError` / `FileWriteError`）；`manager.py` 编排 CRUD 与命名规则（非法文件名处理），异常抛 `TemplateError`（新增于 `core/exceptions.py`）。

## 三、数据模型（`core/template/config.py`）

### TemplateColumn — 模板中的一列

```python
@dataclass
class TemplateColumn:
    key: str           # 语义键（稳定标识，如 name / phone / company / website / custom_1）
    name: str          # 列显示名（导出的表头文字）
    enabled: bool = True  # 导出时是否包含该列
```

### Template — 一个模板

```python
@dataclass
class Template:
    name: str                  # 模板名（也是文件名的来源）
    columns: List[TemplateColumn]
    mappings: Dict[str, str] = field(default_factory=dict)  # 建议映射：模板列 key → 源表列名
```

`mappings` 为可选建议映射：应用模板时优先恢复（作为手动映射传入匹配引擎），未建议的列走自动匹配；模板文件版本升级为 2，v1 旧文件（无 `mappings`）兼容加载（缺省空字典）。

### BuiltinColumn — 内置列（语义字段，可增删改查）

```python
@dataclass
class BuiltinColumn:
    key: str               # 语义键（创建时分配，不再修改）
    label: str             # 显示名（用户可改）
    aliases: List[str]     # 匹配别名（用户可增删，用于自动匹配）
```

### 默认内置列（首次启动写入 settings.json）

| key | label | 默认 aliases |
|-----|-------|-------------|
| `name` | 姓名 | `["姓名", "姓", "名称", "联系人", "名字"]` |
| `phone` | 手机 | `["手机", "手机号", "电话", "联系电话", "有效手机号", "家庭手机", "手机号码", "联系方式"]` |
| `company` | 公司名 | `["公司", "公司名", "公司名称", "单位", "企业名称"]` |
| `website` | 网址 | `["网址", "官网", "网站", "官网网址", "主页", "网址链接"]` |

用户可对内置列执行增（自定义 key 如 `custom_1`）、删、改（label/aliases）、查。

### 别名默认匹配逻辑

别名匹配为**双向包含关系**：源列名 `strip()` 后与别名**完全相等**，或源列名**包含**别名且长度不超过别名 + 4 个字符（防止「家庭电话」误配到「电话」类长列名？不，此处简化：仅完全相等匹配）。

> 设计决策：v1 采用**完全相等匹配**（源列名 == 模板列名 或 == 任一别名），避免误配。模糊匹配（包含/相似度）列为未来扩展点，不进入 v1。

## 四、存储设计

### 模板目录

- 路径：`core/app_paths.py` 新增 `get_templates_dir() -> Path`，指向 `<应用目录>/template/`
- 应用启动时自动创建该目录（不存在时），与 `logs/` 行为一致

### 模板文件格式（JSON，每模板一个文件）

文件：`<应用目录>/template/<模板名>.json`

```json
{
  "name": "企业通讯录",
  "version": 1,
  "columns": [
    { "key": "name",    "name": "姓名",   "enabled": true },
    { "key": "phone",   "name": "手机",   "enabled": true },
    { "key": "company", "name": "公司名", "enabled": true },
    { "key": "website", "name": "网址",   "enabled": true }
  ]
}
```

### 文件名规则（`manager.py` 中实现）

1. 非法字符：模板名中的 `\ / : * ? " < > |` 替换为 `_`
2. 首尾空白去除；空名禁止（抛 `TemplateError`）
3. 重名处理：目标文件名已存在时自动追加 `_2`、`_3`……（如 `企业通讯录_2.json`）
4. 模板展示名 = JSON 内 `name` 字段（与文件名解耦，重名模板展示名不冲突）

### 全局设置文件

路径：`<应用目录>/settings.json`

```json
{
  "builtin_columns": [
    { "key": "name", "label": "姓名", "aliases": ["姓名", "姓", "名称"] }
  ],
  "app_settings": {
    "phone_validate": true,
    "phone_highlight": true,
    "phone_merge": false,
    "phone_separators": [",", ";", "、", " ", "\n", "|"],
    "csv_encoding": "utf-8-bom",
    "txt_encoding": "utf-8-bom",
    "txt_separator": " ",
    "vcf_fields": ["name", "phone", "company", "website"],
    "vcf_name_prefix": "vcf_",
    "vcf_name_suffix": "",
    "vcf_timestamp": true,
    "vcf_timestamp_position": "prefix",
    "declaration_detect": true,
    "declaration_keywords": ["企查查", "天眼查", "爱企查", "启信宝", "水滴信用", "导出数据", "导出声明", "数据来源", "声明"],
    "log_debug": false
  }
}
```

| 设置键 | 可选值 | 默认 | 说明 |
|--------|--------|------|------|
| `phone_validate` | `true` / `false` | `true` | 是否校验手机号格式 |
| `phone_highlight` | `true` / `false` | `true` | 非法手机号是否标红 |
| `phone_merge` | `true` / `false` | `false` | 同一姓名多手机号是否合并姓名单元格（仅 xlsx/xls） |
| `csv_encoding` | `utf-8-bom` / `utf-8` / `gbk` / `utf-16` / `unicode` | `utf-8-bom` | csv 输出编码（`unicode` 即 UTF-16 LE with BOM 的别名，见 SPEC） |
| `txt_encoding` | 同 `csv_encoding` 可选值 | `utf-8-bom` | txt 输出编码（默认带 BOM，Windows 记事本友好） |
| `txt_separator` | `" "` / `"\t"` / `","` / `"、"` / `"|"` / 自定义字符串 | `" "` | txt 行内分隔符 |
| `phone_separators` | 字符串列表 | `[, ; 、 空格 换行 \|]` | 同一姓名多手机号的分隔符，按序拆分；未勾选合并时每个手机号单独一行 |
| `vcf_fields` | 内置列 key 列表 | 四字段全选 | vcf 导出包含的字段；**映射到的才导出** |
| `vcf_name_prefix` | 任意字符串 | `vcf_` | vcf 姓名前缀（纯文本，配合时间戳形成 `vcf_20260808张三` 效果） |
| `vcf_name_suffix` | 任意字符串 | `""` | vcf 姓名后缀 |
| `vcf_timestamp` | `true` / `false` | `true` | 是否在 vcf 姓名上附加年月日时间戳（`YYYYMMDD`） |
| `vcf_timestamp_position` | `prefix` / `suffix` | `prefix` | 时间戳位置：`prefix`=姓名前（`vcf_20260808张三`）、`suffix`=姓名后（`vcf_张三20260808`） |
| `declaration_detect` | `true` / `false` | `true` | 声明行检测：首行为导出声明（如企查查/天眼查等）时自动跳过，以第二行为表头 |
| `declaration_keywords` | 字符串列表 | 见默认值 | 声明关键词（逗号分隔编辑），**仅首行单非空单元格时**命中即视为声明行；多格行不做关键词判定（防误判），结构判定（单格+次行多列）不依赖关键词 |
| `log_debug` | `true` / `false` | `false` | 详细日志开关：开启后 AOP 日志（DEBUG 级别）输出到日志文件，便于排查；异常日志不受影响始终输出 |

## 五、列匹配引擎（`core/template/matcher.py`，纯函数）

### 输入输出

```python
@dataclass
class ColumnMatch:
    template_col: TemplateColumn   # 模板列
    source_col: Optional[str]      # 匹配到的源表列名；未匹配为 None
    status: str                    # "manual" | "exact" | "alias" | "none"

def match_columns(
    headers: List[str],
    template: Template,
    builtin_columns: List[BuiltinColumn],
    manual_map: Dict[str, str] = {},   # {模板列 key: 源列名}，UI 手动指定
) -> List[ColumnMatch]
```

### 匹配优先级（对每个模板列，按序尝试，命中即停）

1. **manual**：`manual_map` 中该模板列 key 有指定 → 直接采用（即使源列名不在 headers 中也采用，由调用方校验）
2. **exact**：源表 headers 中某列 `strip()` 后与模板列 `name` 完全相等
3. **alias**：模板列 key 对应的内置列 aliases 中，某别名与源表某列 `strip()` 后完全相等
4. **none**：均未命中 → `source_col=None`

### 约束

- 同一源列只能被匹配一次（先匹配到的模板列占用该源列，后匹配者跳过该源列继续找下一个）
- 匹配顺序：模板列按模板中的排列顺序依次匹配
- 纯函数：不读文件、不访问全局状态、不写日志

## 六、模板 CRUD 流程（`core/template/manager.py`）

| 操作 | 行为 |
|------|------|
| 创建（手动） | 输入模板名 → 从内置列勾选 + 手动添加自定义列 → 保存 JSON |
| 创建（从表格导入） | 选择 `.xls/.xlsx/.csv` 文件 → 读取第一个 Sheet 表头 → 每个表头列生成 `TemplateColumn`（自动用内置列别名识别 key，未识别的 key=`custom_<n>`，name=表头原文）→ 用户确认列名/勾选 → 保存 |
| 复制 | 基于现有模板复制为新模板（重名规则同上） |
| 重命名 | 修改 JSON 内 `name` 字段 + 移动文件（保持文件名一致） |
| 删除 | 删除对应 JSON 文件 |
| 列编辑 | 增/删列、改列名、勾选 enabled、调整顺序 |

所有 CRUD 返回新的 `Template` 对象或抛 `TemplateError`，由 UI 层（panel）捕获展示。

## 七、模板字段为空与仅匹配字段生效

- **字段支持为空**：模板列未匹配到源列（`source_col=None`，含用户显式选择「不映射」）时，该列在导出中全部填充空字符串，不报错、不阻断流程
- **仅对匹配的字段做模板设置**：模板的列级配置（enabled、映射、未来扩展如样式/格式）只对**匹配到源列**的字段生效；未匹配字段保持默认空值，不参与任何转换与校验
- 匹配引擎输出 `ColumnMatch.status` 即字段是否生效的依据（`manual`/`exact`/`alias` 为生效，`none` 为不生效）

## 八、可扩展性设计（后续模板支持）

模板 JSON 结构面向未来扩展，遵循以下约定：

1. **版本号**：文件含 `version` 字段（当前 `1`）；未来结构升级时递增版本号，`store.py` 按版本兼容读取，旧模板不失效
2. **未知字段容错**：读取时忽略未知键（不报错），保证新版本应用可读取旧模板、旧应用不会因新字段崩溃
3. **列级扩展点**：`TemplateColumn` 允许未来追加可选字段（如样式、格式、vcf 字段标签等），追加时新字段带默认值，旧模板缺失时按默认值处理
4. **内置列与模板解耦**：模板列通过 `key` 引用内置列语义；内置列集合变化（增删改）不影响已保存模板的读取，仅影响自动匹配结果
5. **新功能接入**：新功能复用 `TemplateManager` + `matcher` 即可获得模板持久化与列匹配能力；如需自定义匹配策略，可替换 `matcher` 的实现而不改存储层

## 九、「应用模板」完整流程（供 contacts_import 使用）

1. 用户选择源文件 + Sheet（`core/file_io` 读取 → `SheetData`）
2. 用户选择模板（从 `TemplateManager.list_templates()` 展示的列表中挑选）
3. 点击「应用模板」→ `matcher.match_columns()` 自动匹配 → **直接进入预览与导出步骤**（映射来自模板保存的建议映射，未建议列自动匹配）
4. 如需调整：点「上一步」回到列映射，未匹配列标黄，用户手动调整下拉框
5. 确认映射 → 按映射生成目标表格数据 → 预览
6. 选择导出格式 → 写入文件

## 十、未来扩展点（不在 v1 范围）

- 模糊匹配（包含 / 相似度 / 拼音匹配）
- 模板分组 / 标签
- 模板内容级匹配（依据模板文件内的示例数据判断列语义）——若用户后续有需求，在「从表格导入创建模板」基础上扩展
