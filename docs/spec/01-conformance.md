# 01 · Conformance

## RFC 2119 in this dialect

A **MUST** is backed by code that breaks. Each rule in the table below names the
consequence and the `file:line` where the behaviour lives, so a producer can
check the claim rather than trust the prose. The provenance is resolved from the
live source at generation time; if a cited symbol is renamed or deleted,
`tools/gen_wire_spec.py` refuses to run rather than publish a stale pointer.

## Profiles

A **profile** is a shape of crate, named by a URI in the root descriptor's
`conformsTo`. The two profiles are **alternatives, not layers** — a crate
conforms to exactly one, and the one it conforms to is decided by whether it
carries a `RuntimePlatform` entity:

| Profile | URI / file | A crate conforms to it when | Emitted by `RocrateBuilder`? |
|---|---|---|---|
| base RO-Crate 1.1 | `https://w3id.org/ro/crate/1.1` | always (first entry of `conformsTo`) | yes |
| **core** | `generated/schema-core.json` | no `RuntimePlatform` entity exists | **yes — always** |
| **infrastructure** | `generated/schema-infrastructure.json` | a `RuntimePlatform` entity exists | no — TOSCA-authored only |

Pick the schema matching the crate you hold. Validating a core crate against the
infrastructure schema fails, and vice versa: the infrastructure schema *requires*
a `RuntimePlatform` and the core schema *forbids* one. That is deliberate —
otherwise a schema would silently accept a crate whose profile the checker never
established.

### Version negotiation

The descriptor's `conformsTo` is an ordered two-entry list; the base RO-Crate
profile comes first so a consumer that only understands RO-Crate 1.1 keeps
working.

<!-- BEGIN GENERATED profile-literals -->
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

`https://w3id.org/eosc-vre/req-packager/1.0` is this dialect's version. Its
policy:

- **Additive change** — a new optional property, a new entity type, a new
  `vre_type`, a new `encodingFormat` value. Shipped under the **same** URI. A
  consumer **MUST** ignore properties and entity types it does not recognise; a
  consumer that rejects unknown keys on additive releases **MUST NOT** expect
  this library to accommodate that.
- **Breaking change** — removing or renaming a property, changing a property's
  type, changing what a reserved `@id` means, changing which entity is the
  anchor. Requires a new profile URI (`…/req-packager/2.0`) and a
  `08-migration-notes.md` entry. A consumer **MAY** treat an unrecognised profile
  URI as a hard error; that is the safety valve the URI exists for.

The <!-- GEN:fixture-input-count -->13 fixtures under `generated/examples/`
with `origin: "fixture-input"` carry
no profile URI at all — they predate it. They are **not** non-conformant in the
sense of being unparseable; they simply cannot be version-negotiated, which is
rule W012, and the reference parser reads all
<!-- GEN:fixture-input-count -->13 without complaint.

## What "valid" means, and the three levels of it

1. **Parses** — `ValidationPipeline.validate_basic` accepts it: every entity has
   a non-empty `@id`, `mainEntity` resolves, `programmingLanguage` is an object
   with a non-empty `identifier`. Three checks. Nothing else.
2. **Schema-valid** — passes the JSON Schema for its profile. Covers
   <!-- GEN:core-encodable-count -->7 rules under the core profile,
   <!-- GEN:schema-encodable-count -->8 under infrastructure, of
   <!-- GEN:rule-count -->14 in total. The one rule the core profile leaves out is
   W013, and it is not an omission: the core schema rejects any
   `RuntimePlatform` entity outright, so there is nothing for W013 to constrain
   there.
3. **Conformant** — violates none of the <!-- GEN:rule-count -->14 rules. Only
   the linter can tell you this.

These are strictly different sets, and the gap is not theoretical: the
`generated/examples/galaxy_tosca_stage__ro-crate-metadata.json` fixture parses
fine, and violates W008 and W013.

## The rules

