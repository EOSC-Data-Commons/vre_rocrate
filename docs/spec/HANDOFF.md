# Handoff: emitting and reading VRE launch crates

One page. Give this to a team implementing one side of the protocol, then point
them at the files named below.

## The artefact in one paragraph

A JSON object `{"@context": "...", "@graph": [...]}` — a RO-Crate 1.1 layout.
`@graph[0]` is a descriptor naming two profiles. `@graph` contains a root
dataset with `@id: "./"`, whose `mainEntity` names the workflow entity and whose
`hasPart` enumerates **every** file. The workflow entity names a
`ComputerLanguage` entity whose `identifier` is the token that says which VRE to
launch on. Input slots are `FormalParameter` entities referenced from the
workflow's `input` array; data files are `File` entities referenced from
`hasPart` and from nowhere else.

## The five facts that are not obvious from the JSON

1. **`hasPart` is the only file enumeration.** A `File` entity absent from
   `root.hasPart` does not exist as far as this library's parser is concerned,
   even though it is in `@graph` and passes validation. Real data does this:
   `generated/examples/galaxy_tosca_stage__ro-crate-metadata.json`.
2. **`programmingLanguage.identifier` routes the launch** — not `name`, not
   `url`. For sciencemesh the identifier is an OpenCloudMesh domain while
   `name`/`url` on the *same entity* say "Jupyter Notebook". Keying on those
   sends sciencemesh jobs to the Jupyter handler.
3. **`@graph` order and both timestamps are ignored by this library; `hasPart`
   order is not.** `VREPayload.files` comes out in `hasPart` order. Never compare
   `datePublished` between two crates.
4. **A schema-valid crate can still be non-conformant.**
   <!-- GEN:unencodable-count -->6 of <!-- GEN:rule-count -->14 rules need
   cross-entity resolution and cannot be written in JSON Schema. Run the linter.
5. **Slot values are looked up by slot *name*,** while the `@id` derives from
   slot *id*. They are different keys and can legitimately differ —
   `"#input-Shared With"` has a space because the name does.

## Give to a producer

1. [`README.md`](README.md) →
   [`01-conformance.md`](01-conformance.md) →
   [`03-entities.md`](03-entities.md).
2. [`07-producer-checklist.md`](07-producer-checklist.md) — ordered,
   self-contained, cites the section for every line.
3. `generated/examples/galaxy.json` as the shape to diff against; your crate
   should look like this modulo values.
4. `tools/wire_spec_lint.py` — copy it, run it, exit 0 before shipping.
5. `generated/negatives/*.json` — your validator MUST reject each of these, and
   the linter must report the rule named in the filename. If it accepts any, your
   validator is too permissive.

## Give to a consumer

1. [`01-conformance.md` §What a consumer must tolerate](01-conformance.md#what-a-consumer-must-tolerate) — unknown keys, unknown
   entity types, and unknown properties are all **expected** and MUST NOT be
   fatal.
2. [`03-entities.md`](03-entities.md) for what is guaranteed present.
3. [`06-payload-profile.md`](06-payload-profile.md) only if you deploy compute;
   that profile is parseable
   but no crate this repo's builder emits will ever carry it.
4. `generated/examples/` — the <!-- GEN:fixture-input-count -->13 crates
   with `origin: "fixture-input"` in `examples.json` are crates a real producer
   actually sent. They predate the profile URI (so all
   <!-- GEN:fixture-input-count -->13 fail W012) and one violates two more rules.
   Use them as
   parser test inputs, not as models of conformance; the `violations_pre_profile`
   field tells you which.

## If you only have ten minutes

Read [`03-entities.md` §root-dataset](03-entities.md#root-dataset) and
[§workflow](03-entities.md#workflow), plus
[`04-slots-and-files.md`](04-slots-and-files.md).
That is 90% of implementations.

## Validating in three commands

```console
# 1. does it parse and is it conformant? (stdlib only, no install)
.venv/bin/python tools/wire_spec_lint.py your-crate.json

# 2. does it match the schema for its profile? (needs the dev extra)
.venv/bin/python -c "
import json, jsonschema
crate = json.load(open('your-crate.json'))
profile = 'infrastructure' if any('RuntimePlatform' in str(e.get('@type'))
    for e in crate['@graph']) else 'core'
schema = json.load(open(f'docs/spec/generated/schema-{profile}.json'))
errs = list(jsonschema.Draft202012Validator(schema).iter_errors(crate))
print(profile, 'OK' if not errs else [e.json_path for e in errs])"

# 3. does the reference parser round-trip it?
.venv/bin/python -c "
from vre_rocrate import VREPayloadBuilder
import json
p = VREPayloadBuilder.build(json.load(open('your-crate.json')))
print(p.vre_type, p.workflow.url, len(p.files), len(p.input_files))"
```

## How much to trust this spec

Every table and JSON excerpt in these files is generated from the builder and
cross-checked by `tests/test_spec/`, and each of the
<!-- GEN:rule-count -->14 rules has a negative
fixture that is re-run on the committed bytes. That covers "the spec matches the
Python library".

It does **not** yet cover "the spec is sufficient to implement from scratch",
which is a different claim and can only be established by someone implementing it
without reading `src/`. [`07-producer-checklist.md`](07-producer-checklist.md)
will grow a **dry run** section recording the result of that exercise; it does not
exist yet, so until it does, treat a question you cannot answer from these pages
as evidence of a spec gap and file it.

## Maintaining

- Change `src/vre_rocrate/` → run `tools/gen_wire_spec.py` → commit the diff.
  `tests/test_spec/test_wire_spec.py` fails if you skip it, and the failure names
  the stale files.
- Prose tables and JSON excerpts between `<!-- BEGIN GENERATED ... -->` markers
  are **generated into the `.md` files**. Do not hand-edit them; edit
  `tools/gen_wire_spec.py` or the code it derives from. The prose outside the
  markers is hand-written and is where the reasoning lives.
- Add a rule → add it to `LINT_RULES` and a `_NEGATIVE_DEFS` entry in
  `tools/gen_wire_spec.py`. Generation fails until the negative actually trips
  the rule, so a rule cannot be added toothless.
- Add an example → drop it in `examples/` with a module-level `request`; it
  becomes a golden automatically and the golden-count test notices if it doesn't.
- The root `README.md` and `AGENTS.md` are known-stale about this library's API.
  `docs/spec/` and the tests are authoritative; see
  [`CLAUDE.md` §Stale docs — what to trust](../../CLAUDE.md#stale-docs--what-to-trust).
