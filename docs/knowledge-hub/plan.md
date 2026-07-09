---
type: plan
feature: knowledge-hub
status: approved
lang: vi
owner: "@trangdangkhai"
created: 2026-07-06
updated: 2026-07-06
links: [docs/knowledge-hub/brainstorms/confluence-mcp-knowledge-hub.md, docs/architecture.md, docs/phase-checklist.md]
tags: [plan, knowledge-hub]
changelog:
  - 2026-07-07 | implementation | E1-E9 + E8 xong toan bo (backend + graph UI); E10 upload flow + docker-compose worker xong; con lai: admin UI, chat UI, version history UI, SSO Keycloak, CI frontend job
  - 2026-07-06 | /brainstorm | danh gia lai hien trang Phase 0-6, plan gap-based, OQ chot xong
  - 2026-07-06 | /brainstorm | plan + task breakdown tu brainstorm confluence-mcp-knowledge-hub
---

# Plan hoàn thiện Nexus-KB: Trung tâm dữ liệu tri thức (Phase 7)

Nguồn yêu cầu: `docs/knowledge-hub/brainstorms/confluence-mcp-knowledge-hub.md`
Hiện trạng tham chiếu: `docs/phase-checklist.md`

## 1. Đánh giá hiện trạng (2026-07-06)

Bằng chứng: `python -m pytest -q` trên nhánh `feat/phase2` — **216 passed, 4 skipped**.

Đã có và hoạt động (Phase 0–6, XÂY TIẾP chứ không viết lại):

| Mảng | Hiện trạng | Code |
|---|---|---|
| Ingestion md/txt/Obsidian | Chunking, content_hash skip, embeddings (deterministic + sentence-transformers), Qdrant | `workers/document-parser` |
| Search | Hybrid rerank (lexical/title/tag/heading), snippets, graph context | `services/nexus-api` search |
| Audit + Review | `audit_logs` bất biến, review queue low-confidence (APPROVE/REJECT/MODIFY), RBAC Reviewer | `audit.py`, `review.py` |
| Auth | JWT nội bộ đang hoàn thiện trên `feat/phase2` | `nexus_api/auth/` |
| Confluence | MCP bridge scaffold chỉ đọc (discover/read, actor authz theo space, redaction) — CHƯA nối vào pipeline ingest | `mcp-servers/confluence-bridge` |
| Knowledge graph | Entities/relationships/hyperedges, LLM extraction + regex fallback, domain templates, GraphCanvas SVG UI | `workers/graph-builder`, web console |
| LLM Gateway | Provider abstraction (Ollama/OpenAI-compatible), retry, cache, telemetry | `services/llm-gateway` |
| Web console | Search / Graph / Ingestion / Review / Audit views | `apps/web-console` |

Khoảng trống so với mục tiêu (đây là phạm vi Phase 7):

1. Chưa có upload file từ UI — ingest hiện là quét đường dẫn server, chạy đồng bộ, không có hàng đợi.
2. Chỉ đọc md/txt — chưa có PDF/DOCX/XLSX/PPTX/CSV (markitdown).
3. Chưa có versioning vX.Y.Z (mới chỉ skip theo content_hash).
4. Chưa có workspace + phân quyền theo phòng ban (RBAC hiện là role header/JWT đơn).
5. Confluence bridge chưa thành connector sync thật (chưa có sync_runs, map space→workspace, cleanup khi fail).
6. Chưa có RAG chatbot (gateway có sẵn nhưng chưa có endpoint trả lời + trích dẫn, chưa có chat UI).
7. Chưa có MCP server cho AI agent tra kho tri thức (bridge hiện tại là chiều ngược — đọc từ Confluence).
8. Chưa có bước "xác nhận đã đọc" trước công bố (review hiện tại là gate low-confidence, giữ song song).

## 2. Quyết định đã chốt (2026-07-06)

- Review 2 tầng: giữ low-confidence review hiện có + thêm xác nhận "đã đọc" (người upload tự xác nhận, ghi audit) trước khi công bố vào workspace.
- Đợt này chỉ tài khoản nội bộ (JWT hiện có); SSO Keycloak OIDC lùi sang P1. MCP verify token Keycloak từ gateway — hai đường xác thực độc lập.
- Giữ toàn bộ phiên bản cũ; chỉ bản mới nhất trong index tìm kiếm; admin dọn thủ công.
- Worker retry 3 lần rồi đánh dấu lỗi; chạy lại thủ công.
- Rate limit MCP do Gateway/Keycloak lo; Nexus log usage theo token.
- Hàng đợi: Postgres-backed job table (không thêm hạ tầng; Redis chỉ làm cache) — ghi ADR khi triển khai.
- Trích xuất đa định dạng bằng markitdown; OCR/hình ảnh để P2.
- Sync Confluence chỉ chạy khi admin bấm; fail giữa chừng thì xóa dữ liệu dở của run, chạy lại từ đầu.

