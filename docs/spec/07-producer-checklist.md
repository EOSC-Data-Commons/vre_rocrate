# 07 · Producer checklist

Self-contained. If you are emitting crates from Java, Go, TypeScript or by hand
and you never open this repository, this file plus `generated/` is enough to
start, and every line cites the section that justifies it so you can check the
claim rather than trust it.

Ordered by "do this or the crate is unusable", then by "do this or it silently
means the wrong thing". **MUST** and **MUST NOT** are normative. Everything here
is enforced by `tools/wire_spec_lint.py` unless marked *(not machine-checked)*.

## Structure

1. Emit `{"@context": "https://w3id.org/ro/crate/1.1/context", "@graph": [...]}`
   and nothing else at the top level. *(not machine-checked — no rule can express
   "you emitted extra top-level keys", and none is needed: consumers ignore them)*
   — [`02-envelope.md` §Top level](02-envelope.md#top-level)
2. Make `@graph[0]` the root descriptor, `@id` exactly
   `ro-crate-metadata.json`, `@type` `CreativeWork`, with `about → {"@id": "./"}`.
   — W012,
   [`03-entities.md` §root-descriptor](03-entities.md#root-descriptor)
3. Declare both profiles in `conformsTo`, base first, as an **array of two
   references**: `https://w3id.org/ro/crate/1.1` then
   `https://w3id.org/eosc-vre/req-packager/1.0`. — W012, [`01-conformance.md` §Version negotiation](01-conformance.md#version-negotiation)
4. Emit exactly one root dataset with `@id` exactly `./`, carrying `mainEntity`
   and `hasPart`. — W003, W007
5. Point `mainEntity` at a workflow entity that **exists in `@graph`**, using the
   `{"@id": ...}` object form. — W004,
   [`02-envelope.md` §Reference forms](02-envelope.md#reference-forms)
6. Emit exactly one `ComputerLanguage` entity and reference it from
   `workflow.programmingLanguage` as an object. Its `identifier` must be
   non-empty and taken verbatim from the vocabulary table. — W005, W006,
   [`05-vre-vocabulary.md`](05-vre-vocabulary.md)

## Identity

7. Give every entity a **non-empty string `@id`**. — W001
8. Make every `@id` **unique across `@graph`**. Validation will *not* catch a
   duplicate — the first match wins and the shadowed entity vanishes. — W002
9. Never build structure into an `@id` beyond the two reserved patterns
   `#input-<slot.id>` and `<file-url-or-name>`. `#input-Shared With` has a space
   in it and that is legal. —
   [`02-envelope.md` §`@id` allocation](02-envelope.md#id-allocation)
10. Treat all URIs as opaque strings **except** `programmingLanguage.identifier`,
    which is the only URI in the format that gets interpreted. —
    [`05-vre-vocabulary.md` §Resolution order](05-vre-vocabulary.md#resolution-order)

## Files

11. List **every** `File`-typed entity in `root.hasPart`, including the workflow
    descriptor. A `File` absent from `hasPart` does not exist to a consumer, even
    though it validates and parses. — W008,
    [`04-slots-and-files.md` §Files](04-slots-and-files.md#files)
12. Keep `hasPart` in the order you want files delivered: `VREPayload.files`
    preserves it and nothing re-sorts. —
    [`02-envelope.md` §Order that matters](02-envelope.md#order-that-matters)
13. Never let a data file share its `@id` with the workflow entity: consumers
    exclude the descriptor by `@id` match, so the collision silently deletes a
    real input file. — W009
14. If you emit `sha256`, emit 64 lowercase hex characters. Nothing validates it
    on the way out; it is copied verbatim from the request. — W010
15. A file with no `url` gets a bare-name `@id` (`notebook.ipynb`). Fine, but
    then never assume `@id` is a URI. —
    [`04-slots-and-files.md` §Files](04-slots-and-files.md#files)

## Slots

16. One `FormalParameter` per declared slot, `@id` `#input-<id>`, referenced from
    `workflow.input[]`. An unresolvable reference makes the slot silently never
    exist. — W011,
    [`04-slots-and-files.md` §Slots](04-slots-and-files.md#slots)
17. `name` must be exactly the string the target VRE looks up, spaces included.
    *(not machine-checked — only the target VRE knows its expected names)*
    — [`04-slots-and-files.md` §Slots](04-slots-and-files.md#slots)
18. Write a file-bound slot's `defaultValue` as `{"@id": ...}`, a literal slot's
    as the scalar itself. —
    [`04-slots-and-files.md` §Binding](04-slots-and-files.md#binding-file-bound-versus-literal-slots)
19. Do not put a URL in a literal slot's `defaultValue` if a file with that `@id`
    is also in the crate — the parse path resolves it and the slot becomes a file
    binding regardless of `additionalType`. *(W011 covers a **missing** target, not
    a colliding one, so nothing catches this)* —
    [`04-slots-and-files.md` §Binding](04-slots-and-files.md#binding-file-bound-versus-literal-slots)

## Shapes that break silently

20. **Every list-valued property MUST be an array, even with exactly one
    element**: `hasPart`, `input`, `output`. Collapsing `input` to a bare object
    parses successfully and returns an **empty slot list** — no exception, and
    the only thing that catches it is rule W014. This is the most common bug from
    serialisers that drop single-element wrappers. — W014,
    [`02-envelope.md` §List-valued properties](02-envelope.md#list-valued-properties)
21. Always write references as `{"@id": ...}`. Bare strings happen to work in
    `mainEntity` and `hasPart` and **crash the parser** in `programmingLanguage`.
    The tolerance is incidental, not a promise. —
    [`02-envelope.md` §Reference forms](02-envelope.md#reference-forms)
22. Handle `@type` as string-or-array when reading; the workflow entity is always
    an array, everything else a string. —
    [`02-envelope.md` §Types](02-envelope.md#types)

## Vocabulary and profile

23. `vre_type` never appears in the crate. Route on
    `programmingLanguage.identifier`, exactly, with no URI normalisation — some
    identifiers have a trailing slash and some do not. —
    [`05-vre-vocabulary.md` §`vre_type` never appears](05-vre-vocabulary.md#vre_type-never-appears-in-the-crate)
24. Do not use `name` or `url` to identify the VRE. Sciencemesh's `name` is
    "Jupyter Notebook". —
    [`05-vre-vocabulary.md` §`vre_type` never appears](05-vre-vocabulary.md#vre_type-never-appears-in-the-crate)
25. Emit the core profile (`runtimePlatform` as a URL string) unless you are
    deliberately the infrastructure side. Nothing in this repository can generate
    the infrastructure profile, so there is no worked example to copy — and its
    `RuntimePlatform.input` entries must be **inline entities carrying `@type:
    "File"`**, not references, or they are dropped with a log warning. — W013,
    [`06-payload-profile.md` §W013](06-payload-profile.md#w013--runtimeplatforminput-entries-are-not-references)

## Timestamps and placeholders

26. `datePublished` (full ISO 8601, on the root) and `dateCreated` (date-only, on
    the workflow) are **parsed and never compared**. Never diff them between
    crates or derive a cache key from them. —
    [`02-envelope.md` §Order that matters](02-envelope.md#order-that-matters)
27. Every generated crate carries three placeholder entities — `#author-dispatcher`,
    `#workflow-hub` ("Example Workflow Hub", `http://example.com/workflows/`),
    and `#license-unspecified` — plus the `creator`/`sdPublisher`/`license`
    references that resolve to them. Emit all six on every crate: **replace** a
    placeholder with a real entity once you have one, but never **omit** it. The
    trio is what makes "this crate has no known author" a stated fact rather than a
    dropped field, and nothing will tell you the difference — deleting all three
    *and* their references is measured as clean by `validate_basic`, the linter and
    the schema, and projects field-for-field identically
    (`generated/must-enforcement.json`, `provenance_deletion`). Copy the literals
    from the section below rather than writing them from memory — they are excerpted
    verbatim there, and an invented value is never reported as wrong.
    Consumers **MUST NOT** treat `license` as
    trustworthy either way. *(not machine-checked)* —
    [`03-entities.md` §The three placeholders](03-entities.md#the-three-placeholders)
28. `raw_definition` round-trips verbatim through the `#tool-metadata` entity.
    Put tool-specific extras there rather than inventing new top-level keys.
    — [`03-entities.md` §tool-metadata](03-entities.md#tool-metadata)

## Before you ship a producer

Run `tools/wire_spec_lint.py` against every crate you generate — stdlib only, no
dependencies, safe to copy into your build:

```console
python3 tools/wire_spec_lint.py path/to/ro-crate-metadata.json
```

It prints `violations` and `undecidable`, and the two are **not** interchangeable:
a rule that could not be evaluated lands in `undecidable`, never as a pass. Treat
a non-empty `undecidable` as a failure of your crate, not of the linter — it
usually means an entity the rule needed is missing.

Then feed yourself `generated/negatives/*.json` — one deliberately broken crate per
rule — and confirm your own validator rejects each for the stated reason. That is
the check that your conformance test can fail; a suite that passes on all 14
negatives is measuring nothing.

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

## Dry run: what implementing this from spec alone found

The claim this file rests on is *"this file plus `generated/` is enough to
start"*. That is a different claim from "the spec matches the Python library",
and only one kind of test can establish it. So: an implementer with no access to
`src/`, `tests/` or `examples/` was given `docs/spec/` and
`tools/wire_spec_lint.py` and asked to emit a ScienceMesh crate from the pages
alone, in a language other than Python, then lint and schema-validate its own
output. It passed both gates. **That is the finding, not the success** — every
guess below was made in the dark and then blessed by a green build.

Recorded because a gap nobody wrote down gets silently re-invented by the next
producer. Fixed ones say so; open ones are open on purpose.

### Caught by nothing, guessed anyway

Ordered roughly hardest-to-guess-first, though nothing measures that; all of them
produce a crate that lints clean, validates, and parses, which is the part that is
measured.

| the guess | where the answer actually was | status |
|---|---|---|
| Whether a `File`'s `url` property is emitted at all, or whether `@id` alone is the address | `building/rocrate.py` writes **both** keys from `FileInput.url`, and `03`'s own prose says so — but the excerpt printed directly under that sentence showed `url` elided, so the page contradicted itself and the reader had to guess which half to copy | **fixed at the generator**, not with a sentence: `_trimmed` exempts `url` from shortening for the same reason it exempts `@id`. Both shapes are now shown verbatim and both are real — `url` present on a builder file, absent on a hand-authored one, and `url` **never** on the builder's own workflow entity |
| The `runtimePlatform` URL for a VRE with none supplied | only the last column of [`05-vre-vocabulary.md`](05-vre-vocabulary.md)'s identity table — `03` marks the field `MUST` and never says where the value comes from | **fixed** — `03` now cites `05` and states that omitting it passes all three checkers |
| Which URL suffix counts as a file extension (`a.final.ipynb`, `FILE.IPYNB`, `x.ipynb?v=2`) | `PurePosixPath(uri).suffix.lower()`, in code only. Getting it wrong drops `File` from the workflow's `@type` and the workflow out of `VREPayload.files`, silently | **fixed** — stated in prose under [`03-entities.md` §workflow](03-entities.md#workflow), with the miss cases named |
| Whether `dateCreated` may be a full datetime | **nowhere**. `format: full-date` looks like a check and is not one — `full-date`/`date-time` are not registered format checkers even with `FormatChecker()` on, so `"not-a-date"` is valid | **documented** in [`02-envelope.md` §Order that matters](02-envelope.md#order-that-matters); deliberately not tightened in the schema, which would reject real inbound crates to catch a shape nothing reads |
| Whether `conformsTo`'s two entries may be swapped | nowhere — **open**. [`08` §`conformsTo` order is meaningful](08-migration-notes.md#conformsto-order-is-meaningful) calls it load-bearing ("consumers keying on the second entry depend on that order") and [`01` §Version negotiation](01-conformance.md#version-negotiation) repeats the rationale; neither, and no checker, acts on it. Re-running the swap here: linter CLEAN, `validate_basic` passes, `schema-core.json` accepts — verified on a probe differing from the baseline in that one array and nothing else. Draft 2020-12 *can* express it (`prefixItems`), so leaving it unenforced is a choice, not a limitation |
| Whether to emit the placeholder trio and every `license` reference at all | [`03` §The three placeholders](03-entities.md#the-three-placeholders) says emit them; nothing checks it, and deleting all three plus their references is measured as byte-clean | **fixed** as far as prose can fix it — the literal objects are now excerpted so they can be copied rather than invented; enforcement is still nothing |
| What `#tool-metadata` should contain when no `raw_definition` was supplied, and where `ToolMeta.id` goes | nowhere in `03`. `ToolMeta.id` is never serialized — one of exactly **two** input fields that alter no byte of the crate, the other being `FileInput.path` — while item 28 above points tool-specific data *at* an entity that most crates omit entirely | **fixed** — [`03` §tool-metadata](03-entities.md#tool-metadata) now says the id legitimately appears nowhere and names `raw_definition` as the only home for extras; the per-field verdicts were already measured, two pages away, in [the field-visibility table under `08` §Prohibitions](08-migration-notes.md#prohibitions) — which is why this row is a wording gap and not a missing measurement |

### Where the spec was wrong, not merely silent

A gap loses you an afternoon; a wrong statement costs you the correctness of a
crate you believe you verified.

- **`additionalType` was documented with counts that did not exist**, and its
  reference form was described as rarer than it is: the builder emits a string,
  the real inbound crates emit `{"@id": "http://edamontology.org/…"}`, and the two
  never co-occur. `VREPayload.additional_type` is annotated `str | None` and hands
  back a `dict` for those crates. The counts now live in
  [`generated/additional-types.json`](generated/additional-types.json) and in the
  generated census table in `03`, which is why none are repeated here: a number
  typed into this section would be the third stale count about the same field.
  `python_types_seen` is measured **through `VREPayloadBuilder`**, so it is
  evidence about the annotation, not an opinion about it.
- **Two prose counts described artefacts that did not exist.** One claimed a
  "14-entity crate / 58 deletions" measurement; the probe crate has 13 entities,
  46 `MUST` rows and 53 deletions. That whole claim is now
  [`generated/must-enforcement.json`](generated/must-enforcement.json), measured
  against the three checkers on every build, and `01` quotes it through inline
  tokens so the sentence cannot outlive its number. The other claimed `03`'s
  `file` table listed "eleven separate `unless` clauses"; it has **9** property
  rows, **6** of them conditional, so the count was simply wrong. That one is
  **deleted rather than corrected to 6** — deliberately, and worth stating
  because the reflex is to fix the digit: a number that has been wrong once in a
  hand-typed place will be wrong again next time the table gains a row, and this
  sentence gains nothing by being exact. If you are tempted to re-type it, note
  that it is the same mistake this section is about.
- **`05` told a producer to check "all four" tables and then listed six names**,
  one of which (`URI_FALLBACK_PATTERNS`) is not a symbol in `constants.py` — the
  URI fallback is an inline list inside `resolve_vre_type`. Corrected to five
  plus the inline list, with the real location.

### What this says about the two gates

Both gates were re-run here before anything above was believed: all
<!-- GEN:negative-count -->14
negatives exit non-zero, all <!-- GEN:builder-output-count -->15
`builder-output` goldens lint CLEAN and pass the
schema for their profile, and the dry-run crate itself passes the linter,
`validate_basic` and `schema-core.json`. (Run the linter across
`generated/examples/` and you will see
<!-- GEN:fixture-input-count -->13 `VIOLATES W012` lines — those are the
fixture-inputs, and that is the expected verdict, not a broken checkout; see
[Not spec defects](#not-spec-defects).) Against those working gates, a
first-attempt crate from a reader with no source access passing immediately
measures **the breadth of the unenforced surface**, which
[`01-conformance.md` §A MUST is not a
check](01-conformance.md#a-must-is-not-a-check) now counts:
<!-- GEN:must-unnoticed-count -->28 of <!-- GEN:must-deletion-count -->53 `MUST`
deletions invisible — plus the two shapes above that are not `MUST` deletions at
all, timestamp format and `conformsTo` order. A producer's green build is close to
a statement about the checker, not the crate.

So the checklist lines above marked *(not machine-checked)* are not caveats
beside the enforced ones — they are the part where your own diligence is the only
mechanism, and they are exactly the ones a fresh implementer skips because the
tool said CLEAN. If you take one thing from this section: **run all three
checkers, then go back through the `MUST` rows in `03` by hand**, because the
table in `01` tells you which ones nothing will tell you about.

### Not spec defects

Recorded so they are not "fixed" into something false.

- **`profile: core` on a `fixture-input` row does not mean it validates.**
  Measured here rather than assumed: all 15 `builder-output` crates pass the
  schema for their labelled profile; **all 13** `fixture-input` crates are
  rejected by it, 9 of them labelled `core`, and the four labelled
  `infrastructure` fail `schema-core.json` too. Nothing is wrong — every one
  predates the profile URI, W012 is encoded in both schemas, and
  `verify_schemas` asserts linter and schema agree on each crate as shipped. The
  defect was that the artefact *invited* the misreading: `profile` reads as a
  verdict and the index's `violates` column is computed with W012 deliberately
  withheld, so a fixture's only real violation rendered as `-`. Both are fixed in
  the artefact — the column now says `violates, W012 withheld`, the
  emitted-types column says what it means, and `examples.json`'s `_note` carries
  the counts, computed. What the four `infrastructure` fixtures additionally fail
  is a `RuntimePlatform` **entity** where the core schema demands a url string —
  [what such an entity carries](06-payload-profile.md#what-a-runtimeplatform-entity-carries),
  and the `plans/` item that would let the builder emit one. Not a bug in either
  schema.
  Consumer framing stays in
  [`HANDOFF.md` §Give to a consumer](HANDOFF.md#give-to-a-consumer).
- A `## W013 — RuntimePlatform.input entries…` heading resolves to a **double**
  hyphen: under GitHub's slugger the em dash is dropped and both surrounding
  spaces become hyphens, so
  `#w013--runtimeplatforminput-entries-are-not-references` is correct even though
  it looks mistyped. A naive link checker reports it broken. It is linked that way
  from here and from `08-migration-notes.md`, and
  `tests/test_spec/test_wire_spec.py::test_spec_cross_references_resolve_as_links`
  implements GitHub's rule, so a passing suite agrees with GitHub and not with the
  checker. Do not "fix" the double hyphen.
- Rule tables list W014 before W013, in the order `LINT_RULES` declares them.
  Harmless while nothing says "the thirteenth rule", and renumbering would churn
  every negative filename for no correctness gain.
