# VRELaunchRequest Transformation Plan (v2)

## Goal

Transform the `vre_rocrate` library's input model from `MinimalVRERequest` to `VRELaunchRequest`
so that it matches `req-packager`'s domain language (`ToolMeta`, `LaunchInput`, `DatasetHandle`,
`Slot`, `SlotValue`, `FileEntry`, etc.).

## Constraints

1. **RO-Crate JSON output format can change** — restructure freely to properly represent
   the slots-vs-files distinction, dataset handle, and tool metadata from req-packager.
2. **`RequestPackage` entity changes must be minimal** — only additive fields.
3. **VRE handlers must not change** — they consume `RequestPackage` and the few fields
   they read must stay present and unchanged.
4. **`RequestPackageBuilder` gets updated** to parse the new RO-Crate format.
5. **Old test fixtures get updated** to the new RO-Crate format.
6. **`MinimalVRERequest` is removed** — `VRELaunchRequest` is the sole input model.
7. **`ToolKind` is NOT in the RO-Crate** — it's a req-packager-internal derived value
   (computed from `tool.types` via a heuristic: `"data access" in types → SlotsAndFiles, else SlotsOnly`).
   The dispatcher can derive it from `tool.types` itself if needed. No current VRE handler reads it.

---

## Flow Diagram

```
req-packager                     vre_rocrate                        dispatcher
─────────────                    ───────────                        ──────────
ToolMeta ─┐                     ┌──────────────────┐
          ├─→ VRELaunchRequest ─┤ RocrateBuilder    ├─→ New RO-Crate JSON ─┐
LaunchInput┘                    │ build_from_launch │                     │
                                └──────────────────┘                     │
                                                                         ▼
                                                              ┌──────────────────┐
                                                              │ RequestPackage   │
                                                              │ Builder (updated)│
                                                              └──────┬───────────┘
                                                                     │
                                                              ┌──────▼───────────┐
                                                              │ RequestPackage   │ ← minimal new fields
                                                              │ (mostly same)    │
                                                              └──────┬───────────┘
                                                                     │
                                                              ┌──────▼───────────┐
                                                              │ VRE Handlers     │ ← ZERO changes
                                                              │ (binder, galaxy, │
                                                              │  vip, etc.)      │
                                                              └──────────────────┘
```

---

## 1. New Input Types (`src/vre_rocrate/models/launch.py`)

### `DatasetHandle`
```python
@dataclass
class DatasetHandle:
    url: str
    title: str
    description: str
```

### `SlotDefinition` (mirrors req-packager `Slot`)
```python
@dataclass
class SlotDefinition:
    id: str                   # e.g. "parameter_file", "image_0.tif"
    name: str                 # e.g. "parameter_file", "Image 0 (TIF)"
    slot_type: str            # "string" | "file" | "data_input" | "data_collection"
    is_optional: bool = False
```

### `FileInput` (mirrors req-packager `FileEntry`)
```python
@dataclass
class FileInput:
    name: str
    path: str | None = None              # original path in source dataset
    url: str | None = None               # download URL
    size_bytes: int | None = None
    mime_type: str | None = None
    checksum: str | None = None
    checksum_type: str | None = None     # "sha256", "md5"
    onedata_domain: str | None = None
    onedata_file_id: str | None = None
```

### `SlotValue` — the key semantic distinction
```python
@dataclass
class SlotValue:
    """Either a primitive value OR a file filling a tool-declared parameter."""
    value: Any = None          # str | int | float | bool | None
    file: FileInput | None = None
```

### `ToolMeta`
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
    # NOTE: ToolKind is intentionally omitted — it's a req-packager-internal derived
    # value, not upstream metadata. The dispatcher can derive it from tool.types if needed.
```

### `LaunchInput` — slots vs files distinction preserved
```python
@dataclass
class LaunchInput:
    dataset: DatasetHandle | None = None
    slots: dict[str, SlotValue] = field(default_factory=dict)    # tool-parameter bindings
    files: dict[str, FileInput] = field(default_factory=dict)    # free-form data attachments
