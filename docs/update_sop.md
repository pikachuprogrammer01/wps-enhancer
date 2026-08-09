# 更新 SOP 设计：下载 · 安装 · 卸载

> 目标：三阶段流程完善、地址可配置、卸载功能可维护可扩展。
> 状态：**设计稿（v1）**——先评审再实施，实施分三个阶段，每阶段独立交付。

---

## 1. 现状盘点（2026-08 实况）

| 阶段 | 现状 | 缺口 |
|------|------|------|
| 检查 | 三通道（Gitee → GitHub API → 网页端）+ 8s 超时 + UI 兜底 18s | ✅ 已完善 |
| 下载 | `download_file` 重试 3 次（1s/3s/7s） | ❌ 目录写死 `~/Downloads`；❌ 无 zip 完整性校验；❌ 无"下载完成定位文件" |
| 安装 | 纯文本指引（`_REPLACE_GUIDE_MAC/_WIN`） | ❌ 无动作抽象；❌ 安装目录写死在文案里 |
| 卸载 | **无任何功能** | ❌ 无卸载入口；❌ 数据/日志残留清理未定义 |

**可复用的现有资产**：`core/app_paths.py` 已统一各平台数据目录/日志目录/设置路径——卸载清理项可直接基于它解析路径，无需重复平台判断。

---

## 2. 目标 SOP（分平台）

### 2.1 下载阶段（DownloadSop）

```
检查更新（三通道）→ 用户确认 → 下载（重试 3 次）→ 校验 → 完成提示
                                                      │
                                        ┌─────────────┴──────────┐
                                   zip 完整性校验          "打开所在文件夹"按钮
                                  （可解压/大小>0）        （macOS open -R / Win explorer /select）
```

**配置化**（进 AppSettings，UI 可改，默认按平台）：
- `download_dir`：macOS 默认 `~/Downloads`，Windows 默认 `%USERPROFILE%\Downloads`
- 文件名：`WPS增强工具_<version>_<platform>-<arch>.zip`（含版本与架构，避免同名覆盖混淆）

**校验策略**（按强度分级，默认取中档）：
| 级别 | 行为 | 场景 |
|------|------|------|
| 轻 | 文件存在且 >0 字节 | 默认（下载不可靠网络） |
| 中 | zipfile 可完整打开（遍历所有条目） | 推荐，默认 |
| 重 | 校验 sha256（update.json 提供 hash 字段） | 自定义源可带 `sha256`；GitHub 源无 hash 则自动降级为"中" |

### 2.2 安装阶段（InstallSop）

**原则**：不自动替换正在运行的 app（macOS 上替换运行中 .app 会失败/损坏）；提供"引导 + 半自动"。

```
下载完成 → 提示替换指引 → （可选）「打开安装目录」按钮 → 用户退出旧版 → 替换 → 重启
```

**macOS**（ad-hoc 签名，Gatekeeper 限制 → 引导式）：
1. 完全退出旧版
2. 解压 zip → 拖 `WPS增强工具.app` 到「应用程序」覆盖
3. 若提示"无法验证开发者" → 右键 → 打开（或 `xattr -d com.apple.quarantine`）
- **半自动增强（可选）**：「打开下载目录」+「打开应用程序目录」按钮，减少手动找路径

**Windows**（无签名，SmartScreen 限制 → 引导式）：
1. 完全退出旧版
2. 解压 zip 到安装目录覆盖（默认 `%LOCALAPPDATA%\WPSEnhancer` 或用户自定义）
3. SmartScreen 提示 → 更多信息 → 仍要运行

**配置化**：
- `install_dir`：macOS 默认 `/Applications`，Windows 默认 `%LOCALAPPDATA%\WPSEnhancer`（安装指引文案从配置读取，不再写死）

### 2.3 卸载阶段（UninstallSop）

**扩展框架**（注册式，加清理项不改主流程）：

```python
@dataclass
class UninstallItem:
    key: str                      # 稳定标识（app / data / logs / downloads）
    label: str                    # 勾选文案（如「删除本地数据（设置/模板）」）
    resolve: Callable[[], Path]   # 路径解析（基于 core/app_paths.py，平台自适应）
    risky: bool                   # True=默认不勾选 + 需在确认框标注（防误删用户数据）
```

**清理项清单（macOS 与 Windows 通用，路径由 app_paths 解析）**：

| key | label | risky | 说明 |
|-----|-------|-------|------|
| app | 删除应用程序本体 | 否（必选） | macOS `/Applications/WPS增强工具.app`；Windows 安装目录 |
| data | 删除本地数据（设置/模板） | **是** | `Application Support/WPS Enhancer` / `%APPDATA%` 同名目录 |
| logs | 删除日志 | 否（默认勾选） | `~/Library/Logs/WPS Enhancer` / `%LOCALAPPDATA%/WPS Enhancer/Logs` |
| downloads | 删除已下载的更新包 zip | 否（默认勾选） | 下载目录中 `WPS增强工具_*.zip` |

**流程**：
```
设置 → 关于/更新 → 「卸载 WPS 增强工具」→ 勾选清理项 → 二次确认（risky 项标注⚠️）
→ 逐项执行（单项失败只提示该项，不中断其他项）→ 完成提示 + 建议重启
```

**扩展方式**：新增清理项 = 在 `uninstall_items()` 列表加一条 `UninstallItem`；新增平台（如 Linux）= 给 `resolve` 一个平台分支。主流程（勾选 → 确认 → 执行 → 反馈）永不动。

---

## 3. 配置化总览（"后续更改下载/安装地址"）

新增三个设置项（`AppSettings`），全部有 UI：

| 设置项 | 默认值（macOS / Windows） | 影响 |
|--------|--------------------------|------|
| `download_dir` | `~/Downloads` / `%USERPROFILE%\Downloads` | 更新包保存位置 |
| `install_dir` | `/Applications` / `%LOCALAPPDATA%\WPSEnhancer` | 安装/替换指引中的目标目录 |
| `update_url` | Gitee raw（已有） | 检查/下载源 |

> 地址全部配置驱动：改地址 = 改设置，不改代码；升级兼容（旧 settings.json 缺字段走默认值，已有模式）。

---

## 4. 实施路线（分期，每期独立可交付）

| 期 | 内容 | 交付物 |
|----|------|--------|
| **P1** | 下载阶段：`download_dir` 配置化 + zip 完整性校验（中档）+ 「打开所在文件夹」按钮 | 设置项 + 校验 + UI 按钮 |
| **P2** | 卸载功能：`UninstallItem` 框架 + 卸载入口（设置 → 关于）+ 四项清理 + 二次确认 | 可卸载 app 及其数据 |
| **P3** | 安装阶段：`install_dir` 配置化 + 指引文案从配置生成 + 「打开安装目录」按钮 | 安装指引与地址解耦 |

---

## 5. 决策记录（用户已确认）

| 决策点 | 结论 |
|--------|------|
| 卸载入口 | **设置 → 关于 tab 底部**（与版本信息、检查更新同区） |
| data 清理默认勾选 | **默认不勾选**（用户数据防误删；logs/downloads 默认勾选） |
| 校验强度默认值 | **中档**（zipfile 完整解压校验）；重档（sha256）作为自定义源扩展，update.json 可带 `sha256` 字段 |
| P1 实施 | **全部实施**（下载目录配置化 + zip 完整性校验 + 打开所在文件夹按钮） |

