# 03 · Entities

The reference. One section per entity role, each with the `@id` pattern, the
emission condition, and a property table.

Every table below is **generated** from a probe matrix that drives
`RocrateBuilder` over requests differing in exactly one input, so "present
unless" is an observed condition, not a guess. The rule of reading:

- **MUST** — always emitted; a consumer may rely on it; a producer must emit it.
- **MAY** — emitted under the stated condition and absent otherwise. A consumer
  must tolerate absence; the condition column is the contract for when it appears.

The *shape* column lists every JSON shape observed for that property. `reference`
means `{"@id": ...}`; see `02-envelope.md` §reference forms before writing a bare
string anywhere.

Order of reading for a new implementation: **root-descriptor → root-dataset →
workflow → computer-language → file → formal-parameter**. The three placeholder
entities exist only to satisfy references those six make.

---

## root-descriptor

<!-- BEGIN GENERATED entity-root-descriptor -->
**`@id` pattern**: `ro-crate-metadata.json`  
**`@type`**: `CreativeWork`  
**Emitted**: always

Crate root descriptor. MUST be the first @graph entity. Declares the base RO-Crate profile and the wire format profile in conformsTo.

| property | shape | producer | present unless |
|---|---|---|---|
| `@type` | `string` | MUST | - |
| `about` | `reference` | MUST | - |
| `conformsTo` | `list_of_references` | MUST | - |
<!-- END GENERATED -->

<!-- BEGIN GENERATED excerpt-galaxy-descriptor -->
```json
{
  "@id": "ro-crate-metadata.json",
  "@type": "CreativeWork",
  "about": {
    "@id": "./"
  },
  "conformsTo": [
    {
      "@id": "https://w3id.org/ro/crate/1.1"
    },
    {
      "@id": "https://w3id.org/eosc-vre/req-packager/1.0"
    }
  ]
}
```
<!-- END GENERATED -->

The descriptor is the only place the wire format declares *what it is*. Three
rules touch it: W003 (its `about`/root must exist), W012 (it must name the
profile URI), and W002 (its `@id` must be unique).

A consumer **SHOULD** read `conformsTo[1]` before interpreting anything else, and
**MAY** refuse an unrecognised profile URI. Note that all
<!-- GEN:fixture-input-count -->13 real fixtures predate
the URI, so refusing on absence will reject crates that work fine — see
`01-conformance.md` §version negotiation for why the URI was added.

`about` points at `./`. It is emitted because RO-Crate requires it; this
library's parser never reads it. **MUST** still be present for a conforming crate.

---

## root-dataset

<!-- BEGIN GENERATED entity-root-dataset -->
**`@id` pattern**: `./`  
**`@type`**: `Dataset`  
**Emitted**: always

Root dataset. The anchor for the whole payload: mainEntity and hasPart are read from here and nowhere else.

| property | shape | producer | present unless |
|---|---|---|---|
| `@type` | `string` | MUST | - |
| `creator` | `reference` | MUST | - |
| `datePublished` | `string` | MUST | - |
| `description` | `string` | MUST | - |
| `hasPart` | `list_of_references` | MUST | - |
| `license` | `reference` | MUST | - |
| `mainEntity` | `reference` | MUST | - |
| `name` | `string` | MUST | - |
<!-- END GENERATED -->

<!-- BEGIN GENERATED excerpt-galaxy-root -->
```json
{
  "@id": "./",
  "@type": "Dataset",
  "name": "Root dataset for tool: Galaxy reverse file workflow",
  "description": "N/A",
  "datePublished": "2000-01-01T00:00:00+00:00",
  "license": {
    "@id": "#license-unspecified"
  },
  "creator": {
    "@id": "#author-dispatcher"
  },
  "mainEntity": {
    "@id": "https://dockstore.org/api/ga4gh/trs/v2/tools/%23workflow%2Fgithub.com%2Flaitanawe%2Fismb2024%2Fgalaxy_example/versions/main/PLAIN_GALAXY/descriptor/Galaxy-Workflow-reverse_file_galaxy_workflow.ga"
  },
  "hasPart": [
    {
      "@id": "https://dockstore.org/api/ga4gh/trs/v2/tools/%23workflow%2Fgithub.com%2Flaitanawe%2Fismb2024%2Fgalaxy_example/versions/main/PLAIN_GALAXY/descriptor/Galaxy-Workflow-reverse_file_galaxy_workflow.ga"
    },
    {
      "@id": "https://example-files.online-convert.com/document/txt/example.txt"
    }
  ]
}
```
<!-- END GENERATED -->

