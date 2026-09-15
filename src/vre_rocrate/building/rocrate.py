from __future__ import annotations

from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Any

from ..constants import (
    VRE_TYPE_TO_PROGRAMMING_LANGUAGE,
    VRE_TYPE_TO_DISPLAY_NAME,
    VRE_TYPE_TO_LANGUAGE_URL,
    resolve_vre_type,
    VRE_TYPE_TO_DEFAULT_RUNTIME_PLATFORM,
)
from ..models.launch import (
    VRELaunchRequest,
    ToolMeta,
    LaunchInput,
    SlotDefinition,
    FileInput,
    DatasetHandle,
)

# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------

_EXTENSION_TO_MIME: dict[str, str] = {
    ".ipynb": "application/x-ipynb+json",
    ".py": "text/x-python",
    ".csv": "text/csv",
    ".json": "application/json",
    ".fastq": "application/fastq",
    ".txt": "text/plain",
    ".sh": "text/x-shellscript",
    ".ga": "application/galaxy",
    ".tiff": "image/tiff",
    ".tif": "image/tiff",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}


def _infer_encoding_format(url: str) -> str | None:
    """Infer MIME type from a URL's file extension."""
    suffix = PurePosixPath(url).suffix.lower()
    return _EXTENSION_TO_MIME.get(suffix)


def _extract_filename_from_url(url: str) -> str:
    """Extract the final path segment (filename) from a URL."""
    return PurePosixPath(url).name


def _file_id(f: FileInput) -> str:
    return f.url or f.name


# Placeholder license entity — the builder cannot assert a concrete license
# on behalf of crate producers; consumers see an honest "Unspecified" node.
_LICENSE_PLACEHOLDER_ID = "#license-unspecified"


