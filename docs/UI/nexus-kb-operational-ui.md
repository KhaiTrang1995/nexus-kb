---
type: ui-design
feature: nexus-kb-ui
idea_slug: operational-console-v1
status: draft
mode: deep
lang: vi
owner: "grok-agent (following user request)"
created: 2026-06-11
updated: 2026-06-11
complexity_flags: [has_multi_role, has_state_machine, has_async_flow, has_graph_context, has_review_actions]
links:
  - docs/architecture.md
  - docs/frontend-plan.md
  - docs/phase-checklist.md
tags: [ui-design, nexus-kb, search, review, graph, audit, ascii-first]
stale_reason: ""
changelog:
  - 2026-06-11 | /ui-design (modeled on brainstorm-skill-package) | initial deep design with ASCII wireframes for core operational screens. ASCII before any code.
---

# Nexus-KB Operational Console — UI Design (ASCII First)

> Feature: nexus-kb-ui | Idea: operational-console-v1
> **ASCII wireframes, text flows, matrices, and exact wording are the primary artifacts.** 
> No React components, no Vite scaffold, no Figma frames until this document (and its ASCII) receive explicit review and approval.
> Aligned with architecture.md "UI Layer": compact operational interface (not marketing/hero page) for search, graph exploration, ingestion status, audit review, and human approval workflows.
> Backend is complete (Phases 1-5 local MVP, tests passing). This design consumes existing contracts and endpoints only.

## 1. Idea Seed

"Xây dựng UI compact cho Nexus-KB: cho phép user search hybrid (vector + rerank + graph context), reviewer xử lý review queue (approve/reject/modify low-conf chunks), xem audit logs, theo dõi ingestion runs, và explore graph entities/relationships. Ưu tiên operational (không landing page). Dùng ASCII wireframe để thiết kế trước khi code. Mock header X-User-Role cho reviewer. Synthetic data."

(Seed derived from architecture.md UI Layer + previous frontend-plan.md + phase completion work.)

## 2. Context

- Backend core (ingestion pipeline with confidence routing to review_items, hybrid search, graph builder, audit, review actions) đã hoàn thiện và verified (36 offline + 4 live tests pass).
- Hiện tại chỉ có CLI + curl + API docs. User (BA, reviewer, knowledge worker) không có giao diện trực quan → khó scale governance + exploration.
- Why now: Sau khi core ports/adapter/audit/review hardening xong (experience ids logged), cần chuẩn bị UI design với ASCII trước khi tạo apps/web-console/.
- Pain: Reviewer phải dùng curl/header để action; search result thiếu graph context trực quan; không thấy rõ "tại sao chunk này bị low conf".
- Scope: 1 operational SPA (dark theme matching current index.html). Local dev proxy đến running uvicorn. Synthetic data cho mọi ví dụ.

## 3. User Types & Access (preliminary)

| User Type | Role / Header (mock for v1) | Primary Pain | Primary Need | Entry Point |
|-----------|-----------------------------|--------------|--------------|-------------|
| Knowledge Worker / Searcher | (any, no special header) | Muốn tìm kiến thức governed nhưng chỉ có curl/backend | Search nhanh + thấy graph context + snippet rõ ràng | Sidebar "Search" hoặc direct /search |
| Reviewer (IT-BA / governance) | X-User-Role: Reviewer | Phải dùng terminal/cURL để approve low-conf items, không thấy preview modify | Queue trực quan, action 1-click, exact wording preview, impact (sẽ index vào vector) | "Review Queue" nav (chỉ hiện nếu role đúng) |
| Auditor / Admin | (any + audit view) | Muốn trace "ai đã review gì, khi nào, tại sao" | Filterable audit log + link ngược về document/chunk | "Audit" tab |

*Gating v1: client-side role switcher (dev only) + header injection. Thực tế RBAC sẽ ở phase sau (không bypass backend review/audit rules).*

## 4. Capabilities Breakdown (P0/P1/P2 — tentative)

