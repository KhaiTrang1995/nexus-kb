# Nexus-KB UI Design Package (ASCII First)

This directory contains the **UI design skill + artifacts** for the Nexus-KB operational console, modeled directly after `docs/brainstorm-skill-package`.

**Core principle (from user request + architecture.md):**
- Complete the design documentation and **ASCII wireframes first**.
- Only after review/approval of ASCII + exact wording do we proceed to actual UI code (Vite/React in `apps/web-console/` per frontend-plan.md).
- No component code, no Figma export, no implementation claims in this phase.

## Structure (mirrors brainstorm-skill-package)

- `SKILL.md` — The `/ui-design` skill definition (deep 7-section interview, mandatory ASCII, IT-BA/UX framing, one-section-at-a-time). Use this to generate future UI designs.
- `_templates/ui-design.md` — 13-section (adapted) output template with slots for ASCII wireframes, scenario matrices, UI state transitions, exact wording tables (error/success/info), risks in business terms, open questions.
- `nexus-kb-operational-ui.md` — Concrete design output for the main operational UI (Search + Graph context, Review Queue + actions, Audit, etc.). **This is the primary deliverable with rich ASCII box-drawing wireframes.**
- `agent-operating-guide.md` (to be added if more rules needed) + this README.

## How to use (for future UI ideas)

1. Read `SKILL.md` + `_templates/ui-design.md`.
2. Invoke the process (manually or via agent following the SKILL):
   - `/ui-design "review queue with graph provenance in results"`
   - Or interactive.
3. Follow 7 sections one-by-one.
4. Synthesize into new `docs/UI/{feature}/designs/{slug}.md` using the template.
5. **ASCII wireframes are mandatory** for primary screens.
6. Get L1 review (plain language).
7. Only then: follow `frontend-plan.md` for code phases + create `apps/web-console/`.

## Current Status (2026-06-20)

- Backend core (Phases 1-7) complete + verified (tests pass).
- This package provides the **pre-code ASCII + structured design** for the UI Layer described in `architecture.md`.
- See `nexus-kb-operational-ui.md` for the first full design (Search, Review, Graph, Audit) with:
  - Multiple detailed ASCII wireframes
  - Scenario matrices
  - UI state transitions
  - Exact button/toast/error wording
  - Risks, assumptions, open questions
  - Clear "ASCII first — code later" guardrails

## References & Alignment
- `../architecture.md` (UI Layer source of truth)
- `../frontend-plan.md` (high-level phases — now references ASCII designs here)
- `../phase-checklist.md` (UI is future work after Phase 5)
- `../../AGENTS.md`, `.rules` (Experience Engine calls before any follow-on UI architecture/code)
- `docs/brainstorm-skill-package/` (the model this package is based on)

## Next (after ASCII review)
- Approve the designs in `nexus-kb-operational-ui.md`.
- Re-call Experience Engine.
- Proceed to scaffold per frontend-plan (only then touch actual UI code or `apps/web-console/`).

All examples use synthetic data. No production claims.
