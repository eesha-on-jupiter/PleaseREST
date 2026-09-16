---
name: pr-gh-package
description: Generate README.md, CLAUDE.md, LICENSE, .gitignore for a generated Grasshopper REST API plugin, then create the GitHub repo and push
---

# Skill: GitHub package

Generate the four files that ship with the generated plugin to GitHub, **and get the plugin onto
GitHub** — repo created, first commit, pushed.
Runs in **Phase 14** (GitHub), after `pr-docs` produces the `docs/` folder in Phase 13 — so the
README may link to it. (CLAUDE.md is also regenerated at the end of every phase and every human
gate, independent of Phase 14, so it is always current.)

Phase 14 is not finished when the four files exist. It is finished when `git remote -v` names a
real repo and `main` has been pushed to it — see "Publish to GitHub" below. Record the result in
`session.json.github` and append 14 to `completed_phases`; a Phase 14 that wrote the files but
never pushed is the single most common way a build ends up looking un-done in `/rest-status` while
the repo is sitting on GitHub (seen in a dogfood run).

---

## Re-runs must not clobber user edits — generated-region markers

`README.md` and `CLAUDE.md` are re-emitted on every re-run (`/rest-add-feature` step 14, every phase
for CLAUDE.md). Users edit both. So every generated block is fenced:

```markdown
<!-- pr:begin components -->
…generated content…
<!-- pr:end components -->
```

- **First run:** write the whole file, every generated section inside its own `pr:begin <id>` /
  `pr:end <id>` pair.
- **Re-run, file exists:** for each `<id>`, replace **only** the text between its markers. Anything
  outside the markers (user prose, extra sections, badges) is preserved byte-for-byte. A section
  whose markers are missing (user deleted them) is **not** re-added — print a one-line notice instead.
- `LICENSE` and `.gitignore` have no markers: `LICENSE` is never rewritten if present; `.gitignore`
  is only ever appended to (missing lines added, nothing removed).

Section ids used in README: `header`, `install`, `quickstart`, `components`, `requirements`,
`license`. `header` covers the byline, **What you can do with it** and **Under the hood**;
`requirements` covers Requirements, **Documentation** and **Development**. The id list has not
changed since the first release — new content goes inside an existing block rather than adding an
id an older plugin's README wouldn't have.

Section ids used in CLAUDE.md: `header`, `state`, `platform`, `structure`, `builders`, `decisions`,
`limitations`, `todo`.

---

## README.md

```markdown
<!-- pr:begin header -->
<img src="[PluginIcon].png" alt="[PluginName]" width="96" align="left" style="margin-right:16px">

# [PluginName]
> Grasshopper plugin for the [Platform] REST API — by [AuthorName]
>
> Built with the [PleaseREST](https://github.com/[GitHubOrg]/PleaseREST) Claude Code plugin — an AI pipeline that turns a REST API reference into a Grasshopper plugin.

[One sentence description of what the plugin does in Grasshopper.]

<br clear="left">

## What you can do with it

[One line framing the plugin as work a user wants done, not as an API wrapper.]

- **[Outcome]** — [what the user gets, and what stays live when the model changes].
- **[Outcome]** — [ditto].
- **[Outcome]** — [ditto].

Component chains for each of these are in [docs/workflows.md](docs/workflows.md); worked examples are in [docs/examples/](docs/examples/).

**Under the hood**

- [The one design decision a user has to understand to wire this plugin correctly.]
- [A second, if there is one — no more than three bullets.]
<!-- pr:end header -->

<!-- pr:begin install -->
## Installation

**Food4Rhino:** [link, or `(pending first release)`]
**Yak:** `_PackageManager` → search `[plugin-name]` [or `(pending first release)`]

**Rhino 8 note:** the Rhino 8 packages are built for .NET 7 and load only when Rhino runs on the .NET Core runtime (its default). If the [PluginName] tab is missing, run `SetDotNetRuntime` in Rhino, choose **.NET Core**, and restart — Rhino.Inside Revit setups often switch this to .NET Framework.

**From source:** `dotnet build [PluginName].csproj`, then drop the `.gha` for your Rhino version into Grasshopper's `Libraries` folder (Rhino 7: `bin/Debug/net48`; Rhino 8 Windows: `bin/Debug/net7.0-windows`; Rhino 8 Mac: `bin/Debug/net7.0`) and restart Rhino — or point Grasshopper's developer-folder setting at the build folder. Close Rhino before rebuilding; it locks the `.gha`.
<!-- pr:end install -->

<!-- pr:begin quickstart -->
## Quick start

1. Get your [Platform] API token from [where] — see [docs/authentication.md](docs/authentication.md).
2. Drop **[Auth component]** onto the canvas and plug your token into `Token` — `Status` confirms the connection.
3. [First real operation — the one that returns the ID everything else needs.]
4. [Author / build step.]
5. [Aggregate / combine step, if the plugin has one.]
6. [The write component — press the button.]

Full walkthrough: [docs/quickstart.md](docs/quickstart.md). Common wirings as component chains: [docs/workflows.md](docs/workflows.md). Reference for every component: [docs/index.md](docs/index.md).
<!-- pr:end quickstart -->

<!-- pr:begin components -->
## Components

| Tab | Component | Inputs | Outputs | Description |
|---|---|---|---|---|
[one row per component from plugin-spec.json, grouped by subcategory in ribbon order]
<!-- pr:end components -->

<!-- pr:begin requirements -->
## Requirements

- Rhino 7 or 8 (Windows or Mac)
- [Platform] account with API access
- API token with scopes: [list required scopes, one line each with what needs it]

## Documentation

- [docs/index.md](docs/index.md) — overview and every component by tab
- [docs/quickstart.md](docs/quickstart.md) — first [thing] in [n] steps
- [docs/workflows.md](docs/workflows.md) — common wirings as component chains
- [docs/authentication.md](docs/authentication.md) — tokens and scopes
- [docs/examples/](docs/examples/) — worked examples
- [docs/changelog.md](docs/changelog.md)

## Development

```
dotnet build [PluginName].csproj                            # net48, net7.0-windows, net7.0
dotnet test  [PluginName].Tests/[PluginName].Tests.csproj   # builder logic, no Rhino needed
```

This plugin was generated with the **PleaseREST** Claude Code plugin (`please-rest` v[version]); `CLAUDE.md` holds the build state and design notes.
<!-- pr:end requirements -->

<!-- pr:begin license -->
## License

[PluginName] is released under the MIT License — Copyright (c) [year] [AuthorName]. See [LICENSE](LICENSE).
<!-- pr:end license -->
```

