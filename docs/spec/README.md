# EOSC VRE req-packager wire format

The normative reference for the RO-Crate document that passes between the EOSC
VRE components. Read this if you produce, consume, or route that document and you
are **not** using the Python library that generates it.

Everything here describes one artefact: a JSON object with `@context` and
`@graph` — a RO-Crate 1.1 layout — posted by a request packager to a dispatcher,
which forwards it to a VRE-specific handler.

## Who you are, and what to read

| You | Read |
|---|---|
| **Producing** a crate (emitting from Go / Java / TS / …) | `HANDOFF.md`, then `03-entities.md`, then work through `07-producer-checklist.md` and validate against `generated/negatives/` |
| **Consuming** a crate (a dispatcher or VRE handler) | `01-conformance.md` §"What a consumer must tolerate", then `03-entities.md`, then `06-payload-profile.md` if you deploy infrastructure |
| **Routing** on the target VRE | `05-vre-vocabulary.md`, `01-conformance.md` §version negotiation |
| Reviewing a change to this repo's builder | `HANDOFF.md` §maintaining |

## Normative language

**MUST**, **MUST NOT**, **SHOULD**, and **MAY** carry their RFC 2119 meaning.
A **MUST** here is a promise that something breaks if you ignore it — every one
is stated with the specific failure it prevents and the `file:line` of the code
that enforces or observes it. Where a rule is only advisory, the text says what
degrades.

Anything not marked is descriptive. The wire format is a dialect, not a superset
of RO-Crate 1.1: see `08-migration-notes.md` for the deltas and the deliberate
omissions.

## Two guarantee layers, and why both exist

1. **A dependency-free rule linter** — `tools/wire_spec_lint.py`, pure stdlib,
   no imports from this repo. Copy it into your service and call `lint(crate)`.
   It is Layer 1 because it always runs: `jsonschema` is not a runtime
   dependency of anything here, so a schema-only check would skip silently on
   the machines where it matters.
2. **JSON Schema 2020-12** — `generated/schema-core.json` and
   `generated/schema-infrastructure.json`. Portable to any language, which is
   why they exist. Together they cover **<!-- GEN:schema-encodable-count -->8
   of <!-- GEN:rule-count -->14 rules**; see `01-conformance.md` §what a schema
   cannot say.

**A crate that validates against the schema is not necessarily conformant.**
<!-- GEN:unencodable-count -->6 rules require resolving references across
`@graph`, which no JSON Schema draft can express. They are the ones that fail
*silently* — a lost entity, an invisible file, a slot that never exists.

<!-- BEGIN GENERATED rule-counts -->
14 rules. 8 are encoded in the JSON Schema; **6 are not expressible in JSON Schema at all** (W002, W004, W006, W008, W009, W011) - they need resolution across entities, so a schema-valid crate can still violate every one of them. Run the linter.
<!-- END GENERATED -->

## Layout

```
docs/spec/
  README.md                  this file
  HANDOFF.md                 one page to hand another team
  01-conformance.md          profiles, version negotiation, every rule
  02-envelope.md             @context / @graph, @id allocation, entity order
  03-entities.md             THE REFERENCE: every entity, every property
  04-slots-and-files.md      the distinction that decides what a consumer sees
  05-vre-vocabulary.md       vre_type <-> identity token <-> runtimePlatform
  06-payload-profile.md      infrastructure/TOSCA profile: parseable, not emittable
  07-producer-checklist.md   ordered checklist for a non-Python producer
  08-migration-notes.md      deltas from RO-Crate 1.1, the "do not" list
  generated/                 machine-derived, see below
```

## `generated/` is not documentation you can trust by reading

Every file under `generated/` is derived by driving `RocrateBuilder` and
observing what it emits — not transcribed from the source, and not written by
hand. That distinction is the whole point: `docs/design/` in this repo documents
`root.name` as `<tool.name>` where the builder writes
`"Root dataset for tool: <tool.name>"`, and `README.md` at the root of this repo
still documents four modules and two methods that were deleted months ago. Hand
copies rot; these files are regenerated and a test fails if the committed copy
differs.

