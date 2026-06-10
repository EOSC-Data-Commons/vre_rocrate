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

    @property
    def zenodo_doi(self) -> str | None:
        """Return the bare Zenodo DOI if identifier or @id is a Zenodo DOI URL, else None."""
        candidate = self.id
        if candidate and "zenodo" in candidate:
            doi = candidate
            for prefix in ("https://doi.org/", "http://doi.org/"):
                if doi.startswith(prefix):
                    doi = doi[len(prefix) :]
                    break
            return doi
        return None


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
    programming_language: str
    workflow: WorkflowDescriptor
    files: list[FileReference] = field(default_factory=list)
    workflow_inputs: list[FormalParameter] = field(default_factory=list)
    workflow_outputs: list[FormalParameter] = field(default_factory=list)
    raw_crate: dict[str, Any] = field(default_factory=dict, repr=False)
    ocm_data: OCMData | None = None

    # -- data-access helpers -------------------------------------------------

    def files_by_encoding(self, encoding: str) -> list[FileReference]:
        return [f for f in self.files if f.encoding_format == encoding]

    def file_by_id(self, file_id: str) -> FileReference | None:
        for f in self.files:
            if f.id == file_id:
                return f
        return None

    @property
    def local_files(self) -> list[FileReference]:
        return [f for f in self.files if not f.id.startswith(("http://", "https://"))]

    @property
    def remote_files(self) -> list[FileReference]:
        return [f for f in self.files if f.id.startswith(("http://", "https://"))]

    @property
    def workflow_url(self) -> str | None:
        return self.workflow.url

    @property
    def input_files(self) -> list[FileReference]:
        """Files that match declared workflow inputs, or all files if none declared.

        Resolves file references through ``FormalParameter.default_value``.
        If ``default_value`` is a dict with ``@id``, that @id is matched
        against ``FileReference.id``.  Falls back to all files when no
        inputs are declared or none carry a resolvable default value.
        """
        if not self.workflow_inputs:
            return self.files
        file_ids: set[str] = set()
        for param in self.workflow_inputs:
            dv = param.default_value
            if isinstance(dv, dict) and "@id" in dv:
                file_ids.add(dv["@id"])
            elif isinstance(dv, str):
                file_ids.add(dv)
        if not file_ids:
            return self.files
        return [f for f in self.files if f.id in file_ids]

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