### P0 — must have (core operational value, ASCII đã cover)
- Search bar + basic filters (tags, source_type) → results list với snippet, score, metadata, heading_path.
- Mỗi result có thể mở "Graph context" (entities + relationships từ approved chunks).
- Review Queue: list PENDING items (với confidence, source), detail view, 3 actions: Approve, Reject, Modify (edit content + simple payload tags).
- Exact success/error messages rõ ràng (ví dụ: "Item approved and added to vector index").
- Audit log viewer cơ bản (filter action/actor, link đến resource).
- Ingestion status (từ run response hoặc simple poll).

### P1 — should have
- Graph explorer riêng (build + browse entities/rels với provenance).
- Keyboard shortcuts cho reviewer actions.
- "Why low confidence" explanation (dựa metadata từ pipeline).
- Export audit (CSV, redacted).

### P2 — nice to have
- Bulk review actions.
- Real-time progress cho long ingest/graph build.
- Saved searches / collections.

> P0 được ưu tiên cho ASCII wireframe + validation. P1/P2 chỉ sau khi ASCII + backend contracts ổn.

## 5. Core Screens & Happy Path Flows (ASCII WIREFRAMES — PRIMARY ARTIFACT)

Mỗi flow chính có numbered steps + ASCII wireframe (box-drawing). Đây là thiết kế text-first.

### 5.1 Main Search + Results with Graph Context (Happy Path)

1. User mở Search (từ nav hoặc sau khi login/dev header).
2. Nhập query + optional filters (tags, source) → bấm Search.
3. System gọi POST /api/v1/search (dùng embedding + Qdrant + PG join + optional graph).
4. Hiển thị list kết quả (reranked), mỗi cái có: title, snippet (với highlight), score, metadata, tags, "Graph context" chip.
5. User click vào result hoặc "Graph" → mở panel bên phải với entities + relationships (linkable về chunk).
6. Success: user thấy grounded result + provenance.

```
┌──────────────────────────────────────────────────────────────────────┐
│ Nexus-KB  [Search]  Review Queue  Graph  Audit  │  Role: [Searcher ▼] │
├──────────────────────────────────────────────────────────────────────┤
│ Query: [governed retrieval in enterprise          ] [Search] [Clear]│
│ Filters:  Tags [rag,enterprise] [x]   Source [any ▼]   Limit [10]    │
├──────────────────────────────────────────────────────────────────────┤
│ 8 results • reranked • 142ms                                          │
│ ┌──────────────────────────────────────────────────────────────────┐ │
│ │ 1. Governed Retrieval in Enterprise RAG          score: 0.91      │ │
│ │    Snippet: ... <mark>governed</mark> retrieval combines ...      │ │
│ │    /vault/Platform.md#section-3   tags: [rag]   updated: 2d ago   │ │
│ │    [Graph: 3 entities • 5 rels]  [View full chunk]                │ │
│ └──────────────────────────────────────────────────────────────────┘ │
│ ┌──────────────────────────────────────────────────────────────────┐ │
│ │ 2. Audit & Review Workflows ...                  score: 0.78      │ │
│ │    ... (low conf 0.61 — Reviewer badge if applicable)            │ │
│ │    [Graph: ...]                                                   │ │
│ └──────────────────────────────────────────────────────────────────┘ │
│ ...                                                                   │
├──────────────────────────────────────────────────────────────────────┤
│ Graph Context (for selected result)                                   │
│ Entity: RAG (conf 0.9) ──[enables]──> Entity: Human Review            │
│ Entity: Audit Log ←──[records]── Entity: Review Action                │
│ [Expand full graph] [Filter by this chunk only]                       │
└──────────────────────────────────────────────────────────────────────┘
```

### 5.2 Review Queue + Action (Governance — Phase 2 critical)

