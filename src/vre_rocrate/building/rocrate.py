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
        request: VRELaunchRequest,
    ):
        self.request = request
        self.tool: ToolMeta = request.tool
        self.vre_type = resolve_vre_type(self.tool)
        self.programming_language = VRE_TYPE_TO_PROGRAMMING_LANGUAGE.get(
            self.vre_type, ""
        )
        self.display_name = VRE_TYPE_TO_DISPLAY_NAME.get(self.vre_type, "")
        self.language_url = VRE_TYPE_TO_LANGUAGE_URL.get(self.vre_type, "")
        self.lang_id = f"#{self.vre_type}-lang"
        self.now_iso = datetime.now(timezone.utc).isoformat()
        self.graph: list[dict[str, Any]] = []

    def _runtime_platform(self) -> str:
        if self.request.runtime_platform:
            return self.request.runtime_platform
        return VRE_TYPE_TO_DEFAULT_RUNTIME_PLATFORM.get(self.vre_type, "")

    def _add_metadata_descriptor(self) -> None:
        self.graph.append(
            {
                "@id": "ro-crate-metadata.json",
                "@type": "CreativeWork",
                "about": {"@id": "./"},
                "conformsTo": {"@id": "https://w3id.org/ro/crate/1.1"},
            }
        )

    def _add_root_dataset(self) -> None:
        dataset = self.request.input.dataset
        name = self.tool.name
        description = self.tool.description or "placeholder"

        has_part: list[dict[str, str]] = [{"@id": self.tool.uri}]
        for sv in self.request.input.slots.values():
            if sv.file is not None:
                has_part.append({"@id": _file_id(sv.file)})
        for f in self.request.input.files.values():
            has_part.append({"@id": _file_id(f)})
        if dataset is not None:
            has_part.append({"@id": dataset.url})

        self.graph.append(
            {
                "@id": "./",
                "@type": "Dataset",
                "name": name,
                "description": description,
                "datePublished": self.now_iso,
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
            "description": self.tool.description or "placeholder",
            "programmingLanguage": {"@id": self.lang_id},
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
        self.graph.append(
            {
                "@id": self.lang_id,
                "@type": "ComputerLanguage",
                "identifier": self.programming_language,
                "name": self.display_name,
                "url": self.language_url,
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
        for sv in self.request.input.slots.values():
            if sv.file is not None:
                self.graph.append(self._build_file_entity(sv.file))
        for f in self.request.input.files.values():
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
            sv = self.request.input.slots.get(slot.name)
            if sv is not None:
                if sv.file is not None:
                    fp["defaultValue"] = {"@id": _file_id(sv.file)}
                elif sv.value is not None:
                    fp["defaultValue"] = sv.value
            self.graph.append(fp)

    def _add_dataset_entity(self) -> None:
        dataset = self.request.input.dataset
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
        return RocrateBuilder(request).build()
