from __future__ import annotations

from typing import Any

from ..exceptions import CrateValidationError


def _find_entity(graph: list[dict[str, Any]], entity_id: str) -> dict[str, Any] | None:
    """Find an entity in the graph by its @id."""
    for entity in graph:
        if entity.get("@id") == entity_id:
            return entity
    return None


def _get_root_dataset(graph: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Find the root dataset entity (@id == './') in the graph."""
    return _find_entity(graph, "./")


def _get_main_entity(graph: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Resolve the mainEntity from the root dataset."""
    root = _get_root_dataset(graph)
    if root is None:
        return None
    main_ref = root.get("mainEntity")
    if main_ref is None:
        return None
    if isinstance(main_ref, dict):
        return _find_entity(graph, main_ref.get("@id", ""))
    if isinstance(main_ref, str):
        return _find_entity(graph, main_ref)
    eid = getattr(main_ref, "id", None) or main_ref.get("@id", "")
    return _find_entity(graph, eid)


def _resolve_ref(graph: list[dict[str, Any]], ref: object) -> object:
    """Resolve a reference to an entity in the graph.

    Args:
        graph: The @graph list from the crate.
        ref: The reference to resolve (can be a string @id, dict with @id, or direct entity).

    Returns:
        The resolved entity dict or None if not found.
    """
    if isinstance(ref, dict) and "@id" in ref:
        return _find_entity(graph, ref["@id"])
    if isinstance(ref, str):
        return _find_entity(graph, ref)
    return ref


def _validate_main_entity(graph: list[dict[str, Any]]) -> None:
    """Validate that the crate has a valid mainEntity.

    Raises:
        CrateValidationError: If mainEntity is missing or invalid.
    """
    main = _get_main_entity(graph)
    if main is None:
        raise CrateValidationError("Missing mainEntity inside ROCrate")

    main_type = main.get("@type", "")
    if isinstance(main_type, str) and main_type == "":
        raise CrateValidationError("Missing main entity object")


def _validate_programming_language(
    graph: list[dict[str, Any]], main: dict[str, Any]
) -> None:
    """Validate that the main entity has a valid programmingLanguage.

    Raises:
        CrateValidationError: If programmingLanguage is missing or invalid.
    """
    lang_ref = main.get("programmingLanguage")
    if lang_ref is None or (isinstance(lang_ref, str) and lang_ref == ""):
        raise CrateValidationError("Missing main entity programmingLanguage object")

    lang = _resolve_ref(graph, lang_ref)
    if lang is None:
        raise CrateValidationError("Cannot resolve programmingLanguage reference")

    lang_id = lang.get("identifier")
    if lang_id is None:
        raise CrateValidationError(
            "Missing programmingLanguage identifier inside ROCrate's mainEntity"
        )


class ValidationPipeline:
    """Pipeline for validating ROCrate structures."""

    @classmethod
    def validate_basic(cls, crate: dict[str, Any]) -> None:
        """Perform basic validation of a ROCrate dict.

        This validates:
        - mainEntity exists and is valid
        - programmingLanguage is defined and resolvable
        - programmingLanguage has an identifier

        Args:
            crate: The ROCrate dict (with @graph).

        Raises:
            CrateValidationError: If any validation step fails.
        """
        graph: list[dict[str, Any]] = crate.get("@graph", [])
        _validate_main_entity(graph)
        _validate_programming_language(graph, _get_main_entity(graph))

    @classmethod
    def validate_workflow_required_fields(cls, crate: dict[str, Any]) -> None:
        """Validate that workflow-related required fields are present.

        This can be extended to check for additional workflow-specific requirements.

        Args:
            crate: The ROCrate dict (with @graph).

        Raises:
            CrateValidationError: If required workflow fields are missing.
        """
        graph: list[dict[str, Any]] = crate.get("@graph", [])
        main = _get_main_entity(graph)
        if main is None:
            return  # Already caught by validate_basic

        # Check for common workflow properties that might be required
        # This is a placeholder for future extensions
        pass
