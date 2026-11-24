# AGENTS.md — Figure 工作台接入说明

面向接手本项目的 agent。这里的约定是代码与配置里读不到的部分；命令与用法见 [README.md](README.md)，文档全集见 [docs/README.md](docs/README.md)。

## 项目定位

本地单人的「以论文 Figure 为主体」科研图管理工具，版本 0.2.1（测试版）。FastAPI 后端 + SQLite 索引 + 原生 JS 前端，无构建步骤，数据全留在本机。

**一条根本事实：文件系统是真源，SQLite 只存索引、关系与元数据，不存大文件二进制。**

## 硬约束

改动必须同时满足以下几条：

- 大文件与二进制只落磁盘（`FW_ROOT`）；数据库只记路径、大小、SHA-256 与元数据。
- 删除走软删除：节点可 `archived` 隐藏/恢复，文件与文件夹移进 `<工作区>/.trash/` 可找回。永久销毁只在用户明确要求时做。
- 所有落盘路径统一经 `naming.folder_slug()` 生成文件夹名、`storage.*` 解析；`storage._dest_dir()` 用 `is_relative_to` 做越界校验，新增写盘逻辑沿用这一层。
- schema 变更在 `fw/db.py` 的 `_SCHEMA` 与 `_COLUMNS` 里做，保持幂等迁移；保留 `PRAGMA foreign_keys = ON` 与级联关系。
- 新接口挂在 `fw/api.py` 的 `router`（prefix `/api`），由 `fw_server.py` 统一挂载并托管 `static/`。前端改动直接改 `static/`，不引入打包器。
- 路径读取一律走 `fw.config` 的 `root_dir()` / `db_path()`（每次调用读 env），不在模块导入时固化路径。测试通过 `tests/conftest.py` 把 `FW_ROOT` / `FW_DB` 指向临时目录。

## 工作流

按顺序完成，每步的完成条件是可检查的。

1. **读指针文档**：按下方「上下文指针」的触发条件取用。完成条件：能说明仓库与数据根目录的关系，并能说出至少两条已知问题。
2. **建立基线**：运行 `./.venv/Scripts/python.exe -m pytest -q`。完成条件：全绿；若有失败，先查清原因再动代码。
3. **定位改动落点**：按「改动落点速查」表找到文件。完成条件：改动文件集合与表一致，没有在 `fw/api.py` 里直接写绕过 `storage` 的磁盘操作。
4. **实现并补测试**：完成条件：`tests/test_*.py` 中有覆盖新行为的新用例或改写用例，`pytest -q` 全绿，且原有用例未被放宽或删除来迁就改动。
5. **涉及界面时验证**：起服务后在浏览器实际操作。完成条件：新交互在 `http://127.0.0.1:8000` 上跑通（端口冲突时按 README 换端口）。

## 改动落点速查

| 改动 | 主要文件 | 配套测试 |
| --- | --- | --- |
| 新增/修改 API | `fw/api.py` | `tests/test_api_*.py` |
| 表结构、字段、迁移 | `fw/db.py`（`_SCHEMA` / `_COLUMNS`） | `tests/test_db.py`、`tests/test_db_migrate.py` |
| 文件夹命名、样本码解析 | `fw/naming.py` | `tests/test_naming.py` |
| 目录建/删、上传落盘、trash、越界校验 | `fw/storage.py` | `tests/test_storage.py` |
| 图片格式归一（TIF/TIFF → PNG） | `fw/imaging.py` | 随导入测试 |
| SourceData / 图注 / 数据可得性导出 | `fw/export.py` | `tests/test_export.py` |
| 路径配置、环境变量 | `fw/config.py` | `tests/test_config.py` |
| 界面与交互 | `static/app.js`、`index.html`、`styles.css` | 浏览器验证 |
| 文档 | `docs/`、`README.md`、`CHANGELOG.md` | — |

## 接口面（以 `fw/api.py` 为准）

`/api` 前缀下的路由分组，供外部 agent 对接：

