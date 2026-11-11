# PleaseREST Changelog

Tracks changes to PleaseREST itself (skills, agents, commands, MCPs) that could affect what an
already-in-progress generated plugin's completed phases produced. Each bullet names the phase(s)
it affects, so `/rest-resume-plugin` and `/rest-add-feature` can tell you whether anything you've
already built predates the change.

`plugin.json`'s `version` is the source of truth, and `session.json.please_rest_version` mirrors it
for the resume-time check (see `pr-session`).

Bump `plugin.json`'s `version` and add an entry here whenever a change to a skill, agent, command,
or MCP would change what an already-completed phase produces — see `CLAUDE.md`.

## 1.1.0 — 2026-11-11

Rhino 9 and macOS as a build machine. No generated file changes shape — a plugin built on 1.0.0
does not need any phase rerun.

- **Phase 11 (icons)** — `add_to_resources` now works on macOS / Linux. It used to return a
  "Windows-only" error there, which left Phase 11 unfinishable on a Mac. Off Windows the Bitmap
  `<data>` node is written directly (`write_resx_bitmap`), in the bytearray.base64 form
  `ResXResourceWriter` emits; an empty `<root/>` resx gains the standard resheaders. Windows still
  goes through PowerShell, unchanged.
- **Phase 1 (preflight), Phase 15 (package)** — yak is probed in Rhino 9 first, then 8, then 7.
  Rhino 9 installs the `rh8_0` packages; there is no `rh9_0` package to build.
- **Phase 8 (scaffold)** — documented, not changed: the `net7.0-windows;net7.0;net48` csproj builds
  clean on .NET SDK 10 and its `net7.0` / `net7.0-windows` output loads in Rhino 9 (.NET 10).
- **Phase 9 / Gate 5, Phase 12 / Gate 6** — Rhino 9 instructions: which build folder to load,
  `MCPStart` (not `MCPConnect`) starts the bridge listener, loading a dev `.gha` without a restart,
  and driving `ButtonComponent.TriggerButton()` through the bridge's C# tool.

## 1.0.0 — 2026-09-16

First public release.

Everything before this was unreleased development — PleaseREST was built and then dogfooded by
using it to generate several real Grasshopper plugins end to end, each round feeding its failures
back into the skills. The internal version numbers from that period never shipped to anyone and are
not part of this history; 1.0.0 is where the public record starts.

**What's in it**

- **The pipeline** — `/rest-new-plugin` drives a REST API reference through 15 phases and 7 human
  gates: intake and preflight, API discovery, plugin spec, AEC features, todo, call extraction,
  live HTTP validation, scaffold, auth component, batch build, icons, tests, docs, GitHub, package
  and ship. `/rest-resume-plugin` picks up any build across sessions; `/rest-add-feature` adds a
  component at any point in a plugin's life, including after it has shipped.
- **25 skills, 3 agents, 3 MCP servers, 13 commands.** The MCPs crawl or parse API references
  (OpenAPI 3, Swagger 2.0, Google Discovery), fire real HTTP calls to validate every endpoint
  before a line of C# is written, and render the plugin's icons from Iconify.
- **Generated output** — a buildable Visual Studio Grasshopper project targeting Rhino 7 (net48),
  Rhino 8 Windows (net7.0-windows) and Rhino 8 Mac (net7.0); xUnit builder tests; a portable
  `docs/` folder; README, CLAUDE.md, LICENSE and .gitignore; three `.yak` packages plus three
  install `.zip` bundles; and two GitHub Actions workflows (PR build + tag → Release).
- **Authorship is the user's.** The plugin name, icon prefix, author name and contact, and GitHub
  org are asked for at intake and flow into `GH_AssemblyInfo`, `manifest.yml`, the README byline
  and the LICENSE. There is no naming convention to follow and no default author.
- **364 tests** across the three MCP servers.

---

## Upgrading a plugin started before 1.0.0

