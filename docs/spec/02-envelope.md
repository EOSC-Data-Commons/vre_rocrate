# 02 · Envelope

## Top level

Exactly two keys. No other key is read by anything on either side.

```json
{
  "@context": "https://w3id.org/ro/crate/1.1/context",
  "@graph": [ ... ]
}
```

`@context` is that single string in every crate here — a URL, not an inline
object. A producer **MUST** emit it (RO-Crate requires it) but a consumer
**MUST NOT** branch on it: it has never varied and carries no profile
information. Version information lives in `conformsTo` on the descriptor —
see `01-conformance.md` §version negotiation.

## `@graph`

A flat array. No nesting: every relationship between entities is an `@id`
reference. This matters for implementers coming from an object-document mindset —
there is no containment to walk, and the only traversal that matters starts at
`./`.

### Entity order

`@graph` is emitted in a fixed order:

<!-- BEGIN GENERATED emission-order -->
```json
1. ro-crate-metadata.json
2. ./
3. https://example.org/workflow.ga
4. #galaxy-lang
5. https://example.org/data/input.fastq
6. https://example.org/data/attachment.csv
7. #input-in1
8. #input-lit
9. https://example.org/dataset/doi/10.5072/test
10. #tool-metadata
11. #author-dispatcher
12. #workflow-hub
13. #license-unspecified
```
<!-- END GENERATED -->

**This order carries no meaning that any consumer in this stack relies on.** The
golden crates under `generated/examples/` are sorted by `@id` for diffability, so
they do *not* show emission order — emission order lives here, and `@id` order is
what you will actually see in the artefacts. A consumer **MUST NOT** depend on
`@graph` order, because nothing guarantees it across producers. A producer
**SHOULD** emit the descriptor first, because that is the RO-Crate convention and
some readers assume it.

What *is* order-bearing is `root.hasPart` — see §order that matters below.

## `@id` allocation

<!-- BEGIN GENERATED id-rules -->
- a File's @id is its url, falling back to its bare name when it has no url - so two nameless-url files sharing a name collide
- a File's @id MUST differ from the workflow @id, otherwise the file disappears from VREPayload.input_files
- @id MUST be unique across the whole @graph; duplicates are NOT rejected by validation
<!-- END GENERATED -->

<!-- BEGIN GENERATED id-table -->
| `@id` | role | meaning |
|---|---|---|
| `ro-crate-metadata.json` | root-descriptor | Crate root descriptor. MUST be the first @graph entity. Declares the base RO-Crate profile and the wire format profile in conformsTo. |
| `./` | root-dataset | Root dataset. The anchor for the whole payload: mainEntity and hasPart are read from here and nowhere else. |
| `<tool.uri>` | workflow | The workflow / mainEntity. Its @id IS the workflow uri - there is no separate identifier - and it is also a root hasPart member. |
| `#<vre_type>-lang` | computer-language | ComputerLanguage carrying the VRE identity token in `identifier`. This is the ONLY place the target VRE is declared. |
| `#input-<slot.id>` | formal-parameter | A tool-declared input slot. @id derives from slot.id but values are looked up by slot.name, so id and name are different keys. |
| `<file.url, or the bare name when there is no url>` | file | A data file, reachable ONLY through root hasPart. Slot-bound and free-form files are structurally identical here and differ only in whether a FormalParameter's defaultValue points at them. |
| `<dataset.url>` | input-dataset | Optional Dataset for a browsed dataset. @id IS the dataset url. |
| `#tool-metadata` | tool-metadata | Opaque Thing carrying rawDefinition - the producer's own tool definition, round-tripped untouched. |
| `#author-dispatcher` | author-placeholder | Placeholder Person credited as root creator. |
| `#workflow-hub` | publisher-placeholder | Placeholder Organization carried as sdPublisher. |
| `#license-unspecified` | license-placeholder | Placeholder CreativeWork, emitted because a builder cannot assert a license on the producer's behalf. Never read by the parser and absent from every crate not built by this library - an emitter convention, not a protocol feature. |
<!-- END GENERATED -->

Two consequences worth restating because they are silent:

- **Two files with no `url` and the same `name` collapse.** Their `@id`s are
  identical, so W002 fires and — because `_find_entity` returns the first match —
  the second file is unreachable while remaining visible in `@graph`. Nothing
  raises.
- **A file whose `@id` equals the workflow's `@id` disappears from
  `VREPayload.input_files`,** which excludes the descriptor by `@id` match.
  Reachable through the public API: pass a `FileInput` whose `url` is the tool
  uri. Both shapes are demonstrated in
  `generated/negatives/W002.json` and `generated/negatives/W009.json`.

### The `#` prefix

`#`-prefixed ids (`#galaxy-lang`, `#input-pdb_id`, `#tool-metadata`,
`#author-dispatcher`, `#workflow-hub`, `#license-unspecified`) are document-local
fragments with no meaning outside the crate. A consumer **MUST NOT** resolve them
against a base URI or fetch them. Everything else — workflow, file, and dataset
ids — is a real URL that doubles as the entity's identity. There is no separate
identifier field for any of them: **the `@id` *is* the workflow/file/dataset
identity.**

A slot's `@id` is `#input-<slot.id>` while its `name` is `slot.name`, and the two
serve different purposes (see `04-slots-and-files.md`). A name can therefore put
arbitrary text into an identifier — `examples/sciencemesh.py` produces
`#input-Shared With`, with a space. Treat `@id` as an opaque string; **MUST NOT**
parse structure out of it beyond exact-match on the reserved patterns above.

## Reference forms

A reference is `{"@id": "..."}` or, in JSON-LD, a bare string. These are
equivalent in JSON-LD and **not** equivalent here:

<!-- BEGIN GENERATED reference-forms -->
| property | alternative form | same value as an object (control) | difference vs control | linter says |
|---|---|---|---|---|
| `mainEntity` — root mainEntity | bare string → files=`3`, input_files=`2`, workflow_inputs=`2`, workflow_outputs=`0` | object with @id → files=`3`, input_files=`2`, workflow_inputs=`2`, workflow_outputs=`0` | — | **nothing** |
| `hasPart` — root hasPart, all four entries as bare ids | bare strings → files=`3`, input_files=`2`, workflow_inputs=`2`, workflow_outputs=`0` | list of 4 object with @id → files=`3`, input_files=`2`, workflow_inputs=`2`, workflow_outputs=`0` | — | **nothing** |
| `programmingLanguage` — workflow programmingLanguage | bare string → *AttributeError* | object with @id → files=`3`, input_files=`2`, workflow_inputs=`2`, workflow_outputs=`0` | *rejected* | W005 |
| `input` — workflow input, one slot, as a bare id instead of an object | bare string inside the array → files=`3`, input_files=`2`, workflow_inputs=`0`, workflow_outputs=`0` | list of 1 object with @id → files=`3`, input_files=`2`, workflow_inputs=`1`, workflow_outputs=`0` | **workflow_inputs** 1→0; **slot values differ** | W014 |
| `input` — workflow input, both slots, as bare ids | bare strings → files=`3`, input_files=`2`, workflow_inputs=`2`, workflow_outputs=`0` | list of 2 object with @id → files=`3`, input_files=`2`, workflow_inputs=`2`, workflow_outputs=`0` | — | **nothing** |
| `input` — workflow input pointing at a missing FormalParameter | reference to a @id that is not in @graph → files=`3`, input_files=`2`, workflow_inputs=`0`, workflow_outputs=`0` | list of 1 object with @id → files=`3`, input_files=`2`, workflow_inputs=`1`, workflow_outputs=`0` | **workflow_inputs** 1→0; **slot values differ** | W011 |
| `output` — workflow output pointing at a missing FormalParameter | reference to a @id that is not in @graph → files=`3`, input_files=`2`, workflow_inputs=`2`, workflow_outputs=`0` | list of 2 object with @id → files=`3`, input_files=`2`, workflow_inputs=`2`, workflow_outputs=`2` | **workflow_outputs** 2→0; **slot values differ** | W011 |
| `input` — input reference that also carries name/defaultValue | inline object carrying the properties itself → files=`3`, input_files=`2`, workflow_inputs=`1`, workflow_outputs=`0` | list of 1 object with @id → files=`3`, input_files=`2`, workflow_inputs=`1`, workflow_outputs=`0` | — | **nothing** |
<!-- END GENERATED -->

