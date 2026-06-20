---
type: ui-design
feature: {{feature}}
idea_slug: {{idea_slug}}
status: draft
mode: {{mode}}                # deep | shallow
lang: {{lang}}
owner: {{owner}}
created: {{date}}
updated: {{date}}
complexity_flags: {{complexity_flags}}   # has_multi_role, has_state_machine, has_async_flow, has_graph_context, has_review_actions, etc.
links: {{links}}
tags: [ui-design, {{feature}}, ascii-first]
stale_reason: ""
changelog: []
---

# {{title}}

> Feature: {{feature}} | Idea: {{idea_slug}}
> ASCII wireframes & text design first. No code or Figma until this doc is reviewed and ASCII approved.
> See architecture.md UI Layer + frontend-plan.md for overall context. Synthetic data only in examples.

## 1. Idea Seed

{{seed}}

*Raw UI idea from user or prior plan (e.g. frontend-plan.md or architecture).*

## 2. Context

{{context}}

*Why this UI now? Relation to backend phases (ingestion + review + graph + audit complete). Pain with current (no UI) experience.*

## 3. User Types & Access (preliminary)

| User Type | Role / Header | Primary Pain | Primary Need | Entry Point |
|-----------|---------------|--------------|--------------|-------------|
| {{user_type}} | {{role}} | {{pain}} | {{need}} | {{entry}} |

*Roles map to backend: searcher (any), reviewer (X-User-Role: Reviewer). No real auth yet — mock headers for design.*

## 4. Capabilities Breakdown (P0/P1/P2 — tentative)

### P0 — must have (core operational value)
{{p0_capabilities}}

### P1 — should have
{{p1_capabilities}}

### P2 — nice to have
{{p2_capabilities}}

> Scope to be finalized after ASCII review + alignment with backend contracts (SearchResponse, ReviewItemRecord, GraphBuildResult, AuditRecord).

## 5. Core Screens & Happy Path Flows (ASCII FIRST)

> Every primary screen/flow **must** have:
> - Numbered steps (User action → What system returns from API → What user sees on screen)
> - Embedded **ASCII wireframe** using box-drawing characters.
> - For complex: decision points, state changes.

### 5.1 {{screen_1_name}} (e.g. Main Search + Results)

1. {{step_user_1}}
2. {{step_system_response_1}}
3. {{step_user_sees_1}}

```
{{ascii_wireframe_search}}
```

*Example wireframe structure (adapt):*
```
┌─────────────────────────────────────────────────────────────┐
│ [Nexus-KB]  Search  Review  Graph  Audit  │  [User: alice] │
├─────────────────────────────────────────────────────────────┤
│ Query: [ governed retrieval          ] [Search] [Clear]   │
│ Filters: Tags [rag, enterprise]  Source [any ▼]  Limit [10]│
├─────────────────────────────────────────────────────────────┤
│ Results (8)  • Reranked • 0.12s                              │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ 1. Title: Governed Retrieval in Enterprise RAG  [0.91]  │ │
│ │    Snippet: ... <mark>governed</mark> retrieval ...     │ │
│ │    Path: /vault/Platform.md#section-3   Tags: [rag]     │ │
│ │    Graph: [Entity: RAG] --builds--> [Entity: Audit]     │ │
│ │    [View full] [Add to Review if low conf]              │ │
│ └─────────────────────────────────────────────────────────┘ │
│ ... more results ...                                        │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 {{screen_2_name}} (e.g. Review Queue)

1. ...
```
{{ascii_wireframe_review}}
```

### 5.3 {{screen_3_name}} (Graph Explorer / per-result context)

...
```
{{ascii_wireframe_graph}}
```

(Include at least the main 4-5 screens from architecture + frontend-plan: Search, Review Queue + Action, Audit Log, Ingestion Status, Graph.)

## 6. UI Behavior Deep Dive

### 6.1 Decision Points (UI level)

| ID | Screen/Flow | When (condition visible to user) | YES path (what appears) | NO path |
|----|-------------|----------------------------------|-------------------------|---------|
| D1 | Search results | Result confidence < 0.70 and user is Reviewer | Show "Low confidence — Send to Review" badge + action | Normal result card only |
| ... | ... | ... | ... | ... |

### 6.2 Scenario Matrix (by role / state)

| From Role/State | Action | To State | What User Sees (exact) | Backend Call |
|-----------------|--------|----------|------------------------|--------------|
| Searcher / normal result | Click "View graph" | Graph panel open | Inline panel with entities + relationships | /graph/chunks/{id} |
| Reviewer / PENDING item | Click APPROVE | APPROVED + indexed | "Item approved and added to vector index" toast | POST /review/action {APPROVE} |
| ... | ... | ... | ... | ... |

### 6.3 UI State Transitions (screens / panels / item states)

```
ReviewItem: PENDING ──[Approve]──> APPROVED (vector upserted)
             │
             ├──[Reject]──> REJECTED (no index)
             │
             └──[Modify]──> MODIFIED (content edited + re-index)
