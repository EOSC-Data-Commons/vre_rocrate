from __future__ import annotations

from typing import Any

from ..constants import VRE_TYPE_TO_PROGRAMMING_LANGUAGE
from ..models.rocrate import ParsedCrate, Entity
from ..models.package import (
    RequestPackage,
    WorkflowDescriptor,
    FileReference,
    FormalParameter,
    OCMData,
)
from ..models.minimal import MinimalVRERequest, MinimalFileInput
from ..models.infrastructure import RuntimePlatform
from ..parsing.infrastructure import runtime_platform_from_dict
from ..parsing.validator import ValidationPipeline


class RequestPackageBuilder:
    """Builds RequestPackage instances from ParsedCrate or minimal VRE data.

    All construction logic lives here; RequestPackage is a pure data container.
    """

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
        package = cls._from_parsed_crate(crate)
        if file_bytes_map:
            for fref in package.files:
                if fref.id in file_bytes_map:
                    fref.properties["content"] = file_bytes_map[fref.id]
        return package

    @classmethod
    def build_from_minimal(
        cls,
        request: MinimalVRERequest,
        file_bytes_map: dict[str, bytes],
    ) -> RequestPackage:
        """Build a RequestPackage from a MinimalVRERequest."""
        programming_language = VRE_TYPE_TO_PROGRAMMING_LANGUAGE[request.vre_type]

        return cls._from_minimal(
            vre_type=request.vre_type,
            programming_language=programming_language,
            workflow_url=request.workflow,
            files=request.files,
            file_bytes_map=file_bytes_map,
            runtime_platform=request.runtime_platform,
        )

    # ------------------------------------------------------------------
    # Construction from ParsedCrate
    # ------------------------------------------------------------------

    @classmethod
    def _from_parsed_crate(cls, crate: ParsedCrate) -> RequestPackage:
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
            runtime_platform = runtime_platform_from_dict(rp_props)

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

        ocm_data = OCMData(
            receiver_userid=cls._entity_prop(crate, "#receiver", "userid"),
            owner_userid=cls._entity_prop(crate, "#owner", "userid"),
            sender_userid=cls._entity_prop(crate, "#sender", "userid"),
            sender_name=cls._entity_prop(crate, "#sender", "name"),
            root_name=cls._entity_prop(crate, "./", "name"),
            root_description=cls._entity_prop(crate, "./", "description"),
            resource_id=cls._entity_prop(crate, "#identifier", "userid"),
        )

        return RequestPackage(
            vre_type=lang_id or "unknown",
            programming_language=lang_id or "unknown",
            workflow=workflow,
            files=files,
            workflow_inputs=workflow_inputs,
            workflow_outputs=workflow_outputs,
            raw_crate=crate.raw,
            ocm_data=ocm_data,
        )

    # ------------------------------------------------------------------
    # Construction from minimal VRE data
    # ------------------------------------------------------------------

    @classmethod
    def _from_minimal(
        cls,
        vre_type: str,
        programming_language: str,
        workflow_url: str | None,
        files: list[MinimalFileInput],
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

        file_refs: list[FileReference] = []
        for f in files:
            file_id = f.url or f.name
            props: dict[str, Any] = {}

            if f.name in file_bytes_map:
                props["content"] = file_bytes_map[f.name]
                if f.url is None:
                    file_id = f.name

            file_refs.append(
                FileReference(
                    id=file_id,
                    name=f.name,
                    encoding_format=f.encoding_format,
                    url=f.url,
                    onedata_domain=f.onedata_domain,
                    onedata_file_id=f.onedata_file_id,
                    properties=props,
                )
            )

        return RequestPackage(
            vre_type=programming_language,
            programming_language=programming_language,
            workflow=workflow,
            files=file_refs,
            raw_crate={},
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_ref(crate: ParsedCrate, ref: object) -> object:
        if isinstance(ref, dict) and "@id" in ref:
            resolved = crate.get(ref["@id"])
            if resolved is not None:
                return resolved
            return ref
        return ref

    @staticmethod
    def _entity_prop(crate: ParsedCrate, entity_id: str, prop: str) -> str | None:
        """Read a property from a ParsedCrate entity, returning None if missing."""
        entity = crate.get(entity_id)
        if entity is None:
            return None
        return entity.get(prop)

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
