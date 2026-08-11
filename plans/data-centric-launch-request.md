# Data-Centric VRELaunchRequest (Tool-Omitted Case)

## Problem

Some VREs in the dispatcher are **not tool/workflow launchers** — they are data-centric services
that don't require a `ToolMeta` (workflow URL, slot definitions, etc.) in any meaningful way.

Examples:

- **ScienceMesh** — OCM share of files to a receiver. No actual compute/tool launch.
- **Binder-Launcher / EGI Replay** — data gets staged into a Jupyter environment; the
  "workflow" is often a GitHub repo (a file consumer), not a formal workflow.
- **RRP** — data staging + container provisioning; the "tool" is opaque.

Currently `VRELaunchRequest` *requires* `tool: ToolMeta` with `id`, `version`, `name`, `uri`,
`types`, `slots[]`. For data-centric cases, this forces an artificial `ToolMeta` with
placeholder or fake slot definitions — just what you flagged as hallucination.

The key is to make `tool` optional (_or none_) in `VRELaunchRequest` while keeping
the RO-Crate output and parser contract valid.

---

## Design Options

### Option A: `tool` becomes `ToolMeta | None`

```python
@dataclass
class VRELaunchRequest:
    tool: ToolMeta | None = None
    input: LaunchInput = field(default_factory=LaunchInput)
    runtime_platform: str | None = None
    # vre_type is now explicit rather than derived (since we can't infer
    # from tool when tool is None)
    vre_type: str | None = None   # e.g. "sciencemesh", "binder", "rrp"
```

**Pros**: Simple minimal change.
**Cons**: Contradicts the "VRELaunchRequest mirrors req-packager ToolMeta" contract; could
confuse callers.

---

### Option B: Split into two request types

```python
@dataclass
class VRELaunchRequest:
    """Tool-centric case — VRELaunchRequest is required."""
    tool: ToolMeta
    input: LaunchInput
    runtime_platform: str | None = None

@dataclass
class DataLaunchRequest:
    """Data-centric case — no tool/workflow, just data + VRE type."""
    vre_type: str          # explicit, since no tool to infer from
    input: LaunchInput
    runtime_platform: str | None = None
```

**Pros**: Clear semantic separation; straightforward.
**Cons**: New type for what's the same concept; `RocrateBuilder` gets `build_from_launch_request()`
and `build_from_data_request()` — more API surface.

---

### Option C: `ToolMeta` gets `kind: "data-centric"` + lightweight slots

```python
@dataclass
class ToolMeta:
    id: str
    version: str
    name: str
    uri: str
    types: list[str]
    description: str = ""
    slots: list[SlotDefinition] = field(default_factory=list)
    raw_definition: dict[str, Any] = field(default_factory=dict)
    # NEW: explicit classification
    is_tool_launch: bool = True   # False for sciencemesh, RRP, some binder cases
```

For sciencemesh/RRP: `is_tool_launch=False`, `slots=[]`, `input.files` holds everything.
**Pros**: No new types; single model.
**Cons**: `ToolMeta.id`, `version`, `uri` still artificial.

---

## Recommended: Option B (Split), or Option A (Optional tool)

Option C keeps artificial metadata, which is the core problem.

The pragmatic choice: **Option B — `DataLaunchRequest`** along side `VRELaunchRequest`.

---

## DataLaunchRequest → RO-Crate Structure

The RO-Crate for data-centric cases has NO `ComputationalWorkflow` mainEntity.
Instead, the root dataset IS the entity:

```
@graph:
├── ro-crate-metadata.json
├── ./                                    (root Dataset)
│   ├── @id: "./"
│   ├── @type: "Dataset"
│   ├── name: <share title OR "Data Package"
│   ├── description: <share desc OR "Data sharing package">
│   ├── datePublished: <now>
│   ├── creator → #author-dispatcher
│   ├── hasPart → [<file @ids...>]        ← note: NO mainEntity
│   ├── programmingLanguage → #sciencemesh-lang  ← ← ← NEW: still needed for VRE resolution
│   └── runtimePlatform: <resolved>
│
├── #sciencemesh-lang                     (ComputerLanguage — for VREFactory)
│
├── <file entities>                       (standalone File, from input.files)
│   ├── @id: <file.url or name>
│   ├── @type: "File"
│   ├── name: <name>
│   ├── url: <url>
│   ├── encodingFormat: <mime_type>
│   ├── contentSize: <size_bytes>
│   ├── sha256: <checksum>
│   └── ...
│
├── #receiver                             (Person — OCM receiver)
│   ├── @id: "#receiver"
│   ├── @type: "Person"
│   └── userid: <resolved from slot or explicitly passed>
│
├── #author-dispatcher                    (Person — unchanged)
├── #workflow-hub                         (Organization — unchanged)
├── <license entity>                      (CreativeWork — unchanged)
```

Key differences from tool-centric RO-Crate:

