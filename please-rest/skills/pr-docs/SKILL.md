---
name: pr-docs
description: Generate the docs/ folder of clean markdown for a generated Grasshopper REST API plugin
---

# Skill: Docs

Generate the `docs/` folder for a generated plugin — clean, portable markdown the user can
drop into Notion, GitBook, Mintlify, Obsidian, Docusaurus, or anything else.

Runs in **Phase 13** (Docs). `pr-gh-package` runs separately in **Phase 14** (GitHub), so the
README it writes can link to the `docs/` folder produced here.
Source: `spec/plugin-spec.json` + `spec/call-library-validated.json`.
Format: plain markdown, no frontmatter, no platform assumptions.

---

## Folder layout

```
docs/
├── index.md               overview paragraph, info block, install, component count by subcategory
├── workflows.md           bulleted "what can you do with this plugin" — one line per capability
├── quickstart.md          minimum steps: get token, drop auth component, verify connection, first create
├── authentication.md      how to get a token for this API, where to plug it in, what Status output means
├── [concept].md           0-2 pages for a cross-cutting mechanic no single component page can hold
│                          (e.g. chaining.md — how style components layer onto one block)
├── components/
│   └── [subcategory]/
│       ├── index.md       lists every component in the group with a one-line description
│       └── [component].md  one file per component
├── examples/              one .md per demo workflow (written from the Phase 12 demo .gh files)
└── changelog.md           version history — starts at 1.0.0, one entry per release
```

---

## Style — bulleted, not wordy

Every page here is meant to be scanned, not read start to finish. Default to bullets and tables;
write a paragraph only where the shape genuinely doesn't fit a list (the one-sentence lead on
`index.md`, single-sentence component descriptions). No filler sentences, no restating the heading
in prose, one idea per line. If a section is trending into a paragraph, break it into bullets.

---

## Per-component page

One file per component — never combine multiple components on one page.

```markdown
# [Display Name]

[One-sentence description.]

## Inputs

| Name | Type | Required | Default | Description |
|---|---|---|---|---|
[one row per input from plugin-spec.json]

## Outputs

| Name | Type | Description |
|---|---|---|
[one row per output from plugin-spec.json]

## API endpoint

`[METHOD] [url_template]`

## Example response

[example_response from call-library-validated.json, fenced as json]

## Notes

[usage notes from spec — edge cases, format requirements]

## Related

- [linked JSON builder component that feeds this HTTP component, etc.]
```

---

## index.md

```markdown
# [PluginName]

[One or two sentence lead — what it does, what API it wraps.]

- **Version:** [csproj <Version>, e.g. 1.0.0]
- **License:** MIT
- **GitHub:** https://github.com/[GitHubOrg]/[repo-name]
- **Food4Rhino:** _(added once listed on food4rhino.com)_
- **Released:** _(added at first tagged release)_

_(Space for a demo video or GIF — drop it above or below this list once one exists.)_

## Install

[First sentence only — Food4Rhino search term or Yak package name.]

## Components by tab

| Subcategory | Components |
|---|---|
[one row per subcategory]
```

Version, License, and GitHub are knowable at generation time — pull Version from the `.csproj`
`<Version>` (the single version source; `GH_AssemblyInfo.AssemblyVersion` reads the same value — see
`pr-assembly`), License is always MIT (see `pr-gh-package`), and `[GitHubOrg]` is `session.json`
`github_org` when present — otherwise ask the user once, write it to `session.json`, and use it (the
same value `pr-yak-package` puts in `manifest.yml` `url`). Food4Rhino and Released cannot be known
until the plugin is actually listed and tagged — leave the placeholder text verbatim rather than
guessing a value or a date.

---

## workflows.md

```markdown
# Workflows

What you can do with [PluginName]:

- [Capability, phrased as an outcome, not a component name] — see [demo name](examples/[demo].md)
- [Capability] — see [demo name](examples/[demo].md)
- [A capability with no matching demo can still be listed, just without a link]
```

