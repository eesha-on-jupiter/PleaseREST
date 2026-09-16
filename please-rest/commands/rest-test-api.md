---
description: "Re-run HTTP validation against the live API and rewrite call-library-validated.json."
---

# /rest-test-api

Run HTTP validation manually against the live API.
Use this if docs changed and call-library.json was refreshed, or to rerun after manual fixes.

---

## Steps

1. Confirm `spec/call-library.json` exists
   If not: "No call-library.json found. Run /rest-extract-api first."

2. Check for token: `PLEASE_REST_TOKEN` env var
   If not set: "Set PLEASE_REST_TOKEN before running tests:
     In your terminal: set PLEASE_REST_TOKEN=your_token_here"
   Wait — do not proceed without a token.

2a. **Protect the previous result.** If `spec/call-library-validated.json` exists, copy it to
   `spec/call-library-validated.prev.json` first (a hand-validated file from a previous run is not
   thrown away by a rerun).

2b. **Disclosure.** Write tests create real records in the user's account (at most one per POST /
   PUT / PATCH endpoint; DELETEs are skipped). If `session.json.decisions.seed_ids` holds a sandbox
   workspace / test IDs from intake, pass it as `seed_ids`; otherwise say so and let the user supply
   IDs now or accept the default behaviour.

3. Run MCP: pr-api-tester →
   `run_all_tests(call_library_path, output_path, skip_destructive=True, seed_ids=decisions.seed_ids)`
   (never pass the token as an argument — the tool reads `PLEASE_REST_TOKEN`).

4. Print Restling progress as tests run

5. Route the results:
   - **All entries FAILED with the same error class** (e.g. every one "missing http:// protocol",
     every one 401, every one "Missing seed ID"): that is a harness / token / base_url problem, not
     N API defects. Fix the one cause (set `base_url`, refresh the token, supply `seed_ids`) and
     rerun — do **not** send every entry to pr-api-scout.
   - **401 mid-run** (token expired): the tester halts and writes the partial result. Refresh the
     token, then `retest_entries(remaining_ids, ..., seed_ids)` for the untested IDs only.
   - **PARTIAL** ("not tested — no request body example" / "redirect — check base_url"): not an API
     failure. Enrich `example_request` (or fix `base_url`) in call-library.json, then
     `retest_entries` for those IDs. Record each enrichment in `decisions.manual_fixes`.
   - **FAILED** (a real non-2xx after a well-formed call): run agent pr-api-scout — it reads
     `test_result.error_body`, re-checks the docs / spec operation, patches call-library.json, and
     calls `retest_entries`. If still failing after one pass: present each to the user (Human Gate 4
     format).

6. Print final summary:
   ```
   Restling complete.
     Validated:  [n]
     Partial:    [n]
     Failed:     [n]
     Skipped:    [n] (destructive — DELETE methods)
     Not tested: [n] (PARTIAL — enrich example_request, then retest_entries)
   ```
   Show a one-line diff against `call-library-validated.prev.json` when it exists (entries whose
   tag changed).

7. Update session.json: last_completed_step = "call-library-validated.json"
