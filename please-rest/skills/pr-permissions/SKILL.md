---
name: pr-permissions
description: Generate .claude/settings.local.json in the generated plugin at Phase 1 intake to pre-approve every command the PleaseREST pipeline needs
---

# Skill: Permissions

Generate the `.claude/settings.local.json` for a generated plugin during Phase 1 intake —
before anything else runs. One approval at intake; nothing interrupts the pipeline after that.

The file is generated fresh per plugin, not copied from a template, so it only includes
what this specific pipeline needs. It lives at **`[PluginName]/.claude/settings.local.json`** —
inside the generated plugin folder's `.claude/` directory, which is the only place Claude Code
reads project-local settings from. A `settings.local.json` at the plugin **root** is silently
ignored (every command then prompts, and the whole point of this skill is lost). Never write it
inside the PleaseREST plugin folder.

---

## When it runs

Phase 1, immediately after the intake questions are answered — before discovery,
extraction, or any code. Claude Code picks the file up automatically once written.

---

## What the user sees first

Show this summary and wait for confirmation before writing the file:

```
PleaseREST — generating .claude/settings.local.json
────────────────────────────────────────
Pre-approving all pipeline commands for this build.

dotnet (new / restore / build / test / run / pack / publish / clean / format / add / nuget / tool / msbuild / …)
msbuild · nuget · yak (build / push)
git (ALL subcommands) · gh (GitHub CLI — releases / PRs)
powershell (icon injection into Resources.resx)
python / pip (MCP servers)
file ops (mkdir / cp / mv / rm / echo / cat / ls)
All 3 MCP servers — every tool (pr-api-extractor, pr-api-tester, pr-icon-generator)

Review the full list in .claude/settings.local.json before continuing.
Confirm to start pipeline? (yes / review first)
────────────────────────────────────────
```

---

## Generated .claude/settings.local.json

```json
{
  "permissions": {
    "allow": [

      "Bash(dotnet new:*)",
      "Bash(dotnet restore:*)",
      "Bash(dotnet build:*)",
      "Bash(dotnet test:*)",
      "Bash(dotnet run:*)",
      "Bash(dotnet pack:*)",
      "Bash(dotnet publish:*)",
      "Bash(dotnet clean:*)",
      "Bash(dotnet format:*)",
      "Bash(dotnet add:*)",
      "Bash(dotnet remove:*)",
      "Bash(dotnet list:*)",
      "Bash(dotnet sln:*)",
      "Bash(dotnet nuget:*)",
      "Bash(dotnet tool:*)",
      "Bash(dotnet msbuild:*)",
      "Bash(dotnet vstest:*)",
      "Bash(dotnet --info)",
      "Bash(dotnet --version)",

      "Bash(msbuild:*)",
      "Bash(nuget:*)",

      "Bash(yak:*)",

      "Bash(git:*)",
      "Bash(gh:*)",

      "Bash(python *)",
      "Bash(pip:*)",

      "Bash(powershell -NonInteractive -Command:*)",
      "Bash(powershell -Command:*)",

      "Bash(claude mcp list)",

      "Bash(mkdir:*)",
      "Bash(cp:*)",
      "Bash(mv:*)",
      "Bash(rm:*)",
      "Bash(echo:*)",
      "Bash(cat:*)",
      "Bash(ls:*)",

      "mcp__plugin_please-rest_pr-api-extractor__*",
      "mcp__plugin_please-rest_pr-api-tester__*",
      "mcp__plugin_please-rest_pr-icon-generator__*"
    ]
  }
}
```

> **MCP tool names are plugin-scoped.** PleaseREST ships its three MCP servers via
> `plugin.json`, so Claude Code namespaces their tools as
> `mcp__plugin_please-rest_<server>__<tool>` — *not* the bare `mcp__<server>__*`.
> Do **not** add an `enabledMcpServers` / `enabledMcpjsonServers` key: those list
> project `.mcp.json` servers, which PleaseREST does not use. Listing the plugin
> servers there makes Claude Code report them as "not loaded" (it looks for a
> `.mcp.json` that defines them and finds none), while the real plugin servers stay
> loaded under their `mcp__plugin_please-rest_*` names.

---

## Rules

- Generated once per plugin at intake — generated fresh, not copied, so it only lists what this pipeline needs
- Shown in full to the user before approving — the pipeline does not start until they confirm
- Lives at `[PluginName]/.claude/settings.local.json` in the generated plugin folder — never at the
  plugin root (ignored by Claude Code) and never in the PleaseREST plugin folder
- All three MCP servers are granted with the `__*` wildcard — Phase 11 needs `generate_plugin_icon`,
  `list_background_shapes` and `preview_backgrounds` as well as `generate_icon` / `add_to_resources`.
  The wildcard means a new MCP tool never needs a permissions change; naming tools individually
  would have made `/rest-icon-preview` prompt on first use
- MCP tool permissions use the **plugin-scoped** names — `mcp__plugin_please-rest_pr-api-extractor__*`, `mcp__plugin_please-rest_pr-api-tester__*`, `mcp__plugin_please-rest_pr-icon-generator__*` — never the bare `mcp__pr-icon-generator__*` (that name only exists for project `.mcp.json` servers, which PleaseREST does not use) and never a legacy server name carried over from an older PleaseREST version
- Never add `enabledMcpServers` / `enabledMcpjsonServers` — PleaseREST's servers come from `plugin.json`, so listing them under those keys makes Claude Code show them as "not loaded"
- The **Grasshopper MCP bridge** (Phase 12 / extend-loop live test) is an EXTERNAL, user-wired dependency (official `mcneel/RhinoMCP`, or fallback `cordyceps` / `SandMartin` — see `pr-rhino-test`). Do **not** add it to `plugin.json` or hardcode a `mcp__<bridge>__*` permission: the user registers it at runtime via Rhino's `MCPConnect` and its server name is not fixed. The template pre-approves only the read-only status check `Bash(claude mcp list)`; the bridge's own tools are discovered at runtime and will prompt once on first use during the live test (and again after a fresh registration) — that is expected, not a gap.
- Custom AEC feature needs a new command: append it to `.claude/settings.local.json`, then ask the user to re-approve before continuing (the `pr-session` skill triggers this)
- `Bash(git:*)` is intentionally broad — it covers every git subcommand, **including history-rewriting / destructive ones** (`reset --hard`, `clean -fd`, `push --force`, `rebase`). It is auto-approved only because the whole file is shown to the user for review at intake. If a build must NOT allow destructive git, narrow it to the explicit safe set (`git add:*`, `git commit:*`, `git push:*`, `git tag:*`, `git status`, `git log:*`, `git fetch:*`, `git pull:*`, `git checkout:*`, `git switch:*`, `git branch:*`) before approving. Same goes for `Bash(dotnet:*)`-style breadth if you ever collapse the enumerated dotnet list.
- Never auto-approve destructive commands without explicit user review — DELETE endpoints in pr-api-tester are `skip_destructive=True` for the same reason
