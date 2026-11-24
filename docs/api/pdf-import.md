# PDF 读取与自动导入接口

> **状态：设计规格，尚未实现。** 仓库中目前没有 PDF 相关代码。本文档是实现者的引导：先定接口与行为，再动代码。实现完成后，请把本节状态改为「已实现」，并同步 [AGENTS.md](../../AGENTS.md) 的接口面与 [CHANGELOG.md](../../CHANGELOG.md)。

## 1. 目的

用户给出一篇论文的 PDF，工作台自动：

1. 读取 PDF 的页数、文字层与图题（Figure N 说明文字）；
2. 列出可导入的图片候选，由用户勾选；
3. 为每个选中的图建 Figure 节点（建图即建文件夹）、挂上来源图片与预览，并把 PDF 本身留档；
4. 写入日志，保证每张图可溯源到「PDF 名 + 页码」。

与现有的「扫描导入」保持同构：先只读发现，再勾选导入，源文件不被修改。

## 2. 范围

| 本规格包含 | 本规格不包含 |
| --- | --- |
| 有文字层的 PDF 读取 | 扫描版 PDF 的 OCR |
| 嵌入式位图的提取 | 矢量图的重新绘制（只提供整页渲染作为兜底） |
| 按图题（Figure N）推断标签 | 理解图的内容或自动判断状态 |
| PDF 本身留档到「原始数据」 | 修改或删除源 PDF |

## 3. 总体流程

```
用户给出 PDF 路径
   │
   ▼
POST /pdf/inspect ──► 返回页数、图题、候选图片（只读，不写库、不写盘）
   │
   ▼  用户勾选候选，确认标签
POST /pdf/import  ──► 校验 → 留档 PDF → 逐图建节点与文件 → 写日志 → 返回结果
```

inspect 与 import 都是**无状态**的：import 不依赖 inspect 的缓存，而是重新读取 PDF，用 `page` 与 `index` 定位候选。这样 inspect 与 import 之间即使 PDF 被替换，import 也会因 SHA 不一致而拒绝（见 §7 错误）。

## 4. 接口

所有路径都在 `/api` 前缀下，与 `fw/api.py` 其他路由一致。

### 4.1 读取 PDF（只读预览）

`POST /api/workspaces/{code}/pdf/inspect`

**请求**

```json
{ "pdf_path": "D:\\papers\\SA-2026.pdf" }
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `pdf_path` | string | 是 | 本机绝对路径。必须是存在的 `.pdf` 文件 |

**响应 200**

```json
{
  "pdf": {
    "name": "SA-2026.pdf",
    "size": 4823391,
    "sha256": "9f2c…",
    "pages": 28,
    "encrypted": false,
    "has_text_layer": true
  },
  "captions": [
    { "page": 5, "label": "Figure 1", "text": "Figure 1. 感染后骨破坏的时间进程" }
  ],
  "candidates": [
    {
      "page": 5,
      "index": 0,
      "kind": "embedded",
      "width": 2480,
      "height": 1754,
      "format": "png",
      "sha256": "a31b…",
      "suggested_label": "Figure 1",
      "caption_text": "Figure 1. 感染后骨破坏的时间进程",
      "duplicate_of": null
    },
    {
      "page": 7,
      "index": 0,
      "kind": "page_render",
      "width": 1600,
      "height": 1131,
      "format": "png",
      "sha256": "c77d…",
      "suggested_label": "Figure 2",
      "caption_text": null,
      "duplicate_of": null
    }
  ],
  "warnings": []
}
```

**字段语义**

- `candidates[].kind`
  - `embedded`：从 PDF 中提取的嵌入式位图，质量最高，优先使用。
  - `page_render`：整页渲染的兜底结果，仅在某页没有嵌入位图、但有图题时出现。
- `candidates[].index`：同一页内的序号，从 0 开始。与 `page` 一起作为候选的唯一定位键。
- `candidates[].suggested_label`：由图题推断（`Figure N`），推断不出时为 `null`，由用户填写。
- `candidates[].duplicate_of`：若该图的 SHA-256 与工作区内已有的源文件相同，给出已有节点的 `id`，前端应默认不勾选。
- `warnings`：非致命问题的字符串数组，例如「第 12 页无文字层」「存在加密权限限制」。

**错误**

| 状态码 | 条件 |
| --- | --- |
| 400 | `pdf_path` 缺失、不是文件、扩展名不是 `.pdf`，或文件不是合法 PDF |
| 404 | 工作区 `code` 不存在 |
| 413 | 文件超过上限（默认 200 MB，见 §8 配置） |
| 422 | PDF 已加密且无法解除限制，无法读取 |

inspect 不写数据库、不复制文件。

### 4.2 导入选中的图

`POST /api/workspaces/{code}/pdf/import`

**请求**

```json
{
  "pdf_path": "D:\\papers\\SA-2026.pdf",
  "expected_sha256": "9f2c…",
  "on_conflict": "skip",
  "picks": [
    { "page": 5, "index": 0, "label": "Figure 1", "title": "感染后骨破坏的时间进程" },
    { "page": 7, "index": 0, "label": "Figure 2" }
  ]
}
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `pdf_path` | string | 是 | 同 inspect |
| `expected_sha256` | string | 是 | inspect 返回的 `pdf.sha256`。用于确认 PDF 未在两次调用之间被替换 |
| `on_conflict` | `"skip"` \| `"new"` | 否，默认 `"skip"` | 标签与已有 Figure 重名时的处理，见 §6 |
| `picks[].page` / `index` | int | 是 | 定位候选 |
| `picks[].label` | string | 是 | 为空则拒绝该条（不静默使用默认值） |
| `picks[].title` | string | 否 | 图题，默认空串 |

