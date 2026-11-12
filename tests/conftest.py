"""Shared test helpers: build crates from examples/ scripts."""

import importlib

from vre_rocrate import RocrateBuilder


def example_crate(name: str) -> dict:
    """Build the crate dict produced by examples/<name>.py.

    Examples are importable: each module exposes a module-level `request`
    and only prints when run as a script.
    """
    example = importlib.import_module(f"examples.{name}")
    return RocrateBuilder.build_from_launch_request(example.request)