If a build's `session.json` carries a `please_rest_version` from the pre-release period — any `2.x`
stamp — or no stamp at all, it predates the fixes below. `pr-session`'s version check treats any
such stamp as behind 1.0.0 and surfaces this list on resume. None of it is urgent unless that
plugin is about to ship.

**Blocks a correct release**

- **Re-run `/rest-package`.** Before 1.0.0 the "Rhino 8 Windows" `.yak` was silently the Mac build
  (`net7.0-windows` was never built for Release), and the CI workflow used `src/` paths that don't
  exist in the flat layout. The same re-run also writes both workflows — `build.yml` was missing
  entirely, and `publish.yml` lacked `permissions: contents: write` (the Release step 403s after a
  fully green build) and the step that produces the three install `.zip` files.
- **Add the Release `PropertyGroup` to the csproj** (`DebugType none`, `DebugSymbols false`,
  `GenerateDependencyFile false`, `GenerateRuntimeConfigurationFiles false`) — see `pr-vs-project`.
  Without it every `.yak` ships a `.pdb`, `.deps.json` and `.runtimeconfig.json`, because
  `yak build` packages whatever is in the output folder.
- **Fix the author.** Pre-1.0.0 skills hardcoded one person's name and email into
  `[PluginName]Info.cs` (`AuthorName` / `AuthorContact`), `manifest.yml` `authors:`, the README
  byline and the LICENSE copyright. Set `session.json.author` and correct those four.

**Security / privacy**

- **Blank the Token panel in any saved `demos/*.gh`,** and rotate the token if one was committed.
- **Check `.gitignore` before pushing.** `dogfood/`, `.claude/`, `settings.local.json` and `demos/`
  were not in the template. A `.gitignore` line added after a file is tracked does nothing —
  `git ls-files | grep -E "^(dogfood|demos|\.claude)/"`, then `git rm -r --cached` what it finds.

**Correctness of generated code**

- **Rebuild presets, button components, and value builders / aggregators** via
  `/rest-build-component`. Presets referenced a constant that doesn't exist (CS0117); button
  components returned null outputs on every recompute instead of re-emitting their last result;
  value builders emitted positional values only, so an aggregator silently misaligned them if
  inputs were wired in a different order.
- **Re-run `/rest-test-api`** if any call was left PARTIAL or FAILED for a harness reason — any 2xx
  response over 2000 chars used to be mis-tagged PARTIAL, which also broke seed-ID chaining, and
  `auth_in` was never set, so every API got `Authorization: Bearer` whether or not that was right.
- **Move `settings.local.json` into `.claude/`** — it was written to the plugin root, where Claude
  Code never reads it, so every command prompted for permission.

**Cosmetic, but visible to users**

- **Re-run `/rest-icon-preview` then `/rest-icons`.** Icons authored before 1.0.0 silently
  inherited the template's blue gradient rounded-square, which is a placeholder, not a house style.
  The same re-run renders the 1024×1024 `[XX]_Plugin_Icon.png` for the README header and the
  Food4Rhino listing — a third size that didn't exist before. `"custom": true` icons are left alone,
  and Grasshopper needs a rebuild to show the change.
- **Re-run `pr-gh-package`** for the README's "What you can do with it" section and the component
  table's Tab column. Edits outside the `<!-- pr: -->` markers survive.
- **Reconcile the phase record.** Phases 14 and 15 used to complete without being written to
  `completed_phases`, so a plugin already on GitHub with packages in `dist/` reads as un-built.
  `/rest-status` and `/rest-resume-plugin` now audit the artifacts on disk and offer to fix it.
- **If the plugin is already published,** do the post-release backfill: the README's
  `(pending first release)` lines and `docs/index.md`'s `(pre-release)` / Food4Rhino / Released
  placeholders are correct at generation time and stale the moment it goes live. See
  `pr-yak-package`, "After publishing".
