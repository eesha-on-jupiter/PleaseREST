---
name: pr-vs-project
description: Create the buildable Visual Studio Grasshopper plugin project (Rhino 7 + Rhino 8 Win/Mac) and verify it builds
---

# Skill: VS project

Generate the actual Visual Studio project for a generated plugin, matching the official Grasshopper
plugin template, and **verify it builds for Rhino 7 and Rhino 8** before handing off to component
codegen. `pr-file-structure` lays down the folder tree; this skill produces the buildable project
files inside it.

## Files this skill produces

```
[PluginName].csproj            multi-target: Rh7 (net48), Rh8 Win (net7.0-windows), Rh8 Mac (net7.0)
[PluginName].sln               references the main project + [PluginName].Tests project
[PluginName].csproj.user       default debug profile
[PluginName]Info.cs            GH_AssemblyInfo + GH_AssemblyPriority (category icon)
Properties/
  ├── launchSettings.json      Rhino 7 / Rhino 8 (netcore + netfx) run profiles
  ├── Resources.resx           seeded with a placeholder [XX]_[PluginName]Logo bitmap (see below)
  └── Resources.Designer.cs    generated designer, namespace [PluginName].Properties
```

**Resources namespace + placeholder logo (dogfood F5/F6).** Two scaffold-time requirements so the
project compiles before icons exist:
- `Resources.Designer.cs` must be in the **`[PluginName].Properties`** namespace (the McNeel template
  default). All resource references in the plugin are `Properties.Resources.[XX]_<Name>` to match —
  `pr-assembly` for the category icon, `pr-component` for component icons.
- `[PluginName]Info.cs` references `Properties.Resources.[XX]_[PluginName]Logo` for the category icon,
  but the real logo isn't rendered until Phase 11. Seed a **placeholder** `[XX]_[PluginName]Logo`
  bitmap resource (any 1×1 PNG) into `Resources.resx` now so the project builds; Phase 11's
  `add_to_resources("[PluginName]Logo", …)` overwrites this exact key with the rendered 16×16 icon.

## Preferred path — use the official template

If McNeel's templates are available, generate from them and then rename — this guarantees the csproj
tracks the current Grasshopper template:

```
dotnet new install Rhino.Templates      # once, if not already installed
dotnet new grasshopper --name [PluginName]
```

Then apply the **renaming rules** below. If the template is not installed and cannot be installed,
fall back to writing the files directly from the template in this skill.

---

## [PluginName].csproj template

Targets are the three real Grasshopper frameworks. **Rhino 7 = `net48`**, **Rhino 8 Windows =
`net7.0-windows`**, **Rhino 8 Mac = `net7.0`**. Output extension is `.gha`, dynamic loading on.

> verify: Rhino 8.20+ runs on the .NET 8 runtime and McNeel's current template targets `net8.0`;
> `net7.0` assemblies still load there via roll-forward, so these TFMs work but are not the newest.
> Moving to `net8.0-windows;net8.0;net48` is a deliberate, separate change (also bumps the
> `Grasshopper` NuGet floor and `System.Drawing.Common`) — do not do it ad hoc inside a build.

> **Rhino 9 needs no fourth target.** Rhino 9 runs on .NET 10 and loads the Rhino 8 builds by
> roll-forward: `net7.0-windows` on Windows, `net7.0` on Mac. Verified on Rhino 9.1 Mac (.NET 10.0.2)
> with this exact csproj: the `.gha` loads, preserialized Bitmap resources resolve (assembly icon,
> category icon, component icons), `ButtonComponent`'s custom attributes render and fire, and
> `HttpClient` + Newtonsoft.Json calls return. Keep the `Grasshopper` 8.0 NuGet floor — referencing
> the 9.x package would lock Rhino 8 out for no gain.
>
> **SDK.** .NET SDK 8.x is the documented baseline; SDK 10.x also builds all three TFMs clean
> (0 warnings), on macOS included — a machine with only SDK 10 does not need SDK 8 installed.