class RocrateBuilder:
    """Builds a complete ROCrate JSON dict from a VRELaunchRequest."""

    def __init__(
        self,
        tool: ToolMeta,
        input: LaunchInput,
        runtime_platform: str
    ):
        self.tool: ToolMeta = tool
        self.input = input
        self.runtime_platform = runtime_platform
        self.graph: list[dict[str, Any]] = []
        self.vre_type = resolve_vre_type(self.tool)
        

    def _runtime_platform(self) -> str:
        if self.runtime_platform:
            return self.runtime_platform
        return VRE_TYPE_TO_DEFAULT_RUNTIME_PLATFORM.get(resolve_vre_type(self.tool), "")

    def _add_metadata_descriptor(self) -> None:
        self.graph.append(
            {
                "@id": "ro-crate-metadata.json",
                "@type": "CreativeWork",
                "about": {"@id": "./"},
                "conformsTo": {"@id": "https://w3id.org/ro/crate/1.1"},
            }
        )

    def _slot_files(self) -> list[FileInput]:
        return [sv for sv in self.input.slots.values()
                if isinstance(sv, FileInput)]

    def _input_files(self) -> list[FileInput]:
        return list(self.input.files.values())

    def _all_files(self) -> list[FileInput]:
        return self._slot_files() + self._input_files()

    def _add_root_dataset(self) -> None:
        name = f"Root dataset for tool: {self.tool.name}"
        description = "N/A"

        has_part: list[dict[str, str]] = [{"@id": self.tool.uri}]
        for file in self._all_files():
            has_part.append({"@id": _file_id(file)})

        input_dataset = self.input.dataset
        if input_dataset is not None:
            has_part.append({"@id": input_dataset.url})

        self.graph.append(
            {
                "@id": "./",
                "@type": "Dataset",
                "name": name,
                "description": description,
                "datePublished": datetime.now(timezone.utc).isoformat(),
                "license": {"@id": _LICENSE_PLACEHOLDER_ID},
                "creator": {"@id": "#author-dispatcher"},
                "mainEntity": {"@id": self.tool.uri},
                "hasPart": has_part,
            }
        )

    def _add_workflow_entity(self) -> None:
        encoding_format = _infer_encoding_format(self.tool.uri)
        now_date = datetime.now(timezone.utc).date().isoformat()

        workflow_types = ["SoftwareSourceCode", "ComputationalWorkflow"]
        if encoding_format:
            workflow_types.insert(0, "File")

        workflow_entity: dict[str, Any] = {
            "@id": self.tool.uri,
            "@type": workflow_types,
            "conformsTo": {
                "@id": "https://bioschemas.org/profiles/ComputationalWorkflow/0.5-DRAFT-2020_07_21/"
            },
            "name": self.tool.name or _extract_filename_from_url(self.tool.uri),
            "description": self.tool.description or "N/A",
            "programmingLanguage": {"@id": self._lang_id()},
            "creator": {"@id": "#author-dispatcher"},
            "dateCreated": now_date,
            "license": {"@id": _LICENSE_PLACEHOLDER_ID},
            "sdPublisher": {"@id": "#workflow-hub"},
            "version": self.tool.version,
            "runtimePlatform": self._runtime_platform(),
        }
        if encoding_format:
            workflow_entity["encodingFormat"] = encoding_format

        input_refs: list[dict[str, str]] = []
        for slot in self.tool.slots:
            input_refs.append({"@id": f"#input-{slot.id}"})
        if input_refs:
            workflow_entity["input"] = input_refs

        self.graph.append(workflow_entity)

    def _add_programming_language(self) -> None:
        programming_language = VRE_TYPE_TO_PROGRAMMING_LANGUAGE.get(
                    self.vre_type, ""
                )
        display_name = VRE_TYPE_TO_DISPLAY_NAME.get(self.vre_type, "")
        language_url = VRE_TYPE_TO_LANGUAGE_URL.get(self.vre_type, "")

        self.graph.append(
            {
                "@id": self._lang_id(),
                "@type": "ComputerLanguage",
                "identifier": programming_language,
                "name": display_name,
                "url": language_url,
            }
        )

    def _build_file_entity(self, f: FileInput) -> dict[str, Any]:
        file_entity: dict[str, Any] = {
            "@id": _file_id(f),
            "@type": "File",
            "name": f.name,
            "license": {"@id": _LICENSE_PLACEHOLDER_ID},
        }
        if f.mime_type:
            file_entity["encodingFormat"] = f.mime_type
        if f.url:
            file_entity["url"] = f.url
        if f.size_bytes is not None:
            file_entity["contentSize"] = f.size_bytes
        if f.checksum and f.checksum_type == "sha256":
            file_entity["sha256"] = f.checksum
        if f.onedata_domain:
            file_entity["onedata:onezoneDomain"] = f.onedata_domain
        if f.onedata_file_id:
            file_entity["onedata:fileId"] = f.onedata_file_id
        return file_entity

    def _add_file_entities(self) -> None:
        for f in self._all_files():
            self.graph.append(self._build_file_entity(f))

    def _add_formal_parameters(self) -> None:
        for slot in self.tool.slots:
            fp: dict[str, Any] = {
                "@id": f"#input-{slot.id}",
                "@type": "FormalParameter",
                "name": slot.name,
                "additionalType": slot.slot_type,
                "required": not slot.is_optional,
            }
            slot_value = self.input.slots.get(slot.name)
            if slot_value is not None:
                if isinstance(slot_value, FileInput):
                    fp["defaultValue"] = {"@id": _file_id(slot_value)}
                else:
                    fp["defaultValue"] = slot_value
            self.graph.append(fp)
    def _lang_id(self) -> str:
        return f"#{self.vre_type}-lang"
    def _add_dataset_entity(self) -> None:
        dataset = self.input.dataset
        if dataset is None:
            return
        self.graph.append(
            {
                "@id": dataset.url,
                "@type": "Dataset",
                "name": dataset.title,
                "description": dataset.description,
            }
        )

    def _add_tool_metadata_entity(self) -> None:
        if not self.tool.raw_definition:
            return
        self.graph.append(
            {
                "@id": "#tool-metadata",
                "@type": "Thing",
                "rawDefinition": self.tool.raw_definition,
            }
        )

    def _add_supporting_entities(self) -> None:
        self.graph.append(
            {
                "@id": "#author-dispatcher",
                "@type": "Person",
                "name": "Dispatcher System",
            }
        )
        self.graph.append(
            {
                "@id": "#workflow-hub",
                "@type": "Organization",
                "name": "Example Workflow Hub",
                "url": "http://example.com/workflows/",
            }
        )
        self.graph.append(
            {
                "@id": _LICENSE_PLACEHOLDER_ID,
                "@type": "CreativeWork",
                "name": "Unspecified license",
                "description": "License not specified by the crate producer",
            }
        )

    def build(self) -> dict[str, Any]:
        self._add_metadata_descriptor()
        self._add_root_dataset()
        self._add_workflow_entity()
        self._add_programming_language()
        self._add_file_entities()
        self._add_formal_parameters()
        self._add_dataset_entity()
        self._add_tool_metadata_entity()
        self._add_supporting_entities()
        return {
            "@context": "https://w3id.org/ro/crate/1.1/context",
            "@graph": self.graph,
        }

    @staticmethod
    def build_from_launch_request(request: VRELaunchRequest) -> dict[str, Any]:
        """Convert a VRELaunchRequest into a complete ROCrate JSON dict."""
        tool_meta = request.tool
        input = request.input
        runtime_platform = request.runtime_platform
        return RocrateBuilder(tool_meta, input, runtime_platform).build()
