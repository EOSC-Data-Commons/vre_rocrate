# Fixture Generation Analysis & Plan

> **Status note (post-launch-request state)**: Suite is fully green against the
> hand-authored fixtures — nothing currently blocks. Regenerating the 10 non-Tosca
> fixtures remains a cleanup backlog item, not a blocker. Two extra things to record
> whenever regeneration happens: (a) `#receiver` does **not** come back — it is
> intentionally not emitted by `RocrateBuilder` anymore (receivers travel as slot
> values); and (b) the crate root `./` is **always** named after `tool.name` —
> an attached `DatasetHandle` no longer shadows it.

## Goal

Determine which existing `tests/fixtures/*/ro-crate-metadata.json` crates can be
regenerated via `RocrateBuilder.build_from_launch_request()` with the current
`VRELaunchRequest` API, and which cannot. For the ones that cannot, describe what
needs to change — either in the API or in the fixtures — to close the gap.

---

## Summary

| Fixture | Generatable? | Blocker |
|---|---|---|
| galaxy/ | **Yes** | — |
| galaxy_and_onedata/ | **Yes** (with onedata fields) | — |
| oscar/ | **Yes** | — |
| jupyter/ | **Yes** | — |
| alphafind-notebook/ | **Yes** | — |
| replay-github-datahugger-dockerfile/ | **Yes** | — |
| replay-github-datahugger-no-dockerfile/ | **Yes** | — |
| simple-binder/ | **Yes** | — |
| simple-binder/ro-crate-metadata-zenodo.json | **Yes** | — |
| sciencemesh/ | **Yes** | — |
| vip/ | **Yes** | — |
| **galaxy_tosca/** | **No** | RuntimePlatform as `#destination` ref + output FormalParameter + edamontology refs |
| **galaxy_tosca_stage/** | **No** | Above + tosca_input_file staging entity |
| **oscar_tosca/** | **No** | RuntimePlatform as `#destination` ref |
| **scipion_tosca/** | **No** | RuntimePlatform as `#destination` ref + output FormalParameter + Dataset entity as input default |

**10 of 14 fixtures are generatable today.** The 4 Tosca fixtures share one
core structural difference and each has additional per-fixture gaps.

---

## Part 1: Generatable Fixtures (10)

These fixtures can be produced by constructing a `VRELaunchRequest` and calling
`RocrateBuilder.build_from_launch_request()`. The current builder output already
matches their structure closely — the only differences are cosmetic
(`datePublished`/`dateCreated` timestamps, `"placeholder"` vs real descriptions,
encoding format strings like `"text/txt"` vs `"text/plain"`).

### Non-Tosca fixture mapping

| Fixture | tool.types | slots | files | runtime_platform |
|---|---|---|---|---|
| galaxy/ | `galaxy_workflow` | `simpletext_input` (file) | — | inferred (galaxy default) |
| galaxy_and_onedata/ | `galaxy_workflow` | `image`, `stopwords` (file) | — | inferred |
| oscar/ | `oscar` | — (no slots, file only) | `example.txt` | `https://oscar.vre.eosc-data-commons.eu` |
| jupyter/ | `jupyter` | — | — | `https://notebooks-dev.egi.zcu.cz` |
| alphafind-notebook/ | `egi-replay` | — | `requirements.txt` | `https://replay.notebooks.egi.eu/v2` |
| replay-github-*dockerfile/ | `egi-replay` | — | `MuRun2010B.csv` | `https://replay.notebooks.egi.eu/v2` |
| replay-github-*no-dockerfile/ | `egi-replay` | — | `MuRun2010B.csv` | `https://replay.notebooks.egi.eu/v2` |
| simple-binder/ | `binder` | — | — | `https://replay.notebooks.egi.eu/v2` |
| simple-binder/zenodo | `binder` | — | — | `https://replay.notebooks.egi.eu/` |
| sciencemesh/ | `sciencemesh` | `Shared With` (string) | `MuRun2010B.csv` | `https://eosc.cernbox.cern.ch` |
| vip/ | `boutique`/`vip` | `parameter_file`, `data_file`, `zipped_folder` (file) | — | inferred |

### What's different from current builder output (cosmetic, non-blocking)

1. **`datePublished` / `dateCreated`** — fixtures have fixed timestamps (`2025-05-06T14:35:47+00:00`); builder produces `now`. These should not be asserted in tests.
2. **Root dataset `name`/`description`** — fixtures have real names ("Galaxy Example Workflow"); builder uses `tool.name`/`tool.description`. This is correct — just need to set `tool.name` accordingly.
3. **`encodingFormat` strings** — fixtures use `"text/txt"`; examples use `"text/plain"`. These are equivalent; tests should not assert exact MIME strings.
4. **`#author-*` entities** — `galaxy_and_onedata` has `#author-schneider`/`#author-nussbaum` instead of `#author-dispatcher`. The current builder hardcodes `#author-dispatcher`. This is a pre-existing fixture-specific author; **not worth supporting** — the fixture should be updated to use `#author-dispatcher`.
5. **License** — `galaxy_and_onedata` and `sciencemesh` use CC-BY-4.0; builder hardcodes GPL-3.0. The current API has no license field. **Defer** — add a `license` field to `VRELaunchRequest` in a future iteration if needed; for now update fixtures to GPL-3.0.

**Action for non-Tosca fixtures**: replace each `ro-crate-metadata.json` with the
output of `build_from_launch_request()`, then update the corresponding
`test_package.py` assertions to match. No API changes needed.

---

## Part 2: Tosca Fixtures (4) — The Challenge

All 4 Tosca fixtures share one fundamental structural difference: the workflow
entity's `runtimePlatform` is a **reference to a `RuntimePlatform` entity**
(`{"@id": "#destination"}`) rather than a plain string URL.

### Core Tosca structure (galaxy_tosca as canonical example)

```json
{
  "@id": "https://...workflow.ga",
  "runtimePlatform": {"@id": "#destination"},   ← REFERENCE, not string
  "input": [{"@id": "#input-textfile"}],
  "output": [{"@id": "#output-result"}]          ← OUTPUT parameter
},
{
  "@id": "#destination",                         ← RuntimePlatform entity
  "@type": "RuntimePlatform",
  "name": "Infrastructure Manager",
  "memoryRequirements": "4 GiB",
  "processorRequirements": ["2 vCPU", "1 GPU"],
  "storageRequirements": "200 GiB",
  "installUrl": "https://.../templates/galaxy.yaml"   ← TOSCA template URL
}
```

### Gap analysis per Tosca fixture

#### galaxy_tosca/ & galaxy_tosca_stage/ (identical except staging)

Gaps vs current `VRELaunchRequest`:

1. **`runtimePlatform` as `RuntimePlatform` entity reference** — current API only supports `runtime_platform: str | None`. The Tosca case needs a structured `RuntimePlatform` with `installUrl` (Tosca template URL), `memoryRequirements`, `processorRequirements`, `storageRequirements`.

2. **Output FormalParameter** (`#output-result`) — current `ToolMeta.slots` only models inputs. The Tosca fixtures declare workflow outputs (`#output-result` with `additionalType` + `encodingFormat` as EDAM ontology refs). Current builder has no output modeling.

3. **EDAM ontology references on FormalParameters** — fixtures use `additionalType: {"@id": "http://edamontology.org/data_3671"}` and `encodingFormat: {"@id": "http://edamontology.org/format_2330"}` (objects with `@id`), plus standalone `Thing` entities for the ontology terms. Current `SlotDefinition.slot_type` is a plain string.

4. **`conformsTo` on FormalParameters** — fixtures have `"conformsTo": {"@id": "https://bioschemas.org/profiles/FormalParameter/0.1-DRAFT-2020_07_21/"}`. Current builder doesn't emit this.

5. **galaxy_tosca_stage only: `#tosca_input_file` staging entity** — a `File` entity with `contentLocation: "/opt/data"` that is referenced from the `#destination` RuntimePlatform's `input` array, not from the workflow. This models data staging into the Tosca-provisioned infrastructure. No current API concept for this.

#### oscar_tosca/

Same as galaxy_tosca minus outputs (no `output` array, no `#output-result`). The oscar workflow has no FormalParameters at all — just the `RuntimePlatform` entity with `installUrl`.

#### scipion_tosca/

Same `#destination` RuntimePlatform, plus:
- Input FormalParameter `#input-empiar-dataset` with `defaultValue: {"@id": "rsync://..."}` — a **Dataset entity** as the default value (not a File). Current `SlotValue.file` only models `FileInput`, not dataset URLs.
- Output FormalParameter `#output-result` (same as galaxy_tosca).

---

## Part 3: Plan to Accommodate Tosca

### Option A: Extend `VRELaunchRequest` (recommended)

Add a structured runtime platform and output slot support to the launch API.

#### 3.1 Structured RuntimePlatform (enables all 4 Tosca fixtures)

```python
# models/launch.py

@dataclass
class ToscaRuntimePlatform:
    """A Tosca/Infrastructure-Manager runtime platform descriptor."""
    install_url: str                    # Tosca template URL
    memory_requirements: str | None = None        # "4 GiB"
    processor_requirements: list[str] = field(default_factory=list)  # ["2 vCPU", "1 GPU"]
    storage_requirements: str | None = None       # "200 GiB"
    staged_files: list[FileInput] = field(default_factory=list)  # galaxy_tosca_stage only

# Update VRELaunchRequest:
@dataclass
class VRELaunchRequest:
    tool: ToolMeta
    input: LaunchInput
    runtime_platform: str | None = None                    # plain URL (existing)
    tosca_platform: ToscaRuntimePlatform | None = None     # structured (NEW)
```

Builder logic:
- If `tosca_platform` is set → emit a `#destination` `RuntimePlatform` entity and set `workflow.runtimePlatform = {"@id": "#destination"}`.
- If `runtime_platform` is set (string) → emit `workflow.runtimePlatform = <string>` (existing behavior).
- If neither → infer from `VRE_TYPE_TO_DEFAULT_RUNTIME_PLATFORM` (existing behavior).

This is mutually exclusive: either a plain string or a Tosca descriptor, never both.

#### 3.2 Output slots (enables galaxy_tosca, galaxy_tosca_stage, scipion_tosca)

```python
# Add to ToolMeta:
@dataclass
class SlotDefinition:
    id: str
    name: str
    slot_type: str
    is_optional: bool = False
    is_output: bool = False          # NEW — distinguishes input vs output slots
    additional_type: str | None = None    # NEW — EDAM ontology @id or plain string
    encoding_format: str | None = None    # NEW — EDAM ontology @id or MIME string
```

Builder logic:
- `is_output=False` slots → emitted as `workflow.input[]` FormalParameters (current behavior)
- `is_output=True` slots → emitted as `workflow.output[]` FormalParameters
- If `additional_type` / `encoding_format` are EDAM URLs (contain `edamontology.org`), emit as `{"@id": ...}` and add standalone `Thing` entities; otherwise emit as plain strings.

#### 3.3 Staged files (galaxy_tosca_stage only)

The `staged_files` field on `ToscaRuntimePlatform` emits `File` entities with
`contentLocation` that are referenced from the `#destination` RuntimePlatform's
`input` array, not from the workflow. This models data pre-staged onto the
Tosca-provisioned VM.

#### 3.4 Dataset as slot default value (scipion_tosca only)

The scipion fixture has `#input-empiar-dataset` with `defaultValue: {"@id": "rsync://..."}`.
This is a Dataset entity, not a File. Currently `SlotValue.file` only accepts
`FileInput`. Options:

- **Option 1**: Allow `SlotValue` to reference a `DatasetHandle` instead of `FileInput`.
  ```python
  @dataclass
  class SlotValue:
      value: Any = None
      file: FileInput | None = None
      dataset: DatasetHandle | None = None    # NEW
  ```
  Builder emits a `Dataset` entity and `defaultValue: {"@id": dataset.url}`.

- **Option 2**: Treat the rsync URL as a file URL in `FileInput` (it's just a URL
  with a different scheme). This is simpler but semantically lossy.

**Recommend Option 1** — it preserves the Dataset-vs-File distinction that the
plan's §2 established.

### Option B: Keep API minimal, update fixtures to non-Tosca format

Replace all 4 Tosca fixtures with `build_from_launch_request()` output (plain
string `runtimePlatform`, no output slots, no EDAM refs, no staging). This loses
the Tosca-specific metadata that real dispatcher deployments need.

**Not recommended** — the Tosca fixtures exist specifically to test Tosca
infrastructure provisioning, and that capability must survive the
transformation.

---

## Implementation steps (Option A)

1. Add `ToscaRuntimePlatform` dataclass to `models/launch.py`
2. Add `is_output`, `additional_type`, `encoding_format` to `SlotDefinition`
3. Add `dataset` field to `SlotValue`
4. Add `tosca_platform` field to `VRELaunchRequest`
5. Update `RocrateBuilder`:
   - Emit `#destination` `RuntimePlatform` entity when `tosca_platform` is set
   - Route `is_output=True` slots to `workflow.output[]`
   - Emit EDAM `Thing` entities for ontology-referenced `additional_type`/`encoding_format`
   - Emit `conformsTo` on FormalParameters
   - Handle `SlotValue.dataset` → Dataset entity + `defaultValue` ref
   - Handle `staged_files` → `File` entities with `contentLocation` referenced from `#destination.input[]`
6. Update `RequestPackageBuilder` to parse the new `#destination` entity and output FormalParameters
7. Regenerate all 14 fixtures from `VRELaunchRequest` constructors
8. Update `test_package.py` assertions to match new fixture format
9. Add assumption tests for the new Tosca fields

---

## Recommendation

Do this in two phases:

**Phase 1 (now)**: Regenerate the 10 non-Tosca fixtures. No API changes needed.
This unblocks the 5 failing `test_package.py` tests and completes the MVP.

**Phase 2 (next)**: Implement Option A (Tosca API extensions) and regenerate
the 4 Tosca fixtures. This is a larger change that touches the builder, parser,
and adds new model fields — deserves its own review cycle.

The Tosca fixtures are indeed the biggest challenge, as suspected. The core
issue is the structured `RuntimePlatform` entity — everything else (outputs,
EDAM refs, staging, dataset-as-default) is additive on top of that.