```

### `VRELaunchRequest` — top-level
```python
@dataclass
class VRELaunchRequest:
    """Top-level input model — replaces MinimalVRERequest."""
    tool: ToolMeta
    input: LaunchInput
    # Optional explicit runtime_platform override. If None, RocrateBuilder infers
    # the runtimePlatform from the resolved vre_type's default service URL and
    # emits it on the workflow/mainEntity entity so it's always present in the crate.
    runtime_platform: str | None = None
```

---

## 2. Slots vs Files — Semantic Distinction

This is the core reason `LaunchInput` has two separate maps. **Note: the current `vre_rocrate` code does NOT make this distinction** — it creates a `FormalParameter` for every file (see [`_add_formal_parameters()`](src/vre_rocrate/building/rocrate.py:194) and [`_add_workflow_entity()`](src/vre_rocrate/building/rocrate.py:147)). The new design changes this: only `input.slots` entries get FormalParameters.

| | `input.slots` | `input.files` |
|---|---|---|
| **What it represents** | Values bound to tool-declared parameters (from `ToolMeta.slots[]`) | Free-form data attachments not tied to any parameter |
| **Key** | `SlotName` — matches `SlotDefinition.name` | `RenameName` — user-chosen label |
| **Value** | `SlotValue` (primitive JSON OR FileInput) | `FileInput` only |
| **How mock uses it** | Galaxy → `request_state` entries; VIP → `inputValues`; RRP → `data_mounts` | Binder-Launcher → `data_files`; CernBox → crate file entities |
| **RO-Crate mapping** | `FormalParameter` entities referenced from `workflow.input[]` | Standalone `File` entities in `hasPart`, NOT referenced by any FormalParameter |

---

## 3. ToolMeta → vre_type Resolution (`constants.py`)

```python
TOOL_TYPE_TO_VRE_TYPE: dict[str, str] = {
    "egi-replay":    "binder",
    "galaxy":        "galaxy",
    "galaxy_workflow": "galaxy",
    "oscar":         "oscar",
    "vip":           "vip",
    "boutique":      "vip",
    "scipion":       "scipion",
    "jupyter":       "jupyter",
    "mddash":        "mddash",
    "sciencemesh":   "sciencemesh",
    "cernbox":       "sciencemesh",
    "mybinder":      "binder",
    "binder-launcher": "binder",
    "rrp":           "rrp",            # new — no real handler yet
}

def resolve_vre_type(tool: ToolMeta) -> str:
    # 1. raw_definition override
    if "vre_type" in tool.raw_definition:
        v = tool.raw_definition["vre_type"]
        if v in VRE_TYPES:
            return v
    # 2. match tool.types against known entries
    for t in tool.types:
        if t in TOOL_TYPE_TO_VRE_TYPE:
            return TOOL_TYPE_TO_VRE_TYPE[t]
    # 3. fallback: URI pattern match
    for pattern, vtype in [
        ("galaxyproject.org", "galaxy"),
        ("jupyter.org", "jupyter"),
        ("oscar.grycap", "oscar"),
        ("vip.creatis", "vip"),
        ("cernbox.cern.ch", "sciencemesh"),
        ("rrp-eosc", "rrp"),
    ]:
        if pattern in tool.uri:
            return vtype
    raise ValueError(f"Cannot resolve vre_type from tool: {tool.id}")


