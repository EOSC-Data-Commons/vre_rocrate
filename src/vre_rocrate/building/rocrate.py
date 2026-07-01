from __future__ import annotations

from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Any

from ..constants import (
    VRE_TYPE_TO_PROGRAMMING_LANGUAGE,
    VRE_TYPE_TO_DISPLAY_NAME,
    VRE_TYPE_TO_LANGUAGE_URL,
)
from ..models.minimal import MinimalVRERequest, MinimalFileInput

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


class RocrateBuilder:
    """Builds a complete ROCrate JSON dict from a MinimalVRERequest.

    Uses instance methods with shared state to construct individual entities
    and assemble them into a complete @graph.
    """

    def __init__(
        self,
        vre_type: str,
        programming_language: str,
        display_name: str,
        language_url: str,
        workflow_id: str,
        lang_id: str,
        runtime_platform: str | None,
        files: list[MinimalFileInput],
        now_iso: str,
        receiver_userid: str | None,
    ):
        self.vre_type = vre_type
        self.programming_language = programming_language
        self.display_name = display_name
        self.language_url = language_url
        self.workflow_id = workflow_id
        self.lang_id = lang_id
        self.runtime_platform = runtime_platform
        self.files = files
        self.now_iso = now_iso
        self.receiver_userid = receiver_userid
        self.graph: list[dict[str, Any]] = []
        self.result: dict[str, Any] | None = None

    def _add_metadata_descriptor(self) -> None:
        """Add the ro-crate-metadata.json descriptor entity to the graph."""
        self.graph.append(
            {
                "@id": "ro-crate-metadata.json",
                "@type": "CreativeWork",
                "about": {"@id": "./"},
                "conformsTo": {"@id": "https://w3id.org/ro/crate/1.1"},
            }
        )

    def _add_root_dataset(self) -> None:
        """Add the root Dataset entity with hasPart references to the graph."""
        root_has_part: list[dict[str, str]] = [{"@id": self.workflow_id}]
        for f in self.files:
            file_id = f.url or f.name
            if file_id == self.workflow_id:
                continue
            root_has_part.append({"@id": file_id})

        self.graph.append(
            {
                "@id": "./",
                "@type": "Dataset",
                "name": "placeholder",
                "description": "placeholder",
                "datePublished": self.now_iso,
                "license": {"@id": "https://spdx.org/licenses/GPL-3.0"},
                "creator": {"@id": "#author-dispatcher"},
                "mainEntity": {"@id": self.workflow_id},
                "hasPart": root_has_part,
            }
        )

    def _add_workflow_entity(self) -> None:
        """Add the workflow (mainEntity) entity to the graph."""
        workflow_name = _extract_filename_from_url(self.workflow_id)
        encoding_format = _infer_encoding_format(self.workflow_id)
        now_date = datetime.now(timezone.utc).date().isoformat()

        workflow_entity: dict[str, Any] = {
            "@id": self.workflow_id,
            "@type": ["File", "SoftwareSourceCode", "ComputationalWorkflow"],
            "conformsTo": {
                "@id": "https://bioschemas.org/profiles/ComputationalWorkflow/0.5-DRAFT-2020_07_21/"
            },
            "name": workflow_name,
            "description": "placeholder",
            "programmingLanguage": {"@id": self.lang_id},
            "creator": {"@id": "#author-dispatcher"},
            "dateCreated": now_date,
            "license": {"@id": "https://spdx.org/licenses/GPL-3.0"},
            "sdPublisher": {"@id": "#workflow-hub"},
            "version": "1.0.0",
        }
        if self.runtime_platform:
            workflow_entity["runtimePlatform"] = self.runtime_platform
        if encoding_format:
            workflow_entity["encodingFormat"] = encoding_format

        # Add input references for each file (excluding the workflow itself)
        input_refs: list[dict[str, str]] = []
        for i, f in enumerate(self.files):
            file_id = f.url or f.name
            if file_id == self.workflow_id:
                continue
            input_refs.append({"@id": f"#input-{i}"})
        if input_refs:
            workflow_entity["input"] = input_refs

        self.graph.append(workflow_entity)

    def _add_programming_language(self) -> None:
        """Add the programming language entity to the graph."""
        self.graph.append(
            {
                "@id": self.lang_id,
                "@type": "ComputerLanguage",
                "identifier": self.programming_language,
                "name": self.display_name,
                "url": self.language_url,
            }
        )

    def _add_file_entities(self) -> None:
        """Add file entities from the files list to the graph."""
        for f in self.files:
            file_id = f.url or f.name
            if file_id == self.workflow_id:
                continue

            file_entity: dict[str, Any] = {
                "@id": file_id,
                "@type": "File",
                "name": f.name,
                "license": {"@id": "https://spdx.org/licenses/GPL-3.0"},
            }
            if f.encoding_format:
                file_entity["encodingFormat"] = f.encoding_format
            if f.url:
                file_entity["url"] = f.url
            if f.onedata_domain:
                file_entity["onedata:onezoneDomain"] = f.onedata_domain
            if f.onedata_file_id:
                file_entity["onedata:fileId"] = f.onedata_file_id
            self.graph.append(file_entity)

    def _add_formal_parameters(self) -> None:
        """Add FormalParameter entities for each file input."""
        for i, f in enumerate(self.files):
            file_id = f.url or f.name
            if file_id == self.workflow_id:
                continue

            self.graph.append(
                {
                    "@id": f"#input-{i}",
                    "@type": "FormalParameter",
                    "name": f.name,
                    "defaultValue": {"@id": file_id},
                }
            )

    def _add_supporting_entities(self) -> None:
        """Add supporting entities (author, license, workflow-hub) to the graph."""
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
                "@id": "https://spdx.org/licenses/GPL-3.0",
                "@type": "CreativeWork",
                "name": "GNU General Public License v3.0",
                "alternateName": "GPL-3.0",
            }
        )

    def _add_receiver_entity(self) -> None:
        """Add the #receiver Person entity if receiver_userid is set."""
        if not self.receiver_userid:
            return
        self.graph.append(
            {
                "@id": "#receiver",
                "@type": "Person",
                "userid": self.receiver_userid,
            }
        )

    def build(self) -> dict[str, Any]:
        """Build and return the complete ROCrate JSON dict.

        Returns:
            A complete ROCrate JSON structure with @context and @graph.
        """
        self._add_metadata_descriptor()
        self._add_root_dataset()
        self._add_workflow_entity()
        self._add_programming_language()
        self._add_file_entities()
        self._add_formal_parameters()
        self._add_supporting_entities()
        self._add_receiver_entity()
        self.result = {
            "@context": "https://w3id.org/ro/crate/1.1/context",
            "@graph": self.graph,
        }
        return self.result

    @staticmethod
    def build_from_minimal(request: MinimalVRERequest) -> dict[str, Any]:
        """Convert a MinimalVRERequest into a complete ROCrate JSON dict.

        Args:
            request: The minimal VRE request.

        Returns:
            A complete ROCrate JSON structure with @context and @graph.
        """
        vre_type: str = request.vre_type
        programming_language: str = VRE_TYPE_TO_PROGRAMMING_LANGUAGE[vre_type]
        display_name: str = VRE_TYPE_TO_DISPLAY_NAME[vre_type]
        language_url: str = VRE_TYPE_TO_LANGUAGE_URL[vre_type]
        workflow: str = request.workflow
        runtime_platform: str | None = request.runtime_platform
        receiver_userid: str | None = request.receiver_userid

        lang_id = f"#{vre_type}-lang"
        now_iso = datetime.now(timezone.utc).isoformat()

        builder = RocrateBuilder(
            vre_type=vre_type,
            programming_language=programming_language,
            display_name=display_name,
            language_url=language_url,
            workflow_id=workflow,
            lang_id=lang_id,
            runtime_platform=runtime_platform,
            files=request.files,
            now_iso=now_iso,
            receiver_userid=receiver_userid,
        )

        return builder.build()
