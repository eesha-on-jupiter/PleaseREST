---
name: pr-unit-tests
description: xUnit test scaffold for Grasshopper REST API plugins — pure builder-logic tests, net8.0
---

# Skill: Test scaffolder

Produce a small, **concern-based** test project for the generated plugin. Tests target the **pure
logic that can actually run headless** — the static `[Resource]Builders` classes — never one file per
component. This design is forced by what a dogfood run proved unachievable (see "Why builder tests").

## Location & project shape

A single separate test project, sibling to the flat plugin project at the repo root:

```
[PluginName].Tests/
├── [PluginName].Tests.csproj
├── BuilderTests.cs         — each builder method emits the expected JSON shape
└── BulkAssemblyTests.cs    — tree→list bulk-upload assembly (only if the plugin has aggregators)
```

The project targets **plain `net8.0`** and **compiles the builder sources in directly** — it does
**NOT** `ProjectReference` the main plugin. The main output is a windows-only `.gha` that cannot be
referenced by name, and a windows-desktop testhost fails to start in CI (dogfood F7). Pulling the
pure builder `.cs` files into a plain net8.0 assembly sidesteps both.

```xml
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net8.0</TargetFramework>     <!-- plain net8.0, NOT -windows -->
    <IsPackable>false</IsPackable>
    <Nullable>enable</Nullable>
  </PropertyGroup>
  <ItemGroup>
    <PackageReference Include="xunit" Version="2.*" />
    <PackageReference Include="xunit.runner.visualstudio" Version="2.*" />
    <PackageReference Include="Newtonsoft.Json" Version="13.0.3" />
  </ItemGroup>
  <!-- Compile the pure builder sources in directly — no reference to the windows-only .gha -->
  <ItemGroup>
    <Compile Include="..\JSON Builders\**\*.cs" />
  </ItemGroup>
</Project>
```

The main `[PluginName].csproj` still carries its `Compile Remove` for `[PluginName].Tests\**` so its
root-level recursive glob does not pull the test files into the plugin build.

> **Builders must be pure.** For this to compile, `[Resource]Builders` classes use only
> `Newtonsoft.Json` and BCL types — no `Grasshopper` / `RhinoCommon` references. `pr-builders`
> already mandates static, GH-free builders, which is exactly why they are the testable surface.

---

## Why builder tests (and not component tests)

A dogfood run established that the "mock the client + drive `SolveInstance`" approach does not work
as the generated code stands (F6/F7):
- components `new` the client **inside** `SolveInstance` → not injectable → **can't be mocked**
- `SolveInstance` needs a live Grasshopper runtime; `IGH_DataAccess` is **not mockable**
- the windows-only `.gha` can't be referenced from a test project, and the windows testhost won't start

What *did* run clean: pure builder-class tests on a plain net8.0 project. So builders are the suite.

**Component call-shape / error-handling tests are deferred**, not forgotten — they become viable only
if `pr-client` / `pr-component` are changed to **inject** the client (constructor or factory) so it
can be mocked. Until then, do not scaffold them; they cannot pass. If real in-Rhino component tests
are ever wanted, the supported route is McNeel's **`Rhino.Testing`** NuGet (xUnit/NUnit fixtures that
boot Rhino.Inside headless) — a separate, opt-in test project, not this one.

---

## Concerns

### 1 — Builder logic (`BuilderTests.cs`) — primary, always
Proves each static builder method emits the JSON shape the API expects (the shapes validated by
`pr-api-tester`). Pure functions in, JSON strings out — no API, no Grasshopper.

- **Data source:** the builder methods listed in `plugin-spec.json` `builders[]`, cross-checked
  against `spec/call-library-validated.json` `body_schema` / `example_request`. `[Theory]` +
  `[MemberData]` over the builder catalogue — never one `[Fact]` per component.
- **Assert:** calling `[Resource]Builders.[Method](args)` returns JSON whose structure matches the
  validated body (required keys present, value types correct, `Formatting.None`).
- Include null/empty input cases — builders null-coalesce strings, so they must not throw.

### 2 — Bulk assembly (`BulkAssemblyTests.cs`) — only if the plugin has aggregators
Proves the **tree → list bulk-upload assembly** is correct. Per `pr-bulk-data`, this logic lives in a
**pure builder method** (e.g. `[Resource]Builders.AssembleRecords(fields, recordValues)`), so it is
unit-testable without Grasshopper — the component only adapts the GH tree to/from plain lists.

- **Data source:** the `aggregator` components from `plugin-spec.json`. `[Theory]` + `[MemberData]`.
- **Assert** the assembly behaviour from `pr-bulk-data`, calling the pure builder method directly:
  - record count in == payload count out (in order)
  - **ragged input** (field count ≠ value count) → uses `Min`, returns a per-record warning, does
    **not** throw and does **not** drop the upload
  - empty/blank value → that pairing skipped with a note, rest of the record still assembled
  - index alignment preserved: outputs the same length as the input, position `i` maps to record `i`
- No `IGH_DataAccess`, no client — the builder method is plain logic.

---

## Pattern — data-driven, pure

```csharp
using System.Collections.Generic;
using Xunit;
using Newtonsoft.Json.Linq;

namespace [PluginName].Tests
{
    public class BuilderTests
    {
        public static IEnumerable<object[]> BuilderCases => TestData.LoadBuilderCases();

        [Theory]
        [MemberData(nameof(BuilderCases))]
        public void Builder_EmitsExpectedShape(BuilderCase c)
        {
            var json = JObject.Parse(c.Invoke());   // call [Resource]Builders.[Method](...)
            foreach (var key in c.RequiredKeys)
                Assert.True(json.ContainsKey(key), $"missing key: {key}");
        }
    }

    public class BulkAssemblyTests
    {
        [Fact]
        public void Assemble_RaggedRecord_UsesMin_AndWarns_NoThrow()
        {
            // arrange — fields=3, one record with 2 values
            // act     — [Resource]Builders.AssembleRecords(fields, records)
            // assert  — 1 payload out, warning present, no exception, index aligned
        }
    }
}
```

A small `TestData` helper loads `plugin-spec.json` + `spec/call-library-validated.json` and builds the
case records — keep it in the test project, one file.

---

## Rules
- **Never one test file per component** — only concern files, driven by `[Theory]` data.
- Primary and always: `BuilderTests.cs`. Add `BulkAssemblyTests.cs` **only when** the spec has
  `aggregator` components. Both test pure logic.
- Test project targets **plain `net8.0`** and **compiles builder sources in** — never a
  `ProjectReference` to the windows-only `.gha`, never a `-windows` target. (dogfood F6/F7)
- Do **not** scaffold component call-shape / error-handling tests unless the client is injectable —
  they cannot pass against the current code shape.
- The test project never validates I/O wiring — that is `pr-spec`'s job at Phase 3.
- The main `.csproj` keeps the `Compile Remove` for `[PluginName].Tests\**`.