<!-- BEGIN GENERATED reference-forms-verdict -->
- **tolerated, no loss**: `mainEntity on ./ (bare string)`, `hasPart on ./ (bare strings)`, `input on https://example.org/workflow.ga (bare strings)`, `input on https://example.org/workflow.ga (inline object carrying the properties itself)`
- **fatal**: `programmingLanguage on https://example.org/workflow.ga (bare string)`
- **data loss, and the linter says so**: input on https://example.org/workflow.ga (bare string inside the array) -> workflow_inputs 1->0 [W014]; input on https://example.org/workflow.ga (reference to a @id that is not in @graph) -> workflow_inputs 1->0 [W011]; output on https://example.org/workflow.ga (reference to a @id that is not in @graph) -> workflow_outputs 2->0 [W011]
- **data loss with NO rule firing** — the rows a consumer can't detect: **none**

Control row (all four counts at their healthy values): files=`3`, input_files=`2`, workflow_inputs=`2`, workflow_outputs=`0`.
<!-- END GENERATED -->

So: a producer **MUST** always write the object form. The positions that tolerate
a bare string do so incidentally; there is no promise, and `programmingLanguage`
— the one field you cannot do without — crashes the parser on the string form.
The single case where the *object* form itself is wrong is `runtimePlatform`,
which is a plain string in the core profile and may be a reference in the
infrastructure profile (`06-payload-profile.md`).

`defaultValue` on a `FormalParameter` is genuinely polymorphic — a literal for a
scalar slot, an `@id` reference for a file-bound slot — and that distinction is
the subject of `04-slots-and-files.md`.

## List-valued properties

Four properties are arrays in every crate this library emits. A producer **MUST**
emit the array form **even with exactly one element**, because the parse path
iterates these values directly. A serialiser that drops the wrapper around a
one-element list — a default in several XML/YAML-to-JSON bridges, and an
easy mistake in any language whose JSON library treats a single-element
collection as a scalar — produces a crate that is still valid JSON, still has a
`@context`, and still parses without an exception. What changes is the count.

The table below is measured: each row takes one property of a real built crate and
runs the real parser over the same crate twice, once with the array intact and
once with the lone element substituted for the array.

<!-- BEGIN GENERATED array-forms -->
| list-valued property | builder emits | array intact | array wrapper dropped | lost | linter today | …without W014 |
|---|---|---|---|---|---|---|
| `hasPart` on `./` | list of 4 | files=`3`, input_files=`2`, workflow_inputs=`2`, workflow_outputs=`0` | files=`0`, input_files=`0`, workflow_inputs=`2`, workflow_outputs=`0` | **files** 3→0, **input_files** 2→0 | W008, W014 | W008 |
| `input` on `https://example.org/workflow.ga` | list of 2 | files=`3`, input_files=`2`, workflow_inputs=`2`, workflow_outputs=`0` | files=`3`, input_files=`2`, workflow_inputs=`0`, workflow_outputs=`0` | **workflow_inputs** 2→0 | W014 | **silence** |
| `output` on `https://example.org/workflow.ga` | list of 2 | files=`3`, input_files=`2`, workflow_inputs=`2`, workflow_outputs=`2` | files=`3`, input_files=`2`, workflow_inputs=`2`, workflow_outputs=`0` | **workflow_outputs** 2→0 | W014 | **silence** |
| `conformsTo` on `ro-crate-metadata.json` | list of 2 | files=`3`, input_files=`2`, workflow_inputs=`2`, workflow_outputs=`0` | files=`3`, input_files=`2`, workflow_inputs=`2`, workflow_outputs=`0` | — | W012 | W012 |
<!-- END GENERATED -->

<!-- BEGIN GENERATED array-forms-verdict -->
Producer baseline: files=`3`, input_files=`2`, workflow_inputs=`2`, workflow_outputs=`0`.

