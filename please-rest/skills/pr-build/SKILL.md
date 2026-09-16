---
name: pr-build
description: dotnet build + test loop with failure surfacing for Grasshopper REST API plugins
---

# Skill: Build runner

Run `dotnet build` then `dotnet test`. Surface every failure with file + line or test
name + assertion. Fix the specific error using the relevant skill. Rerun. Repeat until
all green. Print Restling progress throughout.

---

## Sequence

```
0. environment check (once per session, before the first build)
   → `dotnet --version` fails            → STOP: .NET SDK 8.x not installed — tell the user, link
                                            https://dotnet.microsoft.com/download; nothing below can run
   → build error NETSDK1045 / MSB3644
     "reference assemblies for net48…"   → STOP: net48 targeting pack missing — the csproj already
                                            pulls Microsoft.NETFramework.ReferenceAssemblies for the
                                            Mac path; on Windows install ".NET Framework 4.8 targeting
                                            pack" (VS Installer) or `dotnet restore` after adding
                                            <PackageReference Include="Microsoft.NETFramework.ReferenceAssemblies" Version="1.0.3" PrivateAssets="all" />
   These are environment faults, not code faults — do NOT enter the fix loop on them.

1. dotnet build            (attempt budget: 5 build↔fix loops)
   → if errors: surface each error with file path and line number
     → identify which component/file caused it
     → load the relevant skill (pr-component, pr-button, pr-builders, pr-client, etc.)
     → fix the specific error
     → rerun dotnet build
     → do not move to tests until build is clean
   → after 5 loops still red: STOP. Print the remaining errors verbatim, which fixes were tried,
     and hand to the user — an unbounded loop on the same error is never acceptable

2. dotnet test             (attempt budget: 5 test↔fix loops, same escalation)
   → if failures: surface each with test name + failing assertion
     → identify which builder the test covers
     → fix the builder or the test (determine which is wrong)
     → rerun dotnet test
     → do not mark phase complete until all tests pass
```

---

## Progress output

```
Restling — building [PluginName]...
  dotnet build... ✓ (or: ✗ 3 errors)
  → [file.cs:42] CS0246: type 'JObject' not found — adding Newtonsoft.Json using
  dotnet build... ✓

Restling — testing [PluginName]...
  dotnet test... ✓ 47 passed (or: ✗ 2 failed)
  → [ComponentTests.SolveInstance_MissingToken] expected AddRuntimeMessage, got exception
  → fixing SolveInstance guard clause in GetBoardComponent.cs
  dotnet test... ✓ 47 passed
```

---

## Error identification rules

| Error pattern | Likely cause | Skill to load |
|---|---|---|
| `CS0246` missing type | Missing `using` (file) or missing package/`Reference` (csproj) | pr-client (HttpClient/Json types) or pr-vs-project (csproj refs) |
| `CS0117` no definition for `PluginUtilities.X` | Subcategory constant name doesn't match `pr-utilities` | pr-utilities + pr-preset / pr-component |
| `CS0103` `Resources` not found | Bare `Resources.` instead of `Properties.Resources.` | pr-component / pr-assembly |
| `CS1061` member not found | Wrong client method name | pr-client |
| `CS1069` `HttpClient` not found (net48 only) | `System.Net.Http` reference missing | pr-vs-project |
| `CS0115` no suitable override | Wrong base class | pr-component or pr-button |
| `MSB3823` / `MSB3822` resx | Preserialized-resource settings missing | pr-vs-project |
| `CS0102` duplicate `Resources` member | Designer.cs got a second property for the same icon | pr-icons (re-run `add_to_resources` after removing the duplicate) |
| Null reference in test | Builder not null-coalescing | pr-builders |
| Test assertion: wrong JSON shape | Builder drifted from `call-library-validated.json` | pr-builders |
| Test: ragged assembly throws | `AssembleRecords` missing `Min` guard | pr-bulk-data |

---

## Rules

- Do not proceed past build until `Build succeeded` with 0 errors and 0 warnings **other than the
  suppressed `CA1416`** (pr-vs-project adds it to `<NoWarn>`; if it still appears the csproj is missing
  that entry — fix the csproj, don't argue with the warning). Unrelated GH SDK warnings: flag, don't block
- Do not mark phase complete until `Passed!` with 0 failed tests
- Fix one error at a time — rerun after each fix to confirm it resolved without introducing new errors
- **5 loops max per stage**, then stop and report — see Sequence
- Environment faults (no SDK, no targeting pack) are surfaced immediately, never "fixed" by editing code
- Never skip a failing test — if a test is genuinely wrong (testing the wrong thing), fix the test and explain why
