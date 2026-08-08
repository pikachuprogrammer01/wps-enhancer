# WPS Enhancer

为 WPS 表格提供增强功能的跨平台桌面应用。

## 当前功能

| 功能 | 描述 | 状态 |
|------|------|------|
| **Excel 批量导入通讯录** | 选择源表格与模板，按列映射生成新表格，支持 xlsx / xls / csv / vcf / txt 导出 | 已实现 |

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
# 必须用 python3.12（依赖只装在 3.12，系统默认 python3 可能是其他版本）
python3.12 main.py
```

### 运行单元测试

```bash
# 全部测试（模板系统 / 导出层 / 转换逻辑 / UI 冒烟 / 端到端）
python3.12 -m unittest discover tests -v
```

### 打包为独立可执行文件

```bash
# 注意：必须设置 PYINSTALLER_CONFIG_DIR（本机 ~/Library/Application Support/pyinstaller
# 旧缓存被 macOS TCC 保护，不设置会报 PermissionError 打包失败）
PYINSTALLER_CONFIG_DIR=/tmp/pyinstaller-cache python3.12 -m PyInstaller "WPS增强工具.spec" --noconfirm
```

产物：`dist/WPS增强工具.app`（macOS）/ `dist/WPS增强工具`（无 GUI 壳环境）。

> 打包模式：**onedir**（模块直接放在 `.app` 内，启动即用，约 0-1s；此前 onefile 每次启动解包到临时目录需 5-6s）。spec 中 `excludes` 排除了 `tkinter`/`lib2to3`/`pydoc_data`/`test`/`unittest` 等运行用不到的模块。

### 验证打包产物

1. 运行：`open "dist/WPS增强工具.app"`
2. 查看日志确认功能模块加载成功（打包版日志在 `~/Library/Logs/WPS Enhancer/wps_enhancer_<日期>.log`）：
   - ✅ 出现 `INFO | main | 应用启动`
   - ✅ **没有** `WARNING | ui.main_window | 加载功能 ... 失败`（出现即说明打包漏了模块，检查 spec 的 `hiddenimports`）
3. 源码版日志在项目 `logs/` 目录

## Excel 批量导入通讯录功能说明

从源表格文件（`.xls` / `.xlsx` / `.csv`）中读取数据，选择或创建**模板**（模板定义新表格的列结构，持久化于应用目录 `template/` 文件夹），系统按「模板列 + 内置列别名」自动匹配源表列并支持手动调整，生成新表格。

- **模板系统**：模板 = 名称 + 列集合，每模板一个文件存于 `template/`，启动时自动加载展示
- **内置列**：姓名 / 手机 / 公司名 / 网址，支持增删改查并持久化
- **列映射**：自动匹配（精确列名 + 别名）+ 手动调整，未匹配列标黄提示
- **手机号处理**：校验、标红、姓名合并可在全局设置中调整（默认：校验开、标红开、合并关）
- **导出格式**：xlsx / xls / csv（编码可配置）/ vcf（vCard 3.0，字段可配置）/ txt（分隔符可配置）；默认导出格式为 **vcf**
- **预览所见即所得**：xlsx/xls 表格预览；csv/txt/vcf 直接展示导出文件的真实文本内容（vcf 含姓名前后缀与时间戳效果）
- **vcf 姓名自定义**：前缀（默认 `vcf_`）+ 后缀 + 「使用时间戳（年月日）」开关 + 时间戳位置（姓名前/姓名后），方便导入通讯录后按前缀批量管理
- **vcf 多手机号区分**：同一姓名对应多个手机号时，姓名自动追加 `_1`、`_2`…（从 1 累加；单手机号不加），预览可见
- **全局设置**：主窗口设置入口，配置项对后续功能通用

详细规格见 `features/contacts_import/SPEC.md`，模板系统设计见 `docs/template_system.md`。

## 项目结构

```
├── main.py                      # 应用入口
├── core/                        # 公共基础设施
│   ├── exceptions.py            # 全局异常定义
│   ├── logger.py                # 统一日志模块
│   ├── settings.py              # 全局设置（settings.json）读写入口
│   ├── app_paths.py             # 应用路径工具
│   ├── template/                # 模板系统（模型/存储/匹配/管理器）
│   └── file_io/                 # 文件读写抽象层
│       ├── base.py              # Reader/Writer 抽象接口
│       ├── xlsx_handler.py      # xlsx 格式处理
│       ├── xls_handler.py       # xls 格式处理
│       ├── csv_handler.py       # csv 格式处理
│       ├── vcf_handler.py       # vcf 格式写入
│       └── txt_handler.py       # txt 格式写入
├── features/                    # 功能模块（每个功能一个子包）
│   └── contacts_import/         # Excel 批量导入通讯录
│       ├── config.py            # 配置与数据结构
│       ├── processor.py         # 纯业务逻辑（无 IO、无 UI）
│       ├── panel.py             # UI 面板
│       └── SPEC.md              # 功能规格文档
├── docs/                        # 设计文档
│   └── template_system.md       # 模板系统设计文档
├── template/                    # 用户模板目录（运行时创建）
└── ui/                          # 通用 UI 组件
    ├── main_window.py           # 主窗口（自动发现功能面板 + 设置入口）
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

无需修改 `main_window.py`。需要"按模板生成表格"的新功能可直接复用 `core/template/`（见 `docs/template_system.md`）。

## 许可证

本项目基于 [MIT License](LICENSE) 开源。
