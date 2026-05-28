"""Domain-specific exceptions for VRE RO-Crate operations."""


class VreRocrateError(Exception):
    """Base exception for all VRE RO-Crate related errors."""

    pass


class CrateValidationError(VreRocrateError):
    """Raised when the crate does not contain enough information to resolve a service."""

    pass
