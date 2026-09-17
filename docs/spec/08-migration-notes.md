# 08 · Deviations from RO-Crate 1.1, and prohibitions

This format is a RO-Crate 1.1 crate that a conformant RO-Crate tool will read
without complaint. That is the problem: several of its behaviours are
**incompatible with what a reasonable RO-Crate consumer would infer**, and
nothing in the crate signals the difference. Read this before writing a consumer
out of another RO-Crate codebase, and before "cleaning up" anything below.

## Deviations

### `@context` is a string, and `onedata:` is not declared

`@context` is the single string `https://w3id.org/ro/crate/1.1/context` — not an
array, and not an object with a prefix map. Yet `File` entities carry
`onedata:onezoneDomain` and `onedata:fileId` when the producer supplied Oneprovider
coordinates:

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

Under JSON-LD those keys are terms that no context defines. A strict JSON-LD
processor will either drop them on expansion or complain; a RO-Crate tool that
round-trips through expansion will **silently lose the Onedata information**,
which for a galaxy handler resolving an Onedata file id is the payload's whole
point. Consumers that need it must read the raw JSON keys, not the expanded
graph. Producers must keep the prefix spelled exactly `onedata:` — the parse path
does an exact string lookup (`building/payload.py:138`).

This is a deviation, not a style preference: there is no way to satisfy both
JSON-LD term expansion and this library's key lookup without changing one of
them, and changing the wire format is the more expensive option. It is left as-is
and documented instead.

### A `File` entity is not necessarily a file

RO-Crate says: something is a file if it is `File`-typed and present. Here, a
`File` entity **only** exists as a file if it is named in `root.hasPart`. That is
stricter than the base profile, and it cuts both ways:

- a `File` in `@graph` but not in `hasPart` is invisible (W008);
- the workflow descriptor **is** `File`-typed, so "give me the files" returns the
  workflow too, and the way to tell them apart is to compare `@id` against
  `mainEntity` — not to check `@type` (`04-slots-and-files.md`).

Both behaviours come from the same four lines in `building/payload.py`. They are
the single largest source of confusion for consumers ported from other RO-Crate
tooling.

### `programmingLanguage` is a reference whose payload lives elsewhere

RO-Crate permits `programmingLanguage` to be a `ComputerLanguage` object written
inline. Here it **must** be `{"@id": ...}` naming a top-level entity, and the
entity must carry a non-empty `identifier`. Inline is not merely discouraged: the
bare-string form raises `AttributeError` mid-parse, and an object written inline
without a graph entity to resolve to yields `identifier: None` and therefore
`vre_type == "unknown"` (`02-envelope.md` §reference forms).

### `conformsTo` order is meaningful

RO-Crate treats `conformsTo` as a set. Here it is a two-element **array** with
base RO-Crate first and the profile URI second, and consumers keying on the
second entry depend on that order (`01-conformance.md`). Emitting a bare object
rather than an array is what all pre-profile producer data does, and trips W012.

### `input` is three different things

The key `input` appears in two places with two different semantics, and they are
parsed by different code:

- `workflow.input` — slot references, resolved against `@graph` by
  `_extract_parameters` (`04-slots-and-files.md`);
- `RuntimePlatform.input` — **inline** file specifications, never dereferenced,
  exact-`@type`-matched (W013, `06-payload-profile.md`).

A reference that is correct in the first position is wrong in the second. Both
failures are silent.

## Prohibitions

Each of these has been considered and rejected, and each is load-bearing in a way
that is invisible from the code. The symptom is given because all of them are
silent.

**Do not add a `@graph` entity without an `@id`.** Blank nodes are rejected at
parse time by `ValidationPipeline._validate_entity_ids`. Do not add tolerance for
missing ids somewhere else instead: downstream code addresses everything by `@id`,
and the validation failure is the only thing that will tell a producer their crate
is unusable.

**Do not make the parser tolerant of a collapsed array.** A one-element `input`
written as a bare object currently yields an empty slot list (W014). "Fixing" this
by accepting a lone object in `as_list` would hide the producer's serialiser bug
and turn a loud lint failure into permanently missing slots. Normalise on the
consumer side if you must interoperate with a broken producer — see
`02-envelope.md` §list-valued properties.

**Do not rename or remove a field or accessor on `VREPayload`.** It is the
contract with externally-written handlers in the Dispatcher repo, which is a
separate codebase on a separate release train. Additive changes only. Note the
asymmetry in error types while you are there: `VREPayloadBuilder.__init__` raises
a plain `ValueError` for a missing `mainEntity`, while
`ValidationPipeline.validate_basic` raises `CrateValidationError` for the same
crate — both paths are live, and handlers catch different things.

