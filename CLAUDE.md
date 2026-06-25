# WPS Enhancer — AI 工作指南

## 项目简介
为 WPS 表格提供增强功能的跨平台桌面应用，当前功能：手机号导出（`phone_export`）。

## 技术栈（已锁定，禁止自行修改或引入新依赖）

| 用途 | 库 | 版本 |
|------|----|------|
| GUI | PyQt6 | 6.11.0 |
| xlsx 读写 | openpyxl | 3.1.5 |
| xls 读取 | xlrd | 2.0.2 |
| xls 写入 | xlwt | 1.3.0 |
| 打包 | PyInstaller | 6.21.0 |
| Python | — | 3.12.x |

## 目录职责

| 路径 | 职责（一句话） |
|------|---------------|
| `core/exceptions.py` | 全局统一异常定义，只定义不捕获 |
| `core/logger.py` | 统一日志入口，所有模块通过此模块记录日志 |
| `core/file_io/base.py` | Reader/Writer 抽象接口，features/ 只能通过此层访问文件 |
| `core/file_io/xlsx_handler.py` | xlsx 格式的 Reader/Writer 具体实现 |
| `core/file_io/xls_handler.py` | xls 格式的 Reader/Writer 具体实现 |
| `features/phone_export/` | 手机号导出功能完整子包 |
| `ui/main_window.py` | 主窗口，负责扫描并加载各 feature 的 Panel |
| `ui/components/` | 可复用 UI 组件 |
| `logs/` | 运行时日志目录（程序启动时自动创建） |

## 必读顺序（每次任务开始前）

1. 本文件（CLAUDE.md）— 了解全局约定和禁令
2. `CLAUDE-detailed.md` — 数据结构 + 接口签名 + 规范细节
3. 对应功能的 `features/<功能名>/SPEC.md` — 所实现功能的完整规格

## 铁律（无例外，违反即为错误实现）

1. 每个函数只做一件事，超过 20 行必须拆分
2. 函数所有依赖通过参数传入，禁止读取全局变量
3. 模块间传递数据使用已定义的 dataclass，禁止使用裸字典
4. `processor.py` 中的函数必须是纯函数（相同输入始终返回相同输出）
5. 失败通过抛出自定义异常传递，禁止用 `return None` 表示失败
6. 每个函数必须有完整类型注解（参数类型 + 返回值类型）
7. 每个函数必须有一行注释说明其职责

## 禁止行为（此处列出是因为模型常在此产生幻觉）

- 在 `processor.py` 中读写文件或调用任何 UI 组件
- 在 `file_io/` 中包含业务逻辑或数据转换
- 在 `panel.py` 以外的文件中捕获自定义异常（`WpsEnhancerError` 及其子类）
- 在 `features/` 中直接 import openpyxl、xlrd 或 xlwt
- 新建未在 SPEC.md 中定义的 dataclass 或数据结构
- 引入 requirements.txt 之外的任何第三方依赖
- 用 `return None` 或 `print()` 传递错误信息