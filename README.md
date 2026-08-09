# WPS Enhancer

为 WPS 表格提供增强功能的跨平台桌面应用（macOS / Windows）。

## 当前功能

| 功能 | 描述 | 状态 |
|------|------|------|
| **Excel 批量导入通讯录** | 选择源表格与模板，按列映射生成新表格，支持 xlsx / xls / csv / vcf / txt 导出 | 已实现 |

> **平台支持**：macOS 与 Windows（PyQt6 跨平台）。路径规范：macOS 打包用 `~/Library/Application Support|Logs`，Windows 打包用 `%APPDATA%` / `%LOCALAPPDATA%`；自动更新按平台下载对应更新包。

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

产物：`dist/WPS增强工具.app`（macOS，显示名中文）/ `dist/WPSEnhancer/`（Windows 产物目录，exe 名 `WPSEnhancer.exe`，ASCII 规避 PowerShell 编码问题）。

> 打包模式：**onedir**（模块直接放在 `.app` 内，启动即用，约 0-1s；此前 onefile 每次启动解包到临时目录需 5-6s）。spec 中 `excludes` 排除了 `tkinter`/`lib2to3`/`pydoc_data`/`test`/`unittest` 等运行用不到的模块。

### 发布新版本（完整流程）

**每次发版只需 2 个动作，其余全自动**：

1. **改版本号**：编辑 `core/version.py` 的 `APP_VERSION`（如 `1.1.0`），提交推送：
   ```bash
   git add core/version.py && git commit -m "chore(version): 版本号更新至 1.1.0"
   git push origin main
   ```
2. **打标签推送**（tag 必须与 `APP_VERSION` 一致，CI 强制校验，不一致直接构建失败）：
   ```bash
   git tag v1.1.0 && git push origin v1.1.0
   ```

**CI 自动完成**（无需人工干预）：macOS 构建 → Windows 构建（串行）→ 上传 Releases（资产 `WPSEnhancer-macOS-arm64.zip` / `WPSEnhancer-Windows-x86_64.zip` 等，带平台+架构）→ 自动生成 `update.json`（version / 四平台 urls / notes=本次 changelog）推回 main。

3. **（可选但推荐）Gitee 立即同步**：若配置了 Gitee 镜像（见下节），发布后到 Gitee 仓库 → 管理 → 镜像仓库 → 点「立即同步」，让 `update.json` 马上生效（不点则按镜像频率自动同步）。
4. **（可选）Gitee 发行版上传 zip**：想让 zip 下载也完全走国内，到 Gitee 仓库「发行版」手动上传 2 个 zip，并把仓库内 `update.json` 的 `urls` 改指 Gitee 直链（约 1 分钟；不做则下载仍走 GitHub release 直链，检查更新走 Gitee）。

**发布验证（3 个检查点）**：GitHub Actions 两个 job 全绿 ✓ ｜ Releases 描述是自动 changelog（不是 "Full Changelog"）✓ ｜ Gitee 仓库 `update.json` 的 version = v1.1.0 ✓

**用户端（用 app 的人）无需任何操作**：默认启动 4 秒后自动检查（设置可关），也可手动「设置 → 更新 → 检查更新」；发现新版弹窗显示更新说明 → 下载到下载目录 → 按指引替换。

> 架构说明：资产名由 CI runner 架构动态生成（macOS `uname -m`；Windows 优先 `PROCESSOR_ARCHITEW6432`，回退 `PROCESSOR_ARCHITECTURE`，映射 `AMD64→x86_64`、`ARM64→arm64`、其余→`x86`）。客户端 `_current_arch()` 同样区分 `arm64` / `x86_64` / `x86` 三档（32 位 Windows 不会误下 64 位包），文件名按 `-` 分词段精确匹配（x86 不会误中 x86_64 资产）。匹配优先级：平台+架构精确匹配 → 回退仅平台（兼容无架构标签的旧资产）。
> 重新发布同一 tag 时旧资产不会自动删除，请先手动清理 Releases 页面残留的旧资产（如 `WPS.-macOS.zip`、`WPS.exe`）。

### 更新源说明（update.json + GitHub × Gitee 联动）

app 默认更新源为 **Gitee 镜像**（`https://gitee.com/pikachuprogrammer01/wps-enhancer/raw/main/update.json`，国内可达），检查失败自动回退 GitHub Releases 双端点；可在 **设置 → 更新 → 自定义更新源** 修改或清空（清空 = 纯 GitHub）。

**GitHub × Gitee 联动原理**：你只提交 GitHub，CI 发布时自动生成最新 `update.json` 并推回 main；Gitee 仓库通过官方镜像同步代码后，`update.json` 即生效——app 从 Gitee 检查更新（快），zip 默认从 GitHub release 下载（`urls` 指向 GitHub 直链）。

**Gitee 仓库准备（一次性）**：

1. Gitee 新建仓库 → 选择「从 GitHub 导入」（Gitee 设置 → 账号绑定中先绑定 GitHub）→ 导入 `wps-enhancer`
2. **删除镜像配置**：仓库 → 「管理」 → 「镜像仓库」 → 删除 GitHub 镜像源——Gitee 镜像仓库是**单向同步且禁止 push**（CI 自动推送会被拒绝），删除后变普通仓库，由 CI 全自动接管同步

**全自动同步（秒级）**：仓库已内置 workflow（`.github/workflows/sync-gitee.yml`），**每次 push main 自动推送到 Gitee**，无需手动点同步。启用只需一次性配置 token：

