# Agent Operating Guide for Nexus-KB UI Design

For agents (Grok, Claude, etc.) working on UI design docs in `docs/UI/`.

## 1. Read First (mandatory per AGENTS.md + phase-checklist)
- `../AGENTS.md`
- `../architecture.md` (especially UI Layer)
- `../frontend-plan.md` (now references ASCII gate)
- `../phase-checklist.md`
- This package's `SKILL.md`, `_templates/ui-design.md`, `nexus-kb-operational-ui.md`, `README.md`
- The model: `../brainstorm-skill-package/.claude/skills/brainstorm/SKILL.md` and its template

## 2. When to Use This Package
- User asks for UI design, wireframes, flows, or "prepare ASCII before UI code".
- Before touching `apps/web-console/` or any frontend code.
- To generate new design docs for additional screens/features.

## 3. Process (ASCII First)
1. Follow `SKILL.md` (7 sections one at a time, deep interview).
2. Use `_templates/ui-design.md` for output.
3. **Mandatory**: ASCII wireframes (box drawing ┌─┐│ etc.) for every primary screen/flow.
4. Include scenario matrices, state transitions, exact UI wording (buttons, errors, toasts), business risks.
5. L1 preview in plain UX/BA language.
6. Write to `docs/UI/{feature}/designs/{slug}.md` (or top level for main console).
7. Update `frontend-plan.md`, `docs/ui.md`, README, index.html, phase-checklist with links + "ASCII approved" note only after review.
8. Re-call Experience Engine before any follow-on code that touches UI layer or new contracts.

## 4. Hard Rules
- No actual UI code, components, or `apps/web-console/` creation in design phase.
- No marketing/hero language — compact operational per architecture.
- Synthetic data only in examples.
- Exact wording is sacred (copy-paste ready for later impl).
- Document "why ASCII first" explicitly.
- Keep scoped to docs/UI/.

## 5. Verification for Documentation Changes
- Manual review of links and headings.
- Cross-check against architecture.md UI Layer and current backend contracts (no invention of new endpoints).
- Confirm Experience Engine was called for the design session.
- The concrete design (`nexus-kb-operational-ui.md`) must contain multiple real ASCII wireframes + matrices.

## 6. Useful References
- Current backend routes and contracts (see `services/nexus-api/...` and `packages/shared-contracts`).
- Existing `frontend-plan.md` phases (A=Search MVP, B=Review, C=Graph/Audit, D=Polish).
- Experience Engine (`.rules`) for any architecture/UI decisions.

After ASCII design is solid, the next real work is code — and only then create the web console directory.
