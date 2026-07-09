---
type: brainstorm
feature: knowledge-hub
idea_slug: confluence-mcp-knowledge-hub
status: draft
mode: deep
lang: vi
owner: "@trangdangkhai"
created: 2026-07-06
updated: 2026-07-06
complexity_flags: [has_external_redirect, has_async_flow, has_multi_role, has_state_machine, has_throttle_rules]
links: [docs/knowledge-hub/plan.md, docs/architecture.md, docs/phase2-plan.md]
tags: [brainstorm, knowledge-hub]
stale_reason: ""
changelog:
  - 2026-07-06 | /brainstorm | resolved OQ-1..OQ-4, OQ-7; SSO doi sang P1; review 2 tang; plan cap nhat theo gap
  - 2026-07-06 | /brainstorm | initial brainstorm deep mode, 7 OQs flagged
---

# Trung tam du lieu tri thuc: Confluence + MCP + Knowledge Graph

> Feature: knowledge-hub | Idea: confluence-mcp-knowledge-hub
> 1 feature co the co nhieu brainstorm — day la 1 idea/draft doc lap.

## 1. Idea Seed

Hoan thien Nexus-KB tu backend toi UI thanh trung tam du lieu tri thuc doanh nghiep: co MCP server, knowledge graph UI giong Onyx (github.com/KhaiTrang1995/onyx), connector lay data tu Confluence, xu ly tot PDF/Excel/DOCX. Tham chieu github.com/nduckmink/arkon nhung tranh kien truc lon xon vibe-code cua arkon.

## 2. Context

- Chu du an dang dung arkon nhung thay arkon chua toi uu, vibe-code nhieu lam hong kien truc, loan va rac. Quyet dinh xay ban thay the kien truc sach tren nen Nexus-KB.
- Khong co deadline cung. Uu tien hoan thien core truoc: upload file, trich xuat, luu vector vao Qdrant; toi uu roi moi mo rong.
- Hien trang repo: da co ingestion `.md`/`.txt` (Phase 1), search API, web console (search / graph / ingestion / review / audit), auth dang lam o Phase 2.
- Giai phap trich xuat de xuat: thu vien `markitdown` (Microsoft) chuyen moi dinh dang ve markdown. OCR/hinh anh de tuong lai.
- Ha tang co san cua chu du an: MCP Gateway (Keycloak) da dung xong; LLM host noi bo (OpenAI-compatible, cau hinh qua API key).

## 3. User Types (preliminary)

| User Type | Pain Point | Primary Need |
|-----------|-----------|--------------|
| Nguoi dung thuong (~100 nguoi) | Tim tai lieu roi rac tren Confluence cham, khong co hoi dap AI | Upload tai lieu, tim kiem, hoi dap RAG, xem graph trong pham vi workspace cua minh |
| Admin | Quan ly nguoi dung, nguon du lieu, gioi han he thong | Tao/import user, cau hinh Confluence connector, chay sync, tuy chinh quota, xem audit |
| AI agent (qua MCP Gateway) | Goi MCP Confluence truc tiep cham va thieu ngu canh | Tim kiem + hoi dap nhanh tren kho tri thuc da vector hoa (chi doc) |

## 4. Capabilities Breakdown

### P0 — must have
- Upload file (pdf, docx, xlsx, pptx, md, txt, csv) toi da 5 file/lan, 50MB/file (admin tuy chinh).
- Hang doi FIFO xu ly nen: trich xuat bang markitdown, chunk, embedding, luu Qdrant; hien thi trang thai "dang nap du lieu".
- Vong doi tai lieu: cho xu ly, dang trich xuat, da index, loi; review nhanh + audit "da doc" truoc khi cong bo. Giu song song co che review low-confidence hien co (2 tang: chunk kem chat luong van phai Reviewer duyet).
- Chong trung: hoi nguoi dung khi trung, them thanh phien ban moi (vX.Y.Z), xem lich su phien ban.
- Workspace + RBAC: admin full quyen, tao/import user; phan quyen tai lieu theo workspace (mo phong Confluence space).
- Dang nhap: tai khoan noi bo (JWT auth hien co tren feat/phase2). SSO Keycloak doi sang P1 (quyet dinh 2026-07-06).
- Tim kiem theo doan nguon va chatbot RAG (LLM noi bo, cau hinh API key), luon loc theo quyen workspace, tra loi kem trich dan.
- Confluence connector: admin cau hinh, bam sync thu cong; sync loi giua chung thi xoa du lieu do va chay lai tu dau.
- MCP server chi doc (tim kiem + hoi dap), xac thuc token Keycloak qua MCP Gateway.