**Do not read `FormalParameter.required`.** It is emitted as `not is_optional` and
no code in this library consumes it. That does not make it dead — a consumer
outside this repo may honour it — but it does mean nothing here enforces that its
semantics are what the name suggests. `SlotDefinition.is_optional` defaults to
`False`, so an omitted flag means *required*.

**Before you wire a producer-side field into a consumer, check how far it
actually travels.** The table below is measured, not read off the dataclasses:
each row changes exactly one field of a fixed request, diffs the crate that comes
out, and then looks for the new value in the *parsed* payload. Two claims are
kept apart on purpose, because an earlier hand-written version of this table
conflated them and got half its rows wrong:

- **never serialized** — the crate is byte-identical. Nobody downstream could
  recover the value even if they wanted to.
- **no named field** — the parser has no attribute for it, yet it is usually
  perfectly readable, because the parser copies every entity into a `properties`
  dict, and `VREPayload.raw_crate` holds the whole crate regardless.

<!-- BEGIN GENERATED field-visibility -->
| producer-side field | reach | what the crate does with it | readable through |
|---|---|---|---|
| `FileInput.name` | named field | `name` (2 places) `input.fastq`→`renamed-by-probe.fastq`; `attachment.csv`→`renamed-by-probe.fastq` | `named field` · `properties` · `raw_crate` |
| `FileInput.url` | named field | `@id` (5 places) `https://example…ut.fastq`→`https://example…ed.fastq`; `https://example…ment.csv`→`https://example…ed.fastq`; `url` (2 places) `https://example…ut.fastq`→`https://example…ed.fastq`; `https://example…ment.csv`→`https://example…ed.fastq` | `named field` · `properties` · `raw_crate` |
| `FileInput.path` | **never serialized** | *no byte of the crate changed* | **nothing** |
| `FileInput.size_bytes` | `properties` only | `contentSize` (2 places) `1024`→`999999` | `properties` · `raw_crate` |
| `FileInput.mime_type` | named field | `encodingFormat` (2 places) `application/fastq`→`application/x-probe`; `text/csv`→`application/x-probe` | `named field` · `properties` · `raw_crate` |
| `FileInput.checksum` | `properties` only | `sha256` (2 places) `000000000000000…00000000`→`aaaaaaaaaaaaaaa…aaaaaaaa` | `properties` · `raw_crate` |
| `FileInput.checksum_type` | **unreadable** | `sha256` (2 places) **removed** | **nothing** |
| `FileInput.onedata_domain` | named field | `onedata:onezoneDomain` (2 places) `one.example.org`→`probe.onedata.org` | `named field` · `properties` · `raw_crate` |
| `FileInput.onedata_file_id` | named field | `onedata:fileId` (2 places) `F1234`→`PROBEFILEID` | `named field` · `properties` · `raw_crate` |
| `ToolMeta.id` | **never serialized** | *no byte of the crate changed* | **nothing** |
| `ToolMeta.name` | named field | `name` (2 places) `Root dataset fo…obe Tool`→`Root dataset fo…ool Name`; `Probe Tool`→`Probed Tool Name` | `named field` · `properties` · `raw_crate` |
| `ToolMeta.version` | named field | `version` `1.2.3`→`9.9.9-probe` | `named field` · `properties` · `raw_crate` |
| `ToolMeta.uri` | named field | `@id` (3 places) `https://example…kflow.ga`→`https://example…workflow`; `@type` (3 places) `File`→`SoftwareSourceCode`; `SoftwareSourceCode`→`ComputationalWorkflow`; **removed**; `encodingFormat` **removed** | `named field` · `properties` · `raw_crate` |
| `ToolMeta.description` | `properties` only | `description` `A workflow.`→`Changed by probe.` | `properties` · `raw_crate` |
| `SlotDefinition.id` | named field | `@id` (4 places) `#input-in1`→`#input-probed-slot-id`; `#input-lit`→`#input-probed-slot-id` | `named field` · `properties (within a longer value)` · `raw_crate (within a longer value)` |
| `SlotDefinition.name` | named field | `@id` **removed**; `defaultValue` **removed**; `name` (2 places) `Input 1`→`Probed Slot Name`; `pdb_id`→`Probed Slot Name` | `named field` · `properties` · `raw_crate` |
| `SlotDefinition.slot_type` | named field | `additionalType` (2 places) `data_file`→`probed_type`; `string`→`probed_type` | `named field` · `properties` · `raw_crate` |
| `SlotDefinition.is_optional` | `properties` only | `required` (2 places) `true`→`false` | `properties (inverted)` · `raw_crate (inverted)` |
| `DatasetHandle.url` | `raw_crate` only | `@id` (2 places) `https://example…072/test`→`https://example…/dataset` | `raw_crate` |
| `DatasetHandle.title` | `raw_crate` only | `name` `A dataset`→`Probe dataset title` | `raw_crate` |
| `DatasetHandle.description` | `raw_crate` only | `description` `Dataset description`→`Probe dataset description` | `raw_crate` |
<!-- END GENERATED -->

