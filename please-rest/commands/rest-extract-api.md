---
description: "Re-run API extraction to refresh call-library.json without rerunning the full pipeline."
---

# /rest-extract-api

Run API extraction manually. Use this if the API docs changed and you need to
refresh call-library.json without rerunning the full pipeline.

---

## Steps

1. Read `spec/session.json` for docs_url and plugin context
   If not found: ask the user for the docs URL and plugin name

2. Read `spec/plugin-spec.json` to get the component list

3. Check whether an OpenAPI spec URL is known (session.json flags.openapi_spec_used or from intake.json)

4. Run MCP: pr-api-extractor
   - If OpenAPI spec available: `extract_from_openapi(spec_url, component_list)`
   - Otherwise: `extract_from_docs(...)` for each endpoint in component_list

5. Print Restling progress as extraction runs

6. **Protect hand edits before overwriting.** If `spec/call-library.json` already exists, copy it
   to `spec/call-library.prev.json` first. Then call
   `write_call_library(entries, "spec/call-library.json")`.

6a. Show a diff summary against `call-library.prev.json` (entries added / removed / changed
   method, url_template, body_schema, auth_in). Then read `session.json.decisions.manual_fixes`:
   for every entry that was hand-enriched in a previous run (typical: `body_schema` /
   `example_request` filled in by hand for JS-rendered docs), re-apply that enrichment to the new
   entry if the endpoint still exists, or list it as "manual fix no longer applies" — never let a
   re-extract silently erase work the user did at Gate 4.

7. Print extraction summary:
   ```
   Restling complete.
     Extracted:  [n]
     Ambiguous:  [n]
     Missing:    [n]
   ```
   List PARTIAL, AMBIGUOUS and MISSING entries with their notes. Every entry now also carries
   `auth_in` (`header` | `header:<Name>` | `query:<param>`, from the spec's security schemes),
   `body_required` and `content_type` — check `auth_in` matches what Phase 2 found.
   If **0 entries are EXTRACTED**, stop here: the spec source is wrong (marketing page, JS-only
   docs, Discovery doc not detected). Try the OpenAPI / Google Discovery URL or apis.guru before
   moving on — do not proceed to `/rest-test-api` with nothing to test.

8. Update session.json: last_completed_step = "call-library.json"

9. Prompt: "Run /rest-test-api to validate the extracted calls against the live API."