- 工作区：`GET/POST /workspaces`、`GET /workspaces/{code}`、`POST /workspaces/{code}/archive`
- 节点树：`POST /workspaces/{code}/nodes`、`POST /workspaces/{code}/figures`（原子建图 + 面板）、`PATCH /nodes/{nid}`、`GET /nodes/{nid}`、`DELETE /nodes/{nid}`、`POST /nodes/{nid}/logs`
- 文件与预览：`POST /nodes/{nid}/files`、`POST /workspaces/{code}/files`、`GET/DELETE /files/{fid}`、`POST /nodes/{nid}/preview`、`GET /preview/{code}/{rel:path}`
- 标签与检索：`POST /nodes/{nid}/tags`、`DELETE /nodes/{nid}/tags/{tag}`、`GET /search`
- 扫描导入：`POST /workspaces/{code}/scan`、`POST /workspaces/{code}/scan/import`
- 其他：`GET /settings`、`GET /workspaces/{code}/export/{kind}`、`POST /backup`、应用级 `GET /api/health`

请求体结构与返回字段直接读 `fw/api.py` 对应函数；不要凭这份分组猜测参数。

## 上下文指针

| 何时读 | 文档 |
| --- | --- |
| 问启动、换电脑、数据迁移、用户用法 | [README.md](README.md) |
| 改动涉及文件夹命名/删除、或遇到「名字撞车」「删不掉」「预览异常」 | [docs/known-issues.md](docs/known-issues.md) |
| 改动触及目录模型、数据模型或产品边界 | [docs/superpowers/specs/2026-09-08-figure-workspace-design.md](docs/superpowers/specs/2026-09-08-figure-workspace-design.md) |
| 需要任务分解或当年实现脉络 | [docs/superpowers/plans/2026-09-08-figure-workspace-mvp.md](docs/superpowers/plans/2026-09-08-figure-workspace-mvp.md) |
| 需要历史决策与「为什么这样设计」 | [docs/dev-log.md](docs/dev-log.md) |
| 需要版本历史与发布说明 | [CHANGELOG.md](CHANGELOG.md) |

## 非显然的约定

以下细节配置里查不到，改代码前先看：

- 数据根目录默认 `D:\ResearchData`（无 D 盘时启动脚本退回 `%USERPROFILE%\ResearchData`）；数据库默认仓库内 `data/fw.db`。`data/`、`.trash/` 不入库，换机器默认是空工作区。
- `folder_slug()` 剥掉**所有**空白字符，两个仅空格位置不同的 label 会得到同一基础名。文件夹名现在持久化在 `node.folder`，由 `naming.allocate_folder()` 分配：同层不重名、避开保留名 `原始数据` / `.trash`（大小写不敏感），冲突时加 ` (2)` 后缀。**不要再用 label 现算路径。**
- `PATCH /api/nodes/{nid}` 改 label 会同步 `Path.rename` 文件夹，并改写该子树所有 `file_item.rel_path` 与 `node.preview_rel`；磁盘改名失败或数据库写入失败都会回退。Figure label 在工区内唯一（重名 409），面板 label 在同 Figure 内唯一（400）。
- `db.node_rel_dir()` 按 `folder` 与父链算相对路径；建目录用 `storage.ensure_dir()`，只算路径用 `storage.resolve_in_workspace()`（越界抛 `ValueError`）。删除时 `api.delete_node` 仅对旧数据中「同层 `folder` 相同」的共用文件夹保留逐个移文件的保护；这类旧数据改名会返回 409。
- 上传是把文件**复制**进目标文件夹并记 SHA-256，不动源文件；扫描导入只读发现图片，同样不动源目录。
- 预览：浏览器可直接解码的格式内联显示；TIF/TIFF 等由 `imaging.py` 转成真 PNG 缩略图。导出只针对 `status='adopted'` 的节点。
- 路径处理统一用 `pathlib`；Windows 中文路径在 PowerShell 回显可能乱码，文件本身正常。

## 任务完成定义

同时满足：`pytest -q` 全绿；改动落点与速查表一致；文件系统仍是真源、数据库仍是索引；删除仍可找回；已有测试未被迁就性修改。