```xml
<Project Sdk="Microsoft.NET.Sdk">

  <PropertyGroup>
    <!-- Rhino 7: net48 | Rhino 8 Windows: net7.0-windows | Rhino 8 Mac: net7.0 -->
    <TargetFrameworks>net7.0-windows;net7.0;net48</TargetFrameworks>
    <EnableDynamicLoading>true</EnableDynamicLoading>
    <TargetExt>.gha</TargetExt>
    <!-- CA1416: System.Drawing / WinForms platform-compat warnings on the net7.0 (Mac) target are
         expected and unavoidable for a GH plugin — suppressed so pr-build's "0 warnings" gate is
         meaningful. Do not add other codes here without a reason comment. -->
    <NoWarn>$(NoWarn);NU1701;NETSDK1086;CA1416</NoWarn>
    <EnableWindowsTargeting>true</EnableWindowsTargeting>
    <!-- A Bitmap (icon) resource in Resources.resx requires preserialized resources to build on
         net48 (Rhino 7) AND net7.0 (Rhino 8 Mac). net7.0-windows gets this transitively via WinForms,
         which is why an empty-resx Phase-8 build passes and the failure only appears once the first
         icon lands at Phase 9/11. Set it for all targets up front. (dogfood F4) -->
    <GenerateResourceUsePreserializedResources>true</GenerateResourceUsePreserializedResources>
  </PropertyGroup>

  <PropertyGroup>
    <!-- Assembly + Yak metadata. <Version> is THE version: GH_AssemblyInfo.AssemblyVersion reads it
         from the compiled assembly (pr-assembly), manifest.yml copies it (pr-yak-package), and CI
         overrides it from the git tag with `dotnet build -p:Version=x.y.z` (pr-ci-template).
         Always three parts — yak requires x.y.z. -->
    <Version>1.0.0</Version>
    <Title>[PluginName]</Title>
    <Company>[PluginName] Authors</Company>
    <!-- This string is the plugin's public blurb: pr-yak-package copies it into manifest.yml's
         `description`, which is what Rhino's _PackageManager and the Food4Rhino listing show.
         One line, ends with the PleaseREST attribution. -->
    <Description>[one-line plugin description] Built with the PleaseREST Claude Code plugin (please-rest v[version]).</Description>
  </PropertyGroup>

  <!-- Test project lives in a subfolder; keep it out of the main plugin build -->
  <ItemGroup>
    <Compile Remove="[PluginName].Tests\**\*.cs" />
    <EmbeddedResource Remove="[PluginName].Tests\**" />
    <None Remove="[PluginName].Tests\**" />
  </ItemGroup>

  <!-- Yak packaging: a Release build must leave ONLY what ships in bin/Release/<tfm>, because
       `yak build` packages whatever it finds there. These four are MSBuild *outputs* — they cannot
       be removed with <None Remove> or ExcludeAssets, only by not generating them. Debug builds
       keep their symbols; this is Release-only. -->
  <PropertyGroup Condition="'$(Configuration)' == 'Release'">
    <DebugType>none</DebugType>
    <DebugSymbols>false</DebugSymbols>
    <GenerateDependencyFile>false</GenerateDependencyFile>
    <GenerateRuntimeConfigurationFiles>false</GenerateRuntimeConfigurationFiles>
  </PropertyGroup>

  <!-- Yak packaging inputs: `yak build` packages the CONTENTS of the output folder and needs
       manifest.yml (and the icon it names) to be sitting there. Copying them on every build means
       pr-yak-package and CI never have to hand-place files into bin/. manifest.yml lives at the
       project root (pr-yak-package writes it); the 16x16 logo is the one pr-icons renders. -->
  <ItemGroup>
    <None Include="manifest.yml" CopyToOutputDirectory="PreserveNewest" Condition="Exists('manifest.yml')" />
    <None Include="Icons\[XX]_[PluginName]Logo.png" Link="[PluginName]Logo.png" CopyToOutputDirectory="PreserveNewest" Condition="Exists('Icons\[XX]_[PluginName]Logo.png')" />
  </ItemGroup>

  <ItemGroup>
    <PackageReference Include="Grasshopper" Version="7.0.20314.3001" Condition="$(TargetFramework) == 'net48'" ExcludeAssets="runtime" />
    <PackageReference Include="Grasshopper" Version="8.0.23304.9001" Condition="!$(TargetFramework.StartsWith('net4'))" ExcludeAssets="runtime" />
    <PackageReference Include="Newtonsoft.Json" Version="13.0.3" />
    <!-- Runtime support for the preserialized Bitmap resources above; required on net48 + net7.0
         Mac when Resources.resx holds any icon. (dogfood F4) -->
    <PackageReference Include="System.Resources.Extensions" Version="8.0.0" />
  </ItemGroup>

  <!-- net48 (Rhino 7): the System.Net.Http facade is NOT auto-referenced in an SDK-style net48
       project, but [Plugin]Client.cs uses HttpClient/HttpRequestMessage/HttpMethod. Without this the
       net48 target fails with CS1069. (dogfood F3) -->
  <ItemGroup Condition="$(TargetFramework) == 'net48'">
    <Reference Include="System.Net.Http" />
  </ItemGroup>

  <!-- Windows-only builds (Rh7 net48 + Rh8 net7.0-windows) -->
  <PropertyGroup Condition="$(TargetFramework.Contains('-windows')) or $(TargetFramework.StartsWith('net4'))">
    <UseWindowsForms>true</UseWindowsForms>
  </PropertyGroup>

  <!-- WinForms for .NET 7.0 on macOS (Rh8 Mac) -->
  <ItemGroup Condition="!($(TargetFramework.Contains('-windows')) or $(TargetFramework.StartsWith('net4')))">
    <PackageReference Include="Microsoft.NETFramework.ReferenceAssemblies.net48" Version="1.0.3" ExcludeAssets="all" GeneratePathProperty="true" />
    <Reference Include="$(PkgMicrosoft_NETFramework_ReferenceAssemblies_net48)\build\.NETFramework\v4.8\System.Windows.Forms.dll" Private="False" />
    <PackageReference Include="System.Drawing.Common" Version="7.0.0" ExcludeAssets="runtime" />
  </ItemGroup>

  <ItemGroup>
    <Compile Update="Properties\Resources.Designer.cs">
      <DesignTime>True</DesignTime>
      <AutoGen>True</AutoGen>
      <DependentUpon>Resources.resx</DependentUpon>
    </Compile>
    <EmbeddedResource Update="Properties\Resources.resx">
      <Generator>ResXFileCodeGenerator</Generator>
      <LastGenOutput>Resources.Designer.cs</LastGenOutput>
    </EmbeddedResource>
  </ItemGroup>

  <!-- Enable debugging in Rhino 7 on Mac -->
  <Target Name="CopyPdbForMonoDebugging" AfterTargets="AfterBuild">
    <Copy SourceFiles="$(TargetDir)$(TargetName).pdb" DestinationFiles="$(TargetDir)$(TargetName).gha.pdb"
          Condition="$([MSBuild]::IsOSPlatform(OSX)) and $(TargetFramework.StartsWith('net4')) and Exists('$(TargetDir)$(TargetName).pdb')" />
  </Target>

</Project>
```

