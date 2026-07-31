"""Input models for VRELaunchRequest — the req-packager-aligned launch API."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DatasetHandle:
    url: str
    title: str
    description: str


@dataclass
class SlotDefinition:
    id: str
    name: str
    slot_type: str  # "string" | "file" | "data_input" | "data_collection"
    is_optional: bool = False


@dataclass
class FileInput:
    name: str
    path: str | None = None
    url: str | None = None
    size_bytes: int | None = None
    mime_type: str | None = None
    checksum: str | None = None
    checksum_type: str | None = None  # "sha256", "md5"
    onedata_domain: str | None = None
    onedata_file_id: str | None = None


@dataclass
class SlotValue:
    """Either a primitive value OR a file filling a tool-declared parameter."""
    value: Any = None          # str | int | float | bool | None
    file: FileInput | None = None


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


@dataclass
class LaunchInput:
    dataset: DatasetHandle | None = None
    slots: dict[str, SlotValue] = field(default_factory=dict)
    files: dict[str, FileInput] = field(default_factory=dict)


@dataclass
class VRELaunchRequest:
    """Top-level input model — replaces MinimalVRERequest."""
    tool: ToolMeta
    input: LaunchInput
    runtime_platform: str | None = None
