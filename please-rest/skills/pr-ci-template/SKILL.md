---
name: pr-ci-template
description: Generate .github/workflows/publish.yml and build.yml for a generated Grasshopper REST API plugin
---

# Skill: CI template

Generate the generated plugin's two GitHub Actions workflows:

| File | Trigger | Does |
|---|---|---|
| `.github/workflows/build.yml` | pull request → `main` | restore, build all three targets, run the tests. Nothing is packaged or published. |
| `.github/workflows/publish.yml` | push of a `v*.*.*` tag | build + test, then **three `.yak` packages and three Libraries-folder `.zip` files**, attached to a GitHub Release. |

Both mirror `pr-yak-package` exactly. Paths are the **flat layout** from `pr-file-structure` — the
`.csproj` sits at the repo root and the test project in `[PluginName].Tests/`. There is no `src/`.

---

## Two release artifacts, not one

The Release carries **six files**, and they are not interchangeable:

- **3 × `.yak`** — the Rhino package-manager format. This is what `_PackageManager` and
  Food4Rhino's package listing install. Built by `yak build` (see `pr-yak-package`).
- **3 × `.zip`** — a plain "copy these files into Grasshopper's Components Folder" bundle: the
  `.gha`, the `.dll`s beside it, and an `INSTALL.txt`. This is the layout uploaded to Food4Rhino as
  a file download, and the only install route for a user who can't or won't use the package
  manager (locked-down IT, Rhino.Inside Revit setups, an older Rhino).

Ship both. A Release with only `.yak` files strands every manual installer; a Release with only
zips is invisible to `_PackageManager`.

---

## publish.yml

**Trigger:** push of a version tag matching `v*.*.*`. The tag **is** the version: it is passed to
every `dotnet build` as `-p:Version=`, which overrides the csproj `<Version>`, flows into
`GH_AssemblyInfo.AssemblyVersion` (reads the assembly), and is written into `manifest.yml` before
packaging — so `v1.1.0` really ships a 1.1.0 assembly and a 1.1.0 package.

**`permissions: contents: write` is required.** `GITHUB_TOKEN` is read-only by default under most
org policies, and without this block the whole workflow goes green and then the *Create GitHub
Release* step fails at the very end with a 403. Never omit it.