**响应 200**

```json
{
  "source": { "file_id": 41, "rel_path": "原始数据\\SA-2026.pdf", "sha256": "9f2c…" },
  "created": [
    { "id": 58, "label": "Figure 1", "file_count": 2 },
    { "id": 59, "label": "Figure 2", "file_count": 2 }
  ],
  "skipped": [
    { "page": 9, "index": 0, "label": "Figure 3", "reason": "label_exists" }
  ]
}
```

**错误**

| 状态码 | 条件 |
| --- | --- |
| 400 | 缺字段、`label` 为空、`on_conflict` 取值非法、`picks` 为空 |
| 404 | 工作区不存在 |
| 409 | `expected_sha256` 与当前 PDF 不一致（PDF 已被替换，需重新 inspect） |
| 409 | `picks` 内部标签重复（同一次导入里两个 pick 的 `label` 相同） |
| 422 | `page` 或 `index` 在 PDF 中不存在 |

## 5. 导入的落盘与数据

对每次成功的导入，按以下顺序执行：

1. **留档源 PDF**：复制到 `<工作区>/原始数据/`，记录一条 `file_item`（`node_id` 为空，`sha256` 为 PDF 的 SHA-256）。源 PDF 不被移动或修改。
2. **逐图建节点**：对每个 pick，复用阶段 B 的原子建图逻辑（`api._create_figure_tree`），由它校验 label、分配 `folder` 并建目录；
   - 把提取的图片复制进新节点的 `folder`，记 `file_item`（`node_id` 指向新节点，`rel_path` 相对工作区）；
   - 若格式不可直接渲染（如 TIFF），按现有 `imaging.to_png` 生成 `preview.png` 并设为 `preview_rel`；否则直接用原图作预览。
3. **写日志**：每个新节点写一条 `log_entry`，内容形如「由 SA-2026.pdf 第 5 页导入（嵌入图 0）」。这是溯源的依据。
4. **样本码**：对 PDF 文件名调用 `naming.parse_sample_hint`，结果写入 PDF 的 `file_item.sample_note`，与现有上传行为一致。

## 6. 标签冲突（`on_conflict`）

- `"skip"`（默认）：若工作区内已存在同名 label 的 Figure，跳过该 pick，并在 `skipped` 中记录 `reason: "label_exists"`。不覆盖、不合并。
- `"new"`：给 label 追加 ` (2)` 后缀（必要时递增）后新建，保证 Figure label 仍唯一；文件夹名随新 label 由 `naming.allocate_folder` 分配。

