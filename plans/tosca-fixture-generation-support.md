# Tosca Fixture Support — Phase 2 Plan

> Scope: this document covers **only the 4 `*_tosca*` fixtures** and the work
> needed for `RocrateBuilder.build_from_launch_request()` to generate them.
> (The 10 non-Tosca fixtures were handled in Phase 1 — removed from this
> document. Version note: written after the `SlotValue` union refactor.)
>
> Until this plan lands, the Tosca fixtures remain **parse-only** — the parser
> already understands everything in them; the builder just cannot emit them.
>
> Out of scope by decision: workflow **output** FormalParameters, EDAM
> ontology refs, and `conformsTo` on FormalParameters — these appear in some
> fixtures but are not blockers and are not modeled here.

## Goal

Extend the launch-request API and `RocrateBuilder` so the 4 Tosca fixtures
under `tests/fixtures/` can be regenerated from `VRELaunchRequest`
constructors, covering the Tosca-specific structure below.

## Fixtures & blockers

| Fixture | Blocker |
|---|---|
| galaxy_tosca/ | RuntimePlatform as `#destination` ref |
| galaxy_tosca_stage/ | RuntimePlatform as `#destination` ref + `#tosca_input_file` staging entity |
| oscar_tosca/ | RuntimePlatform as `#destination` ref |
| scipion_tosca/ | RuntimePlatform as `#destination` ref + Dataset entity as input default |

## Core structural difference

All 4 fixtures declare the workflow's `runtimePlatform` as a **reference to a
`RuntimePlatform` entity** instead of a plain URL string:

```json
{
  "@id": "https://...workflow.ga",
  "runtimePlatform": {"@id": "#destination"},
  "input": [{"@id": "#input-textfile"}]
},
{
  "@id": "#destination",
  "@type": "RuntimePlatform",
  "name": "Infrastructure Manager",
  "memoryRequirements": "4 GiB",
  "processorRequirements": ["2 vCPU", "1 GPU"],
  "storageRequirements": "200 GiB",
  "installUrl": "https://.../templates/galaxy.yaml"
}
```

Additional per-fixture structure:

### `#tosca_input_file` — staging entity (galaxy_tosca_stage)

```json
{
  "@id": "#destination",
  "@type": "RuntimePlatform",
  "...": "as in the core structure above",
  "input": [{"@id": "#tosca_input_file"}]
},
{
  "@id": "#tosca_input_file",
  "@type": "File",
  "name": "simpletext_input",
  "encodingFormat": "text/txt",
  "contentLocation": "/opt/data"
}
```

- **Reference path**: the staged File hangs off the *infrastructure*, not the
  workflow — it is referenced only from `#destination.input[]`. This is the
  third place a file can live in these crates, distinct from root `hasPart`
  (crate payload) and `FormalParameter.defaultValue` (workflow slot binding).
- **Semantics**: when the Infrastructure Manager deploys the TOSCA template
  (`installUrl` → `galaxy.yaml`), this input is staged onto the provisioned
  VM at `contentLocation` (`/opt/data`). Data reaches the execution
  environment through provisioning, not through the workflow engine's upload.
- **`contentLocation` form**: plain `"/opt/data"` here; the general form is
  `"node:/path"` (the parse side splits the prefix into `compute_node`).
- **Fixture quirk**: the entity's `@id` is a bare fragment with no `url` —
  it names no fetchable source; it pairs with the real data file
  (`https://example-files.../example.txt`, present in `hasPart`) only via a
  shared `name`. Regeneration must therefore decide the staged File's
  `@id`/`url` policy: `IMInputFile.url` is where a real source URL would go,
  but as-authored the parsed `url` is the literal `"#tosca_input_file"`.
- **Parse side (already works)**: maps to
  `IMInputFile(url="#tosca_input_file", destination="/opt/data", compute_node=None)`.

### Dataset entity as input default (scipion_tosca)

```json
{
  "@id": "#input-empiar-dataset",
  "@type": "FormalParameter",
  "name": "empiar_dataset",
  "defaultValue": {"@id": "rsync://ftp.ebi.ac.uk/empiar/world_availability/12944/"}
},
{
  "@id": "rsync://ftp.ebi.ac.uk/empiar/world_availability/12944/",
  "@type": "Dataset",
  "name": "empiar_dataset"
}
```

- **Semantics**: the workflow's `empiar_dataset` input is filled by an
  entire remote *collection* (an EMPIAR dataset directory over rsync), not a
  single file. Same `defaultValue {"@id"}` binding mechanism as file slots,
  but the referenced entity's `@type` is `Dataset` — a collection in
  RO-Crate terms.
- **Also in `hasPart`**: the rsync entity is additionally listed among the
  root dataset's parts (crate payload), mirroring how slot-bound files are
  listed.
