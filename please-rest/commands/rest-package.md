---
description: "Build .yak packages for all three Rhino targets and generate the CI publish workflow."
---

# /rest-package

Package the plugin as .yak files for all 3 targets and generate the CI workflow.
Load skills: pr-yak-package + pr-ci-template

---

## Steps

1. Read `spec/session.json` — confirm the plugin name and current state

2. Confirm tests are passing before packaging:
   Run `dotnet test` — if failures: "Tests are failing. Fix them before packaging."
   Do not proceed until tests are green.

2a. **Validated-calls check.** Read `spec/plugin-spec.json` and `spec/call-library-validated.json`.
   For every component that names an `endpoint_id`, look up that entry's `test_result.tag`. If any
   is not `VALIDATED` (FAILED / PARTIAL / never tested), STOP and list them:
   ```
   Not validated — these components would ship on untested calls:
     • [ComponentName]  →  [endpoint_id]  ([tag] — [error])
   Fix: /rest-test-api (or enrich example_request → retest_entries), or reply "ship anyway".
   ```
   Only continue on an explicit "ship anyway"; record the list under
   `session.json.decisions.ship_unvalidated` so the decision is on record.

3. Load skill: pr-yak-package
   - dotnet build -c Release for net48, net7.0-windows and net7.0 (all three targets)
   - yak build in each output dir (`--platform win` / `--platform mac` for the Rh8 builds)
   - Validate manifests
   - Copy to dist/

4. Load skill: pr-ci-template
   - Generate **both** workflows: `.github/workflows/publish.yml` (tag → 3 .yak + 3 .zip on a
     GitHub Release) and `.github/workflows/build.yml` (PR → build all targets + test).
     Re-running this command overwrites both — they are generated files, not user-edited ones.

5. Print:
   ```
   Restling complete. 3 targets packaged.
     dist/[plugin]-[version]-rh7_0-any.yak
     dist/[plugin]-[version]-rh8_0-win.yak
     dist/[plugin]-[version]-rh8_0-mac.yak
   (yak names the files — do not rename them)

   CI: .github/workflows/build.yml (PR) + publish.yml (tag → Release with 3 .yak + 3 .zip)

   To publish: push a version tag to GitHub.
     git tag v1.0.0
     git push origin v1.0.0
   ```

6. Update session.json (see pr-session "Write timing"):
   - `current_phase` = 15, `current_phase_name` = "Package + Ship" — Phase 14 is GitHub and is not
     touched here
   - `last_completed_step` = "dist/*.yak + .github/workflows/{build,publish}.yml"
   - **append `15` to `completed_phases`** — the phase is done when the three packages and the two
     workflows exist. Gate 7 stays in `gates_pending`; it is a separate human cross-platform test,
     and withholding the phase until it passes is what makes a packaged plugin read as un-packaged.
   - If `14` is not in `completed_phases`, run `pr-session`'s phase-completion audit before
     finishing: a plugin that has `dist/` but no recorded GitHub phase either never pushed (say so,
     and point at `pr-gh-package` "Publish to GitHub") or pushed without recording it (offer to
     reconcile).

   When Gate 7 then passes, append `7` to `gates_passed` and mark the plugin `status: complete` in
   the global sessions index. Publishing follows — tag push, `yak push`, Food4Rhino listing, then
   the README / `docs/index.md` backfill (`pr-yak-package` "Publishing" and "After publishing"),
   each recorded in `github.released_tags` / `published` as it actually happens.