### P1 — should have
- SSO cong ty qua Keycloak OIDC (doi tu P0 theo quyet dinh 2026-07-06).
- Knowledge graph UI kieu Onyx: truc quan, tim node, bam node hien noi dung linh dong.
- Man hinh admin: quan ly workspace, quota (so file/lan, dung luong, do rong hang doi), API key LLM.
- Sync Confluence theo lich (admin bat/tat).

### P2 — nice to have
- CDC phat hien sua/xoa tren Confluence de cap nhat vector (uu tien thap, tuong lai).
- Ho tro hinh anh + OCR (chu du an se goi y thu vien khi den luc).

> P0/P1/P2 la tentative; final scope chot o `/prd knowledge-hub`.

## 5. Core Flows (Happy Path)

### 5.1 Upload tai lieu

1. Nguoi dung chon toi da 5 file (moi file toi da 50MB) va bam upload.
2. He thong kiem tra dinh dang + dung luong; file khong hop le bi tu choi kem ly do.
3. He thong kiem tra trung (hash/ten): neu trung, hoi nguoi dung; dong y thi tao phien ban moi vX.Y.Z.
4. File hop le vao hang doi FIFO, trang thai "cho xu ly"; nguoi dung thay "Dang nap du lieu...".
5. Worker trich xuat (markitdown), chunk, embedding, luu Qdrant; trang thai "dang trich xuat" roi "da index".
6. Tai lieu cho review nhanh; nguoi dung xac nhan "da doc"; he thong ghi audit va cong bo vao workspace.

```
 USER                          SYSTEM                                TRANG THAI
  |
  | Chon <=5 file (<=50MB/file)
  +----------------------------> Kiem tra dinh dang + dung luong
  |                                |
  |                                +- Khong hop le --> Bao loi, tu choi file do
  |                                |
  |                                v
  |                              Kiem tra trung (hash/ten)?
  |                                |
  |                    +--- CO ----+--- KHONG ---+
  |                    v                         v
  |  <-- Hoi "Da co tai lieu,            Dua vao hang doi FIFO ---- [cho xu ly]
  |       them phien ban moi?"                   |
  |      |                                       v
  |      +- Dong y -> tao version v+1 -> queue   |
  |      +- Huy    -> dung, khong nap            |
  |                                              v
  |  <-- "Dang nap du lieu..."          Worker: markitdown -> chunk   [dang trich xuat]
  |                                       -> embedding -> luu Qdrant
  |                                              |
  |                                   +-- Loi ---+-- OK --+
  |                                   v                   v
  |  <-- Bao loi + ly do        [loi]              Cho REVIEW nhanh
  |      (cho admin/user chay lai)                        |
  |                                                       v
  |  <-- Xac nhan "da doc" -------------------- Ghi audit + cong bo   [da index]
  |                                             (workspace tim thay)
```

### 5.2 Dong bo Confluence (admin)

1. Admin cau hinh ket noi Confluence, chon space, he thong kiem tra token.
2. Admin bam "Sync" (khong tu chay theo lich o giai doan dau).
3. He thong tao sync run trang thai "running", keo trang theo space, map space sang workspace va ap phan quyen.
4. Hoan tat: run "completed" kem so trang da index. Loi giua chung: run "failed", xoa du lieu do, admin chay lai tu dau.

```
 ADMIN                         SYSTEM                       CONFLUENCE
  |
  | Cau hinh ket noi + chon space
  +---------------------------> Luu cau hinh, kiem tra token --> xac thuc
  |                                |
  | Bam "Sync"                     v
  +---------------------------> Tao sync run [running] --------> keo trang theo space
  |                                |  (map space -> workspace,
  |                                |   phan quyen theo workspace)
  |                                |
  |                     +- Dut/loi +---- Hoan tat --+
  |                     v                           v
  |  <-- Bao fail;  XOA du lieu do            Run [completed]
  |      run [failed], chay lai tu dau        + so trang da index
```

### 5.3 Tim kiem / hoi dap / MCP (chi doc)

1. Nguoi dung (web) hoac AI agent (qua MCP Gateway voi token Keycloak) gui truy van.
2. He thong loc theo quyen workspace cua nguoi goi.
3. Che do tim kiem: truy van Qdrant, tra ve doan tai lieu kem nguon.
4. Che do hoi dap RAG: lay ngu canh, goi LLM noi bo, tra loi kem trich dan.