## Properties/launchSettings.json

Run profiles for Rhino 7 and Rhino 8 (both netcore and netfx). Adjust the Rhino install paths if the
machine differs.

```json
{
  "profiles": {
    "Rhino 8 - netcore": {
      "commandName": "Executable",
      "executablePath": "C:\\Program Files\\Rhino 8\\System\\Rhino.exe",
      "commandLineArgs": "/netcore /runscript=\"_Grasshopper\"",
      "environmentVariables": { "RHINO_PACKAGE_DIRS": "$(ProjectDir)$(OutputPath)\\" }
    },
    "Rhino 8 - netfx": {
      "commandName": "Executable",
      "executablePath": "C:\\Program Files\\Rhino 8\\System\\Rhino.exe",
      "commandLineArgs": "/netfx /runscript=\"_Grasshopper\"",
      "environmentVariables": { "RHINO_PACKAGE_DIRS": "$(ProjectDir)$(OutputPath)\\" }
    },
    "Rhino 7": {
      "commandName": "Executable",
      "executablePath": "C:\\Program Files\\Rhino 7\\System\\Rhino.exe",
      "commandLineArgs": "/runscript=\"_Grasshopper\""
    }
  }
}
```

## [PluginName]Info.cs

Two classes in the root namespace — see the `pr-assembly` skill for the full rules. Generate a fresh
GUID for `Id` (never reuse a template GUID). `AuthorName` and `AuthorContact` come from
`session.json.author` — the user building the plugin, captured at Phase 1 intake; never a hardcoded
person. `AssemblyVersion` is **not** a literal — it reads the compiled assembly version
(`GetType().Assembly.GetName().Version.ToString(3)`), which comes from the `.csproj` `<Version>`.

