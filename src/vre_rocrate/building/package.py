from __future__ import annotations

from typing import Any

from ..constants import VRE_TYPE_TO_PROGRAMMING_LANGUAGE
from ..models.rocrate import ParsedCrate
from ..models.package import RequestPackage
from ..parsing.validator import ValidationPipeline


class RequestPackageBuilder:
    @classmethod
    def build(
        cls,
        crate: ParsedCrate,
        file_bytes_map: dict[str, bytes] | None = None,
    ) -> RequestPackage:
        ValidationPipeline.validate_basic(crate)
        package = RequestPackage.from_parsed_crate(crate)
        if file_bytes_map:
            for fref in package.files:
                if fref.id in file_bytes_map:
                    fref.properties["content"] = file_bytes_map[fref.id]
        return package

    @classmethod
    def build_from_minimal(
        cls,
        data: dict[str, Any],
        file_bytes_map: dict[str, bytes],
    ) -> RequestPackage:
        vre_type = data["vre_type"]
        programming_language = VRE_TYPE_TO_PROGRAMMING_LANGUAGE[vre_type]
        workflow = data.get("workflow")
        runtime_platform = (
            str(data["runtime_platform"]) if data.get("runtime_platform") else None
        )

        return RequestPackage.from_minimal(
            vre_type=vre_type,
            programming_language=programming_language,
            workflow_url=workflow,
            files_data=data.get("files", []),
            file_bytes_map=file_bytes_map,
            runtime_platform=runtime_platform,
        )
