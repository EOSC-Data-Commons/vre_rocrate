"""VRE RO-Crate library — parsing, validation, building, and minimal-VRE handling."""

from .models import (
    Entity,
    ParsedCrate,
    RequestPackage,
    WorkflowDescriptor,
    FileReference,
    FormalParameter,
    RuntimePlatform,
    IMInputFile,
    MinimalVRERequest,
    MinimalFileInput,
)
from .parsing import ROCrateParser, ValidationPipeline, parse_minimal_vre_form
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
)
from .exceptions import VreRocrateError, CrateValidationError

__all__ = [
    "Entity",
    "ParsedCrate",
    "RequestPackage",
    "WorkflowDescriptor",
    "FileReference",
    "FormalParameter",
    "RuntimePlatform",
    "IMInputFile",
    "MinimalVRERequest",
    "MinimalFileInput",
    "ROCrateParser",
    "ValidationPipeline",
    "parse_minimal_vre_form",
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
    "VreRocrateError",
    "CrateValidationError",
]
