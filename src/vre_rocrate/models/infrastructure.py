from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class IMInputFile:
    """Typed descriptor for a file to stage into the deployed service."""

    url: str
    destination: str | None = None
    compute_node: str | None = None


@dataclass
class RuntimePlatform:
    """Domain representation of a RO-Crate RuntimePlatform entity."""

    name: str
    install_url: str | None = None
    memory: str | None = None
    num_cpus: int = 1
    num_gpus: int = 0
    storage: str | None = None
    input_files: list[IMInputFile] = field(default_factory=list)