## 3. Nguyên tắc kiến trúc (chống lặp lại arkon)

1. Ports & adapters: business logic không import FastAPI/Qdrant/SQLAlchemy trực tiếp — qua ports trong `packages/shared-contracts` (pattern đã có trong `nexus_document_parser/ports.py`, giữ nghiêm).
2. Ranh giới module cứng: `services/*` (API, gateway), `workers/*` (xử lý nền), `packages/*` (contracts, clients), `mcp-servers/*` (MCP), `apps/web-console` (UI). Không import chéo ngược chiều.
3. Không fail silent: lỗi parse/DB/Qdrant nổi lên qua trạng thái job + log correlation ID + audit event.
4. Fail closed cho phân quyền; không bypass RBAC/audit/review để test xanh (rule sẵn trong phase-checklist).
5. Mỗi epic kèm test offline (mock LLM/Confluence) trước khi merge; test live gated qua env như hiện tại.
6. Mọi thay đổi kiến trúc cập nhật `docs/architecture.md` + `docs/phase-checklist.md` cùng PR.
7. Không phát sinh service/hạ tầng mới khi module hiện có gánh được (bài học arkon: đẻ service vô tội vạ).

## 4. Epic và task

Ký hiệu: [P0]/[P1]/[P2]; (dep: ...) phụ thuộc. Task đánh số để trace vào commit/PR.

### E1 — Trích xuất đa định dạng markitdown [P0]

- E1.1 Port `DocumentConverter` trong `packages/shared-contracts` + adapter markitdown trong `workers/document-parser`; thêm dependency `markitdown` vào `requirements.txt` với ghi chú `.env.example` nếu có biến mới.
- E1.2 Mở rộng loader: nhận .pdf, .docx, .xlsx, .pptx, .csv → convert sang markdown → đi tiếp pipeline chunk/embedding hiện có; giữ nguyên hành vi .md/.txt (không regress Phase 1 checklist).
- E1.3 Validate boundary: whitelist định dạng, 50MB/file, từ chối 0 byte; giới hạn đọc từ bảng cấu hình hệ thống (E4.5).
- E1.4 Test synthetic: mỗi định dạng 1 file mẫu nhỏ trong `tests/fixtures/`, mock embedding; test convert + metadata + chunk.
- E1.5 Đánh giá chất lượng markitdown trên bộ tài liệu thật (export từ Confluence), ghi kết quả vào `docs/knowledge-hub/`.

### E2 — Upload + hàng đợi FIFO [P0] (dep: E1)

- E2.1 ADR: Postgres-backed queue. Migration `004`: bảng `ingestion_jobs` (id, document ref, workspace_id, status `queued|extracting|indexed|failed`, attempt, error_message, queued_at, started_at, finished_at, correlation_id).
- E2.2 API upload multipart: `POST /api/v1/documents` (tối đa 5 file/lần theo cấu hình) → lưu file staging → tạo job → trả job ids; `GET /api/v1/jobs/{id}` trạng thái + vị trí hàng đợi; `POST /api/v1/jobs/{id}/retry`.
- E2.3 Worker loop trong `workers/document-parser`: poll FIFO, concurrency cấu hình, retry tự động 3 lần, cleanup chunk/vector dở khi fail (tái dùng `IngestionPipeline`).
- E2.4 Audit events cho upload/queue/retry (nối vào `audit_logs` hiện có, thêm event types mới).
- E2.5 Test: thứ tự FIFO, chuyển trạng thái, retry đúng 3 lần, cleanup không để rác vector, upload quá quota bị chặn.

### E3 — Chống trùng + versioning [P0] (dep: E2)

- E3.1 Upload trùng content_hash/tên → API trả 409 + thông tin tài liệu hiện có; UI hỏi người dùng tạo phiên bản.
- E3.2 Migration: bảng `document_versions` (chuỗi vX.Y.Z); bản mới nhất thay thế trong index Qdrant, bản cũ giữ metadata + nội dung (giữ tất cả — đã chốt).
- E3.3 `GET /api/v1/documents/{id}/versions`; version mới đi qua cùng queue + review gate.
- E3.4 Test: trùng → 409, tạo version, search chỉ trả bản mới nhất, lịch sử đầy đủ.

### E4 — Workspace + RBAC [P0] (song song E2)

