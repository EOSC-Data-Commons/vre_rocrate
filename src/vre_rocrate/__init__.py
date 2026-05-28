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
)
from .parser import ROCrateParser
from .validator import ValidationPipeline
from .builder import RequestPackageBuilder, RocrateBuilder
from .minimal import MinimalVRERequest, MinimalFileInput, parse_minimal_vre_form
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
    "ROCrateParser",
    "ValidationPipeline",
    "RequestPackageBuilder",
    "RocrateBuilder",
    "MinimalVRERequest",
    "MinimalFileInput",
    "parse_minimal_vre_form",
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