- **Minimal entity**: no `description`, no separate `url` key — the rsync
  URL *is* the `@id`. Regeneration via `DatasetHandle` (whose `description`
  is required) will add a `description` — an accepted cosmetic difference.
- **Why the builder cannot emit it today**: the `SlotValue` union offers
  only `FileInput` as a referenceable fill, and `DatasetHandle` can only
  occupy `LaunchInput.dataset` (crate-level attachment, not a slot). Faking
  it as `FileInput(url="rsync://...")` would serialize `@type: "File"` —
  semantically wrong for a collection.
- **Parse side (already works)**: `FormalParameter.default_value` stays raw
  (`{"@id": ...}`), the entity is excluded from `files` (not File-typed),
  and consumers resolve it via `get_entity(rsync_url)`.
- **Phase 2 §3 consequence**: `SlotValue += DatasetHandle`; the builder
  emits the Dataset entity + `defaultValue` ref + a `hasPart` entry, the
  exact mirror of slot-bound files.

## What already works (parse side — nothing to change)

- `RequestPackageBuilder._resolve_runtime_platform()` already resolves
  `runtimePlatform` refs to a typed `models.RuntimePlatform`
  (`install_url`, `memory`, `num_cpus`, `num_gpus`, `storage`,
  `input_files`) via `parsing/infrastructure.py`.
- Staged files already parse: `#destination.input[]` entries with
  `contentLocation` (`"node:/path"` split included) become `IMInputFile`s.

So Phase 2 is **builder/input-model work only** — the round-trip consumer
side needs no changes.

## Plan

### 1. Structured runtime platform in `VRELaunchRequest`

Widen the existing field — do not add a second one:

```python
runtime_platform: str | RuntimePlatform | None = None
```

reusing the existing `models.RuntimePlatform`
(`models/infrastructure.py`). This mirrors the parse side exactly, where
`workflow.runtime_platform` is already `str | RuntimePlatform | None` —
a symmetric round-trip. Builder precedence:

1. `RuntimePlatform` instance → emit `#destination` entity
   (`name`, `installUrl`, `memoryRequirements`, `storageRequirements`,
   `processorRequirements` rendered back to `"N vCPU"` / `"N GPU"` strings)
   and set `workflow.runtimePlatform = {"@id": "#destination"}`.
2. `str` → plain URL (current behavior).
3. `None` → `VRE_TYPE_TO_DEFAULT_RUNTIME_PLATFORM` fallback (current).

`num_cpus: int` / `num_gpus: int` → `processorRequirements` string rendering
is the only lossy edge; acceptable (parse renders the same strings for the
fixtures' values).

### 2. Staged files (galaxy_tosca_stage only)

Already modeled: `RuntimePlatform.input_files: list[IMInputFile]`. Builder
emits each as a `File` entity with `contentLocation`
(recompose `"node:/path"` when `compute_node` is set) referenced from
`#destination.input[]`. No new model needed.

### 3. Dataset as a slot fill (scipion_tosca only)

Extend the union — one line, no wrapper:

```python
SlotValue = str | int | float | bool | FileInput | DatasetHandle
```

Builder: a `DatasetHandle` fill emits a `Dataset` entity (`@id`=url,
`name`=title, `description`) plus `defaultValue: {"@id": url}`. The union
refactor made this additive where the old dataclass would have needed a
third field.

## Implementation steps

1. Launch model: widen `VRELaunchRequest.runtime_platform`; extend
   `SlotValue` with `DatasetHandle`; export `RuntimePlatform` from the
   models package for launch-side use.
2. `RocrateBuilder`: `#destination` entity + runtimePlatform ref; staged
   `File` entities with `contentLocation`; `DatasetHandle` fills → Dataset
   entity + defaultValue ref.
3. Regenerate the 4 Tosca fixtures from `VRELaunchRequest` constructors;
   add round-trip tests (build → validate → `RequestPackageBuilder.build`,
   asserting `runtime_platform` is a structured `RuntimePlatform` with
   `install_url` and staged `input_files`). Byte-equality is asserted only
   for the structure in scope — extra entities already present in the
   hand-authored fixtures stay untouched.
4. Confirm the existing Tosca fixture tests keep passing unchanged
   (parse side untouched).

## Non-goals

- No parser changes (already complete).
- No output-slot modeling (`workflow.output[]`), no EDAM ontology refs,
  no `conformsTo` on FormalParameters — deliberately out of scope.
- No `OCMData`/`#receiver` revival.
- No license/authors modeling (deferred from Phase 1 as before).
- Not replacing the Tosca fixtures with non-Tosca approximations ("Option B"
  from Phase 1 analysis) — the Tosca metadata is what these fixtures exist
  to test.