# Default runtime platforms per vre_type. Used by RocrateBuilder when the
# VRELaunchRequest does not provide an explicit runtimePlatform override.
VRE_TYPE_TO_DEFAULT_RUNTIME_PLATFORM: dict[str, str] = {
    "galaxy":      "https://usegalaxy.eu/",
    "binder":      "https://mybinder.org/",
    "jupyter":     "https://jupyterhub.egi.eu/",
    "oscar":       "https://oscar.grycap.net/",
    "vip":         "https://vip.creatis.insa-lyon.fr/",
    "scipion":     "http://scipion.i2pc.es/",
    "mddash":      "https://mddash.cerit-sc.cz/",
    "sciencemesh": "https://eosc.cernbox.cern.ch",
    "rrp":         "https://rrp-eosc.ethz.ch/",
}
```

---

## 4. New RO-Crate Format

The RO-Crate is restructured to properly separate slots from files:

```
@graph:
├── ro-crate-metadata.json           (descriptor — unchanged)
├── ./                                (root Dataset)
│   ├── @id: "./"
│   ├── @type: "Dataset"
│   ├── name: <input.dataset.title or tool.name>
│   ├── description: <input.dataset.description or tool.description>
│   ├── datePublished: <now>
│   ├── mainEntity → <workflow @id>
│   ├── hasPart → [<workflow @id>, <file @ids...>, <dataset entity @id>]
│   └── creator → #author-dispatcher
│
├── <workflow entity>                 (mainEntity — tool definition)
│   ├── @id: <tool.uri>
│   ├── @type: ["File","SoftwareSourceCode","ComputationalWorkflow"]
│   ├── name: <tool.name>
│   ├── description: <tool.description>
│   ├── version: <tool.version>
│   ├── programmingLanguage → #<vre>-lang
│   ├── runtimePlatform: <resolved>               ← from request.runtime_platform or
│   │                                                  VRE_TYPE_TO_DEFAULT_RUNTIME_PLATFORM
│   └── input → [#input-<slot.id>, ...]          ← from input.slots (user-filled values)
│
├── #<vre>-lang                       (ComputerLanguage — unchanged)
│
├── #input-<slot.id>                  (FormalParameter — replaced old #input-<i>)
│   ├── @id: "#input-<slot.id>"
│   ├── @type: "FormalParameter"
│   ├── name: <SlotDefinition.name>
│   ├── additionalType: <SlotDefinition.slot_type>
│   ├── required: <not SlotDefinition.is_optional>
│   └── defaultValue: <literal> OR {"@id": <file_url>}
│       ↑ SlotValue::Value           ↑ SlotValue::File
│
├── <file entities>                   (File — from input.files + SlotValue::File)
│   ├── @id: <file.url or name>
│   ├── @type: "File"
│   ├── name: <FileInput.name>
│   ├── encodingFormat: <FileInput.mime_type>
│   ├── url: <FileInput.url>
│   ├── contentSize: <FileInput.size_bytes>       ← NEW
│   ├── sha256: <FileInput.checksum>              ← NEW (when checksum_type="sha256")
│   ├── onedata:onezoneDomain: <...>
│   └── onedata:fileId: <...>
│
├── <dataset entity>                  (Dataset — from input.dataset; only when
│   │                                   dataset is actually provided, e.g. when
│   │                                   req-packager delivers a browsed dataset)
│   ├── @id: <input.dataset.url>
│   ├── @type: "Dataset"
│   ├── name: <input.dataset.title>
│   └── description: <input.dataset.description>
│
├── #tool-metadata                    (NEW — opaque tool metadata entity)
│   ├── @id: "#tool-metadata"
│   ├── @type: "Thing"
│   └── rawDefinition: <tool.raw_definition>
│
├── #author-dispatcher                (Person — unchanged)
├── #workflow-hub                     (Organization — unchanged)
├── <license entity>                  (CreativeWork — unchanged)
└── #receiver                         (Person — optional, from ScienceMesh "Shared With" slot)
```

### Key structural differences from old format:

| Old format | New format |
|---|---|
| `#input-<i>` (numbered by file index) | `#input-<slot.id>` (named by tool parameter) |
| Only file `defaultValue` references | Both literal `defaultValue` AND file `{"@id": ...}` references |
| No distinction between parameter files and attached files | `input.slots` → FormalParameter + File; `input.files` → standalone File |
| No dataset entity | `input.dataset` → standalone Dataset entity |
| No `contentSize`/`sha256` on File | Added from `FileInput` |
| No tool metadata | `#tool-metadata` entity with `rawDefinition` |

---

## 5. RequestPackage — Minimal Changes

The `RequestPackage` dataclass gains exactly **one** new optional field:

```python
@dataclass
class RequestPackage:
    vre_type: str
    programming_language: str
    workflow: WorkflowDescriptor
    files: list[FileReference] = field(default_factory=list)
    workflow_inputs: list[FormalParameter] = field(default_factory=list)
    workflow_outputs: list[FormalParameter] = field(default_factory=list)
    raw_crate: dict[str, Any] = field(default_factory=dict, repr=False)
    # ocm_data removed — OCMData was dropped; receiverId comes from the
    # "Shared With" input slot via RequestPackage.input_by_name("Shared With")
    # ─── NEW ───
    raw_definition: dict[str, Any] = field(default_factory=dict)  # from ToolMeta.raw_definition
```

All existing fields stay **unchanged**. All existing properties (`input_files`, `oscar_input_files`, `local_files`, `remote_files`, `zenodo_doi`, etc.) stay **unchanged**. No VRE handler reads `raw_definition` — it is a future-facing addition. `ToolKind` is intentionally excluded (derived from `tool.types`, not upstream metadata).

`WorkflowDescriptor` gains one new field:

```python
@dataclass
class WorkflowDescriptor:
    id: str
    type: str
    url: str | None = None
    programming_language_id: str | None = None
    runtime_platform: str | RuntimePlatform | None = None
    properties: dict[str, Any] = field(default_factory=dict, repr=False)
    tool_version: str | None = None    # NEW — from ToolMeta.version
```

---

## 6. RequestPackageBuilder — Updated Parser

The parser is updated to extract from the new RO-Crate format but still populates the
same `RequestPackage` shape:

| New RO-Crate entity/property | How parser reads it | Maps to |
|---|---|---|
| `#tool-metadata.rawDefinition` | `_resolve_ref("#tool-metadata")` → `get("rawDefinition")` | `RequestPackage.raw_definition` |
| `workflow.version` | Already exists in `_build_workflow` via `main.get("version")` | `WorkflowDescriptor.tool_version` |
| `#input-<slot.id>` FormalParameters | `_extract_parameters` already handles them | `workflow_inputs` (unchanged path) |
| Literal `defaultValue` on FormalParameter | Already handled — `isinstance(dv, str)` fallback | Falls through to `file_ids.add(dv)` — same behavior |
| Standalone `File` entities (from `input.files`) | Already extracted via `_extract_files` | `files` (unchanged path) |
| Dataset entity in `hasPart` | Skipped by `@type == "File"` filter | Not added to `files` (correct) |
| `File.contentSize`, `File.sha256` | Stored in `FileReference.properties` | Available in `properties` dict |
| `FormalParameter.required` | New field on `FormalParameter` | `formal_parameter.properties["required"]` |

### `input_files` property — no change needed

The [`input_files`](src/vre_rocrate/models/package.py:97) property resolves files through `FormalParameter.default_value` and excludes the workflow descriptor (itself File-typed in `files`):
- If `workflow_inputs` is empty → returns all **data** files (descriptor excluded)
- If `workflow_inputs` has FormalParameters → returns slot-referenced files **plus** free-form files (descriptor excluded)

In the new format, only `input.slots` entries produce FormalParameters (free-form `input.files` do not).
This means:

| Scenario | `workflow_inputs` | `input_files` returns | VRE handlers affected |
|---|---|---|---|
| Tool with no slots (e.g. binder) | empty | all data files (descriptor excluded) | `VREBinder` uses `local_files` (not `input_files`) — OK |
| Tool with slots only (e.g. galaxy/vip) | has FormalParameters | slot-referenced files | `VREGalaxy`, `VREVIP` — correct, they only use slots |
| Tool with files only (e.g. binder-launcher) | empty | all data files (descriptor excluded) | No real handler yet |
| Tool with slots + files (e.g. cernbox) | has FormalParameters | slot-referenced **and** free-form files | Both available, as required for SlotsAndFiles tools |

The descriptor is excluded by `@id` match. `ValidationPipeline.validate_basic` enforces that every `@graph` entity declares a non-empty `@id` (RO-Crate 1.1 requirement; blank nodes are rejected at parse time), so the id comparison cannot misfire on missing ids. Slot-bound files are resolvable individually via `RequestPackage.file_for_input(param)`.

### Validation update

The `ValidationPipeline` must be updated to validate the new crate structure:

- `programmingLanguage` must resolve (unchanged)
- `#tool-metadata` entity is optional (not present for crates not built from `VRELaunchRequest`)

---

## 7. RocrateBuilder — New Static Method

```python
@staticmethod
def build_from_launch_request(request: VRELaunchRequest) -> dict[str, Any]:
```

This replaces `build_from_minimal()` entirely. Key building logic:

1. **Resolve vre_type** from `ToolMeta.types` / `raw_definition` / URI patterns
2. **Resolve runtimePlatform** — if `request.runtime_platform` is set, use it directly;
   otherwise look up `VRE_TYPE_TO_DEFAULT_RUNTIME_PLATFORM[resolved_vre_type]` and emit that
   on the workflow entity. The runtime platform is always present in the crate.
3. **Build workflow entity** — `@id = tool.uri`, `version = tool.version`,
   `runtimePlatform = resolved_platform`
4. **Build FormalParameters from slots**:
   - For each `SlotDefinition` in `tool.slots`:
     - Look up value in `input.slots[slot.name]`
     - If `SlotValue::Value` → `defaultValue: <literal>`
     - If `SlotValue::File` → `defaultValue: {"@id": file.url}`
     - If no value found → no `defaultValue` (parameter declared but unfilled)
5. **Build File entities from `input.files`** — standalone, not referenced by any FormalParameter
6. **Build File entities from `SlotValue::File`** — referenced by their owning FormalParameter
7. **Build Dataset entity from `input.dataset`**
8. **Build `#tool-metadata` entity from `tool.raw_definition`**
9. **No `#receiver` entity** — the `"Shared With"` slot is emitted only as a `FormalParameter`; receivers travel as slot values, not named entities

---

## 8. What Gets Removed

- `src/vre_rocrate/models/minimal.py` — `MinimalVRERequest` + `MinimalFileInput`
- `RocrateBuilder.build_from_minimal()` — replaced
- All imports of `MinimalVRERequest` / `MinimalFileInput`

## 9. What Stays Unchanged

- `src/vre_rocrate/models/package.py` — `RequestPackage` (one additive field: `raw_definition`), `WorkflowDescriptor` (one additive field: `tool_version`), `FileReference`, `FormalParameter`
- `src/vre_rocrate/models/infrastructure.py` — `RuntimePlatform`, `IMInputFile`
- `src/vre_rocrate/parsing/infrastructure.py` — unchanged
- `src/vre_rocrate/exceptions.py`
- **All dispatcher VRE handlers** — zero changes
- Dispatcher tasks (`app/celery/tasks.py`) — still calls `RequestPackageBuilder.build(crate_dict)`

## 10. What Gets Updated

- `src/vre_rocrate/building/package.py` — `RequestPackageBuilder` updated to parse new format, extract `raw_definition`
- `src/vre_rocrate/parsing/validator.py` — validation for new crate entities
- **All test fixtures** (`tests/fixtures/*/ro-crate-metadata.json`) — reformatted to new RO-Crate structure
- Test builder (`tests/test_building/test_rocrate.py`) — uses `VRELaunchRequest`
- Test models (`tests/test_models/`) — new `test_launch.py`, updated `test_package.py`
- **All `examples/*.py`** — converted from `MinimalVRERequest` to `VRELaunchRequest`

## 11. Examples Conversion

All five examples are rewritten from the old minimal API to the new launch-request API.
`dataset` is set to `None` unless the VRE launch genuinely depends on a browsed
upstream dataset (e.g. ScienceMesh OCM share, RRP DOI, Zenodo binder). For the
examples where a dataset was artificially constructed (replay_github, sciencemesh),
the artificial `DatasetHandle` is removed—the examples correctly use `dataset=None`.
By default, `runtime_platform` is omitted unless an explicit override is desired.

### `examples/galaxy.py`

```python
import json
from vre_rocrate import (
    VRELaunchRequest, ToolMeta, LaunchInput,
    SlotDefinition, SlotValue, FileInput, RocrateBuilder,
)

WORKFLOW_URL = (
    "https://dockstore.org/api/ga4gh/trs/v2/tools/%23workflow%2Fgithub.com"
    "%2Flaitanawe%2Fismb2024%2Fgalaxy_example/versions/main/PLAIN_GALAXY"
    "/descriptor/Galaxy-Workflow-reverse_file_galaxy_workflow.ga"
)

request = VRELaunchRequest(
    tool=ToolMeta(
        id="galaxy-reverse-file",
        version="main",
        name="Galaxy reverse file workflow",
        uri=WORKFLOW_URL,
        types=["galaxy_workflow", "workflowhub"],
        description="A simple Galaxy workflow for demonstration purposes.",
        slots=[
            SlotDefinition(
                id="simpletext_input",
                name="simpletext_input",
                slot_type="file",
                is_optional=False,
            ),
        ],
        raw_definition={},
    ),
    input=LaunchInput(
        dataset=None,
        slots={
            "simpletext_input": SlotValue(
                file=FileInput(
                    name="simpletext_input",
                    url="https://example-files.online-convert.com/document/txt/example.txt",
                    mime_type="txt",
                )
            ),
        },
        files={},
    ),
)

print(json.dumps(RocrateBuilder.build_from_launch_request(request), indent=2))
```

### `examples/mddash.py`

```python
import json
from vre_rocrate import (
    VRELaunchRequest, ToolMeta, LaunchInput,
    SlotDefinition, SlotValue, FileInput, RocrateBuilder,
)

PDB_ID = "1L2Y"

request = VRELaunchRequest(
    tool=ToolMeta(
        id="mddash-example",
        version="1.0.0",
        name="MDDash notebook",
        uri="https://github.com/sb-ncbr/mddash-notebooks.git",
        types=["mddash"],
        description="MDDash notebook for PDB analysis.",
        slots=[
            SlotDefinition(
                id="pdb_id",
                name="pdb_id",
                slot_type="string",
                is_optional=False,
            ),
        ],
        raw_definition={},
    ),
    input=LaunchInput(
        slots={"pdb_id": SlotValue(value=PDB_ID)},
    ),
)

print(json.dumps(RocrateBuilder.build_from_launch_request(request), indent=2))
```

### `examples/replay_github.py`

```python
import json
from vre_rocrate import (
    VRELaunchRequest, ToolMeta, LaunchInput, FileInput, RocrateBuilder,
)

REPLAY_RUNTIME = "https://replay.notebooks.egi.eu"

request = VRELaunchRequest(
    tool=ToolMeta(
        id="datalens-notebook",
        version="unknown",
        name="DataLens notebook",
        uri="https://github.com/andrejcermak/DataLens",
        types=["egi-replay"],
        description="DataLens notebook hosted on GitHub.",
        slots=[
            # NOTE: No formal slots — the notebook binder doesn't declare
            # file parameters. The CSV below goes to input.files, not slots.
        ],
        raw_definition={},
    ),
    input=LaunchInput(
        # dataset=None — EGI Replay binder doesn't strictly need it;
        # a real datahugger/filemetrix dataset would be populated by
        # req-packager when one is actually browsed.
        dataset=None,
        slots={},
        files={
            "MuRun2010B.csv": FileInput(
                name="MuRun2010B.csv",
                url="https://github.com/EOSC-Data-Commons/dataplayer-example-dataset"
                    "/blob/master/cernbox/CMSDimuon/MuRun2010B.csv",
                mime_type="text/csv",
            ),
        },
    ),
    runtime_platform=REPLAY_RUNTIME,  # explicit override for EGI Replay
)

print(json.dumps(RocrateBuilder.build_from_launch_request(request), indent=2))
```

### `examples/sciencemesh.py`

```python
import json
from vre_rocrate import (
    VRELaunchRequest, ToolMeta, LaunchInput,
    DatasetHandle, SlotDefinition, SlotValue, FileInput, RocrateBuilder,
)

WORKFLOW_URL = (
    "https://raw.githubusercontent.com/dpiparo/swanExamples/"
    "refs/heads/master/notebooks/CMSDimuon_py.ipynb"
)

request = VRELaunchRequest(
    tool=ToolMeta(
        id="cms-dimuon-notebook",
        version="1.0.0",
        name="CMS Dimuon py notebook",
        uri=WORKFLOW_URL,
        types=["sciencemesh"],
        description="Jupyter notebook for analyzing research data in ScienceMesh environment.",
        slots=[
            SlotDefinition(
                id="Shared With",
                name="Shared With",
                slot_type="string",
                is_optional=False,
            ),
        ],
        raw_definition={},
    ),
    input=LaunchInput(
        # dataset=None — sciencemesh OCM share doesn't need it;
        # the title/description come from the dispatcher-side OCMData
        # (root dataset name/description) instead.
        dataset=None,
        slots={"Shared With": SlotValue(value="rwelande@eosc.cernbox.cern.ch")},
        files={
            "MuRun2010B.csv": FileInput(
                name="MuRun2010B.csv",
                url="https://raw.githubusercontent.com/dpiparo/swanExamples/master/notebooks/MuRun2010B.csv",
                mime_type="text/csv",
            ),
        },
    ),
)

print(json.dumps(RocrateBuilder.build_from_launch_request(request), indent=2))
```

### `examples/vip.py`

```python
import json
from vre_rocrate import (
    VRELaunchRequest, ToolMeta, LaunchInput,
    SlotDefinition, SlotValue, FileInput, RocrateBuilder,
)

parameter_file = FileInput(
    name="parameter_file",
    url="https://www.creatis.insa-lyon.fr/~abonnet/quest_param_117T_A.txt",
    mime_type="txt",
)
data_file = FileInput(
    name="data_file",
    url="https://www.creatis.insa-lyon.fr/~abonnet/Rec003_Vox1.mrui",
    mime_type="application/octet-stream",
)
zipped_folder = FileInput(
    name="zipped_folder",
    url="https://www.creatis.insa-lyon.fr/~abonnet/basis_11_7.zip",
    mime_type="application/zip",
)

request = VRELaunchRequest(
    tool=ToolMeta(
        id="cquest-pipeline",
        version="0.6",
        name="CQUEST Pipeline",
        uri="https://vip.creatis.insa-lyon.fr/rest/pipelines/CQUEST/0.6",
        types=["boutique", "vip"],
        description="CQUEST pipeline for VIP platform.",
        slots=[
            SlotDefinition(
                id="parameter_file",
                name="parameter_file",
                slot_type="file",
                is_optional=False,
            ),
            SlotDefinition(
                id="data_file",
                name="data_file",
                slot_type="file",
                is_optional=False,
            ),
            SlotDefinition(
                id="zipped_folder",
                name="zipped_folder",
                slot_type="file",
                is_optional=False,
            ),
        ],
        raw_definition={},
    ),
    input=LaunchInput(
        dataset=None,
        slots={
            "parameter_file": SlotValue(file=parameter_file),
            "data_file": SlotValue(file=data_file),
            "zipped_folder": SlotValue(file=zipped_folder),
        },
        files={},
    ),
)

print(json.dumps(RocrateBuilder.build_from_launch_request(request), indent=2))
```

## 12. Implementation Steps

1. Create `src/vre_rocrate/models/launch.py` with all new dataclasses
2. Add `TOOL_TYPE_TO_VRE_TYPE`, `VRE_TYPE_TO_DEFAULT_RUNTIME_PLATFORM`, and `resolve_vre_type()` to `constants.py`
3. Add `RocrateBuilder.build_from_launch_request()` to `building/rocrate.py`
4. Update `tools/rocrate.py` — remove `build_from_minimal()`
5. Update `models/__init__.py` — export launch types, drop minimal
6. Delete `models/minimal.py`
7. Update `building/package.py` — `RequestPackageBuilder` parses new format
8. Update `parsing/validator.py` — validate new format
9. Update `vre_rocrate/__init__.py` — expose new public API
10. Update all test fixtures to new RO-Crate format
11. Rewrite test_minimal.py → test_launch.py
12. Update test_rocrate.py to use VRELaunchRequest
13. Update test_package.py for new RequestPackage fields
14. Convert all `examples/*.py` to `VRELaunchRequest`
15. Run full test suite (including examples as smoke test)
16. Verify dispatcher still boots and VRE handlers still work
