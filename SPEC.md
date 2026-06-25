# WPS Enhancer — 项目规格说明

## 一、项目目标与范围

### 是什么

- 为 WPS 表格操作提供增强功能的**跨平台桌面应用**
- 通过图形界面操作，不要求用户有编程能力
- 以独立可执行文件分发（Windows: `.exe`，macOS/Linux: 无扩展名），无需安装 Python 环境

### 不是什么（明确排除，禁止 Agent 自行扩展）

- 不是 WPS 插件（不注入 WPS 进程，不使用 WPS 宏 API）
- 不是命令行工具
- 不操作当前正在被 WPS 打开的文件
- 不连接任何网络服务
- 不支持 Google Sheets、LibreOffice、Excel Online 等其他表格工具

---

## 二、支持的文件格式

| 格式 | 读取 | 写入 | 底层库 |
|------|------|------|--------|
| `.xlsx` | ✅ | ✅ | openpyxl 3.1.5 |
| `.xls` | ✅ | ✅ | xlrd 2.0.2（读）/ xlwt 1.3.0（写） |
| `.csv` | ❌ 不支持 | ❌ 不支持 | — |
| `.et`（WPS 私有格式） | ❌ 不支持 | ❌ 不支持 | — |
| `.ods` | ❌ 不支持 | ❌ 不支持 | — |

**输出格式规则**：输出文件格式必须与输入文件格式完全一致，禁止跨格式转换。

**xls 格式已知限制**：xlwt 1.3.0 最大支持 65,536 行 × 256 列。本项目数据规模上限 5,000 行，在安全范围内。xlwt 自 2019 年起停止维护，禁止在代码中寻找或引入替代库。

---

## 三、功能扩展模型

### 目录约定

每个 WPS 增强功能对应 `features/` 下的一个独立子包，子包命名规则：全小写，下划线分隔（如 `phone_export`）。

### 每个功能子包必须包含的文件

| 文件 | 职责 | 缺少时的影响 |
|------|------|------------|
| `__init__.py` | 暴露 `FEATURE_NAME: str` 和 `Panel` | 主窗口无法自动发现该功能 |
| `config.py` | dataclass 定义 + 配置默认值 | 数据结构无权威来源 |
| `processor.py` | 纯业务逻辑，无 IO，无 UI | 业务逻辑与 IO/UI 耦合 |
| `panel.py` | UI 面板，继承 `QWidget` | 功能无法呈现在主窗口 |
| `SPEC.md` | 该功能的完整行为规格 | Agent 无参考来源，产生幻觉 |

### 自动发现机制

`ui/main_window.py` 在启动时扫描 `features/` 目录下所有子包，读取 `__init__.py` 中的 `FEATURE_NAME` 和 `Panel`，自动将面板作为标签页加载到主窗口。**新增功能无需修改 `main_window.py`。**

---

## 四、公共基础设施约定

### 文件 IO 抽象层

- 路径：`core/file_io/`
- `features/` 中的所有模块禁止直接 import openpyxl、xlrd 或 xlwt
- 所有文件读写必须通过 `core/file_io/base.py` 中定义的抽象接口进行
- 此约定的目的：未来可在不修改功能代码的情况下替换底层 IO 库

### 日志

- 所有模块通过 `core/logger.py` 提供的接口记录日志
- 禁止在功能代码中直接使用 `print()` 或 Python 标准库 `logging` 模块
- 日志文件存储在 `logs/` 目录，程序启动时自动创建该目录（不存在时）

### 异常

- 所有自定义异常必须继承自 `core/exceptions.py` 中的 `WpsEnhancerError`
- 异常只能在各功能的 `panel.py` 中捕获，其他所有模块只负责抛出
- 禁止用 `return None` 或布尔值表示操作失败

---

## 五、当前功能清单

| 功能名 | 子包路径 | 状态 | 规格文档 |
|--------|---------|------|---------|
| 手机号导出 | `features/phone_export/` | MVP | `features/phone_export/SPEC.md` |

---

## 六、依赖版本（已锁定）

```
Python==3.12.x
PyQt6==6.11.0
openpyxl==3.1.5
xlrd==2.0.2
xlwt==1.3.0
pyinstaller==6.21.0
```

禁止引入 `requirements.txt` 之外的任何第三方依赖。

---

## 七、MVP 阶段固定内容

以下内容在 MVP 阶段固定不变，禁止在实现中开放或绕过：

- 列映射配置（`ColumnMapping` 的四个字段）不可在 UI 中修改，使用 `config.py` 默认值
- 支持的文件格式固定为 `.xls` 和 `.xlsx`，不做扩展

---

## 八、已知的后续扩展方向（不在当前实现范围）

- 列映射在 UI 中开放配置
- 更多 WPS 表格增强功能

---

## 九、文档维护约定

修改项目任何内容时，必须同步更新对应文档。**文档与代码不一致时，以文档为准，代码需修正。**

| 变更类型 | 必须同步更新的文件 |
|---------|----------------|
| 新增 feature | `SPEC.md`（功能清单）|
| 新增 feature 且涉及公共目录变化 | `SPEC.md` + `CLAUDE.md`（目录职责表）|
| 修改任何 dataclass | `CLAUDE-detailed.md` + 对应 `features/<name>/SPEC.md` |
| 修改编码规范或铁律 | `CLAUDE.md` + `CLAUDE-detailed.md` |
| 修改业务逻辑 | 对应 `features/<name>/SPEC.md` |
| 修改 MVP 固定值 | 对应 `features/<name>/SPEC.md` + `CLAUDE-detailed.md` |
| 修改依赖版本 | `SPEC.md`（依赖版本）+ `CLAUDE.md`（技术栈表）|