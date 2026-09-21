# Plan: `docs/spec/` — RO-Crate wire format specification

## Context

`vre_rocrate` emits a RO-Crate 1.1 dialect that is the **communication payload between
independently developed components**. Those components do not all use this library — some are
in other languages and will hand-roll emitters. Today the only description of that dialect is
`docs/design/vre-launch-request-transformation.md` §4, which describes design *intent* and is
**already wrong**: it states `root.name = <tool.name>` and `root.description =
<tool.description or "placeholder">`, whereas `building/rocrate.py:109-110` writes
`"Root dataset for tool: {name}"` and a hardcoded `"N/A"`. A transcribed spec inherits
transcription errors, and this repo has a demonstrated rot problem (README fully stale,
`AGENTS.md` wrong on test count / black scope / file paths — see `CLAUDE.md`).

Outcome: a **producer-facing, normative, generated-where-possible** spec in `docs/spec/`, with
machine-readable artifacts, a version profile URI, and a pytest drift check that makes silent
divergence impossible. No CI exists, so the drift check must be a plain pytest test.

### Decisions taken (from user)
Producer-only normative scope · full generated kit · lives in `docs/spec/` · add a profile URI.

### Producer-only scope, and its one tension
The user chose producer-only, so the doc's *obligations* are "you MUST emit…". But every
obligation is only justified by what a consumer dereferences, and several are **inverted traps**
(a property you must emit *even though nothing reads it*, because a future consumer will). The
document is therefore organised as producer obligations, with a one-line **"why"** on each rule
that names the consuming behaviour. The existing `models/launch.py:13-61` comments already use
this idiom (`# → File.contentSize; unread by VREs`) and it should be carried through —
`rocrate.py` has no such annotations, so the payload side is the part that must be derived.

---

## Ground truth established (verified by running the library, not by reading)

These are the facts the spec will assert. Several **contradict the subagent reports**, which I
spot-checked and rejected:

1. **`root.hasPart` is the sole enumeration source for `VREPayload.files`**
   (`building/payload.py:119-142` walks `hasPart` → dereferences → keeps `@type` containing
   `"File"`). *Not* free space: a File entity present in `@graph` but absent from `hasPart` is
   **completely invisible** (verified), and `hasPart` **absent entirely raises a bare
   `TypeError: 'NoneType' object is not iterable`** — no validation message. `hasPart: []`
   parses and yields zero files.
2. **Exactly 3 hard rules** (`parsing/validator.py`): non-empty string `@id` on every `@graph`
   entity; root `./` with a `mainEntity` that dereferences to an existing entity whose `@type`
   is not `""`; that entity's `programmingLanguage` resolves and has `identifier`. Duplicate
   `@id`s are **not** caught.
3. **Silent-failure modes a producer must be forbidden to create** (all reproduced):
   - Duplicate `@id` between a File and the workflow URI ⇒ the file vanishes from `input_files`.
   - Two `FileInput`s with no `url` and the same `name` ⇒ both get `@id = name`
     (`rocrate.py:55` `_file_id = f.url or f.name`) ⇒ duplicate id, validator passes, one file
     lost.
   - `checksum_type != "sha256"` ⇒ checksum **dropped in silence** (`rocrate.py:193`).
   - A `LaunchInput.slots` key not matching any `SlotDefinition.name` ⇒ a value that **exists
     nowhere in the output**; the FormalParameter is emitted without `defaultValue`.
   - `vre_type` = `rrp` ⇒ builder emits `identifier:""`, `name:""`, `url:""`; `validate_basic`
     **passes** (empty string is not `None`), and the consumer silently gets
     `vre_type == "unknown"`.
   - `tool.uri` with an extension outside `_EXTENSION_TO_MIME` (e.g. a Zenodo DOI) ⇒
     `"File"` is *not* prepended to the workflow `@type` and `encodingFormat` is omitted
     (`rocrate.py:138-141,158-159`). Consequence verified: the workflow is then absent from
     `.files`, so the descriptor-exclusion rule in `input_files` never fires.
   - `programmingLanguage` / `runtimePlatform` as a **JSON array** ⇒ `AttributeError: 'list'
     object has no attribute 'get'` in both validator and builder.