| File | What it is |
|---|---|
| `entities.json` | per entity role: every property, its observed shapes, and the exact condition under which it is absent |
| `id-patterns.json` | reserved `@id` shapes, their meaning, and the allocation rules |
| `vocabulary.json` | every `constants.py` table plus the `vre_type` resolution order |
| `mime-extensions.json` | the extension table, and proof of what it does *not* govern |
| `unemitted.json` | keys this library **reads** that no producer request can make it **write** |
| `lint-rules.json` | the <!-- GEN:rule-count -->14 rules with their `file:line` provenance |
| `negatives/` | one deliberately-broken crate per rule — test your validator against these |
| `examples/` | <!-- GEN:golden-count -->28 real crates with per-file provenance in `examples.json` |
| `schema-*.json` | the two profiles' JSON Schema |
| `schemas.json` | which rules each schema encodes, and which it structurally cannot |
| `field-visibility.json` | which producer-side fields survive the round trip, and how far they get (`08-migration-notes.md`) |

<details>
<summary>Index of all <!-- GEN:golden-count -->28 crates in `generated/examples/` —
where each came from, its profile, and whether this library's builder can emit it</summary>

The two origins are not interchangeable. **builder-output** crates
(<!-- GEN:builder-output-count -->15 of them) are what `RocrateBuilder` emits,
captured by running each script in `examples/` under a frozen clock; they show
what a conformant producer sends. **fixture-input** crates
(<!-- GEN:fixture-input-count -->13) were sent by real producers; they are what a
consumer must survive, and they predate the profile URI, so none of them satisfies
W012. Test your parser against the second group and your emitter against the
first.

