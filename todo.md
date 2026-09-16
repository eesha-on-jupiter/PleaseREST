# PleaseREST — Plugin File Structure TODO
> Target: spec Section 1 — full plugin package

---

## PHASE 1 — REORGANISE EXISTING FILES
Rename skill folders to pr- prefix. Move MCP files into pr-icon-generator subfolder.

[x] Rename `.claude/skills/conventions/`     → `.claude/skills/pr-conventions/`
[x] Rename `.claude/skills/component/`       → `.claude/skills/pr-component/`
[x] Rename `.claude/skills/button/`          → `.claude/skills/pr-button/`
[x] Rename `.claude/skills/client/`          → `.claude/skills/pr-client/`
[x] Rename `.claude/skills/builders/`        → `.claude/skills/pr-builders/`
[x] Rename `.claude/skills/assembly/`        → `.claude/skills/pr-assembly/`
[x] Rename `.claude/skills/preset/`          → `.claude/skills/pr-preset/`
[x] Move `mcps/server.py`         → `mcps/pr-icon-generator/server.py`
[x] Move `mcps/icon_config.json`  → `mcps/pr-icon-generator/icon_config.json`
[x] Move `mcps/requirements.txt`  → `mcps/pr-icon-generator/requirements.txt`
[x] Delete old commands: `restghpluginplanner.md`, `restghplugintodo.md`

---

## PHASE 2 — FIX pr-icon-generator MCP
Three fixes required before pr-icon-generator is spec-compliant.

[x] Fix 1 — add optional `config_path` param to `generate_icon()` and `add_to_resources()`; fall back to same-directory config if not provided
[x] Fix 2 — confirm `plugin_prefix` always comes from the loaded config (resolved by Fix 1)
[x] Fix 3 — update `load_config()` to accept the path from Fix 1 so per-plugin `icon_config.json` files are read correctly
[x] Verify: load_config default + explicit config_path both work; draw_background renders all 6 shapes at 96x96

---

## PHASE 3 — NEW MCPs
Two new MCP servers. Highest-risk items — build and test against a real API before Phase 4.

[x] Create `mcps/pr-api-extractor/requirements.txt`   — httpx, beautifulsoup4, pyyaml, mcp[cli]
[x] Create `mcps/pr-api-extractor/server.py`           — tools: `extract_from_openapi`, `extract_from_docs`, `write_call_library`
[x] Create `mcps/pr-api-tester/requirements.txt`       — httpx, mcp[cli]
[x] Create `mcps/pr-api-tester/server.py`              — tools: `test_endpoint`, `run_all_tests`, `retest_entries`
[x] Verify: extract_from_openapi against Petstore spec — EXTRACTED/MISSING tags correct, path+query params resolved
[x] Verify: test_endpoint against httpbin — VALIDATED on 200, FAILED on 404/401, POST body sent correctly

---

## PHASE 4 — MISSING SKILLS
Ten new SKILL.md files. Write in dependency order.

[x] `.claude/skills/pr-utilities/SKILL.md`       — PluginUtilities.cs: TabName + subcategory constants, GetValues<T>() helper
[x] `.claude/skills/pr-file-structure/SKILL.md`   — scaffold full generated plugin folder layout, rename namespaces/GUIDs, generate icon_config.json
[x] `.claude/skills/pr-spec/SKILL.md`            — produce plugin-spec.json from feasibility.json; subcategory rules, component naming, I/O chain, inline validator
[x] `.claude/skills/pr-todo/SKILL.md`            — produce spec/todo.md from plugin-spec.json; phased structure, [CODE]/[TEST]/[ASSET]/[MANUAL] tags, mark existing files [x]
[x] `.claude/skills/pr-unit-tests/SKILL.md` — xUnit test file per component: input validation, output type, mocked API call shape, error handling
[x] `.claude/skills/pr-build/SKILL.md`    — dotnet build → dotnet test → surface failures → fix → rerun until all green; Restling progress output
[x] `.claude/skills/pr-gh-package/SKILL.md`      — generate README.md, CLAUDE.md (with header block from spec Section 4.1), LICENSE, .gitignore
[x] `.claude/skills/pr-yak-package/SKILL.md`    — dotnet build -c Release × 3 targets, yak build, validate manifest, output to /dist/
[x] `.claude/skills/pr-ci-template/SKILL.md`     — generate .github/workflows/publish.yml; trigger v*.*.*, build/test/yak steps, Restling log messages
[x] `.claude/skills/pr-session/SKILL.md`         — read/write/resume session.json; global ~/.please-rest/sessions.json index; write timing rules; edge cases

---

## PHASE 5 — AGENTS
Two agent markdown files in `.claude/agents/`.

[x] `.claude/agents/pr-api-scout.md`    — reads FAILED entries, re-fetches docs, patches call-library.json, triggers retest_entries; escalates after one pass if still failing
[x] `.claude/agents/pr-aec-advisor.md`  — reads plugin-spec.json, cross-references AEC feature library (spec Section 9), outputs structured recommendations with rationale

---

## PHASE 6 — COMMANDS
Eleven command files. Replace the two old commands.