- E4.1 Migration: `workspaces`, `workspace_members` (user_id, role `admin|member`); documents/chunks gắn `workspace_id`; thêm `workspace_id` vào Qdrant payload (migration script cho điểm dữ liệu cũ).
- E4.2 Mở rộng JWT auth hiện có (`nexus_api/auth/`): claims chứa workspace memberships; dependency `require_workspace_access` — fail closed.
- E4.3 Lọc workspace bắt buộc ở search, graph, documents, review, audit read APIs.
- E4.4 Admin API: CRUD user, import danh sách (CSV/JSON), gán workspace, bảng cấu hình hệ thống (số file/lần, MB/file, worker concurrency) + API đọc/ghi cấu hình.
- E4.5 Audit event cho mọi thao tác cấp quyền/cấu hình.
- E4.6 Test bảo mật: user phòng A không thấy dữ liệu phòng B trên search/graph/RAG/MCP; thiếu quyền → 403; fail closed khi thiếu context.
- E4.7 [P1] SSO Keycloak OIDC cho web console (cùng realm với MCP Gateway).

### E5 — Review 2 tầng + audit "đã đọc" [P0] (dep: E2, E4)

- E5.1 Giữ nguyên tầng low-confidence hiện có. Thêm trạng thái `awaiting_ack` sau khi index: người upload xác nhận "đã đọc" → audit event `DOCUMENT_ACK` → công bố vào workspace.
- E5.2 Tài liệu chưa ack không xuất hiện trong search/graph/MCP của người khác.
- E5.3 UI: badge trạng thái trong IngestionView; hàng chờ ack trong ReviewView; lịch sử ack trong AuditView.
- E5.4 Test: chưa ack → người khác không thấy; ack → audit ghi đúng user + thời điểm; không ack được 2 lần.

### E6 — Confluence connector thật [P0] (dep: E1, E2, E4)

- E6.1 Nâng `mcp-servers/confluence-bridge` thành adapter nguồn: client REST Confluence thật (token), list space, kéo trang + attachment; giữ redaction + authz scaffold hiện có.
- E6.2 Migration: bảng `sync_runs` (running/completed/failed, space_key, workspace_id, pages_indexed, error). Map 1 space → 1 workspace. Trang + attachment đi qua pipeline E1/E2 (attachment PDF/DOCX qua markitdown).
- E6.3 Sync chỉ chạy khi admin bấm: `POST /api/v1/sync-runs` + `GET /api/v1/sync-runs`; fail giữa chừng → đánh dấu failed, xóa toàn bộ dữ liệu dở theo run_id, admin chạy lại từ đầu.
- E6.4 UI admin: cấu hình kết nối, chọn space, nút Sync, bảng lịch sử run.
- E6.5 Test: mock Confluence API; map space→workspace, cleanup khi fail, không lộ token/URL trong log (giữ chuẩn redaction hiện có).
- E6.6 [P1] Sync theo lịch (admin bật/tắt). [P2] CDC sửa/xóa (OQ-6).

### E7 — RAG chatbot [P0] (dep: E4)

- E7.1 Endpoint `POST /api/v1/chat`: retrieve (search hiện có, lọc workspace) → build context → gọi `services/llm-gateway` (provider OpenAI-compatible, API key LLM nội bộ từ cấu hình admin) → trả lời + citations (chunk_id, document, version).
- E7.2 Degrade rõ: LLM down → lỗi E-kh-007, search thường vẫn chạy; không giấu lỗi.
- E7.3 UI SearchView: toggle "Tìm kiếm / Hỏi đáp", khung chat, citation bấm mở tài liệu; wording theo brainstorm Mục 7.3.
- E7.4 Audit event `CHAT_QUERY` (không lưu raw câu trả lời nếu chứa nội dung nhạy cảm — theo chuẩn audit hiện có: không raw content).
- E7.5 Test: mock gateway; citation đúng chunk; permission filter trong RAG; LLM down → degrade đúng.

### E8 — Graph UI kiểu Onyx [P1] (dep: E4)

- E8.1 Graph API thêm: tìm node theo tên, lấy láng giềng theo độ sâu, lọc workspace + phân trang.
- E8.2 GraphCanvas nâng cấp: ô tìm node, bấm node mở panel nội dung (chunk/tài liệu nguồn, láng giềng), highlight quan hệ; giữ SVG force-directed hiện có, chỉ thêm thư viện khi đo được giới hạn hiệu năng (ghi ADR nếu thêm).
- E8.3 Wikilink/`LINKS_TO` hiện có + entities từ tài liệu Confluence hiển thị cùng một graph.
- E8.4 Test: search node, workspace filter, neighbor expansion trên bộ synthetic.

