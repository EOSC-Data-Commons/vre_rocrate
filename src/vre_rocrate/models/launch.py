"""Input models for VRELaunchRequest — the req-packager-aligned launch API."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DatasetHandle:
    """Packaged dataset; when set, the crate root is named after it."""

    url: str  # → Dataset entity @id + hasPart
    # → Dataset.name; when set, ./ (root) name → sciencemesh share "name"
    # (otherwise root name falls back to tool.name)
    title: str
    # → Dataset.description; when set, ./ description → sciencemesh share "description"
    description: str


@dataclass
class SlotDefinition:
    """Slots are looked up by name in every VRE: galaxy request_state,
    vip inputValues, mddash pdb_id, sciencemesh "Shared With"."""

    id: str  # → FormalParameter @id (#input-<id>) + workflow.input ref (structural)
    name: str  # → FormalParameter.name — the lookup key in every VRE
    slot_type: str  # "string" | "file" | "data_input" | "data_collection"
    is_optional: bool = False  # → FormalParameter.required (inverted); unread


@dataclass
class FileInput:
    """onedata fields drive the galaxy onedata upload location."""

    name: str  # → File.name — debug label only; no handler keys by it
    path: str | None = None  # ignored — never serialized
    url: str | None = None  # → File.@id + File.url; galaxy/vip fetch target
    size_bytes: int | None = None  # → File.contentSize; unread by VREs
    mime_type: str | None = None  # → File.encodingFormat; galaxy "filetype"
    checksum: str | None = None  # → File.sha256; unread by VREs
    checksum_type: str | None = None  # only "sha256" honored; others dropped
    onedata_domain: str | None = None  # → onedata:onezoneDomain (see class doc)
    onedata_file_id: str | None = None  # → onedata:fileId (see class doc)


@dataclass
class SlotValue:
    """Either a primitive value OR a file filling a tool-declared parameter."""

    value: Any = None  # scalar → defaultValue literal (mddash pdb_id, vip params)
    file: FileInput | None = None  # → File entity + defaultValue {"@id"} (binding)


@dataclass
class ToolMeta:
    id: str  # ignored — never serialized
    version: str  # → workflow.version; surfaced to handlers/logs only
    name: str  # → workflow.name (fallback: uri filename); ./ name if no dataset
    uri: str  # → workflow.@id / mainEntity; workflow_id / pipeline / notebooks-repo
    types: list[str]  # only used to resolve vre_type → programmingLanguage.identifier
    description: str = ""  # → workflow.description ("placeholder" fallback)
    slots: list[SlotDefinition] = field(default_factory=list)  # → FormalParameters
    raw_definition: dict[str, Any] = field(
        default_factory=dict
    )  # → #tool-metadata.rawDefinition (future-facing)


@dataclass
class LaunchInput:
    """files: standalone File entities (sciencemesh payload, binder/jupyter)."""

    dataset: DatasetHandle | None = None  # → Dataset entity; unread today
    slots: dict[str, SlotValue] = field(
        default_factory=dict
    )  # names match slots → each defaultValue
    files: dict[str, FileInput] = field(
        default_factory=dict
    )  # → standalone File entities (class doc)


@dataclass
class VRELaunchRequest:
    """Top-level input model — replaces MinimalVRERequest."""

    tool: ToolMeta  # → workflow entity + FormalParameters
    input: LaunchInput  # → hasPart files + slot defaultValues + optional Dataset
    runtime_platform: str | None = (
        None  # → runtimePlatform (installUrl / svc_url); default from VRE_TYPE constants
    )