1. **Gitee 生成私人令牌**：Gitee 头像 → 设置 → 安全设置 → 私人令牌 → 生成新令牌 → **权限只勾选 `projects`（仓库），其余全部不勾**（推送代码唯一必需权限；user/groups/issues/hooks 等一律不需要）→ 有效期建议 90 天或永久 → 复制
2. **GitHub 添加 Secret**：仓库 Settings → Secrets and variables → Actions → New repository secret → 名称填 `GITEE_TOKEN`，值粘贴令牌
3. 下次 push 即自动同步；未配置 token 时 workflow 会跳过并提示（不影响其他流程）

> `--force-with-lease` 保护：Gitee 侧若有手工修改会拒绝推送，不会覆盖你的改动。

**update.json 格式**（CI 自动生成，一般无需手改）：

```json
{
  "version": "1.1.0",
  "urls": {
    "macos-arm64": "https://github.com/.../releases/download/v1.1.0/WPSEnhancer-macOS-arm64.zip",
    "macos-x86_64": "…",
    "windows-x86_64": "…",
    "windows-x86": "…"
  },
  "notes": "本次更新说明（自动取自 changelog，可选）"
}
```

- `version`：版本号（可带 `v` 前缀）
- `urls`：各「平台-架构」的 zip 直链（`macos-arm64` / `macos-x86_64` / `windows-x86_64` / `windows-x86`）
- `notes`：可选，更新说明（显示在更新提示框中）
- 兼容旧格式：单 `url` 字段（只有一条下载地址时）
- 配置错误（非 JSON / 缺 `version` / 缺 `urls` 中当前平台的地址）会直接提示，不会静默回退；仅"源不可达"时回退 GitHub

> ⚠️ 当前 app 为 ad-hoc 签名，从 GitHub 下载的 .app 首次打开需右键 → 打开（或 `xattr -d com.apple.quarantine <路径>`）绕过 Gatekeeper。

### 更新机制架构（零维护设计）

**设计目标**：发布者只提交 GitHub，其余全自动；用户端零操作；任何单点故障都有自动兜底。

```
检查更新（三通道，自动逐级回退）
  ├─ ① Gitee raw update.json（默认，国内可达；CI 发布时自动生成推回 main，镜像同步）
  ├─ ② GitHub API（api.github.com，8s 超时）
  └─ ③ GitHub 网页端（github.com/releases/latest，fastly CDN）

下载更新包（自动重试 3 次，1s/3s/7s 退避）
  └─ GitHub Releases 直链（CI 自动上传；抖动自动重试自恢复）
     （可选优化：Gitee 发行版手动传 zip 后改 update.json 的 urls 走国内下载）
```

**可维护性/可扩展性要点**：

- **更新源配置驱动**：app 端唯一入口是「设置 → 更新 → 自定义更新源」（默认 Gitee，可改可清空），更换/新增更新源**不需要改代码**
- **update.json 格式即契约**：`version` + `urls`（平台-架构映射）+ `notes`；新增平台（如 linux）只需在 `urls` 加一个键，检查代码自动支持
- **错误语义明确**：配置错误（非 JSON / 缺字段）直接提示不静默回退；仅"源不可达"才回退下一通道——排障时一眼看出是配置问题还是网络问题
- **纯标准库**：检查/下载只依赖 urllib + certifi，无第三方运行时依赖；CI 生成 update.json 只依赖 git + python3

**已知边界（诚实说明）**：外部服务（GitHub/Gitee）无法保证 100% 可用；三通道检查 + 下载重试覆盖了绝大多数场景，若 GitHub 与 Gitee 同时不可达，app 会明确提示"检查更新失败"而不是卡死（UI 兜底 18s 保证状态复位）。

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
├── main.py                      # 应用入口（setrecursionlimit 兼容打包环境）
├── core/                        # 公共基础设施
│   ├── exceptions.py            # 全局异常定义
│   ├── logger.py                # 统一日志模块（log_call AOP 装饰器）
│   ├── settings.py              # 全局设置（settings.json）读写入口
│   ├── app_paths.py             # 平台路径（macOS ~/Library / Windows %APPDATA%）
│   ├── mac_paths.py             # macOS 打包专用路径
│   ├── updater.py               # 自动更新（GitHub Releases 检查/比较/下载）
│   ├── version.py               # 应用版本号（APP_VERSION，tag v* 触发发布）
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
│       ├── panel.py             # 主面板（流程编排，组合各 mixin）
│       ├── processor.py         # 纯业务逻辑（无 IO、无 UI）
│       ├── config.py            # 配置与数据结构
│       ├── ui/                  # 界面层拆分
│       │   ├── base.py              # 常量、_safe_slot、弹窗共享引用
│       │   ├── panel_ui.py          # 控件构建
│       │   ├── template_table.py    # 模板表格
│       │   ├── mapping_table.py     # 列映射表格
│       │   ├── preview.py           # 预览展示
│       │   ├── template_actions.py  # 模板管理流程
│       │   └── export_actions.py    # 导出流程
│       └── SPEC.md              # 功能规格文档
├── docs/                        # 设计文档
│   └── template_system.md       # 模板系统设计文档
├── ui/                          # 通用 UI 组件
│   ├── main_window.py           # 主窗口（功能发现 + 设置入口 + 启动自动更新检查）
│   └── components/              # 可复用 UI 组件
│       ├── settings_dialog.py   # 全局设置对话框（导入/导出/内置列/日志/更新）
│       ├── file_picker.py       # 文件选择控件
│       ├── status_bar.py        # 状态栏
│       ├── template_edit_dialog.py # 模板列编辑对话框
│       └── update_flow.py       # 更新检查/下载引导流程
├── .github/workflows/           # CI：tag v* 自动构建 macOS + Windows 并发布
├── tests/                       # 单元/UI/端到端测试（unittest）
└── WPSEnhancer.spec 相关         # 打包配置（WPS增强工具.spec）
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
