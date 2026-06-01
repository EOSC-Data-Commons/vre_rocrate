from __future__ import annotations

from typing import Any

from ..models.rocrate import ParsedCrate
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
    """Builds RequestPackage instances from ParsedCrate.

    Uses instance methods with shared state to construct individual components
    and assemble them into a complete RequestPackage.
    """

    def __init__(self, crate: ParsedCrate):
        self.crate = crate
        self.root = crate.root_dataset
        self.main = crate.main_entity
        if self.main is None:
            raise ValueError("Cannot build RequestPackage without mainEntity")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @classmethod
    def build(
        cls,
        crate: ParsedCrate,
        file_bytes_map: dict[str, bytes] | None = None,
    ) -> RequestPackage:
        """Build a RequestPackage from a parsed RO-Crate."""
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
            raw_crate=self.crate.raw,
            ocm_data=ocm_data,
        )

    # ------------------------------------------------------------------
    # Component builders
    # ------------------------------------------------------------------

    def _resolve_language_id(self) -> str | None:
        lang_ref = self.main.get("programmingLanguage", {})
        lang_obj = self._resolve_ref(lang_ref)
        return lang_obj.get("identifier") if lang_obj is not None else None

    def _resolve_runtime_platform(self) -> str | RuntimePlatform | None:
        raw = self.main.get("runtimePlatform")
        resolved = self._resolve_ref(raw)
        if isinstance(resolved, str):
            return resolved
        if resolved is not None:
            rp_props = (
                dict(resolved.properties)
                if hasattr(resolved, "properties")
                else resolved
            )
            return runtime_platform_from_dict(rp_props)
        return None

    def _build_workflow(
        self, lang_id: str | None, runtime_platform: str | RuntimePlatform | None
    ) -> WorkflowDescriptor:
        workflow_url = (
            self.main.id
            if self.main.id.startswith(("http://", "https://"))
            else self.main.get("url")
        )
        return WorkflowDescriptor(
            id=self.main.id,
            type=(
                self.main.type if isinstance(self.main.type, str) else self.main.type[0]
            ),
            url=workflow_url,
            programming_language_id=lang_id,
            runtime_platform=runtime_platform,
            properties=self.main.properties,
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
        has_part = self.root.get("hasPart", []) if self.root else []
        files: list[FileReference] = []
        for ref in has_part:
            eid = ref if isinstance(ref, str) else ref.get("@id")
            entity = self.crate.get(eid)
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

    def _extract_parameters(self, param_refs: list[Any]) -> list[FormalParameter]:
        params: list[FormalParameter] = []
        for ref in param_refs:
            eid = ref if isinstance(ref, str) else ref.get("@id")
            if not eid:
                continue
            entity = self.crate.get(eid)
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

    # ------------------------------------------------------------------
    # Low-level helpers
    # ------------------------------------------------------------------

    def _resolve_ref(self, ref: object) -> object:
        if isinstance(ref, dict) and "@id" in ref:
            resolved = self.crate.get(ref["@id"])
            if resolved is not None:
                return resolved
            return ref
        return ref

    def _entity_prop(self, entity_id: str, prop: str) -> str | None:
        """Read a property from a ParsedCrate entity, returning None if missing."""
        entity = self.crate.get(entity_id)
        if entity is None:
            return None
        return entity.get(prop)