<!-- BEGIN GENERATED field-visibility-tiers -->
- **named field** (11) - the parser copies it onto a field of the payload
- **`properties` only** (4) - no field of its own, but present in the dict the parser fills from the whole entity, so it IS readable
- **`raw_crate` only** (3) - not on any parsed object; only in the verbatim copy of the crate that `VREPayload.raw_crate` holds
- **unreadable** (1) - the builder used it and the crate shows the effect, but the value itself cannot be recovered by any consumer
- **never serialized** (2) - changing it alters no byte of the crate
<!-- END GENERATED -->

**Fields that make the crate lose a property** — not "fields that behave
surprisingly", which would be a judgement, but the rows where the probe was
enough to delete a property from the output. No other field removes one:

<!-- BEGIN GENERATED field-visibility-losses -->
- setting `FileInput.checksum_type` to "md5" removes `sha256`
- setting `ToolMeta.uri` to "https://example.org/probed-workflow" removes `@type[2]`, `encodingFormat`
- setting `SlotDefinition.name` to "Probed Slot Name" removes `defaultValue/@id`, `defaultValue`
<!-- END GENERATED -->

This list is generated by the same probe as the table, so check it against your
own producer rather than trusting any paragraph about it. Three notes, one per
row, because the rows have very different consequences:

- `FileInput.checksum_type` — `sha256` is emitted only when the type already says
  `sha256` (`building/rocrate.py:202`), so a non-SHA-256 checksum is **deleted**
  rather than emitted under another key, with no diagnostic at any layer. It is
  also the one field in the table no consumer can recover at all, which is what
  the **unreadable** tier means.
- `SlotDefinition.name` — a producer footgun with consequences for consumers,
  because the files survive while the slot bindings do not. Spelled out in
  `04-slots-and-files.md` §slots.
- `ToolMeta.uri` — benign and already documented: the workflow's `@type` and
  `encodingFormat` are derived from the uri's file extension, so an unrecognised
  extension drops `File` from the type list and drops `encodingFormat` entirely.
  That rule, including which extensions are recognised, is
  `03-entities.md` §workflow.

Separately from losing a property, `SlotDefinition.is_optional` is *inverted* on
the way in, not lost. The table carries a transition column precisely so a row can
say `true`→`false` instead of a verdict that would have to be right about intent.

These are the fields most likely to be "helpfully" wired into a consumer later,
which would create a dependency on something no producer is required to send
correctly. If you need one of them, add it to the format properly: emit it, parse
it, add a rule, and it will appear in `03-entities.md` on the next generation.

**Do not populate `workflow.output`.** Nothing in this library writes it, and the
parse path reads it into `VREPayload.workflow_outputs`, so today that list is
always empty. It is on the list of keys that can never arrive
(`02-envelope.md` §unread keys). A hand-authored crate **may** emit it — the
parser handles it correctly and W011 covers its references — but do not assume a
peer sends it, and do not be surprised that a round trip through this library
produces `workflow_outputs == []`.

**Do not fix the `rrp` vocabulary gap by inventing a URI.** See
`05-vre-vocabulary.md` §gaps. The empty-`identifier` crate is currently the
documented behaviour of a live format; the fix is an identity decision, not a
code change.

**Do not run `black` over this repository.** Not a wire-format matter, but it will
cost the next person an hour: `black --check` wants to rewrite a large fraction of
the tree including most of `examples/`, so any formatting commit buries the real
diff. `examples/sciencemesh.py`'s grouped import block is deliberately
unformatted.

## Renames, for anyone reading older material

Commit `04ff146` ("Transformation to req-packager domain language") renamed most of
this vocabulary. Documents older than it — including both files in `plans/` and
large parts of `README.md` — use the old names:

| current | old |
|---|---|
| `VRELaunchRequest` | `MinimalVRERequest` |
| `VREPayload` | `RequestPackage` |
| `VREPayloadBuilder` | `RequestPackageBuilder` |
| `models/payload.py` | `models/package.py` |
| `building/payload.py` | `building/package.py` |
| `SlotValue` = `str \| int \| float \| bool \| FileInput` | a `{value, file}` dataclass |

`build_from_minimal()` and `ROCrateParser.parse()` in `README.md`'s snippets **do
not exist**; the two entry points are `RocrateBuilder.build_from_launch_request`
and `VREPayloadBuilder.build`. `tests/fixtures/*/simple_example.json` are legacy
files in the pre-rename request format, referenced by no test — not API examples.
`build/` and `src/*.egg-info/` are stale, gitignored build artefacts whose
`PKG-INFO` is an old README.