One bullet per demo built in Phase 12, rephrased from that demo's `**Goal:**` line into an
outcome a reader is looking for ("Update a slide's text from Grasshopper data", not "Wires
UpdateTextStyle into a String param"). Add a bullet without a demo link only for a capability
that's real but not yet demoed — never invent a capability that isn't backed by an actual
component or demo.

### When `demos/` has no `.gh` files (Phase 12 degraded — no bridge)
Two of the first four dogfood runs ended here. Do **not** skip `examples/` and do **not** fabricate
`.gh`-derived detail:
- Write one `examples/[workflow].md` per **target workflow** in `spec/plugin-spec.json`
  (`workflows` / the confirmed Step-0 list), each with `**Goal:**`, the components in wiring order,
  and the inputs a user sets — the same shape as a demo page, sourced from the spec instead
- If `demos/README.md` exists (hand-built canvases described by `pr-rhino-test`'s fallback), link
  each example to its section there
- Open each such page with the line `_Demo file pending — built from the plugin spec, not a saved
  canvas._` so readers know why there is no `.gh` to download
- `workflows.md` links to these pages exactly as it would to demo-derived ones

---

## Concept pages (0-2, only when earned)

Some plugins have a mechanic that spans many components and belongs on none of them — how styling
components chain onto one block, how index-free placement resolves, how a data tree maps to rows.
A reader who doesn't understand it can't use the plugin, and repeating it on 20 component pages is
worse than one page. Both dogfooded plugins needed exactly one (`chaining.md`).

- Write one **only** for a mechanic that (a) is referenced by three or more component pages and
  (b) cannot be stated in a sentence on each. Two is the ceiling; if a third wants to exist, the
  plugin's design is the problem, not the docs.
- Name it for the concept (`chaining.md`), not for a component.
- Link it from `index.md`'s Features list, from the README's Documentation list, and from the
  "Related" section of every component page it explains.
- It is prose-with-examples, not a component reference — the one place in `docs/` where a worked
  before/after beats a bullet list.

---

## Subcategory index page

`docs/components/[subcategory]/index.md` — lists all components in that group with a
one-line description each. A subcategory with only one component still gets its own
folder and index — no collapsing.

---

## Other pages

| File | Covers |
|---|---|
| `index.md` | Plugin name, what API it wraps, info block (version/license/links), install, component count by subcategory |
| `workflows.md` | Bulleted list of what a user can accomplish with the plugin, linked to demos where one exists |
| `quickstart.md` | Get token → drop auth component → verify connection → first create operation |
| `authentication.md` | How to get a token for this specific API, where to plug it into GH, what the Status output means |
| `examples/*.md` | One page per demo workflow, written from the demo `.gh` files built in Phase 12 (Step B, `pr-rhino-test`); if `demos/` holds no `.gh`, one page per spec workflow instead (see workflows.md section) |
| `changelog.md` | Starts at 1.0.0, one entry per release |

---

## Rules

- One file per component — never combine components on one page
- One index file per subcategory — lists components with one-line descriptions
- Plain markdown only — no frontmatter, no platform-specific syntax
- Source of truth is `plugin-spec.json` + `call-library-validated.json` — do not invent fields or responses
- Subcategory with a single component still gets its own folder and index — no collapsing
- `index.md`'s info block ships with the Food4Rhino and Released placeholders unfilled — never guess a link or date that doesn't exist yet. They are **filled in after publishing**, by the backfill in `pr-yak-package` ("After publishing"); leaving them is correct at generation time and wrong the moment the plugin is live
- At most two concept pages, and only for a mechanic three or more component pages depend on
- Default to bullets over prose everywhere a page allows it (see Style, above)

---

## Edge cases

- Component has a **PARTIAL** validated call: note it on the page with a warning that response shape may vary
- Component was **skipped** (MISSING endpoint): generate a stub page noting it is planned for a future version
- Response schema undocumented: omit the example-response section rather than inventing one