1. Reviewer mở "Review Queue" (nav chỉ active khi role=Reviewer).
2. System lấy GET /api/v1/review/queue?status=PENDING (có min_confidence).
3. Hiển thị list: source, confidence, short content, "View detail".
4. Chọn item → mở modal/detail: full content, payload (tags, wikilinks, chunk meta), 3 buttons.
5. Approve: gọi action → toast success + item biến mất hoặc move sang APPROVED (re-fetch queue).
6. Modify: cho edit content + tags → preview diff → submit.
7. Reject: confirm → item removed from index path.

```
┌──────────────────────────────────────────────────────────────────────┐
│ ... nav ...                                      │ Role: [Reviewer]  │
├──────────────────────────────────────────────────────────────────────┤
│ Review Queue (12 pending, min conf 0.4)   [Refresh] [Filters]        │
│ ┌──────────────────────────────────────────────────────────────────┐ │
│ │ [0.42] review.md  "low confidence entity extraction..."          │ │
│ │        chunk#3 • source: obsidian   created: 1h ago              │ │
│ │        [View & Act]                                               │ │
│ └──────────────────────────────────────────────────────────────────┘ │
│ ... more rows ...                                                     │
└──────────────────────────────────────────────────────────────────────┘

(After click View & Act — modal or split)

┌──────────────────────────────────────────────────────────────────────┐
│ Review Item Detail — confidence: 0.42                                 │
│ Source: /vault/review.md   chunk_index: 3                             │
│ ┌──────────────────────────────────────────────────────────────────┐ │
│ │ Content (editable if Modify):                                    │ │
│ │ [ low confidence entity about RAG governance ...               ] │ │
│ │                                                                  │ │
│ │ Tags: [rag] [governance]   Wikilinks: []                         │ │
│ └──────────────────────────────────────────────────────────────────┘ │
│ Graph context (if any): ...                                           │
│                                                                       │
│ [Approve & Index]   [Modify & Re-index]   [Reject (do not index)]     │
│                                                                       │
│ Exact wording on success: "Item approved. 1 chunk added to Qdrant."   │
└──────────────────────────────────────────────────────────────────────┘
```

### 5.3 Graph Explorer (per result or global build)

ASCII tương tự (list + simple node-link text diagram).

### 5.4 Audit Log Viewer

Simple table + filters. ASCII:

```
┌──────────────────────────────────────────────────────────────────────┐
│ Audit Log                                      Filter: [ITEM_REVIEW] │
├──────────────────────────────────────────────────────────────────────┤
│ Time | Actor | Action | Resource | Details                            │
│ 14:22| reviewer@.. | ITEM_REVIEW | rev_abc | action=APPROVE status=..│
│ ...                                                                   │
└──────────────────────────────────────────────────────────────────────┘
```

(Other screens: Ingestion status dashboard — list runs with docs_indexed / chunks_indexed / error.)

### 5.5 Authentication & Permissions (v1 - Mock Login + Role-based Feature Gating)

**Current state (per backend):** No real auth. All APIs accept optional `X-User-Role` (e.g. "Reviewer") and `X-User-Id` headers for audit/review context. Review actions require "Reviewer" role (backend returns 403 otherwise). Search/Graph/Audit are open but should be permission-aware in UI for UX.

**v1 design:** Simple mock login (no backend call yet). Select from 3 synthetic users at startup or via header. Persist in localStorage for dev session. Gate UI elements (hide/disable nav, show permission hints). Pass headers on every API call. Real JWT/OIDC planned for later (see frontend-plan Phase D).

**Mock users:**
- Alice (Searcher) — default, can Search + basic Graph/Audit view.
- Bob (Reviewer) — + full access to Review Queue + actions.
- Carol (Auditor) — + advanced Audit filters + Graph build trigger.