4. **Load-bearing vs inert** (differential test: delete one emitted key, diff the parsed payload
   projected onto named fields, excluding the verbatim `raw_crate` / `properties` copies):
   - *Load-bearing*: `./mainEntity`, `./hasPart`, `./name`, `./description` (the latter two only
     via the `root_name`/`root_description` accessors, degrading to `""` — `models/payload.py:182-190`);
     workflow `name`, `version`, `runtimePlatform`, `input`, `encodingFormat`,
     `programmingLanguage`; `#<vre>-lang.identifier`; File `name`, `encodingFormat`,
     `onedata:*`; FormalParameter `name`, `additionalType`, `defaultValue`.
   - *Never read as a named field* — survives only in the verbatim `raw_crate` / `properties`
     escape hatches: `./creator`, `./license`, `./datePublished`, workflow `creator`,
     `dateCreated`, `license`, `sdPublisher`, `conformsTo`, `description`, File `url`,
     `contentSize`, `sha256`, `license`, FormalParameter `required`, the whole
     `#tool-metadata` payload *as an entity* (though `raw_definition` **is** a named field via
     the `#tool-metadata.rawDefinition` path), and `#author-dispatcher` / `#workflow-hub` /
     `#license-unspecified` entirely. **This is the forward-compatibility space** and is
     exactly what a producer spec must state explicitly.
   - `File.url` is inert on the named path because it defaults to `@id`
     (`building/payload.py:139` `entity.get("url") or entity.get("@id")`).
   - Note `WorkflowDescriptor.type` is annotated `type: str` but is `main_type[0]` when `@type`
     is a list (`building/payload.py:106`) — so `@type: ["File","SoftwareSourceCode",
     "ComputationalWorkflow"]` reads back as `"File"`. Consumers in other languages must take
     the *set*, not the first element.
5. **Vocabulary traps** (`constants.py`): `programmingLanguage.identifier` is the VRE identity
   token — for sciencemesh it is `https://eosc.cernbox.cern.ch` — while the *same* language
   entity has `name: "Jupyter Notebook"` and `url: "https://jupyter.org/"` (`:31`, `:42`).
   Keying on `name` or `url` routes sciencemesh to the wrong handler.
   `VREPayload.vre_type` is that **identifier URL**, not a short name.
6. **Profile URI is safe to add**: `conformsTo` is never read in `src/`; all 13 fixtures and the
   builder emit `{"@id": "https://w3id.org/ro/crate/1.1"}`; RO-Crate permits an array here (the
   vip/oscar/tosca fixtures already use `conformsTo` on other entities).
7. `onedata:onezoneDomain` / `onedata:fileId` use a **`onedata:` prefix declared nowhere** —
   `@context` is the remote string `https://w3id.org/ro/crate/1.1/context`, which defines no
   `onedata` prefix. Valid for this library (which reads literal keys) but a JSON-LD processor
   in another language will not expand it. Must be documented as a known deviation.
8. Repository-based launches have **no wire flag**: `is_repository_only` is *inferred* as
   `workflow.url is not None and no local and no remote files` (`models/payload.py:92-99`) —
   verified true for a GitHub URI with zero files, false with one attached CSV.
9. Emission order is fixed, 14 entities max (verified dump): descriptor, `./`, workflow,
   `#<vre>-lang`, Files (slot-bound then free-form), `#input-<slot.id>` FormalParameters,
   optional Dataset, optional `#tool-metadata`, then `#author-dispatcher` / `#workflow-hub` /
   `#license-unspecified`.