<!-- BEGIN GENERATED rule-table -->
| rule | requirement | if you don't | checked by | decided at |
|---|---|---|---|---|
| W001 | every @graph entity declares a non-empty string @id | ValidationPipeline rejects the crate | schema + linter | `src/vre_rocrate/parsing/validator.py:54` |
| W002 | @id values are unique across @graph | validation does NOT catch this: dereferencing returns the first match and the shadowed entity is silently lost | **linter only** | `src/vre_rocrate/parsing/validator.py:8` |
| W003 | a root dataset with @id './' exists and declares mainEntity | ValidationPipeline rejects the crate | schema + linter | `src/vre_rocrate/parsing/validator.py:73` |
| W004 | mainEntity resolves to an entity that exists in @graph | ValidationPipeline rejects the crate | **linter only** | `src/vre_rocrate/building/payload.py:192` |
| W005 | the workflow declares programmingLanguage as an object with @id | a bare string passes validation but crashes the parser; an array crashes both | schema + linter | `src/vre_rocrate/parsing/validator.py:88` |
| W006 | programmingLanguage resolves to an entity with a non-empty identifier | validation requires the key but not that it be non-empty; an empty value yields vre_type 'unknown' downstream | **linter only** | `src/vre_rocrate/building/payload.py:79` |
| W007 | root dataset declares hasPart (an empty list is legal) | a missing hasPart raises TypeError deep in the parser, with no useful message | schema + linter | `src/vre_rocrate/building/payload.py:119` |
| W008 | every File entity appears in root hasPart | hasPart is the ONLY enumeration source for files; a File entity absent from it is invisible to consumers. RocrateBuilder never emits this shape, but the TOSCA-authored galaxy_tosca_stage fixture does, so the rule is about hand-authored producers | **linter only** | `src/vre_rocrate/building/payload.py:119` |
| W009 | no File entity shares its @id with the workflow | VREPayload.input_files excludes the descriptor by @id, so a colliding file is dropped from the data files. A crate cannot make this mistake without ALSO duplicating an @id, so W002 always fires alongside it | **linter only** | `src/vre_rocrate/models/payload.py:106` |
| W010 | a sha256 property, when present, is a 64-character lowercase hex digest | this library copies FileInput.checksum verbatim and does not check its shape, so a truncated or non-hex digest is published as-is and only fails a consumer that verifies it | schema + linter | `src/vre_rocrate/building/rocrate.py:189` |
| W011 | every reference in workflow.input and workflow.output resolves to an entity in @graph | unresolvable references are skipped, so the slot silently never exists for the consumer. Note that an inline FormalParameter object is NOT a substitute for a graph entity: only its @id is read, and the entity with that @id supplies every property, so inline properties are ignored | **linter only** | `src/vre_rocrate/building/payload.py:145` |
| W012 | the root descriptor declares the wire format profile | consumers cannot detect a payload shape change | schema + linter | `src/vre_rocrate/building/rocrate.py:90` |
| W014 | every hasPart, input and output value is a list, even with exactly one element | the parse path iterates these values directly, so a single object instead of a one-element array iterates its members and yields nothing: the slot list or file list comes back EMPTY with no exception and no other rule firing. Serialisers that omit the wrapper for a lone element are common, which makes this the cheapest way to lose a whole payload section in a non-Python producer | schema + linter | `src/vre_rocrate/building/payload.py:145` |
| W013 | INFRASTRUCTURE PROFILE ONLY: each entry in a RuntimePlatform's input array is a full inline entity carrying @type "File", not a "{"@id": "..."}" reference to one | parsing/infrastructure.py reads @type off the entry itself and never dereferences a reference, so a reference logs "Input is not of type File, skipping." and the input file silently does not exist in RuntimePlatform.input_files | schema + linter | `src/vre_rocrate/parsing/infrastructure.py:33` |
<!-- END GENERATED -->

Rules are **reported, not short-circuited**: the linter evaluates every rule
whose preconditions resolve, so a crate with three problems reports three.
Where a rule cannot be judged because the entity it is stated about is missing,
the linter returns it under `undecidable` rather than as a pass:

```python
from wire_spec_lint import lint_report
lint_report(crate)
# {"violations": ["W003"],
#  "undecidable": ["W004", "W005", "W006", "W007", "W008", "W009", "W011"]}
```

A conformance harness **MUST** treat `undecidable` as a non-pass. A crate with no
root descriptor is not "clean on 12 checks"; it is unjudgeable on 12 checks.

