# WPS Enhancer

为 WPS 表格提供增强功能的跨平台桌面应用。

## 当前功能

| 功能 | 描述 | 状态 |
|------|------|------|
| **手机号导出** | 从 Excel 文件中提取姓名和手机号，按通讯录导入模板导出为新文件 | MVP |

## 快速开始

### 环境要求

- Python 3.12.x
- 依赖列表见 `requirements.txt`

### 安装

```bash
# 创建虚拟环境（推荐）
python3.12 -m venv venv
source venv/bin/activate   # macOS / Linux
# venv\Scripts\activate    # Windows

# 安装依赖
pip install -r requirements.txt
```

### 运行

```bash
python main.py
```

### 打包为独立可执行文件

```bash
pyinstaller "WPS增强工具.spec"
```

## 手机号导出功能说明

从源 Excel 文件中读取指定列（默认：`法定代表人` 和 `有效手机号`），将数据转换后写入新文件：

- **手机号拆分**：按英文分号 `;` 分割多个手机号，每个手机号独占一行
- **姓名合并**：同一姓名对应多个手机号时，姓名单元格跨行合并
- **格式校验**：自动校验大陆手机号（11 位数字，1 开头，第二位 3-9），不合法手机号标记红色背景
- **输出格式**：与源文件保持一致（xls→xls，xlsx→xlsx）
- **输出模板**：25 列 WPS 通讯录导入模板

详细规格见 `features/phone_export/SPEC.md`。

## 项目结构

```
├── main.py                      # 应用入口
├── core/                        # 公共基础设施
│   ├── exceptions.py            # 全局异常定义
│   ├── logger.py                # 统一日志模块
│   ├── app_paths.py             # 应用路径工具
│   └── file_io/                 # 文件读写抽象层
│       ├── base.py              # Reader/Writer 抽象接口
│       ├── xlsx_handler.py      # xlsx 格式处理
│       └── xls_handler.py       # xls 格式处理
├── features/                    # 功能模块（每个功能一个子包）
│   └── phone_export/            # 手机号导出
│       ├── config.py            # 配置与数据结构
│       ├── processor.py         # 纯业务逻辑（无 IO、无 UI）
│       ├── panel.py             # UI 面板
│       └── SPEC.md              # 功能规格文档
└── ui/                          # 通用 UI 组件
    ├── main_window.py           # 主窗口（自动发现并加载功能面板）
    └── components/              # 可复用 UI 组件
```

## 技术栈

| 用途 | 库 | 版本 |
|------|----|------|
| GUI | PyQt6 | 6.11.0 |
| xlsx 读写 | openpyxl | 3.1.5 |
| xls 读取 | xlrd | 2.0.2 |
| xls 写入 | xlwt | 1.3.0 |
| 打包 | PyInstaller | 6.21.0 |

## 设计原则

- **纯本地运行**：不连接任何网络服务，不注入 WPS 进程
- **分层架构**：IO 层 → 业务逻辑层 → UI 层，严格分离
- **纯函数设计**：业务逻辑层无副作用，所有依赖通过参数传入
- **失败即抛异常**：用自定义异常传递错误，禁止 `return None` 表示失败

## 扩展新功能

在 `features/` 下创建新的子包（如 `features/my_feature/`），包含以下文件即可被主窗口自动发现和加载：

- `__init__.py` — 暴露 `FEATURE_NAME` 和 `Panel`
- `config.py` — 数据结构定义
- `processor.py` — 纯业务逻辑
- `panel.py` — UI 面板
- `SPEC.md` — 功能规格

无需修改 `main_window.py`。

## 许可证

本项目基于 [MIT License](LICENSE) 开源。