#### ASCII Wireframe — Login Modal (triggered from header "Login" or on first load)
```
┌─────────────────────────────────────────────────────────────┐
│ Nexus-KB Login (Mock / Dev)                                 │
├─────────────────────────────────────────────────────────────┤
│ Select user to simulate role & actor context:               │
│                                                             │
│ [ ] Alice — Searcher (default)                              │
│     Can: Search, view Graph context, read Audit             │
│                                                             │
│ [x] Bob   — Reviewer                                        │
│     Can: + Review Queue + Approve/Modify/Reject             │
│                                                             │
│ [ ] Carol — Auditor                                         │
│     Can: + Full Audit + trigger Graph builds                │
│                                                             │
│ [Login as selected]  [Cancel / Use default]                 │
│                                                             │
│ Note: This only sets X-User-Role + X-User-Id headers.       │
│ No real session yet. Synthetic data.                        │
└─────────────────────────────────────────────────────────────┘
```

#### Updated Header (with user context instead of simple switcher)
ASCII (extends existing nav):
```
┌──────────────────────────────────────────────────────────────────────┐
│ Nexus-KB  [Search] [Review] [Graph] [Audit]  │ Bob (Reviewer) [Logout] │
├──────────────────────────────────────────────────────────────────────┤
│ ... (role badge visible, Review nav hidden/disabled for Searcher)   │
└──────────────────────────────────────────────────────────────────────┘
```

**Permission Gating examples (in addition to existing D1/D2):**
- Review nav item: only visible + clickable if role == Reviewer (otherwise show disabled + tooltip "Requires Reviewer role").
- Graph "Build Graph" button: only for Reviewer/Auditor.
- Audit advanced filters/export: Auditor only (others see read-only).
- 403 from backend: show toast "Permission denied (current role: Searcher)" + auto-switch hint.

Update existing matrices/decision points with permission rows.

## 6. UI Behavior Deep Dive (selected)

### 6.1 Decision Points (UI)

| ID | Screen | Khi nào (user thấy) | YES | NO |
|----|--------|---------------------|-----|----|
| D1 | Search result | Confidence < threshold + current role == Reviewer | Hiển thị "Low conf" badge + "Send to Review" action | Ẩn badge, chỉ show result |
| D2 | Review action | Item đã FINALIZED (409) | Disable buttons + "Already reviewed" message + Refresh | Normal action |

### 6.2 Scenario Matrix (role + item state)

| From (Role + State) | Action | To | What User Sees (exact) | API |
|---------------------|--------|----|------------------------|-----|
| Reviewer + PENDING | Approve | APPROVED + indexed | "Item approved. 1 chunk added to vector index." toast + queue refresh | POST /review/action {APPROVE} |
| Reviewer + PENDING | Modify | MODIFIED + re-index | "Modified content committed. Vector updated." | POST ... {MODIFY, modified_content} |
| Searcher + any | Click graph chip | Panel opens | Graph entities listed with "provenance: chunk X" | GET /graph/chunks/{id} |

### 6.3 UI State Transitions

```
SearchResults --select--> ResultDetail + GraphPanel (open/close)
ReviewQueueItem --action--> (APPROVED | REJECTED | MODIFIED) + removed from PENDING list
IngestionRun --poll--> running | completed | failed (badge color + progress if available)
```

### 6.4 Interrupted / Async

- User đóng tab giữa lúc "Build Graph" đang chạy → khi quay lại thấy status từ backend run.
- Reviewer đang edit modify → background có search mới → cảnh báo "Results may be stale. Refresh?"

## 7. Validation, Limits & Exact Wording (UI text)

### 7.2 Limits (exact)
- Search limit UI: 10 default, max 50 (nút "load more" hoặc refine).
- Review queue: 50 items per page.

### 7.3 Wording samples (exact, ready to implement)

**Buttons:**
- "Search"
- "Approve & Index to Vector"
- "Modify & Re-index"
- "Reject — Do Not Index"

**Toasts / Messages:**
- Success (approve): "Item approved. 1 chunk added to Qdrant collection."
- Error (403): "Reviewer role required (X-User-Role: Reviewer)."
- Info (empty queue): "No pending items. All ingested chunks met confidence threshold."

**Labels / Placeholders:**
- "Query (min 2 chars)"
- "Confidence: 0.42 (below 0.70 threshold — routed for review)"
- "Modified content preview (will be re-embedded)"