注意：label 唯一性按大小写不敏感比较（`Figure 1` 与 `figure 1` 视为重名）。`naming.folder_slug` 会剥掉空白，文件夹名由 `folder` 字段持久化，不再由 label 现算。

## 7. 一致性与失败处理

- **先校验，后写入**：收到请求后，先完成全部校验（PDF 可读、SHA 一致、所有 `page`/`index` 存在、标签非空且本次不重复），再开始写入。校验失败不产生任何副作用。
- **全有或全无**：写入过程中若任一图失败，应回滚数据库记录，并把本次新建的文件夹移入 `.trash`（复用 `storage.move_dir_to_trash`），不留半成品。
- **只读源**：PDF 与提取过程不得修改源文件；临时文件写到系统临时目录，结束后清理。

## 8. 配置与依赖

| 配置 | 默认 | 说明 |
| --- | --- | --- |
| `FW_PDF_MAX_MB` | `200` | 单个 PDF 上限，超过返回 413 |

依赖（已决定：**不使用 AGPL 许可的库**，不采用 PyMuPDF）：

| 库 | 用途 | 许可证 |
| --- | --- | --- |
| pypdf | 文字层、页面元数据、嵌入图提取（`page.images`） | BSD |
| pypdfium2 | 整页渲染，供 `kind="page_render"` 兜底 | Apache-2.0 / BSD |

注意：pypdf 的嵌入图提取依赖 Pillow（已在 `requirements.txt` 中）。个别图片编码（如 JBIG2）可能提取失败，实现时需用真实论文 PDF 做原型验证；提取失败的图应记入 `warnings`，不得让整次 inspect 失败。两个库需写进 `requirements.txt`，并在注释里注明许可证。

## 9. 给实现者的引导

建议按以下顺序实现，每步先写测试：

1. **读取层**：`fw/pdf.py` 提供 `inspect(path) -> dict` 与 `extract(path, page, index) -> bytes`。纯函数，不接触数据库。测试用一份小型 PDF 夹具（放 `tests/fixtures/`）。
2. **图题解析**：用正则从文字层找 `^(Figure|Fig\.?)\s*(\d+)`，生成 `suggested_label`。单独测试，包括中英文混排、无图题的页。
3. **inspect 接口**：`fw/api.py` 新增路由，只调用读取层。测试 400/404/413 分支与 `duplicate_of` 判定。
4. **import 接口**：先实现校验，再实现写入与回滚。测试：SHA 不一致返回 409；`skip` 与 `new` 两种冲突；中途失败时 DB 与磁盘均无残留。
5. **溯源**：断言导入后日志含页码，源 PDF 的 `file_item` 存在且 SHA 与原文件一致。
6. **文档**：更新本文件状态、`AGENTS.md` 接口面、`CHANGELOG.md`。

### 测试清单（完成定义）

- [ ] inspect 对有文字层的 PDF 返回页数、图题、候选，且不产生任何文件或数据库记录。
- [ ] inspect 对加密、非 PDF、超大文件分别返回对应状态码。
- [ ] import 的 `expected_sha256` 不一致时返回 409，且无副作用。
- [ ] `on_conflict="skip"` 跳过已存在的标签并记入 `skipped`。
- [ ] 中途失败后，数据库与工作区均无本次导入的残留，新文件夹进入 `.trash`。
- [ ] 源 PDF 在导入前后字节级一致。
- [ ] 每个新节点都有来源日志，含 PDF 名与页码。

## 10. 待决问题

1. ~~PDF 库与许可证~~ **已决定**：不接受 AGPL，采用 pypdf + pypdfium2（见 §8）。
2. **矢量图**：是否接受只提取位图、矢量图仅以整页渲染兜底？这会显著影响导入质量。
3. **多图页**：一页多图时，`index` 的顺序以什么为准（文档流顺序还是版面坐标从上到下）？建议按版面坐标，并在 inspect 中返回 `bbox`。
4. **路径输入**：本规格沿用扫描导入的「本机路径」方式。若将来要支持浏览器上传 PDF，需改为 multipart 上传，并把请求体中的 `pdf_path` 换成文件字段。