```

| Entity/Screen | From State | To State | Trigger (user visible) | Reversible? |
|---------------|------------|----------|------------------------|-------------|
| ReviewItem card | PENDING | APPROVED | Click Approve button | No (audit trail) |
| SearchResults | List view | Detail + Graph panel | Click result or "Graph" chip | Yes (close panel) |

### 6.4 Interrupted / Async Flows (ingest, graph build, long review)

| Situation | UI State Left | Resume / Recovery | User Message (exact wording) |
|-----------|---------------|-------------------|------------------------------|
| User closes tab during background ingest | Ingestion run "running" badge | On return: poll / show status from last run | "Ingestion still running in background. Last update: 2m ago." |
| Reviewer starts modify while search re-runs | Form dirty + results stale | Warn + offer "Refresh results (loses edit)?" | "Search results changed while you were editing. Refresh?" |
| ... | ... | ... | ... |

### 6.5 Other Edge Cases
{{edge_cases}}

## 7. Validation, Limits & Exact Wording (UI text only)

### 7.1 Validation / Input rules (visible to user)

| Field / Control | Rule (user-facing) |
|-----------------|--------------------|
| Search query | Min 2 chars. Max 200. No special control chars. |
| Review modify content | ... |

### 7.2 Limits & Quotas (exact, visible or enforced in UI)

| Limit | Value | Behavior when exceeded | Message |
|-------|-------|------------------------|---------|
| Results returned | 50 max (UI shows first 10, "load more") | "Showing top 10 of 47. Refine query or filters for better precision." | ... |

### 7.3 Wording samples (exact strings the user will see — copy-paste ready)

#### Buttons / Actions
- "Search"
- "Approve & Index to Vector"
- "Modify & Re-index"
- "Reject (do not index)"
- "Build Graph (100 chunks)"

#### Error messages
| Situation | Exact string |
|-----------|--------------|
| No results | "No matching knowledge found. Try broadening filters or rephrasing." |
| Review action failed (409 already finalized) | "This item was already reviewed by someone else. Refresh the queue." |
| 403 non-reviewer | "Reviewer role required. Contact your administrator or use header X-User-Role: Reviewer in dev." |

#### Success / Info
- "Item approved. 1 chunk added to Qdrant."
- "Graph built: 23 entities, 41 relationships. View in Graph tab."

## 8. Assumptions

{{assumptions}}

*E.g. "Backend APIs (search, review, graph, audit) are stable and return the contracts in shared-contracts. Synthetic data sufficient for design validation. Dark theme matching current index.html."*

## 9. Risks (UX / Adoption / Governance — business language)

| Risk | Likelihood | Business/UX Impact | Mitigation (in design) |
|------|------------|--------------------|------------------------|
| Reviewer overload (too many low-conf items) | Medium | Slows governance, people skip review | Confidence filter default, bulk actions later, clear "why this was queued" explanation |
| Graph viz confusing for non-technical users | High | Low trust in "knowledge graph" feature | Start with simple list + "why these entities" tooltips; expandable only on demand. ASCII first to validate mental model. |
| ... | ... | ... | ... |

## 10. Success Criteria (preliminary, measurable hints)

{{success_criteria}}

*E.g. "A reviewer can approve a low-conf item and see it appear in subsequent search in < 30 seconds (simulated). New user can perform first search and understand one graph relationship without training."*

## 11. Open Questions

- [ ] OQ-1: {{open_question}}
- ...

## 12. Next Steps (after this ASCII design is approved)

1. Review & iterate ASCII wireframes here (L3 max).
2. Sign-off on exact wording and flows.
3. Then (and only then):
   - Follow `frontend-plan.md` Phase A scaffold (Vite + React + typed API client against current contracts).
   - Create `apps/web-console/` only at that point (with .gitkeep until ready).
   - Map ASCII areas to components.
   - Add vitest / Playwright tests against synthetic backend.
4. Re-call Experience Engine before any code touching UI layer or new frontend contracts.
5. Update `frontend-plan.md`, `phase-checklist.md`, README, index.html with links + evidence (ASCII artifacts + approval).

**Reminder**: This is design documentation + ASCII. No actual UI code or component files are created as part of this skill output.