10. **The two profiles split cleanly on evidence, so the core schema can be strict.** Across all
    13 fixtures: `programmingLanguage` is a `{"@id": ...}` object in **13/13** (never a string or
    list); `runtimePlatform` is a plain string in the 9 non-TOSCA crates and a `{"@id":
    "#destination"}` reference in the 4 `*_tosca*` ones; `hasPart` entries are `{"@id": ...}`
    objects in 26/26 (bare-string entries are parser-tolerated but never produced); `@type` is
    `str` or `list` of `str` over the vocabulary `CreativeWork, Dataset, File,
    SoftwareSourceCode, ComputationalWorkflow, ComputerLanguage, Person, Organization,
    FormalParameter, Thing, RuntimePlatform`.
11. **`additionalProperties: true` is mandatory, and provably so**: fixtures carry 11 keys the
    builder never emits — `alternateName`, `contentLocation`, `familyName`, `givenName`,
    `installUrl`, `memoryRequirements`, `onedata:publicAccess`, `onedata:spaceId`,
    `processorRequirements`, `storageRequirements`, `userid`. A closed schema rejects real
    crates. `creator` is a list in 1 of 26 occurrences (polymorphism confirmed).
12. **`#license-unspecified` appears in NO fixture** — it is a builder-only placeholder, never
    observed input, so the schema must not require it and the spec must present it as an
    emitter convention, not a protocol feature. Conversely `#tosca_input_file`
    (`galaxy_tosca_stage`) is a `File` entity **outside** `hasPart`, reachable only via
    `#destination.input[]` — the concrete proof of rule 1: it is invisible to `.files`.
13. **`jsonschema` is not installed** in this environment. So schema validation cannot be the
    guarantee — it would `importorskip` and rot silently, exactly the failure mode this whole
    effort exists to prevent. The dependency-free guarantee is a **rule linter** (plain-Python
    predicates for the ~12 load-bearing rules, run over every fixture and golden); JSON Schema
    validation is a dev-extra bonus that runs when present.

---

## Proposed structure

```
docs/spec/
  README.md                 # entry point: what this is, who it's for, how to read the normative language
  01-conformance.md         # RFC 2119 terms, profiles, version URI, negotiation, what "valid" means (the 3 rules)
  02-envelope.md            # top-level {@context, @graph}, entity order, @id allocation rules & reserved prefixes
  03-entities.md            # THE CORE REFERENCE: one section per entity, full property tables
  04-slots-and-files.md     # the two-way distinction, with the sciencemesh both-at-once case
  05-vre-vocabulary.md      # generated tables: vre_type ↔ identifier ↔ runtimePlatform ↔ tool.types
  06-payload-profile.md     # infrastructure/TOSCA profile: parseable, NOT emittable
  07-producer-checklist.md  # self-contained checklist for a non-Python team
  08-migration-notes.md     # vs RO-Crate 1.1 base, the onedata: deviation, "do not" list
  generated/
    entities.json           # derived: @type → property, required|conditional|forbidden, condition
    id-patterns.json        # derived: reserved @id shapes and their meaning
    vocabulary.json         # derived: all constants.py tables + resolve_vre_type layers
    mime-extensions.json    # derived: _EXTENSION_TO_MIME
    schema-core.json            # JSON Schema 2020-12 for the emittable profile
    schema-infrastructure.json  # ... for the TOSCA/infrastructure profile
    examples/<name>.json    # normalised golden crates
    examples/<name>.meta.json   # profile, reproducibility, source
  HANDOFF.md                # the 1-page "give this to another team" index
```

Twelve prose is too many; the split above is deliberate so a consumer team can be handed
`HANDOFF.md` + `03-entities.md` + `generated/` and ignore the rest. `08-migration-notes.md`
absorbs the "don't do this" list rather than giving it its own file.

### Normative-device choice
Each entity section is a table of `property | type | status | derived from | why`. `status` ∈
`MUST` / `MUST NOT` / `SHOULD` / `MAY` / `MUST be exactly <literal>`. "Derived from" is a
`file:line` into `src/`, which is what makes the doc auditable and the drift test meaningful.

---

## Generation and verification harness

**Location**: `tools/gen_wire_spec.py` (new `tools/` dir; nothing comparable exists — no
`scripts/`, no `bin/`). Plus `tests/test_spec/test_wire_spec.py` in the repo's existing test
style (`tests/test_*/__init__.py`, `Test*` classes, `from conftest import load_json`).

