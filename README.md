# Figure 工作台

<img src="static/icon.png" alt="HuaiTrace 图徽" width="120">

> 版本 **0.1.0（测试版）** · 本地单人的「图为主体」科研图管理工具

以论文 Figure 为中心，管理原始数据、图文件与溯源。数据全部留在本机，浏览器操作。

## 启动

- **Windows**：双击 `启动工作台.bat`
- **macOS / Linux**：`./run.sh`

首次运行会自动创建虚拟环境、安装依赖，然后起服务。打开 <http://127.0.0.1:8000>

> 端口被占用时改用命令行：`./.venv/Scripts/python.exe -m uvicorn fw_server:app --host 127.0.0.1 --port 8011`

## 换一台电脑

代码会自举——空仓库克隆下来就能直接跑，首次启动自动建数据库和数据目录。

```bash
git clone https://github.com/Bma110/figure_workspace.git
cd figure_workspace
./run.sh                 # Windows 下双击 启动工作台.bat
```

注意：

1. **不带数据**。`data/`（数据库）与 `.trash/` 不在版本库里，科研文件也不在——新机器起来是**空工作区**。
2. **仓库是私有的**，新机器需要能访问 GitHub。
3. **需要 Python ≥ 3.10**（代码用了 `Path | None` 写法）。

### 数据目录

科研文件的根目录默认 `D:\ResearchData`（Mac/Linux 为 `~/ResearchData`），数据库默认在本目录 `data/fw.db`。两者分别可用 `FW_ROOT` / `FW_DB` 改：

```bat
set FW_ROOT=E:\ResearchData
启动工作台.bat
```

```bash
FW_ROOT=~/ResearchData ./run.sh
```

本机没有 D 盘时，`.bat` 会自动退回到 `%USERPROFILE%\ResearchData`。

### 连数据一起搬

除了代码，额外拷贝两样到新机器的对应位置：

- `data/fw.db` → 新机器同路径（或用 `FW_DB` 指向它）
- 原数据根目录整个拷贝 → 新机器的 `FW_ROOT`

## 用法速览

- **工作区列表** → 新建论文工作区（code 会做成磁盘文件夹），可归档。
- **看板**：新建 Figure 即建同名文件夹；上传源文件落该夹；可粘贴截图作预览。
- **状态**：候选 / 采用 / 弃用 / 待重做 · **重要度**：关键 / 一般 / 辅助 · 标签 · 决策日志。
- **图片预览**：常见格式直接内联；TIF/TIFF 等浏览器不支持的格式，导入时自动转成 PNG 缩略图。
- **溯源**：点图看来源文件、相对路径与 SHA-256。
- **全局检索**：跨论文搜标签 / 文件名 / 样本 / 工作区名。
- **扫描导入**：指向已有文件夹 → 只读发现图片 → 勾选导入为 Figure（原图留档 + 缩略图，不动源文件）。
- **导出**：SourceData / 图注草稿 / 数据可得性（以标「采用」的图为准）。
- **备份**：一键备份数据库 + 文件清单，可选整树拷贝。
- **移除图**：删除（文件夹进 `<工作区>/.trash/`，可找回）或隐藏（看板可切换显示已隐藏）。

## 数据位置

- 代码 / 数据库：本目录 `data/fw.db`
- 科研文件：`D:\ResearchData\<工作区 code>\`

数据库只存索引与元数据，**不存大文件**；文件系统是真源。

## 文档

- [更新日志](CHANGELOG.md) · [工作记录](docs/dev-log.md)
- [文档索引](docs/README.md) · [已知问题 / 开发过程记录](docs/known-issues.md)

## 开发

```bash
./.venv/Scripts/python.exe -m pip install -r requirements.txt
./.venv/Scripts/python.exe -m pytest -q
```