The anchor. `mainEntity` and `hasPart` are read from the entity at `./` and from
no other entity, so a well-formed root dataset on some *other* `@id` is inert.

- `mainEntity` — a reference to the workflow entity. W003 (missing → rejected),
  W004 (dangling → rejected).
- `hasPart` — the **only** enumeration of files, and its order is meaningful
  (`02-envelope.md` §order that matters). W007 (missing → `TypeError` inside the
  parser, not a clean validation error), W008 (a `File` not listed here is
  invisible). `hasPart: []` is legal and means "no files".
- `name`, `description` — literals the builder derives as
  `"Root dataset for tool: <tool.name>"` and `"N/A"`. The exact strings are a
  builder convention, **not** a protocol feature: a consumer **MUST NOT** parse
  the tool name out of `name`. (`docs/design/` gets this wrong; the artefacts
  here are right.)
- `datePublished` — full ISO 8601 with offset. Parsed, never compared. See
  `02-envelope.md` before using it for anything.

---

## workflow

<!-- BEGIN GENERATED entity-workflow -->
**`@id` pattern**: `<tool.uri>`  
**`@type`**: `File|SoftwareSourceCode|ComputationalWorkflow`  
**Emitted**: always

The workflow / mainEntity. Its @id IS the workflow uri - there is no separate identifier - and it is also a root hasPart member.

| property | shape | producer | present unless |
|---|---|---|---|
| `@type` | `list_of_string` | MUST | - |
| `conformsTo` | `reference` | MUST | - |
| `creator` | `reference` | MUST | - |
| `dateCreated` | `string` | MUST | - |
| `description` | `string` | MUST | - |
| `encodingFormat` | `string` | MAY | the workflow uri has no extension in _EXTENSION_TO_MIME; this also drops 'File' from @type, which stops the workflow appearing in VREPayload.files |
| `input` | `list_of_references` | MAY | the tool declares no slots |
| `license` | `reference` | MUST | - |
| `name` | `string` | MUST | - |
| `programmingLanguage` | `reference` | MUST | - |
| `runtimePlatform` | `string` | MUST | - |
| `sdPublisher` | `reference` | MUST | - |
| `version` | `string` | MUST | - |
<!-- END GENERATED -->

<!-- BEGIN GENERATED excerpt-galaxy-workflow -->
```json
{
  "@id": "https://dockstore.org/api/ga4gh/trs/v2/tools/%23workflow%2Fgithub.com%2Flaitanawe%2Fismb2024%2Fgalaxy_example/versions/main/PLAIN_GALAXY/descriptor/Galaxy-Workflow-reverse_file_galaxy_workflow.ga",
  "@type": [
    "File",
    "SoftwareSourceCode",
    "ComputationalWorkflow"
  ],
  "conformsTo": {
    "@id": "https://bioschemas.org/profiles/ComputationalWorkflow/0.5-DRAFT-2020_07_21/"
  },
  "name": "Galaxy reverse file workflow",
  "description": "A simple Galaxy workflow for demonstration purposes.",
  "programmingLanguage": {
    "@id": "#galaxy-lang"
  },
  "creator": {
    "@id": "#author-dispatcher"
  },
  "dateCreated": "2000-01-01",
  "license": {
    "@id": "#license-unspecified"
  },
  "sdPublisher": {
    "@id": "#workflow-hub"
  },
  "version": "main",
  "runtimePlatform": "https://usegalaxy.eu/",
  "encodingFormat": "application/galaxy",
  "input": [
    {
      "@id": "#input-simpletext_input"
    }
  ]
}
```
<!-- END GENERATED -->

The `mainEntity`. Its `@id` **is** the workflow URI — there is no separate
identifier — and it is also a member of `root.hasPart`.

`@type` is the one place a value is computed rather than copied:

| tool uri | `@type` | consequence |
|---|---|---|
| extension in the table below | `["File", "SoftwareSourceCode", "ComputationalWorkflow"]` + `encodingFormat` | appears in `VREPayload.files` |
| extension absent or unknown | `["SoftwareSourceCode", "ComputationalWorkflow"]`, no `encodingFormat` | **absent from `VREPayload.files`** |

`files` is built from `hasPart` members whose `@type` includes `File`, so a
workflow uri that misses the table silently drops the workflow out of the file
list. **7 of the 28 goldens are in that state** — including this one:

<!-- BEGIN GENERATED excerpt-mddash-workflow -->
```json
{
  "@id": "https://github.com/sb-ncbr/mddash-notebooks.git",
  "@type": [
    "SoftwareSourceCode",
    "ComputationalWorkflow"
  ],
  "conformsTo": {
    "@id": "https://bioschemas.org/profiles/ComputationalWorkflow/0.5-DRAFT-2020_07_21/"
  },
  "name": "MDDash notebook",
  "description": "MDDash notebook for PDB analysis.",
  "programmingLanguage": {
    "@id": "#mddash-lang"
  },
  "creator": {
    "@id": "#author-dispatcher"
  },
  "dateCreated": "2000-01-01",
  "license": {
    "@id": "#license-unspecified"
  },
  "sdPublisher": {
    "@id": "#workflow-hub"
  },
  "version": "1.0.0",
  "runtimePlatform": "https://mddash.cerit-sc.cz/",
  "input": [
    {
      "@id": "#input-pdb_id"
    }
  ]
}
```
<!-- END GENERATED -->

This is not a corner case: git-repo URIs, a DOI, a bare `dummy-tool`, and a
parameterised REST pipeline URL all miss the table. A consumer that assumes "the
workflow is always `files[0]`" is wrong for roughly half of the builder-output
crates shipped here. Find the workflow by dereferencing `root.mainEntity`; use
`files` only for files.

The extension table, and what it does *not* govern:

<!-- BEGIN GENERATED mime-table -->
| extension | `encodingFormat` |
|---|---|
| `.csv` | `text/csv` |
| `.fastq` | `application/fastq` |
| `.ga` | `application/galaxy` |
| `.ipynb` | `application/x-ipynb+json` |
| `.jpeg` | `image/jpeg` |
| `.jpg` | `image/jpeg` |
| `.json` | `application/json` |
| `.png` | `image/png` |
| `.py` | `text/x-python` |
| `.sh` | `text/x-shellscript` |
| `.tif` | `image/tiff` |
| `.tiff` | `image/tiff` |
| `.txt` | `text/plain` |
<!-- END GENERATED -->

**It applies only to the workflow uri.** A data file's `encodingFormat` is copied
verbatim from the request and is never inferred from its name; a file with no MIME
type simply has no `encodingFormat`. (`generated/mime-extensions.json` carries the
proof, which was written after an earlier draft of this document claimed the
opposite.)

Other properties:

- `programmingLanguage` — a **reference object**, never a bare string or an
  array. W005. The bare-string form crashes the parser outright
  (`02-envelope.md` §reference forms).
- `runtimePlatform` — a plain URL string in the core profile. It *may* also be a
  reference to a `RuntimePlatform` entity, which is the infrastructure profile;
  both are read, and that is the entire difference between the two schemas
  (`06-payload-profile.md`).
- `conformsTo` — the **BioSchema ComputationalWorkflow 0.5-DRAFT** profile URI.
  This is a *per-entity* `conformsTo` and is unrelated to the wire-format profile
  on the descriptor. Do not confuse the two; only the descriptor's is
  version-bearing.
- `input` — references to the `FormalParameter` entities. W011: an unresolvable
  reference is skipped silently, so the slot never exists downstream.
- `version` — copied from `ToolMeta.version` with no validation; it can be any
  string, including a branch name (`"main"`) as several real fixtures show.
- `name` — `tool.name`, falling back to the last path segment of the uri.

---

## computer-language

<!-- BEGIN GENERATED entity-computer-language -->
**`@id` pattern**: `#<vre_type>-lang`  
**`@type`**: `ComputerLanguage`  
**Emitted**: always

ComputerLanguage carrying the VRE identity token in `identifier`. This is the ONLY place the target VRE is declared.

| property | shape | producer | present unless |
|---|---|---|---|
| `@type` | `string` | MUST | - |
| `identifier` | `string` | MUST | - |
| `name` | `string` | MUST | - |
| `url` | `string` | MUST | - |
<!-- END GENERATED -->

<!-- BEGIN GENERATED excerpt-galaxy-language -->
```json
{
  "@id": "#galaxy-lang",
  "@type": "ComputerLanguage",
  "identifier": "https://galaxyproject.org/",
  "name": "Galaxy",
  "url": "https://galaxyproject.org/"
}
```
<!-- END GENERATED -->

**The only place the target VRE is declared.** All four properties are always
present.

`identifier` is the routing token and **`name`/`url` are descriptive only.** The
sciencemesh entity proves why that distinction is load-bearing:

<!-- BEGIN GENERATED excerpt-sciencemesh-language -->
```json
{
  "@id": "#sciencemesh-lang",
  "@type": "ComputerLanguage",
  "identifier": "https://eosc.cernbox.cern.ch",
  "name": "Jupyter Notebook",
  "url": "https://jupyter.org/"
}
```
<!-- END GENERATED -->

`identifier` is an OpenCloudMesh domain while `name` says `Jupyter Notebook` and
`url` says `https://jupyter.org/`. A consumer that routes on `name` or `url` sends
sciencemesh jobs to the Jupyter handler. Full table: `05-vre-vocabulary.md`.

Note the asymmetry that makes this easy to get wrong: the *build* side's
`vre_type` is the short name (`"sciencemesh"`) and the *parse* side's
`VREPayload.vre_type` is this `identifier` URL
(`"https://eosc.cernbox.cern.ch"`). They are both called `vre_type` and they are
**not comparable**.

---

## file

<!-- BEGIN GENERATED entity-file -->
**`@id` pattern**: `<file.url, or the bare name when there is no url>`  
**`@type`**: `File`  
**Emitted**: conditional - omitted when neither slot-bound nor free-form files are supplied

A data file, reachable ONLY through root hasPart. Slot-bound and free-form files are structurally identical here and differ only in whether a FormalParameter's defaultValue points at them.

| property | shape | producer | present unless |
|---|---|---|---|
| `@type` | `string` | MUST | - |
| `contentSize` | `integer` | MAY | FileInput.size_bytes is None |
| `encodingFormat` | `string` | MAY | FileInput.mime_type is None |
| `license` | `reference` | MUST | - |
| `name` | `string` | MUST | - |
| `onedata:fileId` | `string` | MAY | no onedata placement hints are given |
| `onedata:onezoneDomain` | `string` | MAY | no onedata placement hints are given |
| `sha256` | `string` | MAY | FileInput.checksum is None; checksum_type is anything other than 'sha256' - the checksum is DISCARDED, not emitted under another key |
| `url` | `string` | MAY | FileInput.url is None; the entity is then keyed by its bare name |
<!-- END GENERATED -->

<!-- BEGIN GENERATED excerpt-galaxy-file -->
```json
{
  "@id": "https://example-files.online-convert.com/document/txt/example.txt",
  "@type": "File",
  "name": "simpletext_input",
  "license": {
    "@id": "#license-unspecified"
  },
  "encodingFormat": "text/plain",
  "url": "https://example-files.online-convert.com/document/txt/example.txt"
}
```
<!-- END GENERATED -->

A file is reachable **only** through `root.hasPart`. Slot-bound and free-form
files are structurally identical here — the difference lives in whether a
`FormalParameter.defaultValue` references them (`04-slots-and-files.md`).

A file with no `url` is keyed by its bare name, so a local file's `@id` is
`requirements.txt` rather than a URL:

<!-- BEGIN GENERATED excerpt-alphafind-local-file -->
```json
{
  "@id": "requirements.txt",
  "@type": "File",
  "name": "requirements.txt",
  "license": {
    "@id": "#license-unspecified"
  },
  "encodingFormat": "text/plain"
}
```
<!-- END GENERATED -->

Do not read that as "no `url` property". The `@id` is what falls back to the name;
`url` is a separate optional property, and a file can have a full-URL `@id` and no
`url` property at the same time — as this real fixture's file does:

<!-- BEGIN GENERATED excerpt-sciencemesh-file -->
*Long free-text values shortened for readability; every `@id`, type and structure is verbatim.*

```json
{
  "@id": "https://raw.githubusercontent.com/dpiparo/swanExamples/master/notebooks/MuRun2010B.csv",
  "@type": "File",
  "name": "MuRun2010B.csv",
  "license": {
    "@id": "#license-unspecified"
  },
  "encodingFormat": "text/csv",
  "url": "https://raw.githubusercontent.com/dpiparo/swanExamples/master/notebooks/\u2026"
}
```
<!-- END GENERATED -->

Consumers therefore **MUST** take the address from `@id` and treat `url` as an
extra. This library's parser does: `FileReference.url` is
`entity["url"] or entity["@id"]`.

The table above is a list of conditionals, which is hard to read as a shape. This
is one file entity with every optional property populated at once, so the
presence of each row above can be checked against a single object rather than
against eleven separate "unless" clauses:

<!-- BEGIN GENERATED excerpt-probe-file -->
```json
{
  "@id": "https://example.org/data/attachment.csv",
  "@type": "File",
  "name": "attachment.csv",
  "license": {
    "@id": "#license-unspecified"
  },
  "encodingFormat": "text/csv",
  "url": "https://example.org/data/attachment.csv",
  "contentSize": 1024,
  "sha256": "0000000000000000000000000000000000000000000000000000000000000000",
  "onedata:onezoneDomain": "one.example.org",
  "onedata:fileId": "F1234"
}
```
<!-- END GENERATED -->

It is generated, not a fixture — no example in this repo populates all of these
together. `sha256` is dropped, not renamed, when `checksum_type` is anything other
than `"sha256"` — an MD5 checksum vanishes rather than being emitted as `md5`. And
when present it is copied verbatim with no shape check, which is what W010
protects against: a truncated or uppercase digest is published as-is and only
fails a consumer that verifies it.

`onedata:onezoneDomain` and `onedata:fileId` are this protocol's one deviation
from RO-Crate's base vocabulary — see `08-migration-notes.md`.

---

## formal-parameter

<!-- BEGIN GENERATED entity-formal-parameter -->
**`@id` pattern**: `#input-<slot.id>`  
**`@type`**: `FormalParameter`  
**Emitted**: conditional - omitted when the tool declares no slots

A tool-declared input slot. @id derives from slot.id but values are looked up by slot.name, so id and name are different keys.

| property | shape | producer | present unless |
|---|---|---|---|
| `@type` | `string` | MUST | - |
| `additionalType` | `string` | MUST | - |
| `defaultValue` | `reference`/`string` | MAY | the slot is declared by the tool but not filled by the request |
| `name` | `string` | MUST | - |
| `required` | `boolean` | MUST | - |
<!-- END GENERATED -->

A tool-declared input slot, referenced from `workflow.input[]` and never from
`hasPart`. The `@id` comes from `slot.id`; the lookup key every VRE uses is
`name`. Three real examples of the same property, covering both shapes
`defaultValue` takes — a literal string, and a reference into the crate:

<!-- BEGIN GENERATED excerpt-galaxy-parameter -->
```json
{
  "@id": "#input-simpletext_input",
  "@type": "FormalParameter",
  "name": "simpletext_input",
  "additionalType": "file",
  "required": true,
  "defaultValue": {
    "@id": "https://example-files.online-convert.com/document/txt/example.txt"
  }
}
```
<!-- END GENERATED -->

Note `additionalType: "file"` on that one — a producer-declared type that is
*neither* of the two strings elsewhere in this document's examples. It is free
text, and this is a crate a real producer sent.

<!-- BEGIN GENERATED excerpt-mddash-parameter -->
```json
{
  "@id": "#input-pdb_id",
  "@type": "FormalParameter",
  "name": "pdb_id",
  "additionalType": "string",
  "required": true,
  "defaultValue": "1L2Y"
}
```
<!-- END GENERATED -->

<!-- BEGIN GENERATED excerpt-sciencemesh-parameter -->
```json
{
  "@id": "#input-Shared With",
  "@type": "FormalParameter",
  "name": "Shared With",
  "additionalType": "string",
  "required": true,
  "defaultValue": "rwelande@eosc.cernbox.cern.ch"
}
```
<!-- END GENERATED -->

The second is a literal string in a slot named `Shared With`, which is also how a
space gets into an `@id`. `additionalType` carries the producer's slot type
verbatim (`"string"`, `"data_file"`, `"data_input"`, `"data_collection"`) with no
validation and no enumeration — a consumer **MUST** treat it as free text.

`required` is the inversion of `SlotDefinition.is_optional` and is **never read
by anything on the parse side** in this repo. Emit it correctly; do not depend on
a peer enforcing it.

---

## input-dataset

<!-- BEGIN GENERATED entity-input-dataset -->
**`@id` pattern**: `<dataset.url>`  
**`@type`**: `Dataset`  
**Emitted**: conditional - omitted when LaunchInput.dataset is None

Optional Dataset for a browsed dataset. @id IS the dataset url.

| property | shape | producer | present unless |
|---|---|---|---|
| `@type` | `string` | MUST | - |
| `description` | `string` | MUST | - |
| `name` | `string` | MUST | - |
<!-- END GENERATED -->

<!-- BEGIN GENERATED excerpt-probe-dataset -->
```json
{
  "@id": "https://example.org/dataset/doi/10.5072/test",
  "@type": "Dataset",
  "name": "A dataset",
  "description": "Dataset description"
}
```
<!-- END GENERATED -->