## 8. Assumptions
- Backend contracts stable (use SearchResponse, ReviewActionRequest, etc. directly).
- Synthetic data (existing fixtures) đủ để validate design.
- Dark theme + fonts từ current index.html.
- No real auth in v1 design (header mock).
- Graph viz bắt đầu đơn giản (list + text relations) trước force-graph lib.

## 9. Risks (UX / Governance / Adoption)

| Risk | Khả năng | Hậu quả nghiệp vụ | Cách phòng (thiết kế) |
|------|----------|-------------------|-----------------------|
| Reviewer mệt mỏi vì queue dài | Trung bình | Governance chậm, item bị bỏ qua | Default filter + "why low conf" explanation + bulk sau này. ASCII giúp validate flow trước code. |
| Graph context làm user overload | Cao | Giảm trust vào kết quả | Ẩn mặc định, chỉ mở khi user chủ động. "Provenance: chunk X" rõ ràng. |
| Wording không nhất quán giữa UI và backend audit | Thấp | Audit khó trace | Dùng cùng exact strings từ Section 7 trong cả UI và backend logs. |

## 10. Success Criteria (preliminary)
- Một reviewer mới có thể approve 1 item và thấy nó xuất hiện trong search kết quả tiếp theo trong < 30s (simulated với live backend).
- User search lần đầu hiểu được 1 relationship trong graph panel mà không cần training (validate qua ASCII walkthrough).
- Audit log cho phép trace "ai approve item nào" chỉ với 2-3 click/filter.

## 11. Open Questions
- [ ] OQ-1: Có cần real-time progress bar cho long-running graph build không (hay chỉ status poll đủ)?
- [ ] OQ-2: Graph viz nên bắt đầu bằng list text hay thử force-graph ngay (dù ASCII đã validate mental model)?
- [ ] OQ-3: Export audit CSV — filter hiện tại hay export toàn bộ + client-side filter?

## 12. Next Steps (ASCII-first discipline)

1. Review & iterate ASCII wireframes + matrices + exact wording trong file này.
2. L1 approval (BA/UX language, không technical).
3. **Chỉ sau khi ASCII approved**:
   - Re-call Experience Engine.
   - Thực hiện theo `frontend-plan.md` Phase A (scaffold Vite/React/TS, typed client từ contracts, proxy dev).
   - Tạo `apps/web-console/` (chỉ lúc này).
   - Map ASCII regions → components.
   - Viết tests (vitest + MSW hoặc live synthetic).
4. Update `frontend-plan.md`, README, index.html, phase-checklist với link + evidence (ASCII artifacts + approval note).
5. Tiếp tục /ui-design cho các screen còn lại (graph standalone, ingestion dashboard chi tiết).

**This completes the design document + ASCII preparation for the Nexus-KB UI. Actual UI implementation comes after.**

(Modeled directly on the structure, constraints, and artifacts of docs/brainstorm-skill-package.)


## Update (full implementation): Document-to-Document Linking via Wikilinks in Graph

As of latest update, the Knowledge Graph now explicitly links documents:
- Wikilinks from Obsidian (e.g. [[Vector Store]]) are extracted during ingestion.
- Passed via updated GraphChunkInput (with document-level wikilinks).
- GraphBuilder (using WikilinkDocumentLinkExtractor + post-processing) creates LINKS_TO relationships between DOCUMENT entities.
- Provenance always includes chunk_id + document_id.
- Visible in /graph/build, /graph/chunks/{id}, and search results (graph_* fields).
- End-to-end verified with real fixture (Platform.md -> Vector Store / Graph Layer).

This completes the 3 requested improvements for better document connectivity in the KG.

ASCII wireframes in earlier sections can now assume document links appear in graph context panels (e.g. in search results and dedicated graph explorer).

Full flow (ingest fixture with wikilinks -> graph build -> inspect LINKS_TO) passes.
