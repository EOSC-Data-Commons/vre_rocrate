from __future__ import annotations

from dataclasses import replace
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


# Attributes a later same-id file input may fill in when the first left
# them unset (see RocrateBuilder._merged_files); `name` and `url` always
# keep the first occurrence's values.
_FILLABLE_FILE_FIELDS = (
    "mime_type",
    "size_bytes",
    "checksum",
    "checksum_type",
    "onedata_domain",
    "onedata_file_id",
)


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

    def _slot_files(self) -> list[FileInput]:
        return [sv for sv in self.request.input.slots.values()
                if isinstance(sv, FileInput)]

    def _input_files(self) -> list[FileInput]:
        return list(self.request.input.files.values())

    def _all_files(self) -> list[FileInput]:
        return self._slot_files() + self._input_files()

    def _merged_files(self) -> list[FileInput]:
        """Collapse file inputs sharing an entity id into one FileInput.

        Two slots (or a slot and a free-form file) may bind the same
        download URL — one file on disk is one File entity, referenced by
        every binding (Dispatcher issue #166). The first occurrence wins
        on conflicting attributes; later occurrences only fill in unset
        fields.
        """
        merged: dict[str, FileInput] = {}
        for f in self._all_files():
            fid = _file_id(f)
            if fid not in merged:
                merged[fid] = f
                continue
            filled = {
                attr: getattr(f, attr)
                for attr in _FILLABLE_FILE_FIELDS
                if getattr(merged[fid], attr) is None
            }
            merged[fid] = replace(merged[fid], **filled)
        return list(merged.values())

    def _check_entity_id_collisions(self, files: list[FileInput]) -> None:
        """Refuse to build a crate whose file ids collide with other entities.

        The workflow and dataset entities are keyed by their URLs; a file
        sharing one of those ids would yield duplicate @graph ids — the
        ill-defined crate shape ValidationPipeline rejects.
        """
        reserved = {self.tool.uri}
        dataset = self.request.input.dataset
        if dataset is not None:
            reserved.add(dataset.url)
        for f in files:
            fid = _file_id(f)
            if fid in reserved:
                raise ValueError(
                    f"File '{f.name}' id '{fid}' collides with the workflow "
                    "or dataset entity id in the crate"
                )

    def _add_root_dataset(self, files: list[FileInput]) -> None:
        name = f"Root dataset for tool: {self.tool.name}"
        description = "N/A"

        has_part: list[dict[str, str]] = [{"@id": self.tool.uri}]
        for file in files:
            has_part.append({"@id": _file_id(file)})

        input_dataset = self.request.input.dataset
        if input_dataset is not None:
            has_part.append({"@id": input_dataset.url})

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
            "description": self.tool.description or "N/A",
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

    def _add_file_entities(self, files: list[FileInput]) -> None:
        for f in files:
            self.graph.append(self._build_file_entity(f))

    def _add_formal_parameters(self) -> None:
        seen_ids: set[str] = set()
        for slot in self.tool.slots:
            fp_id = f"#input-{slot.id}"
            if fp_id in seen_ids:
                raise ValueError(
                    f"Duplicate slot id '{slot.id}' in tool.slots — "
                    "FormalParameter entities would share an @id"
                )
            seen_ids.add(fp_id)
            fp: dict[str, Any] = {
                "@id": fp_id,
                "@type": "FormalParameter",
                "name": slot.name,
                "additionalType": slot.slot_type,
                "required": not slot.is_optional,
            }
            slot_value = self.request.input.slots.get(slot.name)
            if slot_value is not None:
                if isinstance(slot_value, FileInput):
                    fp["defaultValue"] = {"@id": _file_id(slot_value)}
                else:
                    fp["defaultValue"] = slot_value
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
        files = self._merged_files()
        self._check_entity_id_collisions(files)
        self._add_metadata_descriptor()
        self._add_root_dataset(files)
        self._add_workflow_entity()
        self._add_programming_language()
        self._add_file_entities(files)
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