### The "What you can do with it" section is not optional

It is the only part of the README a first-time reader actually decides on, and it is the one part
that cannot be derived from `plugin-spec.json` alone. Write it from the **confirmed target
workflows** (`plugin-spec.json`'s `workflows` / the Step-0 list `pr-spec` got approved at Gate 2) —
the same source `docs/workflows.md` uses — phrased as outcomes in the user's domain, not component
names:

- ✅ "Schedules and results tables — a Grasshopper data tree becomes a [Platform] table; cells can
  be coloured by value for pass/fail checks."
- ❌ "Exposes the `batchUpdate` endpoint with an `insertTable` request builder."

Three to five bullets. Never invent a capability that isn't backed by a real component. If Phase 12
was degraded and there are no demos, the bullets still stand — they come from the spec, not the
`.gh` files — and `docs/workflows.md` carries the same list.

**Under the hood** is for the one or two non-obvious mechanics a user must know to wire the plugin
at all (an index-free placement hub, a style-chaining rule, one-write-per-button). It is not a
feature list; three bullets maximum, or omit the block entirely.

`[PluginIcon].png` is the plugin logo already at the repo root (the source PNG `pr-icons` rendered
for the ribbon, not the 16×16). If no logo exists, drop the `<img>`/`<br clear="left">` pair rather
than linking a file that isn't there.

---

## CLAUDE.md

Produced from the header block defined in spec Section 4.1. Regenerated every phase — **inside the
markers only** (see above); user notes added outside them survive.

Structure (one `pr:begin`/`pr:end` pair per numbered section):
1. Header block (spec Section 4.1 verbatim format) — skills, agents, MCPs, commands
2. Current build state — phase, last completed step, next step, last active timestamp
3. Platform context — base URL, auth method, API version, extra headers, resource hierarchy
4. Plugin structure — subcategory overview, full component list with I/O
5. JSON builders — which file covers which resources, which components use each builder
6. Key design decisions — anything non-obvious about this plugin's approach
7. Known limitations — skipped endpoints with reason
8. Todo list — current `spec/todo.md` embedded in full

---

## LICENSE

```
MIT License

Copyright (c) [year] [AuthorName]

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## .gitignore

```
bin/
obj/
.vs/
*.user
*.DS_Store
dist/
.env
*.local
dogfood/
demos/
.claude/
settings.local.json
```

**The bottom four lines are the ones that matter, and they must be in place before the first
commit** — once a file is tracked, adding it to `.gitignore` does nothing:

| Line | Why it never goes to GitHub |
|---|---|
| `dogfood/` | The internal findings log — bug write-ups, dead ends, half-finished reasoning, sometimes IDs and document names from the user's own test workspace. It is PleaseREST's build record, not the plugin's. |
| `.claude/` | `settings.local.json` (pre-approved tool permissions — machine-specific and a footgun for anyone who clones), plus scheduled-task locks and other local Claude Code state. |
| `settings.local.json` | Catches the stray root-level copy that pre-1.0.0 builds wrote (see CHANGELOG) and any copy elsewhere in the tree. |
| `demos/` | The `.gh` canvases are user-owned working files that point at the user's own seed documents and often carry a pasted token in a panel. The *documentation* of each demo ships as `docs/examples/*.md`; the binary canvas does not. |

If the user wants the demo canvases published (token panels cleared first), remove `demos/` — it's
the one line here that's a preference rather than a rule. The other three are not negotiable.

`bin/`, `obj/`, `dist/` are build output: `dist/` in particular is rebuilt by CI on every tag, so
committing `.yak`/`.zip` files only creates a second, staler copy of the Release assets.

### `spec/` is tracked, deliberately — say what that means out loud

`spec/` is **not** ignored. All seven files ship: `intake.json`, `feasibility.json`,
`plugin-spec.json`, `call-library.json`, `call-library-validated.json`, `session.json`, `todo.md`.
That is what makes a clone resumable — `/rest-resume-plugin` reads `spec/session.json`, and
`plugin-spec.json` is the most complete description of the plugin that exists.

It also publishes things the user may not have pictured, so **tell them once, before the first
push, rather than assuming**:

- `call-library-validated.json` holds **real response bodies** captured from their test workspace —
  document/board/sheet titles, IDs, and whatever else the API echoed back (truncated to 2000 chars
  each, but real).
- `session.json` holds seed IDs (`test_seed_doc_id`, `decisions.seed_ids`) and the full decision
  log, including anything said at a gate.
- Neither ever contains the token — `pr-api-tester` never writes it to any output file. This is
  about *identifiers and content*, not credentials.

If any of that shouldn't be public, the fix is per-file, not a blanket ignore: scrub the seed IDs,
or add `spec/call-library-validated.json` to `.gitignore` and note in `CLAUDE.md` that a clone will
need `/rest-test-api` re-run. Whatever is decided, record it in
`session.json.decisions.manual_fixes` so the next round doesn't re-litigate it.

**Verify before the first push,** not after:

```
git status --porcelain | grep -E "^\?\? (dogfood|demos|\.claude)/|settings\.local\.json"   # must be empty
git ls-files | grep -E "^(dogfood|demos|\.claude)/|settings\.local\.json"                  # must be empty
```

If the second one returns anything, the file is already tracked: `git rm -r --cached <path>` and
commit that before pushing.

---

## Publish to GitHub

The last step of Phase 14, and the one that makes the phase real. Do it after the four files are
written and the `.gitignore` check above passes.

1. **Org.** `session.json.github_org` (the same value `pr-docs` and `pr-yak-package` use). If it's
   absent, ask once and write it.
2. **Repo name** is the plugin name verbatim — `[GitHubOrg]/[PluginName]`.
3. **Public or private** — ask; never assume. Default to public for a plugin headed for
   Food4Rhino, but a plugin that wraps an internal API may not be publishable at all.
4. **Create, commit, push:**

```
git init -b main                       # skip if already a repo
git add .
git status --short                     # read this — it is the last chance to catch an ignored-too-late file
git commit -m "Initial commit — [PluginName] [version], generated with PleaseREST"
gh repo create [GitHubOrg]/[PluginName] --public --source=. --remote=origin --push
```

   `gh` not installed or not authenticated → don't improvise a token flow. Tell the user to run
   `gh auth login`, or to create the repo in the browser and hand back the URL, then:
   `git remote add origin <url> && git push -u origin main`.

5. **Confirm and record.** `git remote -v` and `git log --oneline -1` must both return something.
   Then write `session.json`:

```json
"github": {
  "repo": "[GitHubOrg]/[PluginName]",
  "url": "https://github.com/[GitHubOrg]/[PluginName]",
  "visibility": "public",
  "pushed_at": "2026-09-16T14:02:00",
  "workflows": [],
  "released_tags": []
}
```

   …and append `14` to `completed_phases`. `workflows` stays empty here — Phase 15
   (`/rest-package`) writes `build.yml` and `publish.yml`, commits them, and fills that list. The
   first tag push is the user's move after Gate 7.

**A tagged release is not part of Phase 14.** `git tag v1.0.0 && git push origin v1.0.0` fires
`publish.yml` and produces the six Release assets — do it only after Gate 7 passes, and append the
tag to `github.released_tags` when it does.

---

## Rules

- README component table must have one row per component with its **Tab** — no grouping, no omissions
- README always carries a **"What you can do with it"** section, written from the confirmed target
  workflows and phrased as outcomes; a README that opens straight into the component table is
  incomplete
- CLAUDE.md's generated sections are regenerated (not appended) every time — always reflect current
  session state; text outside the `pr:` markers is the user's and is never touched
- Never overwrite an existing `LICENSE`; never remove lines from an existing `.gitignore`
- `.gitignore` must exclude `dogfood/`, `.claude/` and `settings.local.json` **before the first
  commit** — verify with the two `git` checks above, don't assume
- LICENSE year is the year the plugin was first created (from session.json `started` field); the
  copyright holder and the README byline are `session.json.author.name` — the person running the
  build, never PleaseREST's own author
- Phase 14 isn't complete until the repo exists and `main` is pushed — record it in
  `session.json.github` and append `14` to `completed_phases`
- Never tag a release here — tagging fires `publish.yml`, and that waits for Gate 7
- Do not create marketing copy in README — outcomes the plugin actually delivers, factual only