```yaml
name: Publish [PluginName]

on:
  push:
    tags:
      - 'v*.*.*'

# GITHUB_TOKEN needs write access to create the Release and upload assets
permissions:
  contents: write

jobs:
  publish:
    runs-on: windows-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup .NET
        uses: actions/setup-dotnet@v4
        with:
          # SDK 8 builds net48, net7.0-windows, net7.0 AND the net8.0 test project.
          # SDK 7 cannot build the test project.
          dotnet-version: '8.x'

      - name: Extract version from tag
        id: version
        run: |
          $tag = "${{ github.ref_name }}"
          $ver = $tag.TrimStart('v')
          if ($ver -notmatch '^\d+\.\d+\.\d+$') { throw "Tag must be vX.Y.Z (yak needs a 3-part version), got '$tag'" }
          echo "VERSION=$ver" >> $env:GITHUB_OUTPUT

      - name: Stamp manifest.yml version
        run: |
          $ver = "${{ steps.version.outputs.VERSION }}"
          (Get-Content manifest.yml) -replace '^version:.*$', "version: $ver" | Set-Content manifest.yml -Encoding utf8
          echo "Restling — manifest.yml version set to $ver"

      - name: Restore
        run: |
          echo "Restling — restoring packages..."
          dotnet restore [PluginName].csproj
          dotnet restore [PluginName].Tests/[PluginName].Tests.csproj

      - name: Build net48 (Rh7 Win)
        run: |
          echo "Restling — building net48..."
          dotnet build [PluginName].csproj -c Release -f net48 --no-restore -p:Version=${{ steps.version.outputs.VERSION }}

      - name: Build net7.0-windows (Rh8 Win)
        run: |
          echo "Restling — building net7.0-windows..."
          dotnet build [PluginName].csproj -c Release -f net7.0-windows --no-restore -p:Version=${{ steps.version.outputs.VERSION }}

      - name: Build net7.0 (Rh8 Mac)
        run: |
          echo "Restling — building net7.0..."
          dotnet build [PluginName].csproj -c Release -f net7.0 --no-restore -p:Version=${{ steps.version.outputs.VERSION }}

      - name: Test (builder tests, net8.0)
        run: |
          echo "Restling — running tests..."
          dotnet test [PluginName].Tests/[PluginName].Tests.csproj -c Release --no-restore

      - name: Install Yak
        run: |
          # verify URL: McNeel's documented standalone download for the yak CLI
          $yakUrl = "https://files.mcneel.com/yak/tools/latest/yak.exe"
          Invoke-WebRequest -Uri $yakUrl -OutFile "$env:RUNNER_TEMP\yak.exe"
          echo "YAK=$env:RUNNER_TEMP\yak.exe" >> $env:GITHUB_ENV

      # manifest.yml + [PluginName]Logo.png are already in each output folder — the csproj copies
      # them on build (pr-vs-project). yak packages the folder it runs in.
      - name: Package net48 (rh7 any)
        working-directory: bin/Release/net48
        run: |
          echo "Restling — packaging net48..."
          & $env:YAK build

      - name: Package net7.0-windows (rh8 win)
        working-directory: bin/Release/net7.0-windows
        run: |
          echo "Restling — packaging net7.0-windows..."
          & $env:YAK build --platform win

      - name: Package net7.0 (rh8 mac)
        working-directory: bin/Release/net7.0
        run: |
          echo "Restling — packaging net7.0..."
          & $env:YAK build --platform mac

      - name: Collect packages
        run: |
          New-Item -ItemType Directory -Force -Path dist | Out-Null
          Get-ChildItem -Path bin/Release -Recurse -Filter *.yak | Copy-Item -Destination dist/
          $count = (Get-ChildItem dist/*.yak).Count
          if ($count -ne 3) { throw "Expected 3 .yak packages, found $count" }
          echo "Restling complete. Packages in dist/:"
          Get-ChildItem dist/

      # Plain "copy into Grasshopper's Components Folder" zips (.gha + DLLs + INSTALL.txt),
      # the same layout uploaded to Food4Rhino.
      - name: Build Libraries-folder zips
        run: |
          $ver = "${{ steps.version.outputs.VERSION }}"
          $note = @"
          [PluginName] $ver — Grasshopper plugin for [Platform]
          https://github.com/[GitHubOrg]/[PluginName]

          Install
            1. In Grasshopper: File > Special Folders > Components Folder
            2. Copy every file from this zip into that folder (keep them together —
               [PluginName].gha needs the .dll files beside it)
            3. If Windows blocked the files: right-click each > Properties > Unblock
            4. Restart Rhino — the [PluginName] tab appears in Grasshopper

          Rhino 8: the plugin needs the .NET Core runtime (Rhino 8's default).
          If the tab is missing, run SetDotNetRuntime, choose .NET Core, restart.

          Docs: https://github.com/[GitHubOrg]/[PluginName]/tree/main/docs
          "@
          $targets = @{ "net48" = "rh7-win"; "net7.0-windows" = "rh8-win"; "net7.0" = "rh8-mac" }
          foreach ($tfm in $targets.Keys) {
            $stage = "$env:RUNNER_TEMP\zip-$tfm"
            New-Item -ItemType Directory -Force -Path $stage | Out-Null
            Get-ChildItem "bin/Release/$tfm" -Include *.gha, *.dll -Recurse -Depth 0 | Copy-Item -Destination $stage
            Set-Content -Path "$stage\INSTALL.txt" -Value $note -Encoding utf8
            Compress-Archive -Path "$stage\*" -DestinationPath "dist/[PluginName]-$ver-$($targets[$tfm]).zip" -Force
          }
          Get-ChildItem dist/*.zip

      - name: Create GitHub Release
        uses: softprops/action-gh-release@v2
        with:
          files: |
            dist/*.zip
            dist/*.yak
          generate_release_notes: true
          name: "[PluginName] ${{ steps.version.outputs.VERSION }}"
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### The zip step, line by line

- `-Recurse -Depth 0` on `Get-ChildItem` is deliberate — it takes the `.gha` and the `.dll`s in the
  target folder itself and **not** the `ref/`, `runtimes/` or satellite subfolders, which would
  make the zip un-droppable into the Libraries folder.
- Staging happens in `$env:RUNNER_TEMP`, never in `bin/`, so `Compress-Archive` can't sweep up
  `manifest.yml`, `.pdb`, `*.deps.json` or the `.yak` that was just built there.
- `INSTALL.txt` is written **inside** the staging folder before compressing. The here-string is
  PowerShell's `@"…"@`, so `$ver` interpolates; the closing `"@` must start its own line.