## [PluginName].sln

A solution that references both the main project and `[PluginName].Tests\[PluginName].Tests.csproj`,
with `Debug|Any CPU` and `Release|Any CPU` configurations. Generate fresh project + solution GUIDs.

---

## Renaming rules (when generated from the template)

- Replace the template plugin name everywhere: `.csproj` (`Title`, `Company`), all `namespace`
  declarations, `[PluginName]Info.cs` class names and `GH_AssemblyInfo` fields
- Generate a fresh GUID for `GH_AssemblyInfo.Id` — never reuse the template's
- Set `AuthorName` / `AuthorContact` as above; make `AssemblyVersion` read the assembly version
- Add the `<NoWarn>` CA1416 entry, the three-part `<Version>`, and the manifest/logo copy `ItemGroup`
  from the template above — the McNeel template has none of them

---

## Build check — verify Rhino 7 and Rhino 8

This is the gate of the skill. After generating the project, build each target and confirm both
Rhino lines compile before any component code is written:

```
dotnet restore
dotnet build -c Debug -f net48            # Rhino 7
dotnet build -c Debug -f net7.0-windows   # Rhino 8 Windows
dotnet build -c Debug -f net7.0           # Rhino 8 Mac  (build-checks the Mac target on any OS)
```

- Print `Restling — building [PluginName] for Rhino 7 (net48)...` etc. per target
- A fresh project must build clean on `net48` and `net7.0-windows`. If either fails, surface the
  compile error with file + line and fix before continuing — do not proceed to component codegen on a
  project that does not build
- Because the resx is seeded with the placeholder `[XX]_[PluginName]Logo` **bitmap** (not empty), this
  gate now exercises the preserialized-resource path (`GenerateResourceUsePreserializedResources` +
  `System.Resources.Extensions`) on `net48` and `net7.0` up front — catching dogfood F4 at Phase 8
  instead of mid-Phase-11
- The `net7.0` (Mac) target build-checks on Windows via `EnableWindowsTargeting`; a full Mac runtime
  test is Human Gate 7, not this skill. On macOS it is the other way round: all three targets build
  (`net48` via the reference-assemblies package, `net7.0-windows` via `EnableWindowsTargeting`), and
  `net7.0` is the one the local Rhino 8 / 9 loads
- Report a short matrix:

```
Build check
  Rhino 7  (net48)            ✓
  Rhino 8  (net7.0-windows)   ✓
  Rhino 8 Mac (net7.0)        ✓  (compile-only on Windows)
```

---

## Rules

- Run during Phase 8, immediately after `pr-file-structure` creates the folder tree
- Project files always at the plugin **root** (flat layout) — never under `src/`
- The main `.csproj` must keep the `Compile Remove` for `[PluginName].Tests\**` so its recursive
  glob does not pull in the test project
- Always finish with the build check — a generated plugin must build for Rhino 7 and Rhino 8 before
  components are added