Two rules are inseparable: violating W009 (a file sharing the workflow's `@id`)
necessarily duplicates an `@id`, so W002 always fires alongside it. That is a
property of the wire format, not of the linter, and the negative fixture for W009
expects both.

### What a schema cannot say

<!-- BEGIN GENERATED encodability -->
- `schema-core.json` enforces: W001, W003, W005, W007, W010, W012, W014
- `schema-infrastructure.json` enforces: W001, W003, W005, W007, W010, W012, W013, W014
- **no schema can enforce**: W002, W004, W006, W008, W009, W011 - each needs a lookup across `@graph`, which JSON Schema `contains` cannot express
<!-- END GENERATED -->

`generated/schemas.json` records this per profile and per rule, including which
clause carries each rule — `entity` (a property constraint on one entity) or
`graph` (a `contains` constraint over `@graph`). Testing an entity-level rule
against whole-crate validation, or a `graph`-level rule against individual
entities, produces a false "the schema is broken" report. The `enforcement` field
tells you which is which.

### Proving a validator has teeth

`generated/negatives/` holds exactly one deliberately-broken crate per rule, with
the expected verdict recorded in `negatives.json`. This exists because a rule
nothing violates is indistinguishable from a rule that cannot be violated — two
of this spec's own tests were caught vacuous by that standard.

<!-- BEGIN GENERATED negative-index -->
| file | what it does wrong | linter must report |
|---|---|---|
| `negatives/W001.json` | a support entity whose @id is the empty string | W001 |
| `negatives/W002.json` | two FileInputs with no url and the same name, so both get @id = name (reachable through the public API) | W002 |
| `negatives/W003.json` | the root dataset './' is absent entirely | W003 |
| `negatives/W004.json` | mainEntity references an entity that is not in @graph | W004 |
| `negatives/W005.json` | programmingLanguage written as a bare string instead of {"@id": ...} | W005 |
| `negatives/W006.json` | the language entity exists but its identifier is empty - validation passes and the consumer gets vre_type 'unknown' | W006 |
| `negatives/W007.json` | the root dataset omits hasPart | W007 |
| `negatives/W008.json` | a File entity present in @graph but absent from root hasPart. This is what the TOSCA-authored fixture galaxy_tosca_stage/ro-crate-metadata.json really contains (#tosca_input_file); RocrateBuilder never produces it, so a producer only hits it by hand-rolling the graph | W008 |
| `negatives/W009.json` | a FileInput whose url is the workflow uri, so the file and the workflow share one @id (reachable through the public API) | W002, W009 |
| `negatives/W010.json` | sha256 truncated to 63 characters | W010 |
| `negatives/W011.json` | workflow.input references a FormalParameter that is not in @graph | W011 |
| `negatives/W012.json` | conformsTo lists only the RO-Crate base profile, so the wire format version is undeclared | W012 |
| `negatives/W013.json` | a RuntimePlatform whose input lists "{"@id": "#file"}" instead of the file's properties inline; the parser reads @type off the entry, finds none, and skips it | W013 |
| `negatives/W014.json` | workflow.input collapses from a one-element array to the bare object; the parser iterates the object's members, finds no @id, and returns no input slots at all | W014 |
<!-- END GENERATED -->

## What a consumer must tolerate

- **Unknown properties on any entity.** Additive releases add them without
  changing the profile URI. `VREPayload`/`FileReference` keep the entire entity
  in a `properties` dict for exactly this reason.
- **Unknown entity types.** `@graph` may hold entities this spec never mentions:
  the `galaxy_tosca_stage` fixture carries `Thing` entities for EDAM topic and
  format URIs (`http://edamontology.org/data_3671`), and `#license-unspecified`
  is a `CreativeWork` nobody asks about.
- **`@type` as either a string or an array.** Every consumer-side read has to
  handle both. The workflow entity is *always* an array; files are always a
  string.
- **References as either a bare string or `{"@id": ...}`.** The builder always
  writes the object form; RO-Crate permits both, and the parser accepts both in
  most positions. One exception is load-bearing and is rule W013.
- **A missing `conformsTo` profile URI**, if you need to read pre-1.0 crates.
- **Empty lists where you might expect absence**: `hasPart: []` is legal and
  means "no parts", distinct from `hasPart` being absent, which is rule W007.

## What a consumer may assume

Because a producer in another language is not running this builder, the
guarantees you may build on are exactly the MUSTs above plus:

- the descriptor is `@graph[0]` and the root dataset is reachable at `./`;
- `mainEntity` and `hasPart` are read from `./` and from no other entity;
- every `@id` is unique and non-empty (W001, W002) — a consumer **MAY** reject a
  crate that violates this, and this library's parser **cannot** handle one that
  does (see W002's consequence);
- a `File` entity listed in `hasPart` has `name` and `license`, and `url` unless
  it is a local file keyed by bare name.

Everything else is conditional; `03-entities.md` states the condition for every
property in the format.