### E9 — MCP server Nexus Knowledge [P0] (dep: E7)

- E9.1 Package mới `mcp-servers/nexus-knowledge`: tools `search_knowledge`, `ask_knowledge`, `list_documents` — chỉ đọc; tái dùng service search/chat qua HTTP nội bộ hoặc import port (không nhân đôi logic).
- E9.2 Verify token Keycloak do MCP Gateway phát hành (JWKS của realm); map token → user → workspace scope; fail closed; log usage theo token (rate limit để gateway).
- E9.3 Chuẩn MCP runtime thật (stdio/HTTP) — bridge JSON runner hiện có làm mẫu; test token hợp lệ/hết hạn/sai scope.
- E9.4 Tài liệu hướng dẫn nối từ Claude/agent qua MCP Gateway.

### E10 — Hoàn thiện UI + vận hành [P0/P1]

- E10.1 [P0] IngestionView: kéo-thả upload, hàng đợi realtime-polling ("Tài liệu đang chờ trong hàng đợi (vị trí n)", "Đang nạp dữ liệu..."), hộp thoại trùng/version, nút chạy lại; wording brainstorm Mục 7.3.
- E10.2 [P0] Màn admin: user/workspace/quota/API key LLM/Confluence connector/sync runs.
- E10.3 [P1] Version history UI trong chi tiết tài liệu.
- E10.4 [P0] Hạ tầng: docker-compose.prod thêm worker queue; `.env.example` đủ biến mới có chú thích; migration script Qdrant payload.
- E10.5 [P0] CI: giữ suite offline xanh (216+), thêm test mới vào matrix; integration gated qua env.
- E10.6 [P1] Correlation ID xuyên suốt API → queue → worker → Qdrant; log structured (đã có `logging_config.py`, nối tiếp).
- E10.7 [P2] OCR/hình ảnh (OQ-5).

## 5. Thứ tự triển khai (milestone)

| Milestone | Gồm | Nghiệm thu | Trạng thái |
|---|---|---|---|
| M1 — Core pipeline | E1, E2, E3 | Upload PDF/DOCX/XLSX từ API → queue FIFO → index Qdrant; trạng thái, retry 3 lần, version vX.Y.Z; test offline pass | ✅ Xong (2026-07-07) |
| M2 — Quyền + review | E4 (trừ E4.7), E5 | Workspace RBAC fail-closed trên JWT nội bộ; ack "đã đọc" + audit; test phân quyền pass | ✅ Xong (2026-07-07) |
| M3 — Nguồn + truy vấn | E6, E7, E9 | Sync Confluence space vào workspace; RAG có trích dẫn; MCP dùng được từ Claude qua gateway | ✅ Xong (2026-07-07) |
| M4 — Trải nghiệm + vận hành | E8, E10, E4.7 | Graph UI kiểu Onyx; UI upload/admin hoàn chỉnh; SSO Keycloak; compose prod + CI xanh | 🟡 Một phần — xem chi tiết dưới |

M4 chi tiết theo từng phần con:
- E8 (Graph UI kiểu Onyx): ✅ Xong — xem `docs/phase-checklist.md` mục E8.
- E10 upload flow + docker-compose worker + README vận hành: ✅ Xong — xem mục E10.
- E10 màn hình admin (workspace/user/quota/Confluence sync UI): ⬜ Chưa làm — API đã có và test đầy đủ, chỉ thiếu UI.
- E10 chat/RAG UI trong SearchView: ⬜ Chưa làm — `POST /api/v1/chat` đã xong, chưa có giao diện.
- E10 version history UI: ⬜ Chưa làm.
- E4.7 SSO Keycloak OIDC: ⬜ Chưa làm — cần thông tin realm/issuer/audience thực tế từ MCP Gateway trước khi thiết kế.
- CI job cho frontend (vitest): ⬜ Chưa làm — hiện CI chỉ chạy pytest, chưa chạy test frontend 40 test đã có.

Trong mỗi milestone: chốt contract trong `packages/shared-contracts` trước, BE trước UI; UI có thể mock theo contract để chạy song song.

Tổng kết bằng chứng (2026-07-07): `python -m pytest -q` → 332 passed, 4 skipped. `cd apps/web-console && npx vitest run` → 40 passed. `npx tsc -b` → sạch (chỉ 3 cảnh báo unused-var có từ trước, không liên quan Phase 7).

## 6. Câu hỏi mở còn lại

- OQ-5 (P2): thư viện OCR/hình ảnh — chủ dự án sẽ gợi ý khi đến lúc.
- OQ-6 (P2): hướng CDC Confluence — chốt khi lên kế hoạch P2.