A browsed dataset the user selected, distinct from the workflow's own files. It
appears in `root.hasPart` alongside the files and is `@type: Dataset`, so it is
**not** picked up by the `File`-typed file extraction — a consumer looking for
"the thing the user pointed at" must match on `Dataset`, not on membership in
`files`.

No example under `examples/` produces this entity; the excerpt comes from the
probe-matrix golden (see §golden index in `README.md`). Treat it accordingly if
you are implementing from scratch.

---

## tool-metadata

<!-- BEGIN GENERATED entity-tool-metadata -->
**`@id` pattern**: `#tool-metadata`  
**`@type`**: `Thing`  
**Emitted**: conditional - omitted when ToolMeta.raw_definition is empty

Opaque Thing carrying rawDefinition - the producer's own tool definition, round-tripped untouched.

| property | shape | producer | present unless |
|---|---|---|---|
| `@type` | `string` | MUST | - |
| `rawDefinition` | `object` | MUST | - |
<!-- END GENERATED -->

<!-- BEGIN GENERATED excerpt-probe-tool-metadata -->
```json
{
  "@id": "#tool-metadata",
  "@type": "Thing",
  "rawDefinition": {
    "vre_type": "galaxy"
  }
}
```
<!-- END GENERATED -->

An opaque escape hatch: the producer's own tool definition, round-tripped to
`VREPayload.raw_definition` untouched. Nothing in this repo interprets it, and
the library builds **no** `#receiver` entity and carries **no** OCM data — named
domain conventions live on the consumer side.

It is emitted **only when `raw_definition` is non-empty**, so most real crates
have no `#tool-metadata` entity at all — including all 14 examples. A consumer
**MUST** tolerate its complete absence, and **MUST NOT** assume any particular key
exists inside `rawDefinition`.

---

## The three placeholders

Emitted into every crate, unconditionally, with fixed values. They exist because
a generator cannot invent provenance on a producer's behalf, and they are the
reason a hand-written crate needs them: `root.creator`, `workflow.creator`,
`workflow.sdPublisher`, and every `license` reference resolves to one of these
three.

<!-- BEGIN GENERATED entity-author-placeholder -->
**`@id` pattern**: `#author-dispatcher`  
**`@type`**: `Person`  
**Emitted**: always

Placeholder Person credited as root creator.

| property | shape | producer | present unless |
|---|---|---|---|
| `@type` | `string` | MUST | - |
| `name` | `string` | MUST | - |
<!-- END GENERATED -->

<!-- BEGIN GENERATED entity-publisher-placeholder -->
**`@id` pattern**: `#workflow-hub`  
**`@type`**: `Organization`  
**Emitted**: always

Placeholder Organization carried as sdPublisher.

| property | shape | producer | present unless |
|---|---|---|---|
| `@type` | `string` | MUST | - |
| `name` | `string` | MUST | - |
| `url` | `string` | MUST | - |
<!-- END GENERATED -->

<!-- BEGIN GENERATED entity-license-placeholder -->
**`@id` pattern**: `#license-unspecified`  
**`@type`**: `CreativeWork`  
**Emitted**: always

Placeholder CreativeWork, emitted because a builder cannot assert a license on the producer's behalf. Never read by the parser and absent from every crate not built by this library - an emitter convention, not a protocol feature.

| property | shape | producer | present unless |
|---|---|---|---|
| `@type` | `string` | MUST | - |
| `description` | `string` | MUST | - |
| `name` | `string` | MUST | - |
<!-- END GENERATED -->

**Every crate this library emits asserts an unspecified license.** That is a
statement about the wire format, not about the workflows. A producer that knows
the real license **MAY** replace the `license` reference with a real `CreativeWork`
or a license URI; a consumer **MUST** be able to see `#license-unspecified` and
**MUST NOT** treat its presence as an error.

`#workflow-hub`'s URL is `http://example.com/workflows/` — an example domain. Do
not fetch it, do not index it, do not report it as a publisher in a UI.

---

## Entities that appear only in hand-authored crates

Two shapes occur in real crates that `RocrateBuilder` cannot emit. They are
documented where they are consumed:

- `RuntimePlatform` — `06-payload-profile.md`.
- Bare `Thing` entities for vocabulary terms, e.g.
  `{"@id": "http://edamontology.org/format_2330", "@type": "Thing", "name": "Plain
  text format"}` in `galaxy_tosca_stage`. Inert to this library: not `File`, not
  referenced from `hasPart`, never read. A consumer **MUST** skip entity types it
  does not know.
