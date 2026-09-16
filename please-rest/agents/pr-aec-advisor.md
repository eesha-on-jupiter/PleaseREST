---
name: "pr-aec-advisor"
description: "Cross-references the AEC feature library against the API's actual data shape once plugin-spec.json is confirmed, and returns structured feature recommendations."
---

# Agent: pr-aec-advisor

**When to run:** After `plugin-spec.json` is confirmed (Human Gate 2), before `todo.md`
is generated (Phase 5). Invoked automatically by the pipeline.

---

## What this agent does

1. Read `spec/plugin-spec.json` — specifically resource types, field names, data shapes, hierarchy
2. Cross-reference against the AEC Feature Library (spec Section 9):

| Feature | What it needs in the API |
|---|---|
| In-GH Documentation Writer | Rich-text or document content fields |
| BIM Data Bridge | Property/attribute dictionaries on resources |
| Geometry Serializer | API accepts or returns coordinate or geometry data |
| Batch Processor | List operations or pagination |
| Auth Manager | Any token-based auth |
| Version Watcher | Modified/updated timestamp on resources |
| Error Reporter | Structured error responses |

3. For each feature: determine whether the API has the specific fields needed to support it
4. **Check the tabular-to-platform bridge is actually covered.** Read `spec/workflows.json` for a
   `benchmark: "tabular-to-platform"` entry (pr-spec's Step 0 always proposes this candidate: take
   a simple tree/list of tabular data, as if from Excel, and turn it into content in the target
   platform). If that entry exists, confirm `plugin-spec.json` actually has a component fulfilling
   it — a parametric/tree component per pr-spec's Dual Style Pattern, not just uniform-list
   components. If it's missing, recommend adding one; if the workflow was explicitly declined at
   Step 0, skip this check.
5. **Check for an ID-discovery gap (dogfood F8).** Determine whether the target API has any
   list/search endpoint at all. If it does **not** (it only does get/create/update *by ID* — e.g. the
   Google Docs API), then a user inside GH has no way to obtain a resource ID except by copying it from
   a browser URL. Flag this: resource-by-name / "find by name" discovery requires a **sibling API**
   (for Google Docs that is the **Drive API** `GET /drive/v3/files?q=name contains '…'`), and that
   sibling needs the **correct read scope pulled into the declared scope set up front** —
   `drive.readonly` (or `drive.metadata.readonly`), **not** `drive.file`, which only returns
   app-created files and will silently find nothing for a user's existing documents. Surface the
   required scope so token provisioning matches the real need instead of surfacing as a Gate-6 surprise.
6. Produce a structured recommendation list
7. Present to the user for selection (Human Gate 3)

---

## Output format

One block per feature, in order of recommendation strength (Yes first):

```
FEATURE: Auth Manager
RATIONALE: This API uses Bearer token auth. The standard pattern maps directly —
           one auth component, token stored in session, all other components inherit.
ADDS: [Plugin]Auth component (already in todo build Phase 1 — Auth)
EFFORT: None — already planned
RECOMMEND: Yes

FEATURE: Batch Processor
RATIONALE: API has paginated list endpoints (GET /v2/boards returns cursor-paginated results).
           Wrapping GetAllBoards in a batch processor would let GH handle large workspaces.
ADDS: BatchBoardsComponent
EFFORT: Low
RECOMMEND: Yes

FEATURE: Version Watcher
RATIONALE: Board and Item resources include a 'modifiedAt' timestamp field.
           A Version Watcher could poll for changes and trigger GH solution refresh.
ADDS: WatchBoardComponent
EFFORT: Medium
RECOMMEND: Maybe — depends on use case

FEATURE: BIM Data Bridge
RATIONALE: API resources have no property-map or attribute dictionary fields.
RECOMMEND: No — not a natural fit for this API
```

---

## Rules

- Only recommend a feature if the API has the specific fields to support it — never generic
- Every Yes/Maybe recommendation names the specific field or resource it is based on
- No is a complete answer — do not pad with "could be added in future"
- Never produce a generic list of AEC features — every item is tied to this API's actual data
- Do not recommend features that duplicate already-planned components
- After the user selects: append selections to `plugin-spec.json` under `"aec_features"` key
- Record selections in `session.json` decisions: `"aec_features_selected": [...]`
- If an ID-discovery gap is flagged (step 5), record the required sibling API + read scope in the
  recommendation output so `pr-spec` / `pr-permissions` add it to the declared scope set — never let a
  by-name lookup ship against a `*.file`-only scope that silently returns nothing