[x] `.claude/commands/rest-new-plugin.md`            — full pipeline entry point: intake → 15 phases → session.json write at each phase
[x] `.claude/commands/rest-resume-plugin.md`         — reads session.json; single/multiple/no session handling (exact output format from spec Section 3)
[x] `.claude/commands/rest-gen-spec.md`         — invokes pr-spec skill on existing feasibility.json
[x] `.claude/commands/rest-gen-todo.md`           — invokes pr-todo skill on existing plugin-spec.json
[x] `.claude/commands/rest-extract-api.md`           — invokes pr-api-extractor MCP manually
[x] `.claude/commands/rest-test-api.md`              — invokes pr-api-tester MCP manually
[x] `.claude/commands/rest-build-component.md`       — scaffolds one component by ID; selects correct skill (component/button/builders/preset) + conventions
[x] `.claude/commands/rest-build-all-components.md`  — iterates todo.md [CODE] items in phase order; applies correct skill per type; marks [x] as each completes
[x] `.claude/commands/rest-add-feature.md`           — re-enters at Phase 3 (spec update only); runs Phases 6–12 for new components only
[x] `.claude/commands/rest-status.md`                — reads todo.md, prints current completion state
[x] `.claude/commands/rest-package.md`               — invokes pr-yak-package skill

---

## PHASE 7 — PLUGIN MANIFEST AND CLAUDE.MD

[x] `plugin.json`   — full manifest from spec Section 2: name, version, skills list, agents list, mcp_servers, commands, permissions
[x] `CLAUDE.md`     — PleaseREST's own CLAUDE.md: what the plugin is, how to work on it, build order, which skills to load for each file type, active sessions index location

---

## PHASE 8 — PERMISSIONS + DOCS
The two remaining spec skills (spec Section 4) plus the stale-MCP cleanup. Build Order Round 8 = Permissions.

[x] `.claude/skills/pr-permissions/SKILL.md` — generate `settings.local.json` at Phase 1 intake; pre-approve all pipeline commands; show summary before confirm; append + re-approve for custom AEC commands; never auto-approve destructive
[x] `.claude/skills/pr-docs/SKILL.md`        — generate `docs/` folder in Phase 13: one md per component, one index per subcategory, quickstart, authentication, examples, changelog; PARTIAL/MISSING edge cases
[x] Register both skills in `plugin.json` skills array (17 → 19) and the Skills section of `please-rest/CLAUDE.md`
[x] Fix `.claude/settings.local.json` — replace the stale legacy server perms and `enabledMcpjsonServers` entry with the renamed `pr-icon-generator` / `pr-api-extractor` / `pr-api-tester` servers

---

## PHASE 9 — DOGFOOD FIXES + ICON RENDERING
GoogleSlidesConnect dogfood findings (F1–F6) encoded and icon rendering improved.

[x] pr-spec/SKILL.md: content-type model — prescriptive tab layout table, naming rules, write path; remove named benchmark reference (F1)
[x] pr-utilities/SKILL.md: content-type model section — separate HTTP/JSON group ordering, code example (F1)
[x] pr-api-extractor/server.py: Google API Discovery adapter — auto-detects `discoveryVersion`/`resources→methods`; fills `base_url`/`auth_in` per entry (F2)
[x] pr-api-tester/server.py: `base_url` join for relative `url_template`s; per-entry `auth_in: "query:<param>"`; seed chaining from POST response IDs (F3)
[x] pr-vs-project/SKILL.md: `GenerateResourceUsePreserializedResources=true` + `System.Resources.Extensions` PackageReference in csproj template (F4)
[x] pr-assembly/SKILL.md + pr-icons/SKILL.md + server.py: plugin icon resource name aligned to `[PluginName]Logo` (not `PluginIcon`) (F5)
[x] pr-component/SKILL.md: Icon property uses `Properties.Resources.[XX]_[Name]` with correct prefix (F6)
[x] pr-vs-project/SKILL.md: `Resources.Designer.cs` namespace `[PluginName].Properties` documented (F6)
[x] pr-icon-generator/server.py: `make_solid()` — gaussian blur + threshold fills interior holes in outline icons; applied to both bg.icon and drop shadows
[x] pr-icon-generator/server.py: bg.icon defaults — `BG_ICON_COLOR = "#FFFFFF"`, `BG_ICON_OPACITY = 0.45`; `opacity` field wired into rendering
[x] test_rendering.py: 8 new tests — `make_solid` behaviour (4) + bg.icon opacity defaults (4); blur test assertion strengthened to unique-alpha-levels metric
[x] PleaseREST-spec.md: v2.4 changelog; Section 6 descriptions for pr-api-extractor, pr-api-tester, pr-icon-generator updated; Section 13 test descriptions updated
[x] CLAUDE.md + spec: test counts corrected to 156

---

## Summary

| Phase | Items | Status |
|---|---|---|
| 1 — Reorganise | 11 moves/deletes | ✅ complete |
| 2 — Fix pr-icon-generator | 3 fixes + verify | ✅ complete |
| 3 — New MCPs | 4 files + 2 verifies | ✅ complete |
| 4 — Missing skills | 10 SKILL.md files | ✅ complete (pr-utilities partial) |
| 5 — Agents | 2 agent files | ✅ complete |
| 6 — Commands | 11 command files | ✅ complete |
| 7 — Manifest + CLAUDE.md | 2 files | ✅ complete |
| 8 — Permissions + Docs | 2 SKILL.md + manifest/CLAUDE.md register + settings fix | ✅ complete |
| 9 — Dogfood fixes + icon rendering | F1–F6 encoded; make_solid; bg.icon defaults; 144 tests | ✅ complete |
| 10 — Remove shadow-icon feature | shadow logic caused unwanted background blobs on no-bg icons; stripped from server.py + tests + docs | ✅ complete |

**Total new/modified files: 47**
**Already correct (content only, pending rename): 7 skills**
**Hard gate before Phase 4: MCPs must pass live API test**
