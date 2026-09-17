# 04 · Slots and files

Two different things are "inputs" in a launch request, they are encoded as two
different entity kinds, and conflating them is the single most common
implementation error. This file is the normative statement of the difference.

| | an **input slot** | an **input file** |
|---|---|---|
| producer-side source | `ToolMeta.slots[]` (declaration) + `LaunchInput.slots{}` (value) | `LaunchInput.files{}` |
| entity type | `FormalParameter` | `File` |
| `@id` | `#input-<slot.id>` | the file's `url`, or its bare `name` if it has no `url` |
| referenced from | `workflow.input[]` | `root.hasPart[]` — **and from nowhere else** |
| what it means to a handler | a named parameter the workflow looks up by name | a blob to fetch, stage, or mount |

A tool can be **both at once**, and several are: sciencemesh takes one literal
slot (`"Shared With"`) *and* a data file. `VREPayload.input_files` therefore has
to return file entities that no slot mentions at all — an earlier version of this
document specified "slot-referenced files only" and that was **wrong**.

## Slots

Every `FormalParameter` carries the same four keys. This is sciencemesh's, which
is a complete one:

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

- **`name` is the lookup key.** Handlers match on it, not on `@id`: galaxy
  fills `request_state`, vip fills `inputValues`, mddash reads `pdb_id`,
  sciencemesh shares with `Shared With`. A producer **MUST** emit `name` exactly
  as the target VRE expects it, spaces and all — sciencemesh's literally contains
  a space, which is why `@id`s can contain spaces
  ([`02-envelope.md` §`@id` allocation](02-envelope.md#id-allocation)).
- **`@id` is structural.** It is `#input-` + the producer's slot id and is used
  only to build the `workflow.input` reference. A consumer **MUST NOT** derive
  meaning from it. The producer's `LaunchInput.slots` map is keyed by **name**,
  so `id` and `name` routinely differ and nothing correlates them in the crate.
- **`additionalType` is informational** — see
  [§Binding](#binding-file-bound-versus-literal-slots) below.
- **`required` is `not is_optional`,** and it is a pure carry-through: nothing in
  this library reads it. A producer **MUST** still set it correctly, because a
  consumer that *does* honour it will honour it.

A slot **declaration** with no matching **value** still gets a full
`FormalParameter` entity and still appears in `workflow.input`; only
`defaultValue` is absent. So an unfilled slot and a slot deliberately filled with
nothing are indistinguishable in the crate — see case 5 below.

Because `id` and `name` are different keys and nothing correlates them, **renaming
a slot silently discards its value.** Measured, on a request carrying one
file-bound slot and one literal slot, changing only `SlotDefinition.name` so the
values map keeps the old keys: the crate still contains both `FormalParameter`
entities and both `workflow.input` references, and contains no `defaultValue` at
all. `lint_report` returns `violations: []` and `undecidable: []`,
`validate_basic` passes, and `VREPayloadBuilder.build` succeeds — because a slot
with no value is legal ([§Slots](#slots) above), not because anything here is
wrong.

The part that makes this dangerous rather than merely lossy is the split at the
top of this file: the **files survive**. `input_files` still returns both of them,
so a consumer that iterates files sees a complete payload, while
`input_file_bindings()` and `input_literal_bindings()` both come back empty and
`file_for_input()` returns `None` for every slot. The crate says *which* files
exist and no longer says *where* they go.

A producer that renames a slot **MUST** rename the value key in the same change.
A consumer **MUST NOT** treat `required: true` with no `defaultValue` as a
malformed crate and reject it — that state is legal and reachable by other means;
if the distinction matters to your handler, compare the slot set against the
binding set rather than assuming a missing value is an error.

## Files

`File` entities are enumerated by exactly one thing: `root.hasPart`. A `File`
entity that is in `@graph` but not in `hasPart` is **invisible** — it validates,
it parses, and no consumer ever sees it. Rule W008; real producer data does this
([`06-payload-profile.md` §The orphan file](06-payload-profile.md#the-orphan-file-in-the-same-fixture)).

This is sciencemesh's data file, and the root that enumerates it:

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

<!-- BEGIN GENERATED excerpt-sciencemesh-root -->
```json
{
  "@id": "./",
  "@type": "Dataset",
  "name": "Root dataset for tool: CMS Dimuon py notebook",
  "description": "N/A",
  "datePublished": "2000-01-01T00:00:00+00:00",
  "license": {
    "@id": "#license-unspecified"
  },
  "creator": {
    "@id": "#author-dispatcher"
  },
  "mainEntity": {
    "@id": "https://raw.githubusercontent.com/dpiparo/swanExamples/refs/heads/master/notebooks/CMSDimuon_py.ipynb"
  },
  "hasPart": [
    {
      "@id": "https://raw.githubusercontent.com/dpiparo/swanExamples/refs/heads/master/notebooks/CMSDimuon_py.ipynb"
    },
    {
      "@id": "https://raw.githubusercontent.com/dpiparo/swanExamples/master/notebooks/MuRun2010B.csv"
    }
  ]
}
```
<!-- END GENERATED -->

Note the ordering inside `hasPart`: the workflow descriptor comes first and the
data file second, and `VREPayload.files` comes back in precisely that order
([`02-envelope.md` §Order that matters](02-envelope.md#order-that-matters)).
`VREPayload.input_files` then drops the descriptor **by `@id` match**, leaving only
`MuRun2010B.csv`.

A `File` with no `url` gets a bare-name `@id` (`notebook.ipynb`, not a URL) —
see `examples/jupyter.py`. Consumers **MUST NOT** assume `@id` is a URI.

## Binding: file-bound versus literal slots

On the way out, the builder writes a file-bound slot's `defaultValue` as a
reference and a literal slot's as the value itself:

```python
if isinstance(slot_value, FileInput):
    fp["defaultValue"] = {"@id": _file_id(slot_value)}
else:
    fp["defaultValue"] = slot_value
```

`building/rocrate.py:225-228`. MDDash is the literal case — `pdb_id` is a PDB
identifier, not a file:

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

That asymmetry is easy to spot in the JSON. What is **not** obvious, and what
this section exists to get right, is that on the way *back in* the parser does
not ask which kind you meant. It takes `defaultValue`, and if the value resolves
to a file that exists in the crate, the slot reports a file:

```python
dv = param.default_value
file_id = dv.get("@id") if isinstance(dv, dict) else dv
return self.file_by_id(str(file_id)) if file_id else None
```

`models/payload.py:71-75`. So **file-bound-ness is decided by resolution, not by
declaration.** Five cases, all built and parsed for real during generation:

<!-- BEGIN GENERATED slot-binding-cases -->
| case | `@type` declared | `defaultValue` as written | `file_for_input()` | in `input_files`? |
|---|---|---|---|---|
| file-bound slot (intended) | `data_file` | `{"@id": "https://example.org/data/input.fastq"}` | `https://example.org/data/input.fastq` | yes |
| literal slot (intended) | `string` | `"1UBQ"` | **None** | no |
| string slot, value collides with a file `@id`, **file present** | `string` | `"https://example.org/data/input.fastq"` | `https://example.org/data/input.fastq` | yes |
| same slot, same string, **file absent** | `string` | `"https://example.org/data/input.fastq"` | **None** | no |
| declared slot, no value supplied | `data_file` | `null` | **None** | no |
<!-- END GENERATED -->

<!-- BEGIN GENERATED slot-binding-findings -->
- `additionalType` (the declared `slot_type`) is carried through to the consumer but never consulted when deciding whether a slot is file-bound - **confirmed**
- two crates with byte-identical `defaultValue` JSON mean different things depending on whether a file with that `@id` is present - **confirmed**
- a declared slot with no value is still emitted and still referenced from `workflow.input`; only `defaultValue` is absent, so an unfilled slot and an empty one are indistinguishable downstream - **confirmed**
<!-- END GENERATED -->

Case 3 is the one to design against. The producer declared `slot_type="string"`
and passed the string `"https://example.org/data/input.fastq"`; because a file
with that `@id` happened to be in the crate, `file_for_input()` returns it.
Whether that is a feature or a footgun depends on which side you are on:

- **A producer** that wants a literal string must ensure it cannot collide with a
  file `@id` in the same crate — in practice, that URLs passed as literal slot
  values are not also passed as files. This is not checked; nothing will warn.
- **A consumer** that decides "is this slot a file?" from `additionalType` will
  disagree with this library on case 3. To reproduce this library's behaviour,
  mirror it: resolve `defaultValue` (unwrapping `@id` when it is an object) and
  test membership in the crate's file set. To implement the *declared* semantics
  instead, read `additionalType` — but then say so, because the two answers
  differ.

`additionalType` is still worth emitting: it is copied onto `FormalParameter` and
reaches the handler (`building/payload.py:158`), and no other field in the crate
records the producer's intent.

## Slot values are not typed

`SlotValue` is `str | int | float | bool | FileInput`. The first four are written
into `defaultValue` verbatim, so `true` stays JSON `true` and `1` stays JSON `1`.
There is no coercion and no `valueType` property to check, so a consumer
**MUST** accept any JSON scalar here and **MUST NOT** assume numbers arrive as
strings. An earlier design had `SlotValue` as a `{value, file}` dataclass; that
was flattened, and crates carrying the old shape are not produced by anything in
this repo.

## What a consumer needs to build

Pseudocode for the whole input surface, in the order that resolves cleanly:

```text
files        = resolve each root.hasPart entry          # ordered, keep the order
workflow_id  = root.mainEntity.@id
input_files  = [f for f in files if f.id != workflow_id]
slots        = [resolve ref for ref in workflow.input]  # skip refs that don't resolve
for slot in slots:
    dv    = slot.defaultValue
    file  = files[dv.@id] if dv is object else files[dv] if dv is a string in files
    # `file` is now a file-bound slot, by resolution — see the cases above
```

Two of those lines are load-bearing in ways that are easy to get wrong: the
`!= workflow_id` filter (not a `@type` check — the descriptor **is**
`File`-typed) and the `skip refs that don't resolve` (unresolvable references are
dropped silently, rule W011; the slot simply never existed for the consumer).
