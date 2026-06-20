---
name: ui-design
description: Use when user wants to design or clarify the UI/UX for a feature before writing any React/TSX code or Figma. Triggered by `/ui-design <idea text>` or `/ui-design @<file>` or interactive. Focus on compact operational interface per architecture.md UI Layer. Output structured design doc in `docs/UI/{feature}/designs/{idea-slug}.md` with **mandatory ASCII wireframes first** (box-drawing), scenario matrices, UI state machines, exact wording (labels, errors, success), before any code. Deep interview: sections one at a time. IT-BA + UX framing only — no implementation details until ASCII approved.
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
user-invocable: true
argument-hint: "<ui idea text> | @<file-path> | (empty for interactive) [--lang vi|en] [--shallow]"
---

# /ui-design — ASCII-First UI Design Skill (modeled on /brainstorm)

## Goal
Turn raw UI idea into structured design document via **7-section deep interview** (one section at a time). Output follows `_templates/ui-design.md` (adapted 13-section style):
- User types & roles (searcher, reviewer, admin)
- Capabilities P0/P1/P2
- Core Screens & Flows with **numbered steps + ASCII wireframe diagram** (mandatory for all main screens)
- System/UI Behavior Deep Dive (decision points, scenario matrix by role/state, UI state transitions, interrupted flows e.g. review during long search)
- Validation/Limits/Wording (exact button text, error messages, placeholders, accessibility notes)
- Assumptions, risks (adoption, cognitive load, compliance with audit/review rules), success metrics, open questions.

**Strict rule**: ASCII wireframes and text-based designs come **before** any code, Figma export, or component files. Only after ASCII sign-off do we discuss Vite/React/Tailwind implementation.

This skill serves UX/IT-BA for Nexus-KB (governed RAG + KG). Compact operational UI (not marketing landing). References `architecture.md` UI Layer and `frontend-plan.md`.

## Constraints
- L1 approval before writing the design file (confirm feature slug + idea slug).
- Per-feature: `docs/UI/{feature}/designs/{idea-slug}.md`. Multiple ideas per feature OK, do not auto-merge.
- Auto-derive slugs from idea (feature from "search with graph context", idea from specific flow).
- Interview one section at a time. User can `skip` → TBD + open question.
- **Mandatory ASCII artifacts** (auto-detect complexity):
  - ASCII wireframe for every primary screen/flow (use box-drawing: ┌─┐│▼ etc.).
  - Scenario matrix if multi-role (searcher vs reviewer) or multi-state (PENDING review items).
  - UI State machine table if screens have modes (viewing result → opening graph panel → acting on review).
  - Interrupted flow matrix for async ops (ingest running while reviewing).
- Push for **exact UI text**: "What does the button say exactly? 'Approve & Index' or 'Commit to Vector'?"
- No technical questions in interview (no "use React Query" or "Tailwind class"). Business/UX only: what user sees, does, feels. Implementation later.
- Vietnamese-first default. Output lang choosable.
- Quality gate before L1: every flow must have ASCII + numbered user+system steps.
- Do not claim "UI is built". This is design artifact only. See `frontend-plan.md` for phased code plan (Phase A+ after ASCII complete).
- Call Experience Engine before any follow-on architecture/UI code changes.

## Inputs
```
/ui-design
/ui-design <raw ui idea text>
/ui-design @docs/frontend-plan.md
/ui-design "Review queue with approve/modify for low-confidence chunks" --lang vi
/ui-design ... --shallow
```

## Approach (follows /brainstorm closely, adapted for UI)

### Phase A — Resolve & Detect (silent)
1. Resolve idea source (text or @file).
2. Auto-derive feature slug (e.g. "search", "review", "graph-explorer", "audit").
3. Auto-derive idea slug.
4. Detect complexity: multi-role (searcher/reviewer), stateful (review status), async (ingest/graph build), branching flows → force ASCII + matrices.
5. Language detection.

### Phase B — Interview (7 sections, one-by-one)
**Section 1 — Overview**
- What does this UI surface do for the user? (1-2 sentences from user view)
- Pain it solves in current (backend-only) workflow?
- Why now? (part of which phase?)

**Section 2 — Users & Access**
- Primary roles: searcher (any), reviewer (X-User-Role: Reviewer), auditor?
- Entry points: sidebar nav, direct link after ingest, notification?
- Expected frequency / number of concurrent users?

**Section 3 — Core Screens & Happy Path Flows**
- Walk through step-by-step: user action → system response (what appears on screen) → user sees success.
- List main screens (e.g. Search Results, Review Queue, Single Review Item, Graph Panel, Audit Log).
- Sub-flows (filter while searching, modify during review).

**Section 4 — Deep Dive (if complexity)**
- For each screen/flow:
  - User actions + visible system reactions (business level).
  - Decision points in UI (e.g. "if low confidence in result, show review badge?").
  - UI state transitions (e.g. ResultCard collapsed → expanded graph → action taken).
  - Interrupted: what if user leaves review queue while background graph build happens?
- **Draw ASCII wireframe** for each major screen (L3 iterate max 3 rounds).
- Scenario matrix (role × state).
- State table.

**Section 5 — Validation, Limits & Exact Wording**
- Required inputs, formats, limits (e.g. max 50 results shown, query min 3 chars).
- Exact labels, buttons, placeholders, error/success/info messages (natural Vietnamese or English).
- Accessibility notes (keyboard, screen reader hints for graph).

**Section 6 — System/UI Context**
- What data must be visible (from backend contracts: snippets, graph_entities, review status, audit actor)?
- Notifications / real-time needs (ingest progress)?
- Integration with existing: reuse search API, review endpoints, no new backend until design approved.

**Section 7 — Edge Cases, Risks, Open Questions**
- Empty states, error states, concurrent reviewer actions, very long content.
- Risks: reviewer fatigue, trust in "AI" scores, information overload in graph view.
- Open questions for later (implementation, backend changes).

### Phase C — Synthesize
- Build output using `_templates/ui-design.md`.
- Embed ASCII wireframes in relevant sections.
- Quality gate (similar to brainstorm): ASCII present, exact wording, matrices for complex, business language only.

### Phase D — L1 Preview + Write (BA/UX language)
- Preview in natural language.
- Write the .md under docs/UI/...
- Append to changelog if applicable.
- Recommend next: ASCII sign-off → then follow `frontend-plan.md` Phase A (scaffold), or more /ui-design for other screens.

## Gotchas (adapted)
- Push for **ASCII first** — user may want pretty Figma immediately. Remind: "ASCII wireframe approved before any visual or code."
- No implementation leakage in interview.
- Multi-screen ideas: one feature can have multiple design docs.
- Continuation: if editing existing design doc, read it first, only ask gaps.
- Vietnamese typography friendly.
- After this skill, do not jump to code — prepare ASCII, get approval, **then** consider actual UI.

## References
- @../../architecture.md (UI Layer)
- @../../frontend-plan.md
- @../brainstorm-skill-package/.claude/skills/brainstorm/SKILL.md (base process)
- @../brainstorm-skill-package/_templates/brainstorm.md (inspiration for structure)
- Project phase-checklist (UI is post-Phase 5)
- Experience Engine must be called before any follow-up UI code.

## Output Location
`docs/UI/{feature}/designs/{idea-slug}.md`

Always produce at least one concrete ASCII wireframe per primary screen in the synthesized design.
