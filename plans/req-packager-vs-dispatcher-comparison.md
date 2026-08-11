# req-packager `Dispatcher` Mock vs Real Dispatcher — Comparison

This document compares the **mocked `Dispatcher` trait** defined in
[`req-packager/src/lib.rs`](file:///home/andrej/Documents/Coding/req-packager/src/lib.rs)
with how the **real dispatcher** actually works.
Domain-language differences (naming, field structure) are noted but not dwelled on —
the focus is on **semantic and behavioral gaps**.

---

## 1. Launch: Signature vs Reality

### req-packager mock (`Dispatcher::launch`)

```rust
// lib.rs:1084-1095
pub trait Dispatcher {
    async fn launch(
        &self,
        user_info: &UserInfo,
        token: &RawToken,
        tool: &ToolMeta,
        input: &LaunchInput,
        api_keys: &HashMap<String, String>,
    ) -> anyhow::Result<Uuid>;
    // ...
}
```

Inputs:
| Param | Type | Role |
|---|---|---|
| `user_info` | `UserInfo` (sub, email, name, preferred_username) | Identity of caller |
| `token` | `RawToken` (String) | OAuth2 access token |
| `tool` | `ToolMeta` (id, version, name, uri, types[], slots[], kind, raw_definition) | Which VRE/tool to launch |
| `input` | `LaunchInput` (dataset + slots + files) | Data + parameters |
| `api_keys` | `HashMap<String, String>` | Per-service API keys |

Returns: `Uuid` (task handler ID).

### Real dispatcher

The real dispatcher exposes **two** equivalent endpoints, both wrapping the same
Celery task pipeline:

```
POST /requests/zip_rocrate/        ← RO-Crate in a ZIP with file blobs
POST /requests/metadata_rocrate/   ← bare RO-Crate JSON (no file content)
```

Both return: `{"task_id": "<celery-uuid>"}`.

The task pipeline ([`app/celery/tasks.py`](file:///home/andrej/Documents/Coding/dispatcher/app/celery/tasks.py)):

```
ROCrate JSON → RequestPackageBuilder.build() → RequestPackage
    → VREFactory(token, request_id, update_state, request_package)
        → vre_handler.post() → callback URL
```

User identity (`user_info`) is **extracted from the OAuth2 middleware** (EGI Check-in JWT)
via FastAPI's dependency injection — it is never embedded in the RO-Crate payload.
The `token` is also extracted from the `Authorization: Bearer` header by the same middleware.

### Gap Analysis

| Aspect | req-packager mock | Real dispatcher | Gap |
|---|---|---|---|
| **User identity** | Passed as explicit `user_info: &UserInfo` param | Extracted from JWT by OAuth2 middleware (`request.auth.provider.access_token`) | Different plumbing — identity flows out-of-band in real dispatcher |
| **Auth token** | Passed as explicit `token: &RawToken` param | Same — extracted from JWT by OAuth2 middleware | Same concern, different plumbing |
| **Tool identity** | `ToolMeta` (rich: id, version, slots, kind, raw_definition) | `RequestPackage.workflow` (URL/DOI) + `RequestPackage.vre_type` + `RequestPackage.workflow_inputs` (FormalParameter list) | **Largest semantic gap** — see §4 |
| **Files** | `LaunchInput.files: HashMap<RenameName, FileEntry>` (with size, checksum, mime, path) | `RequestPackage.files: list[FileReference]` (id, name, encoding_format, url) | `FileEntry` is richer; real `FileReference` lacks size/checksum/path |
| **Slot parameters** | `LaunchInput.slots: HashMap<SlotName, SlotValue>` (values or files per tool-defined slot) | `RequestPackage.workflow_inputs: list[FormalParameter]` (parameter definitions + optional defaults) | Slot *values* (user-filled) don't exist in real dispatcher yet — only declarations |
| **Dataset handle** | `LaunchInput.dataset: DatasetHandle` (url, title, description) | **Not present** in current RO-Crate or `RequestPackage` | Entirely new concept |
| **API keys** | `api_keys: &HashMap<String, String>` | Hardcoded per-VRE (e.g. `VIP_API_KEY` in `vip.py:13`, `token` from JWT) | Per-service keys are hardcoded, not passed dynamically |
| **Return value** | `Uuid` (task handler ID) | `{"task_id": "<celery-uuid>"}` | Same semantics: opaque task ID |

---

## 2. Task Lifecycle: `get_state` / `get_artifact` vs Celery Polling

### req-packager mock

```rust
async fn get_state(&self, handler_id: &Uuid) -> anyhow::Result<ToolState>;
async fn get_artifact(&self, handler_id: &Uuid) -> anyhow::Result<Artifact>;
```

- `ToolState` = Preparing | Ready | Dropped | Exception
- `Artifact` = HostedTool { callback: Url } | EoscInlineTool { callback: Url } | FailedTool

### Real dispatcher

```
GET /requests/{task_id}
→ {"task_id": "...", "status": "PENDING|STARTED|SUCCESS|FAILURE", "result": {...}}
```

Task result on SUCCESS: `{"url": "https://..."}` (a callback URL).
The VRE handler's `post()` method returns a URL string — this is the **artifact**.

The real dispatcher uses **Celery** for async execution. Statuses map as:

| Celery state | Mock `ToolState` equivalent |
|---|---|
| PENDING | Preparing |
| STARTED | Preparing |
| SUCCESS | Ready |
| FAILURE | Exception |

### Gap Analysis

| Aspect | req-packager mock | Real dispatcher |
|---|---|---|
| State machine | `ToolState` enum (4 states) | Celery task states (PENDING/STARTED/SUCCESS/FAILURE/RETRY) |
| Artifact shape | Typed enum: `HostedTool`, `EoscInlineTool`, `FailedTool` | Plain string URL (no type discrimination) |
| Polling model | `get_state()` + `get_artifact()` as two calls | Single `GET /requests/{task_id}` returns both status and result |
| Drop/cancel | `DropRequest` in gRPC, trait not yet impl'd | No cancel endpoint in real dispatcher |

---

## 3. Query: `query_tasks` vs Real Dispatcher

### req-packager mock

```rust
async fn query_tasks(&self, uid: &str) -> anyhow::Result<Vec<TaskHandler>>;
```
Where `TaskHandler` = id (Uuid) + user_id + state + artifact.

### Real dispatcher

**No equivalent endpoint exists.** The real dispatcher has no `GET /requests` endpoint
to list all tasks for a user. It only has `GET /requests/{task_id}` for individual status polls.

This is a functionality gap — the mock assumes user-level task querying that
the real dispatcher does not yet implement.

---

## 4. Tool Resolution: The Critical Semantic Gap

### req-packager mock: ToolMeta → VRE

In req-packager, the tool is selected from a **tool registry** (generic JSON registry
of EOSC tools). A `ToolMeta` includes:

- `id` — e.g. `"::st:001"`
- `types` — e.g. `["general", "egi-replay"]`
- `slots` — parameter definitions with types
- `kind` — `DatasetOnly` | `SlotsOnly` | `FilesOnly` | `SlotsAndFiles`
- `raw_definition` — opaque JSON containing tool-specific config (e.g. `{"urlpath": "notebooks/python.ipynb"}`)

### Real dispatcher: Workflow URL + ComputerLanguage → VRE

The real dispatcher resolves VRE handlers via **programming language URL** (from
`RequestPackage.programming_language`) looked up in `VREFactory.table`:

| Programming Language URL | VRE Handler | Registration |
|---|---|---|
| `https://galaxyproject.org/` | `VREGalaxy` | `galaxy.py:113` |
| `https://jupyter.org/binder/` | `VREBinder` | `binder.py:81` |
| `https://vip.creatis.insa-lyon.fr/` | `VREVIP` | `vip.py:87` |
| `https://oscar.grycap.net/` | `VREOSCAR` | `oscar.py:113` |
| `http://scipion.i2pc.es/` | `VREScipion` | `scipion.py:18` |
| `https://jupyter.org` | `VREJupyter` | `jupyter.py:120` |
| `https://eosc.cernbox.cern.ch` | `VREScienceMesh` | `sciencemesh.py:94` |
| `https://github.com/CERIT-SC/mddash` | `VREMDDash` | `mddash.py:185` |

### Gap

The real dispatcher has **no concept of a generic tool registry**. It only knows
hardcoded VRE types. The `ToolMeta.slots`, `ToolMeta.kind`, and `ToolMeta.raw_definition`
have **no equivalent** in the current dispatcher — they would need to be projected into:

- `RequestPackage.workflow` (from `ToolMeta.uri`)
- `RequestPackage.workflow_inputs` (from `ToolMeta.slots`)
- Or passed through as opaque properties

This is where the `VRELaunchRequest` transformation bridges the gap: it maps
`ToolMeta` → `vre_type` + `WorkflowDescriptor` + `FormalParameter[]`, and maps
`LaunchInput.slots` → `FormalParameter.defaultValue` entries.

---

## 5. File Handling Depth

### req-packager: `FileEntry`

```rust
pub struct FileEntry {
    pub download_url: Option<String>,
    pub path: String,
    pub is_dir: bool,
    pub size_bytes: u64,
    pub mime_type: Option<String>,
    pub checksum: Option<String>,
    pub modified_at: DateTime<Utc>,
}
```

This is a **browse-result** type — files discovered by enumerating a dataset.
The `path` is the original path within the dataset; `download_url` is where to fetch it.

### Real dispatcher: `FileReference`

```python
@dataclass
class FileReference:
    id: str                    # @id or URL
    name: str
    encoding_format: str | None
    url: str | None
    onedata_domain: str | None
    onedata_file_id: str | None
    properties: dict[str, Any]  # catch-all
```

This is simpler — mostly a URL + name + MIME hint. No size, no checksum,
no original path, no modified timestamp.

The richer `FileEntry` fields would land in `FileReference.properties` or
as new optional fields on `FileReference`.

---

## 6. Per-VRE handler: What Each `post()` Actually Needs

| VRE Handler | Reads from `RequestPackage` | What it actually uses |
|---|---|---|
| **VREBinder** | `workflow.zenodo_doi`, `local_files[]`, `local_files[].id`, `local_files[].properties.content` | Workflow identifier (DOI or git) + notebook file content |
| **VREGalaxy** | `workflow_url`, `input_files[]`, `input_files[].name`, `input_files[].url`, `input_files[].encoding_format`, `input_files[].onedata_file_id` | Workflow URL + file URLs + MIME-derived filetype |
| **VREVIP** | `workflow_url`, `input_files[]`, `input_files[].url`, `input_files[].name` | Pipeline identifier (from workflow URL) + input file URLs |
| **VREOSCAR** | `workflow_url`, `oscar_input_files[]`, `oscar_input_files[].url` | FDL JSON URL + input file URLs for job invocation |
| **VREScipion** | (nothing) | Just returns `svc_url` — no data from package |
| **VREJupyter** | `files[]`, `files[].id`, `files[].properties.content` | Notebook .ipynb file content |
| **VREMDDash** | `workflow.url`, `input_files[]`, `input_files[].name` | PDB filename + notebooks repo URL |
| **VREScienceMesh** | `ocm_data`, `files[]`, `raw_crate` | OCM share metadata + raw crate as embedded payload |

**Observation**: Most handlers only need (a) a workflow identifier URL, (b) file URLs or file content.
None of the current handlers use slot values, dataset handles, tool version, or tool kind.
Those are future-facing concepts that would be needed once the dispatcher consumes
`VRELaunchRequest`-shaped input.

---

## 7. Summary of Gaps

| # | Gap | Impact on `VRELaunchRequest` design |
|---|---|---|
| 1 | `ToolMeta` → generic tool registry not present in dispatcher | Mapping table `TOOL_TYPE_TO_VRE_TYPE` + `resolve_vre_type()` needed |
| 2 | `LaunchInput.slots` (user-filled values) no equivalent | Slots become `FormalParameter` entities with `defaultValue` |
| 3 | `LaunchInput.dataset` (DatasetHandle) no equivalent | Optional new `Dataset` entity in RO-Crate |
| 4 | `FileEntry` richer than `FileReference` | New optional properties (`contentSize`, `sha256`, `path`) — stored in `FileReference.properties` for backward compat |
| 5 | `get_state` + `get_artifact` as two calls vs single Celery poll | Not relevant to RO-Crate transformation — transport concern |
| 6 | `query_tasks` not implemented in real dispatcher | Not relevant to RO-Crate transformation |
| 7 | API keys per-service | Not relevant to RO-Crate — transport concern |
| 8 | `UserInfo` identity explicit vs JWT-extracted | User info stays out of RO-Crate entirely |
