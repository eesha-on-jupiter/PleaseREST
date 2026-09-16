---
name: "pr-overview"
description: "What PleaseREST is, its vocabulary, and which command, skill, agent or MCP to reach for. Load when orienting in a PleaseREST-driven build or when unsure which piece handles a task."
---

# Skill: PleaseREST overview

> *Politely turns any REST API into a Grasshopper plugin — so you can take that much needed rest*

PleaseREST automates the repeatable process of building a Grasshopper REST API plugin: API
discovery, call extraction, HTTP validation, code scaffolding, icon generation, tests, packaging,
and Food4Rhino publish. The human plans, reviews, and tests at seven gates; PleaseREST does the
mechanical work between them.

**Active state verb:** `Restling` — used in all progress output, MCP terminal output, and CI logs.

Entry point is `/rest-new-plugin`. State lives in `spec/session.json`, so a build can stop and
resume across sessions with `/rest-resume-plugin`.

## Commands

| Command | Use it to |
|---|---|
| `/rest-new-plugin` | Start a build — preflight, then the full 15-phase pipeline |
| `/rest-resume-plugin` | Pick up from the last saved session |
| `/rest-status` | See the progress tree; read-only, safe any time |
| `/rest-gen-spec` | Regenerate `plugin-spec.json` from `feasibility.json` |
| `/rest-gen-todo` | Regenerate `todo.md` from `plugin-spec.json` |
| `/rest-extract-api` | Refresh `call-library.json` after the docs changed (keeps `.prev.json`, re-applies manual fixes) |
| `/rest-test-api` | Re-run HTTP validation against the live API (PARTIAL → enrich + retest; FAILED → `pr-api-scout`) |
| `/rest-build-component <id>` | Scaffold one component (VALIDATED calls only) |
| `/rest-build-all-components` | Build every unbuilt `[CODE]` item in todo build-phase order; stops before `[SHIP]` items |
| `/rest-icon-preview [glyph]` | See every background shape in each fill style (gradient / solid / none) and pick one |
| `/rest-icons [component]` | Re-render icons from `icons.json` and embed them (manual Phase 11) |
| `/rest-add-feature <desc>` | Add a feature any time, even post-ship — re-enters at Phase 3; incremental extract/test |
| `/rest-package` | Validated-calls check, then `.yak` for all three targets + CI workflow (Phase 15) |

## Which skill handles what

`pr-conventions` loads alongside every other skill and is never loaded alone.

**By file type:** `pr-component` (any `GH_Component`) · `pr-button` (create/update/delete) ·
`pr-builders` (`[Resource]Builders.cs`) · `pr-client` (`[PluginName]Client.cs`) ·
`pr-assembly` (`[PluginName]Info.cs`) · `pr-preset` (`GH_ValueList`) ·
`pr-utilities` (`PluginUtilities.cs`) · `pr-bulk-data` (data-tree bulk writes)

**By phase:** `pr-spec` → `pr-todo` → `pr-file-structure` → `pr-vs-project` → `pr-icons` →
`pr-unit-tests` → `pr-build` → `pr-rhino-test` → `pr-docs` → `pr-gh-package` → `pr-yak-package` →
`pr-ci-template`

`pr-gh-package` also creates the GitHub repo and pushes `main` (Phase 14 isn't done until it has);
`pr-yak-package` carries the post-Gate-7 publish checklist (tag → Release, `yak push`, Food4Rhino)
and the backfill that fills the README / `docs/index.md` pre-release placeholders once live;
`pr-ci-template` writes **two** workflows — `build.yml` on PRs, `publish.yml` on a `v*.*.*` tag.

**Always available:** `pr-session` (state), `pr-permissions` (`.claude/settings.local.json`),
`pr-dogfood` (run logging), and this skill (`pr-overview`)

**Two "Phase N" numberings exist.** The pipeline has Phases 1–15 (with 7 gates). `todo.md` has its
own build Phases 1–10 (Auth → Package). Say "todo build Phase 2" vs "pipeline Phase 2" when it
could be ambiguous. todo items tagged `[SHIP]` (docs / GitHub / package) are pipeline Phases 13–15.

## Agents

- **`pr-api-scout`** — after HTTP validation leaves FAILED or PARTIAL entries: reads the tester's
  `error_body`, re-checks the docs page or spec operation, patches `call-library.json`, retests,
  escalates after one pass. Not for harness-class failures (every entry failing the same way).
- **`pr-aec-advisor`** — after `plugin-spec.json` is confirmed: cross-references the AEC feature
  library against the API's real data shape and recommends features.
- **`pr-spec-critic`** — right after `pr-spec` drafts the spec, before it's confirmed: flags
  components that don't trace to a workflow, missed merges/consolidations, and unneeded tree
  variants as simplification notes for Gate 2.

## MCPs

- **`pr-api-extractor`** — crawls API docs, or parses an OpenAPI 3 / Swagger 2.0 spec / Google API
  Discovery doc, into `call-library.json`. Tags entries EXTRACTED · PARTIAL · AMBIGUOUS · MISSING;
  fills `auth_in` (`header` | `header:<Name>` | `query:<param>`), `body_required`, `content_type`.
- **`pr-api-tester`** — fires real HTTP calls into `call-library-validated.json`. Reads
  `PLEASE_REST_TOKEN` (never pass the token as an argument). `run_all_tests` / `retest_entries` take
  `seed_ids`; PARTIAL entries are listed, not fired; each `test_result` has `error_body`.
- **`pr-icon-generator`** — renders 24×24 component icons and a 16×16 plugin icon from `icons.json`,
  and injects them into `Resources.resx` (Windows-only injection). `preview_backgrounds` renders every
  shape in each fill style (gradient / solid / none) to a labelled contact sheet, so the options are
  seen before one is chosen. `"custom": true` skips a hand-made icon; `"background": {}` removes the
  inherited background. Background shapes are SVG artwork in
  `backgrounds/`, and glyph placement is authored in that artwork as a `#ed1c24` rect — not computed.

The **Grasshopper MCP bridge** used by `pr-rhino-test` is external and user-wired (McNeel
`Rhino-MCP-Platform`); it needs a live Rhino session, so it is deliberately not in `plugin.json`.

## Rules that bite

- The manifest is the **only** file in `.claude-plugin/`. `commands/`, `skills/`, and `agents/` sit
  at the plugin root and are auto-discovered — listing them in `plugin.json` is a schema error that
  loads the plugin with zero skills and no error message.
- `CLAUDE.md` at the plugin root is **not** shipped as plugin context. This skill is what ships.
- The generated plugin's pre-approvals go in `[PluginName]/.claude/settings.local.json` — a
  root-level `settings.local.json` is ignored by Claude Code.
- Components are built only from `VALIDATED` calls. PARTIAL / FAILED / skipped entries never reach
  codegen silently; `/rest-package` refuses to ship them without an explicit "ship anyway".
- Tokens live in `PLEASE_REST_TOKEN` only — never in tool arguments, `session.json`, the validated
  library, or a saved demo `.gh`.
- Any change to a skill/agent/command/MCP that would change what an already-completed phase
  produces must bump `plugin.json`'s `version` and add a `CHANGELOG.md` entry — otherwise
  `/rest-resume-plugin`'s staleness alert silently goes stale itself.
