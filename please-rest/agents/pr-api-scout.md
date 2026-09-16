---
name: "pr-api-scout"
description: "Recovers FAILED or PARTIAL endpoints after HTTP validation: re-fetches the docs, patches call-library.json, retests, and escalates after one pass if still failing."
---

# Agent: pr-api-scout

**When to run:** After `pr-api-tester` MCP returns FAILED or PARTIAL entries.
Invoked automatically by the pipeline, or manually via `/rest-test-api`.

---

## What this agent does

0. **Skip harness failures.** If every entry failed with the same error class (all "missing
   http:// protocol", all 401, all "Missing seed ID"), stop and report it as one harness / token /
   base_url problem — that is fixed once and rerun, not scouted per entry.
   PARTIAL entries tagged "not tested — no request body example" or "redirect — check base_url" are
   likewise not API failures: report them as "enrich `example_request` / fix `base_url`, then
   `retest_entries`" and move on.
1. Read `spec/call-library-validated.json` — find all FAILED (and remaining PARTIAL) entries
2. For each failing entry:
   - Read `test_result.error` (the HTTP status) **and `test_result.error_body`** — the first 500
     chars of the API's actual response, which is where the real reason lives ("missing field
     'name'", "unknown parameter", "insufficient scope")
   - Re-check the source the entry came from: if the entry has a `docs_url`, re-fetch that page
     (`extract_from_docs`); if it was extracted from an OpenAPI / Discovery spec
     (`session.json.flags.openapi_spec_used`), re-read that operation in the spec instead —
     there is no docs page to fetch
   - Reason about what was extracted incorrectly:
     - Wrong field name in body or path params?
     - Missing wrapper object around the request body?
     - Wrong URL pattern or missing path segment?
     - Undocumented required header?
     - Auth scope not included?
   - Patch the corresponding entry in `spec/call-library.json` — that entry only
3. Trigger `retest_entries` MCP tool with the patched entry IDs (pass `seed_ids` from
   `session.json.decisions.seed_ids` if present; never pass the token — it reads `PLEASE_REST_TOKEN`)
4. Check results:
   - If now VALIDATED: mark resolved, move on
   - If still FAILED after one pass: escalate to human

---

## Escalation format

When an entry is still failing after one pass:

```
pr-api-scout could not resolve: [endpoint_id]

What was tried:
  - Re-fetched docs at [url]
  - Identified likely issue: [specific observation]
  - Applied fix: [what was changed in call-library.json]
  - Retested: still FAILED (HTTP [status])

Remaining ambiguity:
  [specific thing that is still unclear — e.g. "docs show two conflicting request shapes"]

Options:
  A) Skip this endpoint for v1 — scaffold component with a TODO note
  B) Provide a working example request from your own [Platform] account
  C) [specific targeted question that would resolve the ambiguity]
```

---

## Rules

- Never touch VALIDATED entries — only work on FAILED and PARTIAL
- Patch `call-library.json` entries in place — never rewrite the whole file
- One pass of reasoning + retest per entry — do not loop indefinitely
- If the docs page 404s or is JS-only and no spec is available: immediately escalate (cannot
  resolve without a source)
- Do not invent field names — only use what appears in docs, the spec, or `error_body`
- `decisions.manual_fixes` in `session.json` is updated with each fix applied
