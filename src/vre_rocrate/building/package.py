from __future__ import annotations

from typing import Any

from ..models.package import (
    RequestPackage,
    WorkflowDescriptor,
    FileReference,
    FormalParameter,
    OCMData,
)
from ..models.infrastructure import RuntimePlatform
from ..parsing.infrastructure import runtime_platform_from_dict
from ..parsing.validator import ValidationPipeline


class RequestPackageBuilder:
    """Builds RequestPackage instances from a raw ROCrate dict.

    Uses instance methods with shared state to construct individual components
    and assemble them into a complete RequestPackage.
    """

    def __init__(self, crate: dict[str, Any]):
        self.crate = crate
        self.graph: list[dict[str, Any]] = crate.get("@graph", [])
        self.root = self._get_root_dataset()
        self.main = self._get_main_entity()
        if self.main is None:
            raise ValueError("Cannot build RequestPackage without mainEntity")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @classmethod
    def build(
        cls,
        crate: dict[str, Any],
        file_bytes_map: dict[str, bytes] | None = None,
    ) -> RequestPackage:
        """Build a RequestPackage from a ROCrate dict."""
        ValidationPipeline.validate_basic(crate)
        builder = cls(crate)
        package = builder._build()
        if file_bytes_map:
            for fref in package.files:
                if fref.id in file_bytes_map:
                    fref.properties["content"] = file_bytes_map[fref.id]
        return package

    # ------------------------------------------------------------------
    # Build orchestration
    # ------------------------------------------------------------------

    def _build(self) -> RequestPackage:
        lang_id = self._resolve_language_id()
        runtime_platform = self._resolve_runtime_platform()
        workflow = self._build_workflow(lang_id, runtime_platform)
        files = self._extract_files()
        workflow_inputs = self._extract_parameters(self.main.get("input", []))
        workflow_outputs = self._extract_parameters(self.main.get("output", []))
        ocm_data = self._build_ocm_data()

        return RequestPackage(
            vre_type=lang_id or "unknown",
            programming_language=lang_id or "unknown",
            workflow=workflow,
            files=files,
            workflow_inputs=workflow_inputs,
            workflow_outputs=workflow_outputs,
            raw_crate=self.crate,
            ocm_data=ocm_data,
        )

    # ------------------------------------------------------------------
    # Component builders
    # ------------------------------------------------------------------

    def _resolve_language_id(self) -> str | None:
        lang_ref = self.main.get("programmingLanguage", {})
        lang_obj = self._resolve_ref(lang_ref)
        if lang_obj is not None:
            return lang_obj.get("identifier")
        return None

    def _resolve_runtime_platform(self) -> str | RuntimePlatform | None:
        raw = self.main.get("runtimePlatform")
        resolved = self._resolve_ref(raw)
        if isinstance(resolved, str):
            return resolved
        if isinstance(resolved, dict):
            return runtime_platform_from_dict(resolved)
        return None

    def _build_workflow(
        self, lang_id: str | None, runtime_platform: str | RuntimePlatform | None
    ) -> WorkflowDescriptor:
        main_id = self.main.get("@id", "")
        workflow_url = (
            main_id
            if main_id.startswith(("http://", "https://"))
            else self.main.get("url")
        )
        main_type = self.main.get("@type", "")
        return WorkflowDescriptor(
            id=main_id,
            type=main_type if isinstance(main_type, str) else main_type[0],
            url=workflow_url,
            programming_language_id=lang_id,
            runtime_platform=runtime_platform,
            properties=dict(self.main),
        )

    def _build_ocm_data(self) -> OCMData:
        return OCMData(
            receiver_userid=self._entity_prop("#receiver", "userid"),
            owner_userid=self._entity_prop("#owner", "userid"),
            sender_userid=self._entity_prop("#sender", "userid"),
            sender_name=self._entity_prop("#sender", "name"),
            root_name=self._entity_prop("./", "name"),
            root_description=self._entity_prop("./", "description"),
            resource_id=self._entity_prop("#identifier", "userid"),
        )

    # ------------------------------------------------------------------
    # Extraction helpers
    # ------------------------------------------------------------------

    def _extract_files(self) -> list[FileReference]:
        has_part = self.root.get("hasPart") if self.root else []
        files: list[FileReference] = []
        for ref in has_part:
            eid = ref if isinstance(ref, str) else ref.get("@id")
            entity = self._find_entity(eid)
            if entity is None:
                continue
            entity_types = entity.get("@type", [])
            if isinstance(entity_types, str):
                entity_types = [entity_types]
            if "File" not in entity_types:
                continue
            files.append(
                FileReference(
                    id=entity.get("@id", ""),
                    name=entity.get("name", entity.get("@id", "")),
                    encoding_format=entity.get("encodingFormat"),
                    url=entity.get("url") or entity.get("@id", ""),
                    onedata_domain=entity.get("onedata:onezoneDomain"),
                    onedata_file_id=entity.get("onedata:fileId"),
                    properties=dict(entity),
                )
            )
        return files

    def _extract_parameters(self, param_refs: list[Any]) -> list[FormalParameter]:
        params: list[FormalParameter] = []
        for ref in param_refs:
            eid = ref if isinstance(ref, str) else ref.get("@id")
            if not eid:
                continue
            entity = self._find_entity(eid)
            if entity is None:
                continue
            params.append(
                FormalParameter(
                    id=entity.get("@id", ""),
                    name=entity.get("name", entity.get("@id", "")),
                    additional_type=entity.get("additionalType"),
                    encoding_format=entity.get("encodingFormat"),
                    default_value=entity.get("defaultValue"),
                    properties=dict(entity),
                )
            )
        return params

    # ------------------------------------------------------------------
    # Low-level helpers
    # ------------------------------------------------------------------

    def _find_entity(self, entity_id: str) -> dict[str, Any] | None:
        """Find an entity in the graph by its @id."""
        for entity in self.graph:
            if entity.get("@id") == entity_id:
                return entity
        return None

    def _get_root_dataset(self) -> dict[str, Any] | None:
        """Find the root dataset entity (@id == './') in the graph."""
        return self._find_entity("./")

    def _get_main_entity(self) -> dict[str, Any] | None:
        """Resolve the mainEntity from the root dataset."""
        root = self.root
        if root is None:
            return None
        main_ref = root.get("mainEntity")
        if main_ref is None:
            return None
        if isinstance(main_ref, dict):
            return self._find_entity(main_ref.get("@id", ""))
        if isinstance(main_ref, str):
            return self._find_entity(main_ref)
        eid = getattr(main_ref, "id", None) or main_ref.get("@id", "")
        return self._find_entity(eid)

    def _resolve_ref(self, ref: object) -> object:
        """Resolve a reference to an entity in the graph.

        If *ref* is a dict with ``@id``, look up the entity.
        Otherwise return *ref* unchanged.
        """
        if isinstance(ref, dict) and "@id" in ref:
            return self._find_entity(ref["@id"])
        return ref

    def _entity_prop(self, entity_id: str, prop: str) -> str | None:
        """Read a property from a crate entity, returning None if missing."""
        entity = self._find_entity(entity_id)
        if entity is None:
            return None
        return entity.get(prop)
