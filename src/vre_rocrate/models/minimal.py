from __future__ import annotations

from dataclasses import dataclass, field

from ..constants import VRE_TYPES


@dataclass
class MinimalFileInput:
    """Represents a file input for a minimal VRE request."""

    name: str
    url: str | None = None
    encoding_format: str | None = None
    onedata_domain: str | None = None
    onedata_file_id: str | None = None


@dataclass
class MinimalVRERequest:
    """Represents a minimal VRE request payload.

    This model validates:
    - vre_type: Must be one of the supported VRE types
    - workflow: Required for Galaxy and OSCAR (URL or filename)
    - files: Optional list of file inputs
    - runtime_platform: Optional override for target service URL
    """

    vre_type: str
    workflow: str | None = None
    files: list[MinimalFileInput] = field(default_factory=list)
    runtime_platform: str | None = None

    def __post_init__(self) -> None:
        if self.vre_type not in VRE_TYPES:
            raise ValueError(
                f"vre_type must be one of {VRE_TYPES}, got '{self.vre_type}'"
            )
        if self.workflow is None:
            raise ValueError("workflow is required")
        if self.workflow is not None and not self.workflow.startswith(
            ("http://", "https://")
        ):
            file_names = {f.name for f in self.files}
            if self.workflow not in file_names:
                raise ValueError(
                    f"workflow '{self.workflow}' is a filename but was not found in files"
                )
