# UI Design for Nexus-KB (docs/ui)

This is the entry point for the UI design work.

**See the full skill package and designs in `docs/UI/`** (modeled on `docs/brainstorm-skill-package`):

- `docs/UI/README.md` — overview + how to use the skill
- `docs/UI/SKILL.md` — `/ui-design` skill (deep interview process, ASCII mandatory first)
- `docs/UI/_templates/ui-design.md` — structured 13-section template with slots for ASCII wireframes, matrices, exact wording
- `docs/UI/nexus-kb-operational-ui.md` — **the completed design document** for the operational console (Search + graph context, Review queue with approve/modify/reject, Audit, etc.)

## Key Principle
Hoàn thiện tài liệu + **thiết kế ASCII trước** (wireframes bằng box-drawing characters, scenario matrices, state transitions, exact UI text).

Chỉ sau khi ASCII và wording được review/approve thì mới chuyển sang làm UI code (theo `frontend-plan.md` Phase A+ và chỉ tạo `apps/web-console/` lúc đó).

## Alignment
- Dựa trực tiếp trên cấu trúc, quy trình 7-section interview, mandatory artifacts (ASCII flow, scenario matrix, state machine, interrupted tx, exact wording) của `docs/brainstorm-skill-package`.
- Phục vụ UI Layer trong `docs/architecture.md`: compact operational interface cho search, graph exploration, ingestion status, audit review, human approval.
- Tuân thủ AGENTS.md, phase-checklist.md, Experience Engine calls, synthetic data only.
- Không claim implementation. Đây là design artifact.

## Current Deliverable
The concrete ASCII-heavy design lives in `docs/UI/nexus-kb-operational-ui.md`.

It was created by following the brainstorm-style process for the raw idea of the Nexus-KB operational UI.

Next steps after review: ASCII iteration → approval → then (and only then) actual UI implementation.

See also:
- `frontend-plan.md` (updated to reference this)
- `architecture.md`
- Experience entries logged for this work
