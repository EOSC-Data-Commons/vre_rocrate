"""VRE RO-Crate library — parsing, validation, building, and launch-request handling."""

from .models import (
    RequestPackage,
    WorkflowDescriptor,
    FileReference,
    FormalParameter,
    RuntimePlatform,
    IMInputFile,
    VRELaunchRequest,
    ToolMeta,
    LaunchInput,
    SlotDefinition,
    SlotValue,
    FileInput,
    DatasetHandle,
)
from .parsing import (
    ValidationPipeline,
)
from .building import RequestPackageBuilder, RocrateBuilder
from .constants import (
    VRE_TYPES,
    VRE_TYPE_TO_PROGRAMMING_LANGUAGE,
    GALAXY_PROGRAMMING_LANGUAGE,
    BINDER_PROGRAMMING_LANGUAGE,
    SCIENCEMESH_PROGRAMMING_LANGUAGE,
    SCIPION_PROGRAMMING_LANGUAGE,
    OSCAR_PROGRAMMING_LANGUAGE,
    JUPYTER_PROGRAMMING_LANGUAGE,
    VIP_PROGRAMMING_LANGUAGE,
    MDDASH_PROGRAMMING_LANGUAGE,
)
from .exceptions import VreRocrateError, CrateValidationError

__all__ = [
    "RequestPackage",
    "WorkflowDescriptor",
    "FileReference",
    "FormalParameter",
    "RuntimePlatform",
    "IMInputFile",
    "VRELaunchRequest",
    "ToolMeta",
    "LaunchInput",
    "SlotDefinition",
    "SlotValue",
    "FileInput",
    "DatasetHandle",
    "ValidationPipeline",
    "RequestPackageBuilder",
    "RocrateBuilder",
    "VRE_TYPES",
    "VRE_TYPE_TO_PROGRAMMING_LANGUAGE",
    "GALAXY_PROGRAMMING_LANGUAGE",
    "BINDER_PROGRAMMING_LANGUAGE",
    "SCIENCEMESH_PROGRAMMING_LANGUAGE",
    "SCIPION_PROGRAMMING_LANGUAGE",
    "OSCAR_PROGRAMMING_LANGUAGE",
    "JUPYTER_PROGRAMMING_LANGUAGE",
    "VIP_PROGRAMMING_LANGUAGE",
    "MDDASH_PROGRAMMING_LANGUAGE",
    "VreRocrateError",
    "CrateValidationError",
]