<!-- BEGIN GENERATED golden-index -->
| file | source | profile | emitted by the builder? | violates (pre-profile) |
|---|---|---|---|---|
| `docs/spec/generated/examples/alphafind-notebook__ro-crate-metadata.json` | `tests/fixtures/alphafind-notebook/ro-crate-metadata.json` | core | yes | - |
| `docs/spec/generated/examples/alphafind_notebook.json` | `examples/alphafind_notebook.py` | core | yes | - |
| `docs/spec/generated/examples/galaxy.json` | `examples/galaxy.py` | core | yes | - |
| `docs/spec/generated/examples/galaxy__ro-crate-metadata.json` | `tests/fixtures/galaxy/ro-crate-metadata.json` | core | yes | - |
| `docs/spec/generated/examples/galaxy_and_onedata.json` | `examples/galaxy_and_onedata.py` | core | yes | - |
| `docs/spec/generated/examples/galaxy_and_onedata__ro-crate-metadata.json` | `tests/fixtures/galaxy_and_onedata/ro-crate-metadata.json` | core | yes | - |
| `docs/spec/generated/examples/galaxy_tosca__ro-crate-metadata.json` | `tests/fixtures/galaxy_tosca/ro-crate-metadata.json` | infrastructure | no: RuntimePlatform | - |
| `docs/spec/generated/examples/galaxy_tosca_stage__ro-crate-metadata.json` | `tests/fixtures/galaxy_tosca_stage/ro-crate-metadata.json` | infrastructure | no: RuntimePlatform | W008, W013 |
| `docs/spec/generated/examples/jupyter.json` | `examples/jupyter.py` | core | yes | - |
| `docs/spec/generated/examples/jupyter__ro-crate-metadata.json` | `tests/fixtures/jupyter/ro-crate-metadata.json` | core | yes | - |
| `docs/spec/generated/examples/mddash.json` | `examples/mddash.py` | core | yes | - |
| `docs/spec/generated/examples/oscar.json` | `examples/oscar.py` | core | yes | - |
| `docs/spec/generated/examples/oscar__ro-crate-metadata.json` | `tests/fixtures/oscar/ro-crate-metadata.json` | core | yes | - |
| `docs/spec/generated/examples/oscar_tosca__ro-crate-metadata.json` | `tests/fixtures/oscar_tosca/ro-crate-metadata.json` | infrastructure | no: RuntimePlatform | - |
| `docs/spec/generated/examples/probe_every_optional_input.json` | `tools/gen_wire_spec.py::_BASELINE (the probe matrix's superset case)` | core | yes | - |
| `docs/spec/generated/examples/replay_github.json` | `examples/replay_github.py` | core | yes | - |
| `docs/spec/generated/examples/replay_github_datahugger_dockerfile.json` | `examples/replay_github_datahugger_dockerfile.py` | core | yes | - |
| `docs/spec/generated/examples/replay_github_datahugger_no_dockerfile.json` | `examples/replay_github_datahugger_no_dockerfile.py` | core | yes | - |
| `docs/spec/generated/examples/sciencemesh.json` | `examples/sciencemesh.py` | core | yes | - |
| `docs/spec/generated/examples/sciencemesh__ro-crate-metadata.json` | `tests/fixtures/sciencemesh/ro-crate-metadata.json` | core | yes | - |
| `docs/spec/generated/examples/sciencemesh_minimal.json` | `examples/sciencemesh_minimal.py` | core | yes | - |
| `docs/spec/generated/examples/scipion_tosca__ro-crate-metadata.json` | `tests/fixtures/scipion_tosca/ro-crate-metadata.json` | infrastructure | no: RuntimePlatform | - |
| `docs/spec/generated/examples/simple-binder__ro-crate-metadata-zenodo.json` | `tests/fixtures/simple-binder/ro-crate-metadata-zenodo.json` | core | yes | - |
| `docs/spec/generated/examples/simple-binder__ro-crate-metadata.json` | `tests/fixtures/simple-binder/ro-crate-metadata.json` | core | yes | - |
| `docs/spec/generated/examples/simple_binder.json` | `examples/simple_binder.py` | core | yes | - |
| `docs/spec/generated/examples/simple_binder_zenodo.json` | `examples/simple_binder_zenodo.py` | core | yes | - |
| `docs/spec/generated/examples/vip.json` | `examples/vip.py` | core | yes | - |
| `docs/spec/generated/examples/vip__ro-crate-metadata.json` | `tests/fixtures/vip/ro-crate-metadata.json` | core | yes | - |
<!-- END GENERATED -->

</details>

Regenerate after changing anything under `src/vre_rocrate/`:

```console
.venv/bin/python tools/gen_wire_spec.py          # write
.venv/bin/python tools/gen_wire_spec.py --check   # fail if stale (used by tests/test_spec)
```

Generation refuses to write if a rule's negative fixture stops tripping its
rule, if a cited `file:line` symbol disappears, if a golden's `@graph` order
carries meaning the sort would lose, or if a schema stops behaving the way
`schemas.json` declares. It is a gate, not a formatter.

## Where this document does not reach

- **The `rrp` vocabulary gap.** `rrp` is a valid `vre_type` with no
  programming-language entry, so a crate for it carries an empty identity token.
  See `05-vre-vocabulary.md` §known gap. Not fixed here because fixing it needs
  an identity token this repo's maintainers must supply.
- **TOSCA emission.** Four fixtures carry a `RuntimePlatform` entity the builder
  cannot produce. `06-payload-profile.md` documents the shape as parsed.
- **`@context`.** The crate emits the RO-Crate 1.1 context URL and nothing else;
  the vocabulary terms used are the base ones plus `onedata:*`, documented in
  `08-migration-notes.md`.
- **What a VRE handler does with a slot.** Domain conventions (galaxy
  `filetype`, VIP `inputValues`, sciencemesh "Shared With") live on the consumer
  side and are named only as motivation.
