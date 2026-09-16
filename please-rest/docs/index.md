# PleaseREST — Overview

PleaseREST turns any REST API into a [Grasshopper](https://www.grasshopper3d.com/) plugin by
automating the repeatable engineering, and keeping a human in the loop for every decision that
matters. It is a Claude Code plugin: a set of slash commands, skills, agents, and MCP servers
that together drive a guided build pipeline.

## What it produces

A complete, buildable Grasshopper REST API plugin:

- A typed API **client** built *from validated HTTP calls* (never hand-written from docs).
- One **`GH_Component`** per endpoint, organised into subcategories, with proper I/O wiring.
- **Write components** (create/update/delete) as button-triggered components.
- **Builders** — pure JSON builder classes that hold the payload/assembly logic (and are the
  unit-test surface).
- **Icons** — 24×24 component icons + a 16×16 plugin/ribbon icon, rendered from Iconify glyphs.
- **Tests** — xUnit builder-logic tests, plus optional live Rhino testing of demo `.gh` files.
- **Docs** — a portable `docs/` folder of markdown for the generated plugin.
- **Packages** — `.yak` for all three Rhino targets, plus a GitHub Actions publish workflow.

## The shape of a run

1. You start with `/rest-new-plugin` and answer a few intake questions.
2. PleaseREST runs **15 phases** with **7 human gates** — it stops at each gate so you can
   review and approve before it proceeds. See [the pipeline](pipeline.md).
3. State is persisted in `spec/session.json`, so you can stop and `/rest-resume-plugin` any
   time.
4. After the live-test gate, PleaseREST offers to **add more components or workflows** and
   loops them through the full build before docs and packaging.
5. You finish with three `.yak` packages and a CI workflow ready to publish.

**Active-state verb:** every progress line uses `Restling` (e.g. *"Restling… Phase 7 of 15"*).

## Design principles

- **Human gates over autopilot.** Seven explicit review points; nothing irreversible happens
  without your approval. The progress tree shows where you are and what to do at each gate.
- **Build from validated calls.** Phases 6–7 (extract → test real HTTP) are mandatory; the
  client and components are generated from `call-library-validated.json`, never from reading
  the docs and guessing.
- **Resumable.** Every phase, gate, and file write updates `session.json` so a build survives
  across sessions and machines.
- **Honest logging.** A dogfood findings log records tool defects vs. target-API issues at
  every phase and failure.
- **Workflow-first, not endpoint-first.** Phase 3 proposes what a user should be able to *do*
  with the plugin before proposing any component — components are derived from that list, not a
  1:1 mapping of every API endpoint.
- **Never stale without saying so.** Resuming a build compares it against PleaseREST's current
  version; if logic it already used has since changed, it says so before you continue.

## Key files in a generated plugin's `spec/` folder

| File | Written by | Purpose |
|---|---|---|
| `intake.json` | Phase 1 | Plugin name, docs URL, token readiness, optional seed IDs |
| `feasibility.json` | Phase 2 | API map: endpoints, auth, hierarchy, base URL |
| `workflows.json` | Phase 3 (Step 0) | Grounded target workflows, confirmed with you, that `plugin-spec.json` is derived from |
| `plugin-spec.json` | Phase 3 | Component list, subcategories, I/O, AEC features |
| `todo.md` | Phase 5 | Build checklist in phase order |
| `call-library.json` | Phase 6 | Extracted endpoint call definitions (`auth_in`, `body_required`, `content_type` per entry) |
| `call-library-validated.json` | Phase 7 | The same calls, after real HTTP validation (`test_result.tag` / `error_body`) |
| `*.prev.json` | re-runs | Previous call libraries, kept by `/rest-extract-api` / `/rest-test-api` before overwriting |
| `session.json` | every phase | Persistent build state (drives resume + progress tree) |

The generated plugin's Claude Code pre-approvals live at `[PluginName]/.claude/settings.local.json`.

## Next

- [The pipeline — 15 phases, 7 gates](pipeline.md)
- [Commands reference](commands.md)
- [Skills & agents](skills-and-agents.md)
- [MCP servers](mcps.md)
- [Troubleshooting](troubleshooting.md)
