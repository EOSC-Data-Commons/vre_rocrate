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
class VREPayload:
    """Pure data container for a VRE launch payload.

    This is the Dispatcher's view of the crate: parsed from the RO-Crate
    posted by req-packager and handed to VRE handlers.

    Construction logic lives in ``VREPayloadBuilder``.
    """

    vre_type: str
    programming_language: str  # redundant info to vre type
    workflow: WorkflowDescriptor
    files: list[FileReference] = field(default_factory=list)
    workflow_inputs: list[FormalParameter] = field(default_factory=list)
    workflow_outputs: list[FormalParameter] = field(default_factory=list)
    raw_crate: dict[str, Any] = field(default_factory=dict, repr=False)
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

    def input_by_name(self, name: str) -> FormalParameter | None:
        """Return the declared input slot with the given name, if any."""
        for p in self.workflow_inputs:
            if p.name == name:
                return p
        return None

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

    def input_file_bindings(self) -> list[tuple[str, FileReference]]:
        """(input name, bound file) pairs — the file half of the inputs.

        Free-form file attachments and literal-value inputs are not
        included — see :attr:`input_files` for the transport view and
        :meth:`input_literal_bindings` for the literal half.
        """
        pairs = []
        for param in self.workflow_inputs:
            f = self.file_for_input(param)
            if f is not None:
                pairs.append((param.name, f))
        return pairs

    def input_literal_bindings(self) -> list[tuple[str, str | int | float | bool]]:
        """(input name, literal value) pairs — the scalar half of the inputs.

        A param is file-bound (see :meth:`input_file_bindings`) or
        literal-bound, never both: a string default is only kept literal
        when ``file_for_input`` cannot resolve it as a file.
        """
        pairs = []
        for param in self.workflow_inputs:
            if self.file_for_input(param) is not None:
                continue
            if isinstance(param.default_value, (str, int, float, bool)):
                pairs.append((param.name, param.default_value))
        return pairs

    def input_value_bindings(
        self,
    ) -> list[tuple[str, FileReference | str | int | float | bool]]:
        """All resolved input bindings as (name, value) pairs.

        The disjoint union of :meth:`input_literal_bindings` and
        :meth:`input_file_bindings` (order not specified). Unresolvable
        bindings (dangling ``@id`` refs) and value-less params are
        omitted. Build a dict from the pairs to key by input name;
        duplicates collapse there.
        """
        return self.input_literal_bindings() + self.input_file_bindings()

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

    @property
    def root_name(self) -> str:
        """Name of the crate root dataset (./), empty if unavailable."""
        return (self.get_entity("./") or {}).get("name", "")

    @property
    def root_description(self) -> str:
        """Description of the crate root dataset (./), empty if unavailable."""
        return (self.get_entity("./") or {}).get("description", "")

    # -- serialization -------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VREPayload:
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