| Element | Tool-centric (galaxy/vip) | Data-centric (sciencemesh/RRP) |
|---|---|---|
| **mainEntity** | Workflow entity (ComputationalWorkflow) | **NO mainEntity** — root is the main data |
| **programmingLanguage on mainEntity** | Yes | Redundant — put on root dataset |
| **FormalParameters** | From `input.slots` | **None** — no tool parameters |
| **hasPart** | workflow + files + dataset | **files only** |
| **workflow hub** | SoftwareSourceCode creator | **Nothing** — no software to credit |

---

## Parser Changes

`RequestPackageBuilder` currently assumes a `mainEntity` exists and fails if not:

```python
def _get_main_entity(self):
    root = self.root
    main_ref = root.get("mainEntity")
    if main_ref is None:
        return None
    ...
```

For data-centric crates, `_get_main_entity()` returns `None` and `RequestPackageBuilder.__init__()` raises.

Changes needed:

1. **`RequestPackageBuilder` accepts missing mainEntity**: when no `mainEntity` found, create a minimal `WorkflowDescriptor` with:
   - `id`: root's @id (`"./"`)
   - `type`: `"Dataset"`
   - `url`: `None`
   - `programming_language_id`: front root's `programmingLanguage` if present
   - `runtime_platform`: from root's `runtimePlatform` if present

2. **`VREScienceMesh` handler**: continues to work — it reads `pkg.ocm_data`, `pkg.raw_crate`, not `pkg.workflow.*` in ways that would crash.

3. **`VREFactory.__call__`**: still resolves `vre_type` from `programming_language` — parsing the root's `programmingLanguage` reference gives this back.

---

## VRELaunchRequest Update (combined model where tool is optional)

To handle both:

```python
@dataclass
class VRELaunchRequest:
    """Launch a VRE. When tool is None, creates a data-only RO-Crate we share/provision."""
    tool: ToolMeta | None = None       # None → data-only (no workflow entity)
    input: LaunchInput = field(default_factory=LaunchInput)
    runtime_platform: str | None = None
    vre_type: str | None = None        # optional explicit vre_type; required when tool is None
```

**Rules**:
- If `tool` is not None → derive `vre_type` from `tool.types`/`raw_definition`/URI (as current)
- If `tool` is None → `vre_type` **must be set explicitly** (e.g. `"sciencemesh"`, `"binder"`, `"rrp"`)
- `RocrateBuilder` branches:
  - `tool=None` → data-only RO-Crate (no mainEntity, no FormalParameters)
  - `tool=Some(ToolMeta)` → tool-centric RO-Crate (workflow mainEntity + FormalParameters)

---

## Examples Conversion (Data-Centric)

### `examples/sciencemesh.py` (updated)

```python
import json
from vre_rocrate import (
    VRELaunchRequest, LaunchInput, SlotValue, FileInput, RocrateBuilder,
)

request = VRELaunchRequest(
    tool=None,                      # ← data-only case
    vre_type="sciencemesh",         # ← explicit since no tool
    input=LaunchInput(
        dataset=None,
        slots={
            "Shared With": SlotValue(value="rwelande@eosc.cernbox.cern.ch"),
        },
        files={
            "MuRun2010B.csv": FileInput(
                name="MuRun2010B.csv",
                url="https://raw.githubusercontent.com/dpiparo/swanExamples/master/notebooks/MuRun2010B.csv",
                mime_type="text/csv",
            ),
            "CMSDimuon_py.ipynb": FileInput(
                name="CMSDimuon_py.ipynb",
                url="https://raw.githubusercontent.com/dpiparo/swanExamples/refs/heads/master/notebooks/CMSDimuon_py.ipynb",
                mime_type="application/x-ipynb+json",
            ),
        },
    ),
)

print(json.dumps(RocrateBuilder.build_from_launch_request(request), indent=2))
```

### `examples/replay_github.py` — stays tool-centric

DataLens notebook is a real file to launch, but the GitHub repo is a **workflow-like** item
(the notebook content is the thing being run). So it stays `tool=ToolMeta(...)` with the
notebook or GitHub repo URL as `uri`.

---

## Validation Update

`ValidationPipeline.validate_basic()` must handle missing `mainEntity` gracefully:

```python
# Old behavior: raises if no mainEntity
# New behavior:
#   - If mainEntity exists → validate as before
#   - If no mainEntity → validate root Dataset has programmingLanguage + hasPart
```

---

## Changes Summary

| File | Change |
|---|---|
| `src/vre_rocrate/models/launch.py` | `VRELaunchRequest.tool: ToolMeta \| None`, add `vre_type: str \| None` field |
| `src/vre_rocrate/building/rocrate.py` | `build_from_launch_request()` branches on `tool is None` vs `tool is not None` |
| `src/vre_rocrate/building/package.py` | `RequestPackageBuilder._get_main_entity()` optional; `__init__` doesn't raise on None mainEntity; create synthetic WorkflowDescriptor from root |
| `src/vre_rocrate/parsing/validator.py` | `validate_basic` handles missing mainEntity |
| `examples/sciencemesh.py` | Uses `tool=None` + `vre_type="sciencemesh"` |

---

## Why a Separate Plan?

This is a structural change with a different RO-Crate shape. It's cleaner to track separately
from the main "slots vs files" plan, but they interconnect — ideally both get implemented
together.
