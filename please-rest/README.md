# PleaseREST

> *Politely turns any REST API into a Grasshopper plugin — so you can take that much needed rest.*

PleaseREST is a Claude Code plugin that automates the repeatable parts of building a
Grasshopper REST API plugin: API discovery, call extraction, HTTP validation, code
scaffolding, icon generation, tests, packaging, and Food4Rhino/GitHub publish.

> This is the plugin folder's readme. The **[repository readme](../README.md)** is the full
> reference — every command, skill, agent, MCP tool, phase and gate in one page.

**You plan, review, and test. PleaseREST does the rest.**

Install it once, then run `/rest-new-plugin` to drive any REST API through a guided
15-phase pipeline with 7 human review gates.

---

## Install

PleaseREST is a standard Claude Code plugin (manifest at `.claude-plugin/plugin.json`).

**From a marketplace**

```
/plugin marketplace add eesha-on-jupiter/PleaseREST   # this repo — it carries .claude-plugin/marketplace.json
/plugin install please-rest
```

**Local development** — point Claude Code at the plugin folder:

```
claude --plugin-dir /path/to/PleaseREST/please-rest
```

After install, confirm the three MCP servers are connected (they load from `plugin.json`):

```
/mcp
# expect: please-rest → pr-api-extractor, pr-api-tester, pr-icon-generator  (connected)
```

> **Requirements:** Python ≥ 3.10 with `mcp[cli] httpx resvg-py pillow pyyaml beautifulsoup4`
> for the MCP servers (`pip install -r please-rest/mcps/<server>/requirements.txt` for each of the
> three). The servers are launched as **`python`**, so that exact command must resolve to a real
> Python ≥ 3.10 on PATH — on macOS/Linux it is often only `python3`, and on Windows it can hit the
> Microsoft Store stub; both show up as all three servers "not connected"
> (see [troubleshooting](docs/troubleshooting.md)). Also: the .NET SDK 8.x (builds the net48 / net7.0-windows / net7.0 targets) for generated
> plugins; `yak` (ships with Rhino, not on PATH) for Phase 15; and an external Grasshopper MCP
> bridge **only** for the optional Phase 12 live Rhino test
> (see [troubleshooting](docs/troubleshooting.md#grasshopper-mcp-bridge)).
> `/rest-new-plugin` checks all of this in a preflight before intake.

---

## Quick start

```
/rest-new-plugin
```

Answer the intake questions — what you want to call the plugin (any name; no required suffix) and
its 2–3 letter icon prefix, your author name / contact and GitHub org (they go in the generated
plugin, not PleaseREST), the API docs URL, token readiness, and optional sandbox / seed IDs for the
live HTTP tests. PleaseREST then walks the full pipeline, pausing at each gate for
your review. Pre-approvals for the build land in the generated plugin's
`.claude/settings.local.json`, so you approve once at intake. The progress tree
(`Restling`) shows where you are and what's next at every gate; `/rest-status` renders it on
demand. Use `/rest-resume-plugin` to pick a build back up later.

---

## Commands

| Command | What it does |
|---|---|
| `/rest-new-plugin` | Start a new plugin build (full 15-phase pipeline) |
| `/rest-resume-plugin` | Resume from the last session |
| `/rest-gen-spec` | Regenerate `plugin-spec.json` from `feasibility.json` |
| `/rest-gen-todo` | Regenerate `todo.md` from `plugin-spec.json` |
| `/rest-extract-api` | Re-run API extraction manually |
| `/rest-test-api` | Re-run HTTP validation manually |
| `/rest-build-component <id>` | Scaffold one component by ID |
| `/rest-build-all-components` | Build all unbuilt components in phase order |
| `/rest-add-feature <description>` | Add a component/feature any time — even post-ship (re-enters at Phase 3) |
| `/rest-icon-preview [glyph]` | Render every background shape in each fill style, and pick one |
| `/rest-icons [component]` | Re-render icons from `icons.json` and embed them |
| `/rest-status` | Show the pipeline progress tree on demand |
| `/rest-package` | Validated-calls check, then `.yak` for all 3 targets + both CI workflows |

Full reference: [docs/commands.md](docs/commands.md).

---

## Documentation

- [Overview & concepts](docs/index.md)
- [The pipeline — 15 phases, 7 gates](docs/pipeline.md)
- [Commands reference](docs/commands.md)
- [Skills & agents](docs/skills-and-agents.md)
- [MCP servers](docs/mcps.md)
- [Troubleshooting](docs/troubleshooting.md)

---

## What's inside

`13 commands · 25 skills · 3 agents · 3 MCP servers` (+ 1 external Grasshopper MCP bridge for
the live Rhino test). The full design lives in
[`PleaseREST-spec.md`](../PleaseREST-spec.md); contributor notes in
[`CLAUDE.md`](CLAUDE.md); what changed and when in [`CHANGELOG.md`](CHANGELOG.md).

**Author:** Eesha Jain · **Version:** 1.0.0
