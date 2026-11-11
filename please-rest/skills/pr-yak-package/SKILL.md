---
name: pr-yak-package
description: Build .yak packages for all 3 targets for a generated Grasshopper REST API plugin
---

# Skill: Yak packager

Build `.yak` files for Rh7 Win, Rh8 Win, and Rh8 Mac. Output to `dist/` (relative to the plugin
root — never `/dist/`).

---

## Locate yak first

`yak` is **not** on PATH — Rhino installs it but does not register it. Probe, in order, and use the
first hit (stop with a clear message if none):

```
Windows:  C:\Program Files\Rhino 9\System\Yak.exe
          C:\Program Files\Rhino 8\System\Yak.exe
          C:\Program Files\Rhino 7\System\Yak.exe
macOS:    /Applications/Rhino 9.app/Contents/Resources/bin/yak
          /Applications/Rhino 8.app/Contents/Resources/bin/yak
          /Applications/Rhino 7.app/Contents/Resources/bin/yak
fallback: `yak` on PATH (user added it)
```

**Rhino 9.** Any of these yaks builds all three packages — the `rh7_0` / `rh8_0` tag comes from the
Grasshopper reference the `.gha` was compiled against, not from the Rhino that owns the yak
(verified: Rhino 9.1's yak 0.19 names the `net7.0` build `*-rh8_0-mac.yak`). There is **no separate
`rh9_0` package**: a distribution tag is a minimum version, so Rhino 9 installs the `rh8_0-win` /
`rh8_0-mac` packages, and Grasshopper 9 picks up the unpacked folder under
`packages/9.0/<name>/<version>/` as an assembly folder.

Refer to it as `$YAK` below. If nothing is found: stop and tell the user where yak normally lives
and that Rhino 7+ must be installed on the packaging machine (or run `/rest-package` on a machine
that has it / let CI do it — see `pr-ci-template`).

---

## Sequence

All three targets are built and packaged **separately** — `yak build` produces **one** `.yak` per run
from the folder it is run in, so the Rhino 8 Windows and Mac packages need their own builds:

```
0. Write / refresh manifest.yml at the plugin root (see below); the csproj copies it and the
   logo PNG into every output folder on build (pr-vs-project's None/CopyToOutputDirectory items)
1. dotnet build -c Release -f net48            → bin/Release/net48            (Rh7 Windows)
2. cd bin/Release/net48         && $YAK build                    → *-rh7_0-any.yak
3. dotnet build -c Release -f net7.0-windows   → bin/Release/net7.0-windows   (Rh8 Windows)
4. cd bin/Release/net7.0-windows && $YAK build --platform win    → *-rh8_0-win.yak
5. dotnet build -c Release -f net7.0           → bin/Release/net7.0           (Rh8 Mac)
6. cd bin/Release/net7.0        && $YAK build --platform mac     → *-rh8_0-mac.yak
7. Copy the three .yak files to dist/
8. Validate each .yak (checklist below)
```

- `--platform win` / `--platform mac` is what makes the two Rhino 8 packages distinct; without it
  both builds would produce an `-any` package and the second would overwrite the first.
- **Never build `net7.0` and call it "Windows + Mac"** — `net7.0-windows` is the Rhino 8 Windows
  target (WinForms attributes compile in), `net7.0` is Mac-only. Packaging the Mac build as the
  Windows package fails Gate 7.

---

## manifest.yml requirements

`manifest.yml` lives at the **plugin root** next to the `.csproj` and is copied into each output
folder by the csproj (so `yak build` finds it). Generate it if missing; refresh `version` on every run:

```yaml
name: [plugin-name-lowercased]        # AcmeConnect → acmeconnect (see pr-conventions)
version: [csproj <Version> — read it from the .csproj, e.g. 1.0.0]
authors:
  - [AuthorName]                 # session.json.author.name — never a hardcoded person
description: "[one sentence from GH_AssemblyInfo.Description]"
url: https://github.com/[GitHubOrg]/[repo-name]
keywords:
  - grasshopper
  - rhino
  - [platform-name]
  - rest
  - api
icon: [PluginName]Logo.png
```

- `version` **must** be three-part `x.y.z` and **must equal** the csproj `<Version>`. That is the single
  version source: `GH_AssemblyInfo.AssemblyVersion` reads the compiled assembly (see `pr-assembly`),
  so all three agree by construction. Never edit `version` here independently.
- `icon` names a file **in the output folder**. The csproj copies `Icons/[XX]_[PluginName]Logo.png`
  there as `[PluginName]Logo.png` (`Link=` attribute) — keep the two names in step. If the icon is
  missing from `bin/…`, `yak build` fails or ships without an icon.
- `[GitHubOrg]` comes from `session.json` `github_org` when set; otherwise ask once and record it.

---

## Output naming

**yak names the files — do not rename them.** The name encodes the distribution tag Package Manager
matches on:

```
dist/
  [plugin-name]-[version]-rh7_0-any.yak     ← from net48
  [plugin-name]-[version]-rh8_0-win.yak     ← from net7.0-windows  (--platform win)
  [plugin-name]-[version]-rh8_0-mac.yak     ← from net7.0          (--platform mac)
```

(The exact `rh7_0` / `rh8_0` prefix comes from the RhinoCommon/Grasshopper reference version yak
detects in the folder — report what yak printed rather than assuming.)

---

## Validation checklist

Before reporting success, verify each `.yak` (it is a zip — list its contents):
- File exists and is non-zero
- Contains `[PluginName].gha` (and `Newtonsoft.Json.dll`, `System.Resources.Extensions.dll`)
- Contains `manifest.yml` with name, version, authors, description, and the icon file it names
- `version` in the manifest == csproj `<Version>` == `GH_AssemblyInfo.AssemblyVersion` at runtime
- The three files carry three **different** distribution tags (`-any`, `-win`, `-mac`)
- No stray files — and the two kinds have **different** fixes, so check which one you're looking at:
  - **MSBuild outputs** — `[PluginName].pdb`, `[PluginName].deps.json`,
    `[PluginName].runtimeconfig.json`. These are *generated*, not copied, so `<None Remove>` and
    `ExcludeAssets` do nothing to them. Fix: the Release-only `PropertyGroup` in `pr-vs-project`
    (`DebugType none`, `DebugSymbols false`, `GenerateDependencyFile false`,
    `GenerateRuntimeConfigurationFiles false`), then rebuild.
  - **Copied references** — `ref/`, `runtimes/`, and a transitively-copied `RhinoCommon.dll` /
    `Grasshopper.dll`. Fix: `ExcludeAssets="runtime"` on the `PackageReference` / `<None Remove>`.

  Verify by listing `bin/Release/<tfm>` once after the first Release build — a Debug build tells you
  nothing here, and the `.yak` ships whatever is in that folder.

---

## Progress output

```
Restling — packaging [PluginName] [version]...
  yak found: C:\Program Files\Rhino 8\System\Yak.exe
  manifest.yml refreshed (version 1.0.0) ✓
  Building net48 (Rh7 Win)... ✓        yak build... ✓ → [plugin]-1.0.0-rh7_0-any.yak
  Building net7.0-windows (Rh8 Win)... ✓  yak build --platform win... ✓ → [plugin]-1.0.0-rh8_0-win.yak
  Building net7.0 (Rh8 Mac)... ✓       yak build --platform mac... ✓ → [plugin]-1.0.0-rh8_0-mac.yak
  Copying to dist/... ✓
Restling complete. 3 targets packaged.
```

---

## The other half of a release: Libraries-folder zips

`.yak` is only one of the two things a release ships. The other is a plain
`[PluginName]-[version]-rh7-win.zip` / `-rh8-win.zip` / `-rh8-mac.zip` — the `.gha`, the `.dll`s
beside it and an `INSTALL.txt` — for users who install by copying into Grasshopper's Components
Folder, and for the Food4Rhino file download. **CI builds these** (see `pr-ci-template`'s "Build
Libraries-folder zips" step); this skill does not, because they aren't packages and nothing here
validates them.

Build them locally only when the user needs a file to hand over before the first tag is pushed —
same contents, from each `bin/Release/<tfm>` folder, top level only (no `ref/`, no `runtimes/`, no
`manifest.yml`, no `.pdb`), staged outside `bin/` so the `.yak` doesn't end up inside the zip.
Otherwise let the tag do it: a locally-zipped file that differs from the Release asset is worse
than no file.

---

## Publishing (not automated — say so)

This skill **builds** packages; it does not push them. Everything below is a human action taken
after **Gate 7 passes**. There are three separate distribution channels and doing one does not do
the others — walk the user through them explicitly and record what actually happened:

**1. GitHub Release** — `git tag v[version] && git push origin v[version]` fires `publish.yml`,
which produces the six assets (3 `.yak` + 3 install `.zip`). Confirm the run went green: the
Release step is the one that fails last and loudest. Record the tag in
`session.json.github.released_tags`.

**2. Yak / `_PackageManager`** — `yak push` requires an interactive `yak login`, so it is the user's
to run:

```
$YAK login
$YAK push dist/[plugin]-[version]-rh7_0-any.yak
$YAK push dist/[plugin]-[version]-rh8_0-win.yak
$YAK push dist/[plugin]-[version]-rh8_0-mac.yak
```

(`yak push --source https://test.yak.rhino3d.com` first for a dry run against the test server.)
Push **all three** — a plugin listed with only the `rh8_0-win` package is invisible to Rhino 7 and
to Mac users, with no error to tell them why. Record `session.json.published.yak_pushed`.

**3. Food4Rhino listing** — a separate web page on food4rhino.com, not a side effect of either of
the above. What goes on it:

| Field | What to upload / paste |
|---|---|
| Downloads | the three **`.zip`** files from the Release (`-rh7-win`, `-rh8-win`, `-rh8-mac`) — the copy-into-Libraries bundles, not the `.yak` files, which the Package Manager serves instead |
| Image / logo | the large `[XX]_Plugin_Icon.png` (1024 px) rendered by `pr-icons`, not the 16 px ribbon icon |
| Description | the csproj `<Description>` — the same line that is in `manifest.yml` |
| Links | the GitHub repo, the GitHub Release, and `docs/` |
| Version | matches the tag and the csproj `<Version>` |

Record the listing URL in `session.json.published.food4rhino_url`.

**A Mac-untested build must say so** on the listing and in the Release notes if Gate 7 only
covered Windows — silently shipping an untested `-mac` package is how a plugin earns its first
1-star review.

---

## After publishing: the backfill (do not skip this)

The generated README and `docs/index.md` ship with deliberate placeholders — `(pending first
release)`, `_(added once listed on food4rhino.com)_`, `(pre-release)`, `Released: _(…)_` — because
at generation time none of those values exist (`pr-docs` is right to refuse to guess them). The
moment they *do* exist, they are stale, and nothing else in the pipeline comes back for them.
Both dogfooded plugins went live with all of them still unfilled.

So, immediately after step 1/2/3 above, edit and re-push:

| File | Placeholder | Becomes |
|---|---|---|
| `README.md` (`install` block) | `**Food4Rhino:** (pending first release)` | the listing URL |
| `README.md` (`install` block) | `**Yak:** … (pending first release)` | `_PackageManager` → search `[plugin-name]` |
| `docs/index.md` | `**Version:** x.y.z (pre-release)` | `**Version:** x.y.z` |
| `docs/index.md` | `**Food4Rhino:** _(added once listed…)_` | the listing URL |
| `docs/index.md` | `**Released:** _(added at first tagged release)_` | the release date |
| `docs/changelog.md` | — | a dated `x.y.z` entry if the release added anything since the last one |

Then set `session.json.published.backfilled: true`. Only edit the channels that actually went
live: a plugin with a GitHub Release but no Food4Rhino listing keeps that placeholder, correctly.

---

## Rules

- Always build Release, never Debug
- Three builds, three `yak build` runs, three distinct `.yak` files — never two
- Do not modify source files during packaging — packaging is read-only, except refreshing
  `manifest.yml`'s `version` to match the csproj
- If yak is not found in the probe locations, stop and tell the user — do not guess a path
- If a build fails: surface the specific error, fix it via `pr-build`, rerun — do not skip targets
- Never `yak push` from this skill