**Silently emptied today** - accepted by the parser, no linter rule fires, and the count is lower than the same crate with the array wrapper intact: **nothing**; every collapse in the table trips at least one rule.

**What rule W014 is for.** Re-running the same crates against a linter without W014 leaves these losses completely undetected, which is the state this spec was in before the rule existed:

- input on https://example.org/workflow.ga: workflow data workflow_inputs 2->0
- output on https://example.org/workflow.ga: workflow data workflow_outputs 2->0

(`hasPart` is not in that list only because W008 happens to fire there as well. The `input` and `output` collapses had no other cover: a dropped array wrapper there returns a **successfully parsed** crate with an empty slot list, no exception, and no diagnostic of any kind.)
<!-- END GENERATED -->

The lesson is asymmetric, and both halves matter. For a producer: **always write
the array**, including for `output`, which this library never populates but a
hand-authored crate might. For a consumer of a crate from an unknown producer:
**normalise before iterating** — accept a bare object wherever the profile says
array — because the alternative is reporting a successful run with zero inputs.
Note that the linter catches this now and the parser deliberately does not:
making the parser tolerant would hide the producer bug, and making it raise
would break the additive-only promise on a shape that is legal JSON-LD.

## Types

`@type` is a string or an array of strings and a consumer **MUST** handle both.
Observed consistently in the goldens:

| entity | `@type` shape |
|---|---|
| workflow | **always an array**, `["File", "SoftwareSourceCode", "ComputationalWorkflow"]` — or two entries with no `File` (see `03-entities.md` §workflow) |
| everything else | always the single string |

Matching is on **type membership**, not equality — `"File" in types` — except in
one place (`parsing/infrastructure.py:39` does an exact `!= "File"` comparison,
which is rule W013's root cause).

## Order that matters

`root.hasPart` is an ordered list and **`VREPayload.files` comes out in that
order.** A producer that cares about file ordering (a workflow whose first input
is its primary input) **MUST** express it in `hasPart`, and a consumer **MUST
NOT** re-sort before handing files to a handler.

Per-golden provenance states this explicitly for every file under
`order_is_meaningful`, and the things this library provably ignores under
`ignored_by_this_library`:

- `@graph` order — irrelevant; `hasPart` order is the real order;
- the *value* of `datePublished` and `dateCreated` — parsed but never compared.

The last point has a practical edge: **do not write a test that compares
`datePublished` between two crates**, and do not derive cache keys or ids from
it. `RocrateBuilder` calls `datetime.now(utc)` twice per build, for
`root.datePublished` (full ISO) and `workflow.dateCreated` (date only), from
separate calls — an unfrozen build at 23:59:59.999Z can legitimately produce
`2025-12-31T23:59:59.999Z` and `2026-01-01` in one crate. The goldens are
generated under a frozen clock (`2000-01-01T00:00:00+00:00`) rather than scrubbed,
so they remain valid crates you can feed to a parser.

## Unread keys, and keys that can never arrive

Some keys the parser reads cannot be produced by any request this library
accepts. A consumer **MAY** implement them; a producer **MUST NOT** assume a peer
sends them; a producer **MAY** send them by hand-authoring a crate:

<!-- BEGIN GENERATED unemitted-keys -->
- `contentLocation` - read at `src/vre_rocrate/parsing/infrastructure.py:48`
- `installUrl` - read at `src/vre_rocrate/parsing/infrastructure.py:86`
- `memoryRequirements` - read at `src/vre_rocrate/parsing/infrastructure.py:87`
- `output` - read at `src/vre_rocrate/building/payload.py:61`
- `processorRequirements` - read at `src/vre_rocrate/parsing/infrastructure.py:80`
- `storageRequirements` - read at `src/vre_rocrate/parsing/infrastructure.py:90`
<!-- END GENERATED -->

`output` is the notable one: the parse path reads `workflow.output` into
`VREPayload.workflow_outputs`, the builder never writes it, and no documented
entity shape produces it. `workflow_outputs` is therefore **always empty** for a
core-profile crate. Do not build a feature on it without negotiating a profile
bump.