```
 USER (web) hoac AI (qua MCP Gateway, token Keycloak)
  |
  +-- Tim kiem ----> Loc theo quyen workspace -> truy van Qdrant -> tra doan + nguon
  |
  +-- Hoi dap RAG -> Loc theo quyen workspace -> lay ngu canh -> LLM noi bo -> tra loi + trich dan
```

## 6. System Behavior Deep Dive

### 6.1 Decision Points

| ID | Flow | Khi nao | YES (nhanh dong y) | NO (nhanh tu choi) |
|---|---|---|---|---|
| D1 | Upload | File dung dinh dang va <=50MB? | Tiep tuc kiem tra trung | Tu choi file, bao ly do |
| D2 | Upload | File trung tai lieu da co? | Hoi nguoi dung tao phien ban moi | Vao hang doi binh thuong |
| D3 | Upload | Nguoi dung dong y tao phien ban? | Tao vX.Y.Z, vao hang doi | Huy, khong nap |
| D4 | Worker | Trich xuat + index thanh cong? | Chuyen sang cho review | Danh dau loi, cho chay lai |
| D5 | Review | Nguoi dung xac nhan da doc? | Ghi audit, cong bo vao workspace | Giu trang thai cho review |
| D6 | Sync | Sync run hoan tat tron ven? | Run completed, cap nhat so trang | Run failed, xoa du lieu do |
| D7 | Truy van | Nguoi goi co quyen workspace chua? | Thuc hien tim kiem/RAG | Tu choi, khong lo du lieu |

### 6.2 Scenario Matrix (vai tro x hanh dong)

| Vai tro | Hanh dong | Rule | Ket qua |
|---------|-----------|------|---------|
| Nguoi dung thuong | Upload file | Trong quota (5 file/lan, 50MB) | Vao hang doi, cho review |
| Nguoi dung thuong | Tim kiem/hoi dap | Chi trong workspace duoc cap | Ket qua da loc quyen |
| Nguoi dung thuong | Cau hinh Confluence | Khong co quyen | Bi tu choi |
| Admin | Tao/import user, cap workspace | Full quyen | Thanh cong, ghi audit |
| Admin | Cau hinh connector, bam sync | Full quyen | Sync run duoc tao |
| Admin | Tuy chinh quota/gioi han | Full quyen | Ap dung cho toan he thong |
| AI agent (MCP) | Tim kiem/hoi dap | Token Keycloak hop le, chi doc | Ket qua da loc quyen |
| AI agent (MCP) | Upload/ghi | Khong ho tro | Tu choi |

### 6.3 State Transitions

```
document: cho_xu_ly -> dang_trich_xuat -> da_index (cho review -> cong bo)
                                 \-> loi (chay lai -> cho_xu_ly)

sync_run: running -> completed
                \-> failed (xoa du lieu do, chay lai tu dau)
```

| Entity | Tu | Sang | Trigger | Quay lai duoc? |
|--------|------|----|---------|-------------|
| document | cho_xu_ly | dang_trich_xuat | Worker nhan job tu hang doi | khong |
| document | dang_trich_xuat | da_index | Trich xuat + embedding thanh cong | khong |
| document | dang_trich_xuat | loi | Parse/embedding/Qdrant loi | co (chay lai ve cho_xu_ly) |
| document | da_index (cho review) | cong bo | Nguoi dung xac nhan da doc, ghi audit | khong |
| document | cong bo | phien ban moi vX.Y.Z | Upload trung + dong y tao version | co (xem lich su phien ban) |
| sync_run | running | completed | Keo het trang trong space | khong |
| sync_run | running | failed | Dut ket noi, token het han, loi API | chay lai tu dau (khong resume) |

### 6.4 Interrupted Transactions

| Tinh huong | He thong con lai gi | Resume | Cleanup |
|---|---|---|---|
| Nguoi dung dong browser giua upload | Job da vao hang doi van chay tiep | Vao lai xem trang thai trong danh sach tai lieu | Khong can |
| Worker loi giua trich xuat | Document trang thai loi + ly do | Nguoi dung/admin bam chay lai (ve cho_xu_ly) | Xoa chunk/vector do dang cua lan chay loi |
| Sync Confluence dut giua chung | Sync run failed | Chay lai tu dau (khong resume — du lieu dut gay, ton tai nguyen xu ly meta) | Xoa toan bo du lieu do cua run |
| Token Confluence het han giua sync | Sync run failed, bao admin | Admin cap nhat token roi chay lai | Xoa du lieu do |
| Token MCP (Keycloak) het han | Request bi tu choi | AI agent lay token moi tu gateway | Khong can |
| 2 nguoi cung upload 1 file trung | Nguoi sau nhan hoi thoai trung/phien ban | Tao version ke tiep theo thu tu hang doi FIFO | Khong can |

