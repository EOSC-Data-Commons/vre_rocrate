from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Core RO-Crate entities
# ---------------------------------------------------------------------------


@dataclass
class Entity:
    id: str
    type: str | list[str]
    properties: dict[str, Any] = field(default_factory=dict, repr=False)

    def get(self, key: str, default: Any = None) -> Any:
        return self.properties.get(key, default)


class _MetadataProxy:
    """Proxy that wraps the raw crate dict and exposes ``generate()``."""

    def __init__(self, raw: dict[str, Any]):
        self._raw = raw

    def generate(self) -> dict[str, Any]:
        return self._raw


@dataclass
class ParsedCrate:
    root_id: str
    entities: dict[str, Entity]
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def root_dataset(self) -> Entity | None:
        return self.entities.get(self.root_id)

    @property
    def main_entity(self) -> Entity | None:
        root = self.root_dataset
        if root is None:
            return None
        main_ref = root.get("mainEntity")
        if main_ref is None:
            return None
        if isinstance(main_ref, dict):
            return self.entities.get(main_ref.get("@id", ""))
        if isinstance(main_ref, str):
            return self.entities.get(main_ref)
        eid = getattr(main_ref, "id", None) or main_ref.get("@id", "")
        return self.entities.get(eid)

    @property
    def name(self) -> str | None:
        root = self.root_dataset
        return root.get("name") if root else None

    @property
    def description(self) -> str | None:
        root = self.root_dataset
        return root.get("description") if root else None

    @property
    def metadata(self) -> _MetadataProxy:
        return _MetadataProxy(self.raw)

    def get(self, entity_id: str) -> Entity | None:
        return self.entities.get(entity_id)

    def get_entities(self) -> list[Entity]:
        return list(self.entities.values())


# ---------------------------------------------------------------------------
# Infrastructure Manager types
# ---------------------------------------------------------------------------


@dataclass
class IMInputFile:
    """Typed descriptor for a file to stage into the deployed service."""

    url: str
    destination: str | None = None
    compute_node: str | None = None


def _parse_cpu_requirements(cpus: Any) -> tuple[int, int]:
    """Parse CPU and GPU requirements from processorRequirements field.

    Returns:
        Tuple of (num_cpus, num_gpus)
    """
    num_cpus = 1
    num_gpus = 0

    if isinstance(cpus, str) and "vCPU" in cpus:
        num_cpus = int(cpus.replace("vCPU", "").strip())
    elif isinstance(cpus, list):
        for cpu in cpus:
            if isinstance(cpu, str):
                if "vCPU" in cpu:
                    num_cpus = int(cpu.replace("vCPU", "").strip())
                if "GPU" in cpu:
                    num_gpus = int(cpu.replace("GPU", "").strip())

    return num_cpus, num_gpus


def _parse_input_file(raw_file: dict[str, Any]) -> IMInputFile | None:
    """Parse a single input file definition from RuntimePlatform spec.

    Returns:
        IMInputFile instance or None if the file should be skipped.
    """
    if raw_file.get("@type") != "File":
        logger.warning("Input is not of type File, skipping.")
        return None

    file_url = raw_file.get("@id")
    if not file_url:
        logger.warning("Input does not have a @id, skipping.")
        return None

    content_location = raw_file.get("contentLocation")
    compute_node = None
    destination = content_location

    if content_location and ":" in content_location:
        parts = content_location.split(":", 1)
        compute_node = parts[0]
        destination = parts[1]

    return IMInputFile(
        url=file_url,
        destination=destination,
        compute_node=compute_node,
    )


def _parse_input_files(input_list: list[dict[str, Any]]) -> list[IMInputFile]:
    """Parse list of input files from RuntimePlatform spec.

    Returns:
        List of IMInputFile instances.
    """
    input_files = []
    for raw_file in input_list:
        parsed = _parse_input_file(raw_file)
        if parsed is not None:
            input_files.append(parsed)
    return input_files


@dataclass
class RuntimePlatform:
    """Domain representation of a RO-Crate RuntimePlatform entity."""

    name: str
    install_url: str | None = None
    memory: str | None = None
    num_cpus: int = 1
    num_gpus: int = 0
    storage: str | None = None
    input_files: list[IMInputFile] = field(default_factory=list)

    @classmethod
    def from_dict(cls, dest: dict[str, Any]) -> RuntimePlatform:
        """Build RuntimePlatform from a RO-Crate RuntimePlatform dict."""
        cpus = dest.get("processorRequirements")
        num_cpus, num_gpus = _parse_cpu_requirements(cpus)
        input_files = _parse_input_files(dest.get("input", []))

        return cls(
            name=dest.get("name", "Infrastructure Manager"),
            install_url=dest.get("installUrl"),
            memory=dest.get("memoryRequirements"),
            num_cpus=num_cpus,
            num_gpus=num_gpus,
            storage=dest.get("storageRequirements"),
            input_files=input_files,
        )


# ---------------------------------------------------------------------------
# Request Package types
# ---------------------------------------------------------------------------


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