**How the conditional-key rules are extracted — the key design question.** Three options:

- *(a) Combinatorial drive*: synthesise a matrix of `VRELaunchRequest`s toggling each optional
  input, build each, and diff which keys appear/disappear per entity. **Recommended.** It is
  black-box, so it is automatically correct when someone edits `rocrate.py` — the whole point.
  It yields real `{"@id": ...}` shapes rather than guesses, and needs no parsing of our own
  source.
- *(b) AST inspection of the `_add_*` methods*: recovers the exact condition expressions, but
  breaks on any refactor and can't observe values computed inside helpers. Not worth it.
- *(c) Hand-written table in the generator*: what produced the design doc's wrong `root.name`.
  Rejected.

Use **(a)**, with two explicit supplements that a black-box drive cannot discover, both kept in
the generator and clearly marked as hand-maintained:
- the **`@id` pattern registry** (semantics of `./`, `#input-<id>`, `#<vre>-lang`,
  `#tool-metadata`, the three reserved support entities) — derived from string literals in
  `rocrate.py` by regex for *presence*, with meaning supplied by hand;
- the **consumer-side "why" annotations** (load-bearing / inert), regenerated by the same
  differential procedure used to establish ground truth #4 above, run against fixtures rather
  than synthesised requests.

**Determinism.** `RocrateBuilder` calls `datetime.now(timezone.utc)` twice — `datePublished`
(full ISO) on the root and `dateCreated` (date-only) on the workflow, from **separate** calls
that can straddle midnight UTC. Normalise both to fixed sentinels
(`<NORMALISED-ISO8601-DATETIME>` / `<NORMALISED-ISO8601-DATE>`) and record the scrub rules in a
`_normalisation` key of each golden file so the artefact is self-describing. Sort `@graph`
**by `@id`** in the golden copies (order is documented separately in `02-envelope.md`, so
sorting doesn't lose information) while keeping emission order asserted as its own generated
list. `sort_keys=True`, 2-space indent, trailing newline.

**Two guarantee layers, deliberately.** JSON Schema is the portable artifact a non-Python team
validates against locally; it is *not* our safety net, because `jsonschema` is absent here and a
skipping test is worse than no test. So:

- **Layer 1 — the rule linter (no dependencies, never skips).** A `lint(crate, profile)`
  function in `tools/gen_wire_spec.py` implementing the load-bearing rules as plain-Python
  predicates (non-empty unique `@id`; `./` present with a dereferenceable `mainEntity`;
  `programmingLanguage` is `{"@id":...}` and resolves to an entity with a non-empty `identifier`;
  `hasPart` present and every `File`-typed entity listed in it; workflow `@id` unique against
  all File `@id`s; `sha256` only with a sha256 checksum; …). Exported from the generator and
  imported by the test, so the rules live in exactly one place. This has real teeth and runs in
  this venv as-is.
- **Layer 2 — JSON Schema 2020-12** (`jsonschema` in `[project.optional-dependencies].dev`;
  the library gains zero runtime deps). Two profiles, `additionalProperties: true` everywhere —
  mandatory, since fixtures carry 11 keys the builder never emits. `required: ["@id","@type"]`
  per entity, encoding rule 1. Constrain to the *shapes that work end-to-end* rather than to
  what the parser tolerates: `programmingLanguage` as `{"@id": string}` only (a bare string
  passes this library's validator but crashes the payload builder — ground truth #3), `hasPart`
  entries as `{"@id": string}` only, `runtimePlatform` `anyOf[string, {"@id":...}]`. Model
  `@graph` with `allOf` + `contains`/`minContains` to require the descriptor, `./`, and a
  `ComputerLanguage` without constraining the rest. Do **not** require `#license-unspecified`
  (ground truth 12).

**Drift test** (`tests/test_spec/test_wire_spec.py`), all pure-stdlib except schema checks:
1. Regenerate every `generated/*.json` **in memory** and compare to the committed bytes; on
   mismatch, fail with a message naming the exact command to regenerate. No temp files, no
   self-modification, no spurious diffs.
2. Validate each golden example against its profile schema (skip with a clear reason if
   `jsonschema` is absent).
3. Assert every `file:line` "derived from" reference in the prose resolves to a line that still
   exists and still contains the symbol it cites — this catches prose rot, which is the failure
   mode that got README and `AGENTS.md`.
4. Assert the profile URI appears in builder output.

**Golden example provenance.** Each `examples/*.py` is run and captured (builder-reproducible by
construction). Fixtures are cited as *observed input*. Per-example `.meta.json` records
`profile`, `source`, and `reproducible_by_builder: true|false` — the 4 `*_tosca*` and
`simple-binder/ro-crate-metadata-zenodo.json` are `false`. `examples/mddash.py` is the only
example whose output is byte-stable without normalisation (no `datePublished` difference is
relevant; it still has both date fields, so it is normalised like the rest).

---

## Plan for filling the structure with source-extracted information

| Section | Source of truth | How filled |
|---|---|---|
| `01` conformance, profiles, version URI | `parsing/validator.py:54-108` (3 rules), new profile URI constant | Verbatim transcription of the 3 rules as MUSTs, each with its error message; the profile URI as a new constant in `constants.py` |
| `02` envelope, entity order, `@id` rules | `building/rocrate.py:271-284` (order), `:55` (`_file_id`), `:61`, `:79`, `:208` | Order **generated** from a full-featured synthetic build; `@id` table generated-by-regex + hand-written meaning |
| `03` entity property tables | `building/rocrate.py:88-269`, `models/payload.py:62-190`, `building/payload.py:76-163` | **Generated** by combinatorial drive (a) for key presence + condition; "why" column from the differential test; hand-written only for semantics |
| `04` slots vs files | `models/launch.py:44-74`, `building/rocrate.py:98-106,161-165,205-220`, `docs/design/…#2` | Hand-written prose (semantics), every JSON shape generated from `examples/sciencemesh.py` (the slots+files case) and `examples/mddash.py` (literal slot) |
| `05` VRE vocabulary | `constants.py:3-104` | **Fully generated** — all 5 tables plus the 8 `resolve_vre_type` URI patterns and the 3-layer precedence. Includes the `rrp` hole as a marked gap |
| `06` infrastructure profile | `parsing/infrastructure.py`, `plans/tosca-fixture-generation-support.md`, 4 tosca fixtures | Generated property inventory from the fixtures (parse-observed), hand-written "not emittable" warning. **Corrects** the plan doc's stale `RequestPackageBuilder` naming |
| `07` producer checklist | sections 01-06 | Hand-written, derived; every line cites a section so it can't diverge silently |
| `08` deviations & prohibitions | ground truth #3, #7 above | Hand-written; the 6 silent-failure modes become explicit MUST NOTs with the reproduced symptom |

### Two code changes required (both small, both in-scope)
1. **Profile URI** — add `WIRE_FORMAT_PROFILE = "https://w3id.org/eosc-vre/req-packager/1.0"`
   to `constants.py` and emit it in `rocrate.py:88-96` as an **array**:
   `"conformsTo": [{"@id": "https://w3id.org/ro/crate/1.1"}, {"@id": WIRE_FORMAT_PROFILE}]`,
   keeping the RO-Crate 1.1 entry first so any external consumer keying on it is unaffected.
   Add one assertion to `tests/test_launch_request_assumptions.py` (public API only, per that
   file's convention). `w3id.org` is the right namespace because RO-Crate itself uses it; the
   `prefixregister` PR is a human follow-up, not a blocker — the URI only needs to be *stable
   and documented*, and a redirect can be added later. Document the major/minor policy in
   `01-conformance.md`: additive = minor (consumers MUST ignore unknown), breaking = major.
2. **Do not fix `rrp`** in this work. It needs a language URI I cannot invent, and inventing an
   identity token for a live protocol is worse than documenting the hole. Spec documents it as a
   marked gap; `plans/` gets a one-line note. Flag to the user as a separate decision.

### Out of scope
No README rewrite (already known-stale; separate task). No `AGENTS.md` edit. No TOSCA emitter.
No CI (none exists; the drift check is pytest). No formatter runs — new files follow the
surrounding hand style with compact grouped imports, per `CLAUDE.md`.

---

## Work order

**Status: phases 1 done and verified, 2–3 written but with two defects to fix first.**

- **Phase 1 — DONE.** Profile URI: `ROCRATE_BASE_PROFILE` / `WIRE_FORMAT_PROFILE` in
  `constants.py`, emitted as a two-entry `conformsTo` array (base first, so RO-Crate-1.1-only
  consumers are unaffected), exported from `__init__`, asserted in
  `tests/test_launch_request_assumptions.py`. 67 tests pass.
- **Phase 2/3 — written, needs the two fixes below before regenerating.**
  `tools/gen_wire_spec.py` derives `entities.json`, `vocabulary.json`, `mime-extensions.json`,
  `id-patterns.json`, `lint-rules.json` by driving the builder over a 16-probe matrix with a
  frozen clock. Verified: byte-identical across runs, `--check` exits 0, the `rrp` table gap is
  auto-detected, and `defaultValue` is observed with both shapes (`reference`, `string`).

### Two defects in the generator, to fix immediately on resuming

1. **`required` mislabelled `conditional` for conditionally-emitted roles.** The `carriers`
   filter (only probes that still emit the role may explain a missing property) made the
   "key never disappears on its own" branch unreachable: for a key present in every carrier,
   `lost_by == []` and `lost_by_whole_entity == ['no_files_at_all']`, so `set(lost_by) !=
   set(lost_by_whole_entity)` falls through to `conditional` with an **empty** condition.
   Affects `file.@type`, `input-dataset.@type`, etc. Fix: restore the short-circuit —
   `if not lost_by: status, when = "required", []` must be tested **before** the whole-entity
   comparison. Then re-run and re-verify the on-disk artefacts.
2. **`PROBE_CLAIMS` is defined but never called.** Three documented behaviours are about
   *values*, which a presence matrix cannot show (`required: false`, default runtime platform,
   non-sha256 checksum discarded). Wire the checks into `derive_entities()` so a claim that
   stops holding fails generation, or delete the table — a dead table is worse than none.

### Remaining

4. **Rule linter + negative fixtures — DONE.** `lint()` / `lint_report()` in
   `tools/gen_wire_spec.py`, 13 rules, one committed negative crate each, all verified to report
   exactly their own rule plus declared partners. Deviations from this line, each forced by
   evidence:
   - `lint_report` returns **`violations` and `undecidable`** separately. The original
     early-return-on-missing-root design meant "clean" and "could not tell" were the same value,
     so a crate with no root descriptor would pass 11 rules by never being measured against them.
   - `profile` and `rules` parameters added (the plan's `lint(crate, profile)`). **All 13 fixtures
     violate W012** because they predate the profile URI; withholding that rule must be an
     explicit, reported act, not a silent pass.
   - **W009 has no clean negative.** Any file sharing the workflow's `@id` is by construction a
     duplicate `@id`, so W002 always co-fires. Recorded in `INSEPARABLE`, not worked around.
   - **W010 was silently near-vacuous** — `re.fullmatch(r"[0-9a-fA-F]+")` accepted 1-char and
     uppercase digests. Now 64-char lowercase hex, which no real digest violates.
   - **W013 added, a rule this plan did not know.** `parsing/infrastructure.py:40` reads `@type`
     off the `RuntimePlatform.input` entry and never dereferences a reference, so
     `{"@id": "#tosca_input_file"}` is skipped with only a `logger.warning`. Proven by inlining
     the entity in `galaxy_tosca_stage` and watching `input_files` go from `[]` to one
     `IMInputFile`. `galaxy_tosca_stage` violates W008 **and** W013 in real data.
   - W002 and W009 negatives are **produced by the builder from a plausible request**, not
     hand-edited, so they prove the mistake is reachable through the public API.
5. **Golden examples + provenance metadata — DONE.** 27 goldens: 14 `builder-output` from
   `examples/*.py` (run as subprocesses) + 13 `fixture-input`. Timestamps scrubbed to `<TIMESTAMP>`
   / `<DATE>`, `@graph` sorted by `@id`, and each one asserted to **round-trip to an identical
   named-field projection** before and after normalisation — so the scrub is proven
   meaning-preserving rather than assumed. Deviations:
   - The plan's single `reproducible_by_builder` flag is **replaced by three derived axes**:
     `origin` (captured from the builder or not), `builder_can_emit_all_types` (could the builder
     express these shapes), `declares_wire_profile`. One boolean cannot say both "where this file
     came from" and "what shapes it contains", and as written it named *fixtures* while being
     attached to *examples* — every example is reproducible, so the flag would have been `true`
     for all 14 and proved nothing.
   - Profile is **derived** from the presence of `RuntimePlatform` (the type the core emitter
     cannot produce), not from the filename. The plan's list — "the 4 `*_tosca*` and zenodo" — is
     wrong twice: `simple-binder/ro-crate-metadata-zenodo.json` is a **core**-profile fixture, and
     `alphafind-notebook` carries an unemittable key too.
   - Slugs keep the **whole** fixture path, because directory `galaxy/` collides with
     `examples/galaxy.py`; the first abbreviated version silently dropped 5 goldens. A collision
     now raises.
   - Builder-output goldens are required to be **lint-clean**, or generation fails.
6. **Schemas.** Verify: all 13 fixtures + 14 examples validate against their assigned profile,
   every negative fails (a schema that passes everything is worthless).
7. **Drift test** `tests/test_spec/test_wire_spec.py`. Verify: green now; touch `rocrate.py`,
   re-run, confirm it fails with the regenerate command in the message; revert.
8. **Prose sections `01`–`08` + `HANDOFF.md`**, tables filled from the generated artefacts, every
   rule citing `file:line`. Verify: the line-reference test passes.
9. **Producer dry run** (verification step 5) — the real completeness test. Fix the spec, not
   the agent.

## Verification

Run after each step; stop and fix before continuing.

1. **After the generator exists** — `mkdir -p .venv`-free check, reusing the existing venv:
   `.venv/bin/python tools/gen_wire_spec.py && git status --short docs/spec/generated` then run
   it **twice** and `diff` the two runs to prove byte-stability independent of wall-clock time
   (specifically: run across a forced date change by monkeypatching the clock in a scratch
   check, since a midnight-straddle bug will not surface in a single sitting).
2. **Schema soundness** — every one of the 13 fixtures + 14 example outputs must validate
   against the profile it is assigned, **and** each negative fixture must fail its schema:
   entity without `@id`, entity with `@id: ""`, missing `mainEntity`, unresolvable
   `programmingLanguage`, language without `identifier`. A schema that passes everything is
   worthless; assert the failures.
3. **Provenance** — for each generated "derived from" line reference, confirm
   `sed -n '<N>p' <file>` still shows the cited construct (this is test 3 above).
4. **Round-trip** — regenerate each golden crate, parse with `VREPayloadBuilder.build`, and
   assert the named-field projection equals the projection of the freshly built crate, i.e. the
   normalisation scrub did not erase anything semantically meaningful.
5. **Producer-perspective dry run** — the real test of "complete reference": pick
   `examples/sciencemesh.py` and hand *only* `docs/spec/` (no `src/`, no `examples/`) to a
   fresh agent, have it emit that crate from the spec alone in a different language, then
   `ValidationPipeline.validate_basic` its output and diff the named-field projection against
   the golden. Any field it gets wrong is a spec defect, not an agent defect — fix the spec.
6. **Whole-suite** — `.venv/bin/python -m pytest -q` stays green (66 tests + the new
   `tests/test_spec/`).
