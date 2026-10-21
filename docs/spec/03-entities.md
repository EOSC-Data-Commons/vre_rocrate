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
means `{"@id": ...}`; see
[`02-envelope.md` §Reference forms](02-envelope.md#reference-forms) before writing
a bare string anywhere.

Order of reading for a new implementation:
[root-descriptor](#root-descriptor) → [root-dataset](#root-dataset) →
[workflow](#workflow) → [computer-language](#computer-language) →
[file](#file) → [formal-parameter](#formal-parameter). The three placeholder
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
[`01-conformance.md` §Version negotiation](01-conformance.md#version-negotiation)
for why the URI was added.

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
  ([`02-envelope.md` §Order that matters](02-envelope.md#order-that-matters)).
  W007 (missing → `TypeError` inside the parser, not a clean validation error),
  W008 (a `File` not listed here is invisible). `hasPart: []` is legal and means
  "no files".
- `name`, `description` — literals the builder derives as
  `"Root dataset for tool: <tool.name>"` and `"N/A"`. The exact strings are a
  builder convention, **not** a protocol feature: a consumer **MUST NOT** parse
  the tool name out of `name`. (`docs/design/` gets this wrong; the artefacts
  here are right.)
- `datePublished` — full ISO 8601 with offset. Parsed, never compared. See
  [`02-envelope.md` §Order that matters](02-envelope.md#order-that-matters)
  before using it for anything.

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

The table is keyed on a **path suffix**, and knowing which suffix decides whether a
uri hits it at all. The reference implementation takes the last `.`-separated
suffix of the whole uri, lower-cased, and matches it against the table literally —
so `…/a.final.ipynb` matches (`.ipynb`, the *last* dot) and `…/FILE.IPYNB` matches
(case-folded), while `…/a.ipynb?v=2`, `…/a.ipynb#frag` and `…/dir.name/file` all
miss, because a query, a fragment or a dot in a *directory* segment changes what
the trailing suffix is. Nothing strips a query string first. A producer that
normalises differently will silently emit no `encodingFormat`, which — per the
table above — also drops `File` from the workflow's `@type` and the workflow out of
`VREPayload.files`, with no rule firing.

Other properties:

- `programmingLanguage` — a **reference object**, never a bare string or an
  array. W005. The bare-string form crashes the parser outright
  ([`02-envelope.md` §Reference forms](02-envelope.md#reference-forms)).
- `runtimePlatform` — a plain URL string in the core profile. It *may* also be a
  reference to a `RuntimePlatform` entity, which is the infrastructure profile;
  both are read, and that is the entire difference between the two schemas
  ([`06-payload-profile.md`](06-payload-profile.md)). **Where the value comes
  from:** the request's own runtime platform if it names one, otherwise the
  per-`vre_type` default in
  [`05-vre-vocabulary.md`'s identity table](05-vre-vocabulary.md#vre_type-never-appears-in-the-crate)
  — that column is the only place those URLs are written down, and this table marks the
  field `MUST` without restating them. Note the asymmetry this creates: the field
  is `MUST` in prose but **not** in `schema-core.json`'s `required` for a
  workflow, which asks only for `name` and `programmingLanguage`. Omitting it
  passes all three checkers (measured — see
  [`01-conformance.md` §A MUST is not a check](01-conformance.md#a-must-is-not-a-check)).
  Emit it: a consumer that has to guess a deployment target will guess wrong.
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
sciencemesh jobs to the Jupyter handler. Full table:
[`05-vre-vocabulary.md` §`vre_type` never appears](05-vre-vocabulary.md#vre_type-never-appears-in-the-crate).

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
`FormalParameter.defaultValue` references them
([`04-slots-and-files.md` §Binding](04-slots-and-files.md#binding-file-bound-versus-literal-slots)).

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

Do not read that as "`url` is derived from `@id`", or as "`@id` is derived from
`url`". `@id` falls back to the *name* when there is no url; `url` is an
independent optional property. Here is a builder-emitted file whose `@id` is a URL:

<!-- BEGIN GENERATED excerpt-sciencemesh-file -->
```json
{
  "@id": "https://raw.githubusercontent.com/dpiparo/swanExamples/master/notebooks/MuRun2010B.csv",
  "@type": "File",
  "name": "MuRun2010B.csv",
  "license": {
    "@id": "#license-unspecified"
  },
  "encodingFormat": "text/csv",
  "url": "https://raw.githubusercontent.com/dpiparo/swanExamples/master/notebooks/MuRun2010B.csv"
}
```
<!-- END GENERATED -->

For a **data file** the builder writes both keys from the same `FileInput.url`, so
`url` always duplicates `@id` — which is why this library's parser takes the
address from `@id` and treats `url` as an extra (`FileReference.url` is
`entity["url"] or entity["@id"]`). The builder's **workflow** entity is the
counter-example it produces itself: typed `File` whenever the uri hits the
extension table above, and carrying no `url` at all.

The same shape turns up on data files in hand-authored crates, where a producer
has written the address into `@id` and left `url` out entirely:

<!-- BEGIN GENERATED excerpt-url-file-without-url -->
```json
{
  "@id": "https://www.creatis.insa-lyon.fr/~abonnet/Rec003_Vox1.mrui",
  "@type": "File",
  "name": "data_file",
  "encodingFormat": "application/octet-stream"
}
```
<!-- END GENERATED -->

Both shapes are conformant and nothing distinguishes them at a distance, so a
consumer **MUST** resolve the address as "`url` if present, otherwise `@id`" and
**MUST NOT** require `url`.

The table above is a list of conditionals, which is hard to read as a shape. This
is one file entity with every optional property populated at once, so the
presence of each row above can be checked against a single object rather than by
re-deriving every "present unless" clause in turn:

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
from RO-Crate's base vocabulary — see
[`08-migration-notes.md` §`@context` is a string](08-migration-notes.md#context-is-a-string-and-onedata-is-not-declared).

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
space gets into an `@id`. `additionalType` carries whatever the producer called
the slot's type, written verbatim with no validation and no enumeration. It is
**not** constrained to a string, and the values a consumer will meet are not the
values this library's own model declares. Counted across every golden in
`generated/examples.json` (see `generated/additional-types.json`, which also
names the crates behind each count):

<!-- BEGIN GENERATED additional-type-census -->
| shape | observed values (count) | who writes it | crates |
|---|---|---|---|
| string | `file` ×6, `string` ×4, `data_file` ×1 | RocrateBuilder, verbatim from `SlotDefinition.slot_type` | 7 |
| reference | `{"@id": "http://edamontology.org/data_3671"}` ×8, `{"@id": "http://edamontology.org/data_2968"}` ×2 | a producer outside this repo (`fixture-input` crates) | 5 |
<!-- END GENERATED -->

The two shapes **do not overlap**: every builder-output crate uses strings, every
reference is in a `fixture-input` crate, and no crate mixes them. So the reference
form is what real inbound traffic actually carries, the builder cannot emit it,
and it is exactly the kind of thing a producer-only reading of this document
misses. Here is one verbatim rather than described:

<!-- BEGIN GENERATED excerpt-edam-parameter -->
```json
{
  "@id": "#input-image",
  "@type": "FormalParameter",
  "conformsTo": {
    "@id": "https://bioschemas.org/profiles/FormalParameter/0.1-DRAFT-2020_07_21/"
  },
  "name": "Input Image",
  "additionalType": {
    "@id": "http://edamontology.org/data_2968"
  },
  "encodingFormat": {
    "@id": "http://edamontology.org/format_3591"
  }
}
```
<!-- END GENERATED -->

Two consequences:

- A consumer **MUST** treat `additionalType` as free text **and** as possibly a
  reference, resolving it through [`02-envelope.md` §Reference forms](02-envelope.md#reference-forms)
  before comparing it to anything. Never `==` it against a string literal.
- `VREPayload` types the parsed field `additional_type: str | None`, but the
  parse path copies the entity verbatim, so for the crates above it hands back a
  **`dict`**. The annotation is wrong; the data is not filtered. Do not write
  `if isinstance(payload.additional_type, str)` as an assertion that it *must*
  be — treat non-string as the expected other case.

`SlotDefinition.slot_type`'s own docstring claims the vocabulary is
`"string" | "file" | "data_input" | "data_collection"`. Real crates also carry
`data_file`, and carry neither `data_input` nor `data_collection` at all. That
docstring is an aspiration about one producer, not the wire contract; the table
above is what has actually been observed, and both shapes are emitted by
`generated/examples/` you can check against.

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
probe-matrix golden (see [the golden index in
`README.md`](README.md#generated-is-not-documentation-you-can-trust-by-reading)).
Treat it accordingly if you are implementing from scratch.

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
have no `#tool-metadata` entity at all: 14 of the
<!-- GEN:builder-output-count -->15 generated example crates omit it, the
exception being
[`generated/examples/probe_every_optional_input.json`](generated/examples/probe_every_optional_input.json),
which exists precisely to carry every optional input. A consumer **MUST**
tolerate its complete absence, and **MUST NOT** assume any particular key exists
inside `rawDefinition`.

A producer holding a tool identifier and finding no field for it should read that
absence as intended: [`ToolMeta.id` is never
serialized](08-migration-notes.md#prohibitions), so the id legitimately appears
nowhere in the emitted crate. Put tool-specific extras in `raw_definition`,
which is what that entity exists to carry.

---

## The three placeholders

Emitted into every crate, unconditionally, with **fixed values**. They exist
because a generator cannot invent provenance on a producer's behalf, and they are
the reason a hand-written crate needs them: `root.creator`, `workflow.creator`,
`workflow.sdPublisher`, and every `license` reference resolves to one of these
three.

Copy the three objects below verbatim. They are generated from a real emitted
crate, so they are the values, not a description of the values — which matters,
because nothing else in this directory states them and nothing on the parse side
reads them, so an invented value is never reported as wrong.

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

<!-- BEGIN GENERATED excerpt-author-placeholder -->
```json
{
  "@id": "#author-dispatcher",
  "@type": "Person",
  "name": "Dispatcher System"
}
```
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

<!-- BEGIN GENERATED excerpt-publisher-placeholder -->
```json
{
  "@id": "#workflow-hub",
  "@type": "Organization",
  "name": "Example Workflow Hub",
  "url": "http://example.com/workflows/"
}
```
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

<!-- BEGIN GENERATED excerpt-license-placeholder -->
```json
{
  "@id": "#license-unspecified",
  "@type": "CreativeWork",
  "name": "Unspecified license",
  "description": "License not specified by the crate producer"
}
```
<!-- END GENERATED -->

`#workflow-hub`'s URL is `http://example.com/workflows/` — an example domain. Do
not fetch it, do not index it, do not report it as a publisher in a UI.

**Every crate this library emits asserts an unspecified license.** That is a
statement about the wire format, not about the workflows. A producer that knows
the real license **MAY** replace the `license` reference with a real `CreativeWork`
or a license URI; a consumer **MUST** be able to see `#license-unspecified` and
**MUST NOT** treat its presence as an error.

Nothing on the parse side reads any of the three. Deleting all three *and* every
reference to them yields a crate that passes `validate_basic`, the linter and the
profile schema — measured, in
[`01-conformance.md` §A MUST is not a check](01-conformance.md#a-must-is-not-a-check).
Emit them anyway: they are the only provenance a human tracing a crate back to
its origin can read, and a consumer that later starts trusting `sdPublisher` will
find existing crates populated rather than empty.

---

## Entities that appear only in hand-authored crates

Two shapes occur in real crates that `RocrateBuilder` cannot emit. They are
documented where they are consumed:

- `RuntimePlatform` — [`06-payload-profile.md` §What a `RuntimePlatform`](06-payload-profile.md#what-a-runtimeplatform-entity-carries).
- Bare `Thing` entities for vocabulary terms, e.g.
  `{"@id": "http://edamontology.org/format_2330", "@type": "Thing", "name": "Plain
  text format"}` in `galaxy_tosca_stage`. Inert to this library: not `File`, not
  referenced from `hasPart`, never read. A consumer **MUST** skip entity types it
  does not know.