### 6.5 Other Edge Cases

- Qdrant khong san sang: job giu trang thai loi ro rang, khong fail silent (theo rule Phase 1).
- LLM noi bo down: tim kiem theo doan van hoat dong; che do RAG bao loi ro rang.
- File PDF hong/ma hoa: danh dau loi kem ly do, khong retry vo han.
- Hang doi qua tai (100 nguoi cung upload): FIFO, hien vi tri/trang thai; admin dieu chinh do rong worker.
- Upload file rong hoac 0 byte: tu choi ngay tu buoc validate.
- Confluence space khong map duoc workspace: bao admin, khong index vao workspace sai (fail closed).

## 7. Validation, Limits & Wording

### 7.1 Validation rules

| Field | Rule |
|---|---|
| File upload | Dinh dang thuoc: .pdf, .docx, .xlsx, .pptx, .md, .txt, .csv; hinh anh de P2 |
| Dung luong file | Toi da 50MB/file (admin tuy chinh) |
| So file moi lan | Toi da 5 file/lan (admin tuy chinh) |
| File rong | Tu choi file 0 byte |
| Ten/noi dung trung | So sanh content hash; trung thi hoi tao phien ban |
| Token MCP | Token Keycloak con han, chi cap quyen doc |
| Truy van | Luon kem pham vi workspace; khong co quyen thi tu choi (fail closed) |

### 7.2 Limits & Quotas (exact values)

| Tham so | Gia tri | Window | Behavior khi vuot |
|---|---|---|---|
| So file / lan upload | 5 (admin tuy chinh) | moi lan | Tu choi phan vuot, bao nguoi dung |
| Dung luong / file | 50MB (admin tuy chinh) | moi file | Tu choi file, bao ly do |
| Thu lai khi worker loi | 3 lan (chot) | moi job | Danh dau loi, cho chay lai thu cong |
| Han token MCP | Theo cau hinh Keycloak | — | Tu choi request, agent lay token moi |
| Sync Confluence | Chi khi admin bam | — | Khong tu chay ngam |

### 7.3 Wording samples (exact strings)

#### Error messages

| Tinh huong | Wording | Code |
|---|---|---|
| File qua lon | "File vuot qua dung luong cho phep (toi da 50MB)." | E-kh-001 |
| Dinh dang khong ho tro | "Dinh dang file khong duoc ho tro. He thong nhan: PDF, DOCX, XLSX, PPTX, MD, TXT, CSV." | E-kh-002 |
| Qua so file / lan | "Moi lan chi upload toi da 5 file. Vui long bo bot va thu lai." | E-kh-003 |
| Trich xuat loi | "Trich xuat that bai: {ly do}. Ban co the bam Chay lai hoac lien he quan tri vien." | E-kh-004 |
| Sync Confluence loi | "Dong bo Confluence that bai: {ly do}. Du lieu do da duoc don dep, vui long chay lai." | E-kh-005 |
| Khong co quyen workspace | "Ban khong co quyen truy cap noi dung nay." | E-kh-006 |
| RAG khong kha dung | "Tro ly AI tam thoi gian doan. Ban van co the tim kiem theo tai lieu." | E-kh-007 |

#### Success messages

| Tinh huong | Wording |
|---|---|
| Index xong, cho review | "Tai lieu da duoc xu ly, dang cho ban xac nhan da doc de cong bo." |
| Review xong, cong bo | "Tai lieu da duoc cong bo vao workspace {ten workspace}." |
| Tao phien ban moi | "Da tao phien ban {vX.Y.Z} cho tai lieu {ten}. Xem lich su phien ban trong chi tiet tai lieu." |
| Sync hoan tat | "Dong bo Confluence hoan tat: {N} trang da duoc index vao workspace {ten}." |

#### Info / neutral messages

| Tinh huong | Wording |
|---|---|
| Dang cho trong hang doi | "Tai lieu dang cho trong hang doi (vi tri {n})." |
| Dang trich xuat | "Dang nap du lieu, vui long cho..." |
| Hoi khi trung | "Tai lieu nay da ton tai trong he thong. Ban co muon them thanh phien ban moi khong?" |