- Names are `[PluginName]-[version]-rh7-win.zip` / `-rh8-win.zip` / `-rh8-mac.zip` — hyphens, not
  the `rh8_0` underscores yak uses. Don't try to match yak's naming: these are different artifacts,
  and the distinct names are what tell a user which one they downloaded.
- Substitute the real plugin name, platform and `[GitHubOrg]` (`session.json.github_org`) into
  `$note` when generating — it ships to users as their install instructions.

---

## build.yml

Every PR into `main` builds all three targets and runs the tests. This is what stops a merge that
compiles on the author's machine but not on a clean checkout — a missing
`None`/`CopyToOutputDirectory` item, a file never committed, a Windows-only API that slipped into
the Mac target.

```yaml
name: Build [PluginName]

on:
  pull_request:
    branches:
      - main

jobs:
  build:
    runs-on: windows-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup .NET
        uses: actions/setup-dotnet@v4
        with:
          # SDK 8 builds net48, net7.0-windows, net7.0 AND the net8.0 test project.
          dotnet-version: '8.x'

      - name: Restore
        run: |
          dotnet restore [PluginName].csproj
          dotnet restore [PluginName].Tests/[PluginName].Tests.csproj

      - name: Build (all targets)
        run: dotnet build [PluginName].csproj -c Release --no-restore

      - name: Test (builder tests, net8.0)
        run: dotnet test [PluginName].Tests/[PluginName].Tests.csproj -c Release --no-restore
```

`dotnet build` with no `-f` builds every TFM in `<TargetFrameworks>` in one step — there is no
version to stamp here, so the three separate build steps `publish.yml` needs are unnecessary.
No `permissions:` block: this workflow writes nothing.

---

## Rules

- **Two files, always** — `build.yml` (PR) and `publish.yml` (tag). Generating only `publish.yml`
  leaves `main` unguarded
- `publish.yml` triggers on tag push only — never on branch push or PR; `build.yml` is PR only
- **`permissions: contents: write` on `publish.yml`** — without it the Release step 403s after a
  fully green build
- Always build Release, never Debug
- **Flat paths** — `[PluginName].csproj` at the root, `[PluginName].Tests/` beside it; never `src/`
- **SDK `8.x`** — it builds every TFM the plugin uses plus the net8.0 test project
- Tests build themselves (no `--no-build`) and run after the plugin builds, before packaging — if
  tests fail, the workflow stops
- Three build steps, three `yak build` steps (`--platform win` / `--platform mac` on the Rhino 8
  pair), and the collect step **fails if it doesn't find exactly three** `.yak` files
- **Six release assets** — `dist/*.yak` *and* `dist/*.zip`, both listed under `files:`
- Version comes from the tag and is applied with `-p:Version=` **and** stamped into `manifest.yml`;
  the csproj `<Version>` is only the local default
- Yak is downloaded fresh per run — do not cache it. (verify the download URL against McNeel's
  current yak docs when generating; if it moves, fall back to a `choco`/Rhino-install step)
- `yak push` is **not** in this workflow — publishing to the McNeel package server is a human step
  after Gate 7 (see `pr-yak-package` "Publishing")
- Restling progress lines appear in the CI log at each step
