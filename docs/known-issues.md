# 已知问题 / 开发过程记录

本文件记录当前已知的限制、有意为之的取舍，以及开发过程中值得留存的经验。按「已知问题」「设计取舍」「开发过程记录」分节。

## 一、已知问题

### 1. Figure 文件夹名会撞车（label 撞名）
**现象**：`naming.folder_slug` 为得到安全的文件夹名，会剥掉**所有空白字符**，只保留中文、字母、数字。于是 `Figure gyh antiacide 40x antiacid ci` 会变成 `Figuregyhantiacide40xantiacidci`；两个仅空格位置不同的 label 会得到**同一个文件夹名**。

**影响**：
- 建图时如遇同名文件夹，`storage` 会用 `unique_name` 追加后缀避免覆盖，所以新建本身不会丢数据。
- 但**删除**时两个节点若 slug 相同，删除其中一个不应连带删掉另一个的文件。当前 `delete_node` 对此做了保护：检测到工作区内存在其它 label 经同一 slug 映射的节点时，**不移动整个文件夹**，改为逐个把本节点及其后代登记的文件移进 `.trash`。

**未做**：把 label 与文件夹名的映射持久化（当前是「每次按 label 现算」），因此重命名 label 不会同步重命名文件夹。

### 2. 旧数据的坏 TIF 预览不修
**背景**：0.1.0 之前，扫描导入把预览**无条件**命名为 `preview.png`，即使源文件是 `.tif`——结果磁盘上是一个「名为 .png、内容却是 TIFF 字节」的文件，浏览器按 PNG 解码失败，缩略图空白。

**现状**：新导入的已修复（TIF 会转成真 PNG）。**已存在的旧坏预览不修复**——用户明确选择「不管旧数据」。如需补救，重新扫描导入对应文件即可。

### 3. 本机 8000 端口被占用
`启动工作台.bat` 固定用 `127.0.0.1:8000`。若端口被占，改用命令行手动指定端口：

```bash
./.venv/Scripts/python.exe -m uvicorn fw_server:app --host 127.0.0.1 --port 8011
```

注意入口是 `fw_server:app`（`fw/api.py` 只有 `router`，没有 `app`）。

### 4. 大 TIF 占双份空间
导入 TIF 时保留**原图 + preview.png**（原图按原名留档，SHA 与原文件一致）。显微扫描图可能很大，接受双份空间占用以换取「缩略图能看」+「溯源可信」。

## 二、设计取舍（有意为之）

- **不做多人/权限/云同步/移动端/ELN**：单人本地工具，明确砍掉以免变成无底洞。
- **不做全文内容检索**：只按标签 / 文件名 / 样本 / 工作区名。
- **数据库只存元数据**：SQLite 不存大文件二进制；文件系统是真源，删记录不等于毁文件。
- **删除即进 `.trash`**：界面上的删除把文件夹移进 `<工作区>/.trash/`，可手动找回，不做永久销毁。
- **迁移靠显式 ALTER**：SQLite 的 `CREATE TABLE IF NOT EXISTS` **不会**给已存在的表补列，因此 `db._migrate` 显式 `ALTER TABLE ADD COLUMN` 补 `archived`（幂等、带默认值，老库安全）。

## 三、开发过程记录

### 顶栏与抽屉曾互抢点击
抽屉的关闭按钮点不动。根因：顶栏是 `position:sticky` + 全宽 + `z-index:25`，盖住了抽屉顶部。修法不是继续叠 z-index，而是让二者**竖向错开**——顶栏固定高度 `--topbar-h:72px`，抽屉 `top:var(--topbar-h)`。仅靠浏览器验收才暴露。

### 仅浏览器验收才能发现的类问题
- **旧 `/app.js` 被缓存**：Chrome 启发式缓存会返回陈旧静态资源，验收时用 `Cache-Control: no-cache` 请求头绕开。
- **Tabbit 验收环境的坑**（与产品无关，记录备查）：
  - 上下文**不接受下载**（`acceptDownloads=false`），`waitForEvent('download')` 永不触发；下载类断言改为拦截 `document.createElement('a')` 记录 `{href, download}` + 直接 `fetch` 校验状态码 / Content-Disposition / 长度。
  - 原生 `prompt/confirm/alert` 被运行时预先关闭，须用 `page.addInitScript` 打桩。
  - 不能在既有上下文里 `newPage`（`Target.createTarget` 报错），须**带目标 URL 启动浏览器**再 `claim` 该标签页。

### 测试状态污染
验收脚本依赖磁盘与 DB 状态，上一轮导入会残留，导致计数断言 `Expected: 1, Received: 2`。修法：每轮跑之前重置临时 `root*` / `fw*.db`，并固定执行顺序。

## 四、尚未做（后续候选）

- Git 远端与 CI（当前仅本地仓库）。
- label 与文件夹名的映射持久化 / 重命名联动。
- 旧坏预览的批量修复工具。
- 拖拽上传、Excel/CSV 在线预览、文件版本回滚、重复文件检测。
