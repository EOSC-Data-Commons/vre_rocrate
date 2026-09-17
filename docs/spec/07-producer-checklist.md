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
   — `02-envelope.md` §top level
2. Make `@graph[0]` the root descriptor, `@id` exactly
   `ro-crate-metadata.json`, `@type` `CreativeWork`, with `about → {"@id": "./"}`.
   — W012, `03-entities.md` §root-descriptor
3. Declare both profiles in `conformsTo`, base first, as an **array of two
   references**: `https://w3id.org/ro/crate/1.1` then
   `https://w3id.org/eosc-vre/req-packager/1.0`. — W012, `01-conformance.md`
4. Emit exactly one root dataset with `@id` exactly `./`, carrying `mainEntity`
   and `hasPart`. — W003, W007
5. Point `mainEntity` at a workflow entity that **exists in `@graph`**, using the
   `{"@id": ...}` object form. — W004, `02-envelope.md` §reference forms
6. Emit exactly one `ComputerLanguage` entity and reference it from
   `workflow.programmingLanguage` as an object. Its `identifier` must be
   non-empty and taken verbatim from the vocabulary table. — W005, W006,
   `05-vre-vocabulary.md`

## Identity

7. Give every entity a **non-empty string `@id`**. — W001
8. Make every `@id` **unique across `@graph`**. Validation will *not* catch a
   duplicate — the first match wins and the shadowed entity vanishes. — W002
9. Never build structure into an `@id` beyond the two reserved patterns
   `#input-<slot.id>` and `<file-url-or-name>`. `#input-Shared With` has a space
   in it and that is legal. — `02-envelope.md` §`@id` allocation
10. Treat all URIs as opaque strings **except** `programmingLanguage.identifier`,
    which is the only URI in the format that gets interpreted. —
    `05-vre-vocabulary.md` §resolution order

## Files

11. List **every** `File`-typed entity in `root.hasPart`, including the workflow
    descriptor. A `File` absent from `hasPart` does not exist to a consumer, even
    though it validates and parses. — W008, `04-slots-and-files.md` §files
12. Keep `hasPart` in the order you want files delivered: `VREPayload.files`
    preserves it and nothing re-sorts. — `02-envelope.md` §order that matters
13. Never let a data file share its `@id` with the workflow entity: consumers
    exclude the descriptor by `@id` match, so the collision silently deletes a
    real input file. — W009
14. If you emit `sha256`, emit 64 lowercase hex characters. Nothing validates it
    on the way out; it is copied verbatim from the request. — W010
15. A file with no `url` gets a bare-name `@id` (`notebook.ipynb`). Fine, but
    then never assume `@id` is a URI. — `04-slots-and-files.md` §files

## Slots

16. One `FormalParameter` per declared slot, `@id` `#input-<id>`, referenced from
    `workflow.input[]`. An unresolvable reference makes the slot silently never
    exist. — W011, `04-slots-and-files.md` §slots
17. `name` must be exactly the string the target VRE looks up, spaces included.
    *(not machine-checked — only the target VRE knows its expected names)*
    — `04-slots-and-files.md` §slots
18. Write a file-bound slot's `defaultValue` as `{"@id": ...}`, a literal slot's
    as the scalar itself. — `04-slots-and-files.md` §binding
19. Do not put a URL in a literal slot's `defaultValue` if a file with that `@id`
    is also in the crate — the parse path resolves it and the slot becomes a file
    binding regardless of `additionalType`. *(W011 covers a **missing** target, not
    a colliding one, so nothing catches this)* — `04-slots-and-files.md` §binding

## Shapes that break silently

20. **Every list-valued property MUST be an array, even with exactly one
    element**: `hasPart`, `input`, `output`. Collapsing `input` to a bare object
    parses successfully and returns an **empty slot list** — no exception, and
    the only thing that catches it is rule W014. This is the most common bug from
    serialisers that drop single-element wrappers. — W014, `02-envelope.md`
    §list-valued properties
21. Always write references as `{"@id": ...}`. Bare strings happen to work in
    `mainEntity` and `hasPart` and **crash the parser** in `programmingLanguage`.
    The tolerance is incidental, not a promise. — `02-envelope.md` §reference forms
22. Handle `@type` as string-or-array when reading; the workflow entity is always
    an array, everything else a string. — `02-envelope.md` §types

## Vocabulary and profile

23. `vre_type` never appears in the crate. Route on
    `programmingLanguage.identifier`, exactly, with no URI normalisation — some
    identifiers have a trailing slash and some do not. — `05-vre-vocabulary.md`
24. Do not use `name` or `url` to identify the VRE. Sciencemesh's `name` is
    "Jupyter Notebook". — `05-vre-vocabulary.md`
25. Emit the core profile (`runtimePlatform` as a URL string) unless you are
    deliberately the infrastructure side. Nothing in this repository can generate
    the infrastructure profile, so there is no worked example to copy — and its
    `RuntimePlatform.input` entries must be **inline entities carrying `@type:
    "File"`**, not references, or they are dropped with a log warning. — W013,
    `06-payload-profile.md`

## Timestamps and placeholders

26. `datePublished` (full ISO 8601, on the root) and `dateCreated` (date-only, on
    the workflow) are **parsed and never compared**. Never diff them between
    crates or derive a cache key from them. — `02-envelope.md` §order that matters
27. Every generated crate carries three placeholder entities — `#author-dispatcher`,
    `#workflow-hub` ("Example Workflow Hub", `http://example.com/workflows/`),
    and `#license-unspecified`. A crate asserting an unspecified license is
    conformant, so consumers **MUST NOT** treat `license` as trustworthy, and
    producers **SHOULD** replace all three with real entities when they have real
    values. *(not machine-checked)* — `03-entities.md`
28. `raw_definition` round-trips verbatim through the `#tool-metadata` entity.
    Put tool-specific extras there rather than inventing new top-level keys.
    — `03-entities.md` §tool-metadata

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
