from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

from .infrastructure import RuntimePlatform


@dataclass
class FormalParameter:
    id: str
    name: str
    additional_type: str | None = None
    encoding_format: str | None = None
    default_value: Any = None
    properties: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass
class FileReference:
    id: str
    name: str
    encoding_format: str | None = None
    url: str | None = None
    onedata_domain: str | None = None
    onedata_file_id: str | None = None
    properties: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass
class WorkflowDescriptor:
    id: str
    type: str
    url: str | None = None
    programming_language_id: str | None = None
    runtime_platform: str | RuntimePlatform | None = None
    properties: dict[str, Any] = field(default_factory=dict, repr=False)
    tool_version: str | None = None


@dataclass
class OCMData:
    """Data extracted from RO-Crate entities for OCM / ScienceMesh sharing."""

    receiver_userid: str | None = None
    owner_userid: str | None = None
    sender_userid: str | None = None
    sender_name: str | None = None
    root_name: str | None = None
    root_description: str | None = None
    resource_id: str | None = None


@dataclass
class RequestPackage:
    """Pure data container for a VRE request package.

    Construction logic lives in ``RequestPackageBuilder``.
    """

    vre_type: str
    programming_language: str  # redundant info to vre type
    workflow: WorkflowDescriptor
    files: list[FileReference] = field(default_factory=list)
    workflow_inputs: list[FormalParameter] = field(default_factory=list)
    workflow_outputs: list[FormalParameter] = field(default_factory=list)
    raw_crate: dict[str, Any] = field(default_factory=dict, repr=False)
    ocm_data: OCMData | None = None
    raw_definition: dict[str, Any] = field(default_factory=dict, repr=False)

    # -- data-access helpers -------------------------------------------------

    def files_by_encoding(self, encoding: str) -> list[FileReference]:
        return [f for f in self.files if f.encoding_format == encoding]

    def file_by_id(self, file_id: str) -> FileReference | None:
        for f in self.files:
            if f.id == file_id:
                return f
        return None

    def file_for_input(self, param: FormalParameter) -> FileReference | None:
        """Resolve an input slot's file binding via its default value, if any."""
        dv = param.default_value
        file_id = dv.get("@id") if isinstance(dv, dict) else dv
        return self.file_by_id(str(file_id)) if file_id else None

    @property
    def local_files(self) -> list[FileReference]:
        return [f for f in self.files if not f.id.startswith(("http://", "https://"))]

    @property
    def remote_files(self) -> list[FileReference]:
        return [f for f in self.files if f.id.startswith(("http://", "https://"))]

    @property
    def is_repository_only(self) -> bool:
        """True when workflow references a remote URL and no local files are provided."""
        return (
            self.workflow.url is not None
            and len(self.local_files) == 0
            and len(self.remote_files) == 0
        )

    @property
    def workflow_url(self) -> str | None:
        return self.workflow.url

    @property
    def input_files(self) -> list[FileReference]:
        """Input data files of the request.

        Slot-bound files (resolved via each input ``FormalParameter``'s
        default value) plus free-form file attachments — everything in
        ``files`` except the workflow descriptor itself, which is File-typed
        and therefore present in ``files``, but is never a data input.

        The descriptor is excluded by ``@id`` match; crates are validated to
        carry unique non-empty ``@id``s (see :class:`ValidationPipeline`), so
        the comparison cannot misfire on missing ids.
        """
        bound_ids = {
            f.id
            for f in (self.file_for_input(p) for p in self.workflow_inputs)
            if f is not None
        }
        return [f for f in self.files if f.id in bound_ids or f.id != self.workflow.id]

    @property
    def fdl_url(self) -> str | None:
        return self.workflow.url

    @property
    def oscar_input_files(self) -> list[FileReference]:
        return [f for f in self.files if f.id != self.workflow.id]

    def get_entity(self, entity_id: str) -> dict[str, Any] | None:
        graph = self.raw_crate.get("@graph", [])
        for item in graph:
            if item.get("@id") == entity_id:
                return item
        return None

    # -- serialization -------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RequestPackage:
        workflow = WorkflowDescriptor(**data.pop("workflow"))
        files = [FileReference(**f) for f in data.pop("files", [])]
        workflow_inputs = [
            FormalParameter(**p) for p in data.pop("workflow_inputs", [])
        ]
        workflow_outputs = [
            FormalParameter(**p) for p in data.pop("workflow_outputs", [])
        ]
        return cls(
            workflow=workflow,
            files=files,
            workflow_inputs=workflow_inputs,
            workflow_outputs=workflow_outputs,
            **data,
        )
