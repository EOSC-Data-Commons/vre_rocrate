# MockDispatcher::launch vs Real VRE Handlers — Per-VRE Comparison

This document compares each branch in `MockDispatcher::launch()`
([`req-packager/src/main.rs:522-1518`](file:///home/andrej/Documents/Coding/req-packager/src/main.rs:522))
against the corresponding real VRE handler in the dispatcher.  Domain-language
differences (ToolMeta vs RequestPackage, FileEntry vs FileReference) are noted
but not the focus — the comparison targets *behavioral* and *structural* gaps.

---

## Branch 1: Galaxy WorkflowHub

### Mock (`main.rs:663-766`)

**Trigger**: `tool.types` contains both `"galaxy_workflow"` and `"workflowhub"`

**What it does**:
1. Extracts `workflow_id` from the last segment of `tool.uri`
2. Calls WorkflowHub's TRS API to resolve the version ID from `tool.version` name
3. Builds a `request_state` map from `input.slots`:
   - Iterates slots, skipping non-file values (`SlotValue::Value → todo!()`)
   - For `SlotValue::File`: extracts `download_url` as location, file extension as `filetype`
   - Produces `{"class": "File", "filetype": "...", "location": "..."}`
4. POSTs to `https://usegalaxy.eu/api/workflow_landings` with:
   ```json
   {
     "public": false,
     "workflow_id": "<trs_url>",
     "workflow_target_type": "trs_url",
     "request_state": { <key → {class,filetype,location}> }
   }
   ```
5. Extracts `uuid` from response, builds callback URL `https://usegalaxy.eu/workflow_landings/{uuid}?public=false`
6. Stores `TaskHandler` in in-memory HashMap

**Key observations**:
- Calls **Galaxy directly** — does not go through dispatcher
- Uses `input.slots` (not `input.files`) to build the request_state
- Workflow ID resolved from WorkflowHub TRS API
- `request_state` keys come from slot names (after finding matching slot id via `tool.slots`)

### Real dispatcher: `VREGalaxy` ([`app/vres/galaxy.py`](file:///home/andrej/Documents/Coding/dispatcher/app/vres/galaxy.py))

**Trigger**: `programming_language == "https://galaxyproject.org/"` (via `VREFactory`)

**What it does**:
1. Reads `workflow_url` from `RequestPackage.workflow.url`
2. Reads files from `RequestPackage.input_files` (resolved from FormalParameters)
3. For each file, extracts `encoding_format` (split on `/` for filetype), `url` as location
   - Special case for `onedata_file_id`: constructs onedata share URL as location
4. POSTs to `{svc_url}/api/workflow_landings` with:
   ```json
   {
     "public": false,
     "request_state": { <name → {class,filetype,location}> },
     "workflow_id": "<url>",
     "workflow_target_type": "trs_url"
   }
   ```
5. Extracts `uuid`, builds callback URL `{svc_url}/workflow_landings/{uuid}?public=false`

### Comparison

| Aspect | Mock | Real VREGalaxy |
|---|---|---|
| **Trigger mechanism** | `tool.types` intersection check | `programming_language` URL match in `VREFactory` |
| **Workflow URL source** | `tool.uri` → WorkflowHub TRS version resolution | `RequestPackage.workflow.url` (already resolved) |
| **Version resolution** | Calls WorkflowHub TRS API to map version name → version ID | None — version must already be in the URL |
| **Input files source** | `input.slots` (keyed by slot name) | `RequestPackage.input_files` (from FormalParameter defaults) |
| **File location** | `SlotValue::File.download_url` | `FileReference.url` or `FileReference.id` |
| **Filetype deduction** | `file.path.rsplit('.').next()` | `encoding_format.split("/")[-1]` |
| **Onedata support** | ❌ Not present | ✅ Constructs onedata share URL from `onedata_file_id`/`onedata_domain` |
| **Galaxy endpoint** | Hardcoded `https://usegalaxy.eu/` | `svc_url` (from runtimePlatform or default config) |
| **Token** | None sent to Galaxy | None sent to Galaxy (no auth on workflow_landings) |
| **Payload structure** | Identical JSON shape | Identical JSON shape |
| **Error handling** | `.unwrap()` on missing slot id | Raises `WorkflowURLError` if workflow URL is None |
| **`SlotValue::Value` (primitive)** | `todo!()` — not implemented | N/A (current FormalParameters only have file defaults) |

**Gap**: The mock resolves the workflow version from WorkflowHub's TRS API, but the real VREGalaxy expects the version to already be embedded in the workflow URL. The `VRELaunchRequest` builder needs to either resolve the version or pass the resolved URL.

---

## Branch 2: VIP

### Mock (`main.rs:767-877`)

**Trigger**: `tool.types` contains both `"boutique"` and `"vip"`

**What it does**:
1. Extracts API key from `api_keys["vip"]`, sets it as header
2. Builds `inputValues` from `input.slots`:
   - Looks up slot definition from `tool.slots` by name → gets `slot.id`
   - `SlotValue::Value` → raw JSON value, keyed by `slot.id`
   - `SlotValue::File` → `download_url` as string value, keyed by `slot.id`
3. Constructs pipeline identifier from `tool.name/tool.version`
4. POSTs to `https://vip.creatis.insa-lyon.fr/test/rest/executions`:
   ```json
   {
     "name": "eosc-{task_id}",
     "pipelineIdentifier": "<name>/<version>",
     "resultsLocation": "/vip/Home",
     "inputValues": { <slot_id → value_or_url> }
   }
   ```
5. Returns callback `https://vip.creatis.insa-lyon.fr/home.html`

### Real dispatcher: `VREVIP` ([`app/vres/vip.py`](file:///home/andrej/Documents/Coding/dispatcher/app/vres/vip.py))

**Trigger**: `programming_language == "https://vip.creatis.insa-lyon.fr/"`

**What it does**:
1. Uses hardcoded `VIP_API_KEY = "9pr5fpfnom57hphp06ee9co70f"` (not from api_keys param)
2. Extracts pipeline identifier by parsing the last two path segments of `workflow_url`
3. Maps `input_files` → `inputValues` keyed by `FileReference.name`
4. POSTs to `{svc_url}/rest/executions`:
   ```json
   {
     "name": "vip-execution-{request_id}",
     "pipelineIdentifier": "<parsed from URL>",
     "resultsLocation": "/vip/Home",
     "inputValues": { <name → url> }
   }
   ```
5. Returns `{svc_url}/home.html`

### Comparison

| Aspect | Mock | Real VREVIP |
|---|---|---|
| **API key** | From `api_keys["vip"]` (passed dynamically) | Hardcoded `VIP_API_KEY` constant |
| **Pipeline identifier** | `tool.name/tool.version` | Parsed from last two path segments of `workflow_url` |
| **Input values source** | `input.slots`, mapped by `slot.id` | `input_files`, mapped by `FileReference.name` |
| **Slot ID resolution** | Looks up `tool.slots` to find `slot.id` by matching `slot.name` | No slot concept — uses file names directly |
| **Primitive values in slots** | Supported: `SlotValue::Value(v)` → raw JSON | Not supported — only file URLs |
| **VIP endpoint** | Hardcoded `https://vip.creatis.insa-lyon.fr/test/` | `svc_url` from runtimePlatform or default |
| **Execution name** | `"eosc-{task_id}"` | `"vip-execution-{request_id}"` |

**Gap**: The mock uses `slot.id` as keys in `inputValues` while the real handler uses `file.name`. This is a significant semantic difference — the mock's VIP slot logic (where slot.id like "parameter_file" is the VIP parameter name) is richer than the real handler's simple file-name mapping.

---

## Branch 3: MyBinder (simple)

### Mock (`main.rs:878-898`)

**Trigger**: `tool.types` contains `"mybinder"`

**What it does**: Simply returns `input.dataset.url` as the callback URL. No API calls.

### Real dispatcher: `VREBinder` ([`app/vres/binder.py`](file:///home/andrej/Documents/Coding/dispatcher/app/vres/binder.py))

**Trigger**: `programming_language == "https://jupyter.org/binder/"`

**What it does**:
1. Checks for Zenodo DOI in `workflow.zenodo_doi`
2. If DOI: returns `{svc_url}/v2/zenodo/{doi}/`
3. If no DOI: creates a local git repo from `local_files`, initializes git, returns `{svc_url}/git/{encoded_url}/HEAD`

### Comparison

| Aspect | Mock | Real VREBinder |
|---|---|---|
| **DOI/Zenodo support** | ❌ Not present | ✅ Parses Zenodo DOI from workflow |
| **File handling** | ❌ Doesn't use files at all | ✅ Creates local git repo from file content |
| **Callback** | Returns `input.dataset.url` directly | Returns constructed BinderHub URL |
| **Complexity** | Trivial passthrough | Full git repo initialization + Binder URL construction |

**Gap**: The mock's "mybinder" is a trivial stub. The real `VREBinder` does significant work (git repo creation, file staging). The mock would need `input.files` with actual file content to match the real behavior.

---

## Branch 4: Binder-Launcher

### Mock (`main.rs:899-1034`)

**Trigger**: `tool.types` contains `"binder-launcher"`

**What it does**:
1. Reads from `tool.raw_definition`: `binder_base`, `launcher_repo`, `launcher_ref`, `target_repo`, `branch`, `notebook_path`
2. Constructs inner URL path with query params (repo, branch, notebookpath, overwrite, cleanup, run_postbuild)
3. Adds `env` key-value pairs from `raw_definition.env`
4. Appends `data_files` from `input.files` (each file: `{url: download_url, path: rename_name}`)
5. Appends dataset URL
6. Builds final callback: `{binder_base}/v2/gh/{launcher_repo}/{launcher_ref}?urlpath=launch?...&data=[...]`

### Real dispatcher

**No equivalent VRE handler exists.** The `binder-launcher` concept is entirely mock-only — it's a specialized BinderHub URL builder that packages repo info, notebook path, environment variables, and data file references into a single URL. The real dispatcher would need a new VRE handler for this.

**What would be needed**: `raw_definition` fields (`binder_base`, `launcher_repo`, `launcher_ref`, `target_repo`, `branch`, `notebook_path`, `env`) passed through to a `VREBinderLauncher` class. These could live in the `WorkflowDescriptor.properties` dict or as a new opaque field on `RequestPackage`.

---

## Branch 5: EGI Replay

### Mock (`main.rs:1035-1075`)

**Trigger**: `tool.types` contains `"egi-replay"`

**What it does**:
1. Reads: `replay_index = "https://replay.notebooks.egi.eu/v2/gh"`, `tool.name`, `tool.version`
2. Extracts `urlpath` from `tool.raw_definition["urlpath"]`
3. Gets `dataset_url` from `input.dataset.url`
4. Constructs callback: `{replay_index}/{tool_name}/{version}?urlpath={urlpath}?dataset_url={dataset_url}`

### Real dispatcher: `VREBinder`

**Trigger**: `programming_language == "https://jupyter.org/binder/"`

The real `VREBinder` already handles EGI Replay via `runtimePlatform`. When the crate has `runtimePlatform: "https://replay.notebooks.egi.eu/v2"`, the `svc_url` is set to that value, and the `VREBinder.post()` constructs the BinderHub URL using that base.

### Comparison

| Aspect | Mock "egi-replay" | Real VREBinder |
|---|---|---|
| **Base URL** | Hardcoded `https://replay.notebooks.egi.eu/v2/gh` | From `runtimePlatform` (or `BINDER_DEFAULT_SERVICE`) |
| **Tool repo** | `tool.name` (e.g. `EOSC-Data-Commons/binder-python-tool`) | From `workflow.zenodo_doi` or local git repo |
| **Version** | `tool.version` (e.g. `v0.1.1`) | In Zenodo mode: embedded in DOI. In git mode: uses main branch |
| **Notebook path** | `tool.raw_definition["urlpath"]` | N/A (Zenodo DOI points to full repo, git mode uses repo contents) |
| **Dataset URL** | Appended as `?dataset_url=...` | ❌ Not passed |
| **File handling** | ❌ None | ✅ Writes local file content to git repo |

**Gap**: The mock "egi-replay" is a simple URL constructor with `raw_definition` fields driving the URL structure. The real `VREBinder` either uses Zenodo DOI or creates a local git repo. These are fundamentally different approaches — the mock constructs a URL pointing to an existing repo, while the real handler provisions a new git repo from file content. However, the mock's `raw_definition.urlpath` + `tool.name`/`tool.version` → Binder URL pattern is essentially a simplified version of what `VREBinder` does with `runtimePlatform`.

---

## Branch 6: CernBox / ScienceMesh

### Mock (`main.rs:1076-1251`)

**Trigger**: `tool.types` contains `"cernbox"`

**What it does**:
1. Extracts `share_with` from `input.slots["Shared With"]` (must be string value)
2. Constructs `share_with = "{user}@{domain}"` (domain = `eosc.cernbox.cern.ch`)
3. Reads `owner` and `email` from `user_info`
4. **Builds an RO-Crate inline** via `create_rocrate()`:
   - Root Dataset with `name` = `input.dataset.title`
   - File entities from `input.files` (name, encodingFormat=mime_type, url=download_url)
   - Static entities: `#destination` (Service), `#creator`, `#sender`, `#receiver` (Person with `userid=share_with`)
   - `ro-crate-metadata.json` descriptor
5. Constructs OCM share payload with `resourceType: "ro-crate"`, `protocol.embedded.payload` = the crate
6. POSTs to `https://eosc.cernbox.cern.ch/ocm/shares`
7. Returns `https://eosc.cernbox.cern.ch` as callback

### Real dispatcher: `VREScienceMesh` ([`app/vres/sciencemesh.py`](file:///home/andrej/Documents/Coding/dispatcher/app/vres/sciencemesh.py))

**Trigger**: `programming_language == "https://eosc.cernbox.cern.ch"`

**What it does**:
1. Reads OCM parties from generic `RequestPackage` accessors (`OCMData` was retired):
   - `Shared With` slot value via `RequestPackage.input_by_name("Shared With")`
   - `root_name`, `root_description` from root Dataset ( `get_entity("./")` )
   - `resource_id` always a fresh UUID (crate-stable ID derivation is still a TODO; nothing emits `#identifier`)
2. Extracts `sender_userid` and `sender_name` from the **JWT access token** (not from crate)
3. Posts `RequestPackage.raw_crate` directly as `protocol.embedded.payload`
4. POSTs to `{svc_url}/ocm/shares`

### Comparison

| Aspect | Mock | Real VREScienceMesh |
|---|---|---|
| **RO-Crate construction** | Built inline in `create_rocrate()` function | Uses `RequestPackage.raw_crate` (parsed from JSON) |
| **Receiver identity** | From `input.slots["Shared With"]` (slot value) | From the `"Shared With"` input slot value (no `#receiver` entity anymore) |
| **Sender identity** | From `user_info.email` + `user_info.name` | From JWT token (`extract_user_from_token`) |
| **Sender OCM address** | Constructed as `{email}@eosc-coordinator.ethz.ch` | Constructed as `{email}@{host}` |
| **Resource ID** | Uses `task_id` (UUID) | Always a fresh UUID (crate-stable derivation TODO) |
| **Crate structure** | Custom minimal crate (only root + files + receiver/creator/sender) | Uses existing `raw_crate` from the incoming RO-Crate |
| **File encoding** | `mime_type` from `FileEntry` | Already in crate entities |
| **File URL** | `download_url` from `FileEntry` | Already in crate entities |
| **Share endpoint** | Hardcoded `eosc.cernbox.cern.ch` | `svc_url` from runtimePlatform or config |
| **Workflow entity** | ❌ No mainEntity/workflow in mock's crate | ✅ Full crate with mainEntity, programmingLanguage, etc. |

**Critical semantic gap**: The mock **builds its own ad-hoc RO-Crate inside the dispatcher logic**. This is exactly what the `VRELaunchRequest → RocrateBuilder` transformation is meant to replace — instead of constructing crates inline, the mock should pass `ToolMeta + LaunchInput` through `vre_rocrate` to get a properly structured RO-Crate. Then the real `VREScienceMesh` can use `RequestPackage.raw_crate` as it already does.

The mock's slot-based `"Shared With"` → receiver pattern is now aligned with the real handler: both read the receiver as a slot value. The crate no longer materializes a `#receiver` entity — `OCMData` and the special-cased receiver generation were removed from the library.

---

## Branch 7: RRP (Reproducible Research Platform)

### Mock (`main.rs:1252-1515`)

**Trigger**: `tool.types` contains `"rrp"`

**What it does**:
1. Extracts DOI from `input.dataset.url` (strips `https://doi.org/` prefix)
2. Reads `docker_image` and `repository_url` from `tool.raw_definition`
3. Maps `input.slots` → `data_mounts`:
   - For each slot, looks up `tool.slots` by name → gets `slot.id`
   - `SlotValue::File` → `{"mountPath": slot.id, "source": {"type": "zenodo", "doi": doi}, "path": file_path}`
4. Creates project via `POST {backend}/external/dispatcher/v1/projects` with docker image + resources + dataMounts
5. Polls for project `creationStatus == "Ready"` (up to 20 attempts)
6. Clones repository from `repository_url` into project
7. Polls clone execution for success
8. Checks out `main` branch
9. Triggers data retrieval
10. Polls until all data slots report `"Available"` status
11. Returns `{backend}/projects/{project_code}` as callback

### Real dispatcher

**No equivalent VRE handler exists.** RRP is entirely mock-only. The real dispatcher would need a new `VRERRP` class registered with a new programming language URL.

**What would be needed**: The full RRP lifecycle (project creation, git clone, data staging, polling) in a new VRE handler. The `raw_definition` fields (`docker_image`, `repository_url`) and zenodo-based data mounts would need to flow through the RO-Crate.

---

## Branch 8: Fallback

### Mock (`main.rs:1515-1517`)

```rust
} else {
    panic!("unknown support VRE");
}
```

**Panics** on unrecognized tool types. This is a hard crash — no graceful error.

### Real dispatcher

The `VREFactory` raises `ValueError(f"Unsupported workflow language {elang}")` which propagates as a task failure in Celery. This is a soft error — the task marks as `FAILURE` with a message, not a process crash.

---

## Summary: Behavioral Gap Matrix

| VRE | Mock uses... | Real handler uses... | Gap |
|---|---|---|---|
| **Galaxy** | `input.slots` + direct Galaxy API call | `input_files` (from FormalParameter defaults) + Galaxy API | Slot→File mapping vs FormalParameter→File mapping. Mock resolves workflow version from TRS. |
| **VIP** | `input.slots` keyed by `slot.id` + dynamic API key | `input_files` keyed by `file.name` + hardcoded API key | Key mapping difference. Slot IDs vs file names. |
| **Binder** | `input.dataset.url` passthrough | Zenodo DOI + local git repo construction | Completely different. Mock is a stub. |
| **Binder-Launcher** | `raw_definition` + `input.files` + `input.dataset` → URL construction | **No equivalent** | Entirely new handler needed. |
| **EGI Replay** | `raw_definition.urlpath` + `tool.name/version` + `dataset.url` → URL | `VREBinder` with `runtimePlatform` = replay URL | Different approach; mock is URL constructor, real is git provisioner. |
| **ScienceMesh** | Builds RO-Crate inline + OCM share POST | Uses `raw_crate` from parsed RO-Crate + OCM share POST | **Mock should delegate crate construction to vre_rocrate** — this is the core motivation for the transformation. |
| **RRP** | Full project lifecycle: create, clone, checkout, data staging, polling | **No equivalent** | Entirely new handler needed. |

### Actions for the VRELaunchRequest Plan

1. **ScienceMesh** is the clearest win — the mock's inline `create_rocrate()` should become `RocrateBuilder.build_from_launch_request()`; the `"Shared With"` slot stays a `FormalParameter` (no `#receiver` entity is generated).

2. **Galaxy** — the mock's slot→file mapping is richer than the real handler's simple FormalParameter→file approach. The plan already accounts for this via `FormalParameter.defaultValue`.

3. **VIP** — the slot.id → VIP parameter name mapping should be preserved. The `raw_definition` or `ToolMeta.slots[].id` carries this mapping.

4. **Binder-Launcher** and **RRP** — new VRE handlers needed in the real dispatcher. Their `raw_definition` fields must flow through the RO-Crate (e.g., in `WorkflowDescriptor.properties` or a new opaque field).

5. **All branches** use `tool.types` intersection for dispatch. The transformation plan's `resolve_vre_type()` via `TOOL_TYPE_TO_VRE_TYPE` table covers this.