## 8. Assumptions

- Nguoi upload tu xac nhan "da doc" o buoc review (chot 2026-07-06).
- Dot nay chi tai khoan noi bo; SSO Keycloak de P1. MCP van verify token Keycloak tu gateway — 2 duong xac thuc doc lap (web: JWT noi bo, MCP: Keycloak).
- Giu toan bo phien ban cu; chi ban moi nhat nam trong index tim kiem; admin don thu cong khi can.
- Hang doi dung Postgres-backed job table (khong them ha tang moi; Redis hien co chi lam cache) — ghi ADR khi trien khai.
- markitdown du tot cho PDF/DOCX/XLSX/PPTX text-based; tai lieu scan/hinh anh de P2.
- LLM noi bo expose API OpenAI-compatible, cau hinh bang API key.
- Map 1 Confluence space = 1 workspace trong he thong.
- MCP Gateway chiu trach nhiem phat hanh/thu hoi token; Nexus chi verify.

## 9. Risks

| Rui ro | Kha nang | Hau qua nghiep vu | Cach phong |
|--------|----------|-------------------|-----------|
| Lap lai vet xe arkon: vibe-code pha kien truc | thuong | He thong loan, kho bao tri, mat niem tin nguoi dung | Giu ports & adapters, module boundaries, rules trong .claude/rules, review moi thay doi kien truc |
| Phan quyen workspace sai -> lo tai lieu phong ban khac | thinh thoang | Vi pham bao mat noi bo, mat niem tin, co the vi pham compliance | Fail closed, test phan quyen truc tiep, audit day du |
| Chat luong trich xuat kem (Excel phuc tap, PDF scan) | thinh thoang | Tim kiem sai/thieu, nguoi dung bo he thong | Danh gia markitdown tren bo tai lieu that truoc khi rollout; OCR de P2 |
| Confluence API rate limit / thay doi | thinh thoang | Sync cham hoac fail, du lieu cu | Sync theo dot do admin chu dong, backoff, thong bao ro |
| Adoption: 100 nguoi khong doi thoi quen tim tren Confluence | thinh thoang | He thong it duoc dung, lang phi cong xay | MCP + RAG tra loi nhanh hon ro ret; do luong truy van/tuan |
| LLM noi bo qua tai khi nhieu nguoi hoi dap | thinh thoang | Tra loi cham, trai nghiem xau | Che do tim kiem van chay doc lap; gioi han dong thoi o gateway |

## 10. Success Criteria (preliminary)

- Upload 1 file PDF/DOCX/XLSX 10MB: index xong trong vai phut, trang thai hien thi dung tung buoc.
- 100% truy van (web + MCP) bi loc theo quyen workspace; test phan quyen pass.
- AI agent qua MCP Gateway tim duoc tai lieu Confluence da vector hoa nhanh hon goi MCP Confluence truc tiep.
- Sync 1 Confluence space hoan tat va tim kiem duoc ngay sau khi run completed.
- Khong co module nao vuot qua ranh gioi kien truc (kiem tra bang review + import rules).

## 11. Open Questions

- [x] OQ-1: Resolved 2026-07-06 — nguoi upload tu xac nhan "da doc"; admin giam sat qua audit log.
- [x] OQ-2: Resolved 2026-07-06 — worker thu lai 3 lan roi danh dau loi, cho chay lai thu cong.
- [x] OQ-3: Resolved 2026-07-06 — rate limit de MCP Gateway/Keycloak lo; Nexus chi log usage theo token.
- [x] OQ-4: Resolved 2026-07-06 — dot nay chi tai khoan noi bo; SSO Keycloak OIDC doi sang P1.
- [ ] OQ-5: Ho tro hinh anh/OCR dung thu vien nao, khi nao bat dau (P2)?
- [ ] OQ-6: CDC Confluence (phat hien sua/xoa) trien khai theo huong nao khi den luc (P2)?
- [x] OQ-7: Resolved 2026-07-06 — giu tat ca phien ban; chi ban moi nhat trong index; admin don thu cong.

## 12. Next Steps

Sau brainstorm nay (sau khi BA approve):
- `/urd knowledge-hub` — capture user perspective
- `/brd knowledge-hub` — business case
- `/prd knowledge-hub` — product scope
- Plan trien khai + task breakdown: xem `docs/knowledge-hub/plan.md`

*KHONG nhay thang SRS — qua PRD truoc.*