@dataclass
class RequestPackage:
    vre_type: str
    programming_language: str
    workflow: WorkflowDescriptor
    files: list[FileReference] = field(default_factory=list)
    workflow_inputs: list[FormalParameter] = field(default_factory=list)
    workflow_outputs: list[FormalParameter] = field(default_factory=list)
    raw_crate: dict[str, Any] = field(default_factory=dict, repr=False)

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
        return self.files

    @property
    def fdl_url(self) -> str | None:
        return self.workflow.url

    @property
    def script_files(self) -> list[FileReference]:
        return self.files_by_encoding("text/x-shellscript")

    @property
    def oscar_input_files(self) -> list[FileReference]:
        excluded = {f.id for f in self.script_files}
        excluded.add(self.workflow.id)
        return [f for f in self.files if f.id not in excluded]

    def get_entity(self, entity_id: str) -> dict[str, Any] | None:
        graph = self.raw_crate.get("@graph", [])
        for item in graph:
            if item.get("@id") == entity_id:
                return item
        return None

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

    @staticmethod
    def _resolve_ref(crate: ParsedCrate, ref: object) -> object:
        if isinstance(ref, dict) and "@id" in ref:
            resolved = crate.get(ref["@id"])
            if resolved is not None:
                return resolved
            return ref
        return ref

    @classmethod
    def from_parsed_crate(cls, crate: ParsedCrate) -> RequestPackage:
        root = crate.root_dataset
        main = crate.main_entity
        if main is None:
            raise ValueError("Cannot build RequestPackage without mainEntity")

        lang_ref = main.get("programmingLanguage", {})
        lang_obj = cls._resolve_ref(crate, lang_ref)
        lang_id = lang_obj.get("identifier") if lang_obj is not None else None

        runtime_platform_raw = main.get("runtimePlatform")
        runtime_platform_resolved = cls._resolve_ref(crate, runtime_platform_raw)
        runtime_platform: str | RuntimePlatform | None = None
        if isinstance(runtime_platform_resolved, str):
            runtime_platform = runtime_platform_resolved
        elif runtime_platform_resolved is not None:
            rp_props = (
                dict(runtime_platform_resolved.properties)
                if hasattr(runtime_platform_resolved, "properties")
                else runtime_platform_resolved
            )
            runtime_platform = RuntimePlatform.from_dict(rp_props)

        workflow_url = (
            main.id if main.id.startswith(("http://", "https://")) else main.get("url")
        )
        workflow = WorkflowDescriptor(
            id=main.id,
            type=main.type if isinstance(main.type, str) else main.type[0],
            url=workflow_url,
            programming_language_id=lang_id,
            runtime_platform=runtime_platform,
            properties=main.properties,
        )

        files = cls._extract_files(
            crate, root.get("hasPart", []) if root else [], main.id
        )
        workflow_inputs = cls._extract_parameters(crate, main.get("input", []))
        workflow_outputs = cls._extract_parameters(crate, main.get("output", []))

        return cls(
            vre_type=lang_id or "unknown",
            programming_language=lang_id or "unknown",
            workflow=workflow,
            files=files,
            workflow_inputs=workflow_inputs,
            workflow_outputs=workflow_outputs,
            raw_crate=crate.raw,
        )

    @staticmethod
    def _extract_files(
        crate: ParsedCrate, has_part: list[Any], main_id: str
    ) -> list[FileReference]:
        files: list[FileReference] = []
        for ref in has_part:
            eid = ref if isinstance(ref, str) else ref.get("@id")
            entity = crate.get(eid)
            if entity is None:
                continue
            entity_types = (
                entity.type if isinstance(entity.type, list) else [entity.type]
            )
            if "File" not in entity_types:
                continue
            props = entity.properties
            files.append(
                FileReference(
                    id=entity.id,
                    name=props.get("name", entity.id),
                    encoding_format=props.get("encodingFormat"),
                    url=props.get("url") or entity.id,
                    onedata_domain=props.get("onedata:onezoneDomain"),
                    onedata_file_id=props.get("onedata:fileId"),
                    properties=props,
                )
            )
        return files

    @staticmethod
    def _extract_parameters(
        crate: ParsedCrate, param_refs: list[Any]
    ) -> list[FormalParameter]:
        params: list[FormalParameter] = []
        for ref in param_refs:
            eid = ref if isinstance(ref, str) else ref.get("@id")
            if not eid:
                continue
            entity = crate.get(eid)
            if entity is None:
                continue
            props = entity.properties
            params.append(
                FormalParameter(
                    id=entity.id,
                    name=props.get("name", entity.id),
                    additional_type=props.get("additionalType"),
                    encoding_format=props.get("encodingFormat"),
                    default_value=props.get("defaultValue"),
                    properties=props,
                )
            )
        return params

    @classmethod
    def from_minimal(
        cls,
        vre_type: str,
        programming_language: str,
        workflow_url: str | None,
        files_data: list[dict[str, Any]],
        file_bytes_map: dict[str, bytes],
        runtime_platform: str | None = None,
    ) -> RequestPackage:
        """Build a RequestPackage from minimal VRE start payload."""
        workflow = WorkflowDescriptor(
            id="#workflow",
            type="ComputationalWorkflow",
            url=workflow_url,
            programming_language_id=programming_language,
            runtime_platform=runtime_platform,
            properties={},
        )

        files: list[FileReference] = []
        for f in files_data:
            file_url = str(f["url"]) if f.get("url") else None
            file_id = file_url or f["name"]
            props: dict[str, Any] = {}

            if f["name"] in file_bytes_map:
                props["content"] = file_bytes_map[f["name"]]
                if file_url is None:
                    file_id = f["name"]

            files.append(
                FileReference(
                    id=file_id,
                    name=f["name"],
                    encoding_format=f.get("encoding_format"),
                    url=file_url,
                    onedata_domain=f.get("onedata_domain"),
                    onedata_file_id=f.get("onedata_file_id"),
                    properties=props,
                )
            )

        return cls(
            vre_type=programming_language,
            programming_language=programming_language,
            workflow=workflow,
            files=files,
            raw_crate={},
        )
