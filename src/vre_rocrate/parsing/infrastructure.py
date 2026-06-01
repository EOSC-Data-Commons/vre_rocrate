from __future__ import annotations

import logging
from typing import Any

from ..models.infrastructure import RuntimePlatform, IMInputFile

logger = logging.getLogger(__name__)


def parse_cpu_requirements(cpus: Any) -> tuple[int, int]:
    """Parse CPU and GPU requirements from processorRequirements field.

    Returns:
        Tuple of (num_cpus, num_gpus)
    """
    num_cpus = 1
    num_gpus = 0

    if isinstance(cpus, str) and "vCPU" in cpus:
        num_cpus = int(cpus.replace("vCPU", "").strip())
    elif isinstance(cpus, list):
        for cpu in cpus:
            if isinstance(cpu, str):
                if "vCPU" in cpu:
                    num_cpus = int(cpu.replace("vCPU", "").strip())
                if "GPU" in cpu:
                    num_gpus = int(cpu.replace("GPU", "").strip())

    return num_cpus, num_gpus


def parse_input_file(raw_file: dict[str, Any]) -> IMInputFile | None:
    """Parse a single input file definition from RuntimePlatform spec.

    Returns:
        IMInputFile instance or None if the file should be skipped.
    """
    if raw_file.get("@type") != "File":
        logger.warning("Input is not of type File, skipping.")
        return None

    file_url = raw_file.get("@id")
    if not file_url:
        logger.warning("Input does not have a @id, skipping.")
        return None

    content_location = raw_file.get("contentLocation")
    compute_node = None
    destination = content_location

    if content_location and ":" in content_location:
        parts = content_location.split(":", 1)
        compute_node = parts[0]
        destination = parts[1]

    return IMInputFile(
        url=file_url,
        destination=destination,
        compute_node=compute_node,
    )


def parse_input_files(input_list: list[dict[str, Any]]) -> list[IMInputFile]:
    """Parse list of input files from RuntimePlatform spec.

    Returns:
        List of IMInputFile instances.
    """
    input_files = []
    for raw_file in input_list:
        parsed = parse_input_file(raw_file)
        if parsed is not None:
            input_files.append(parsed)
    return input_files


def runtime_platform_from_dict(dest: dict[str, Any]) -> RuntimePlatform:
    """Build RuntimePlatform from a RO-Crate RuntimePlatform dict."""
    cpus = dest.get("processorRequirements")
    num_cpus, num_gpus = parse_cpu_requirements(cpus)
    input_files = parse_input_files(dest.get("input", []))

    return RuntimePlatform(
        name=dest.get("name", "Infrastructure Manager"),
        install_url=dest.get("installUrl"),
        memory=dest.get("memoryRequirements"),
        num_cpus=num_cpus,
        num_gpus=num_gpus,
        storage=dest.get("storageRequirements"),
        input_files=input_files,
    )
