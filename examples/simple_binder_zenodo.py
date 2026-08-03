"""Example: Binder notebook referenced by a Zenodo DOI.

Reproduces tests/fixtures/simple-binder/ro-crate-metadata-zenodo.json. The
workflow @id is a DOI URL (no inferable encoding → File + SoftwareSourceCode,
no ComputationalWorkflow).
"""

import json

from vre_rocrate import (
    VRELaunchRequest, ToolMeta, LaunchInput, RocrateBuilder,
)

request = VRELaunchRequest(
    tool=ToolMeta(
        id="binder-zenodo",
        version="1.0.0",
        name="Example jupyter notebook",
        uri="https://doi.org/10.5281/zenodo.12345678",
        types=["binder"],
        description="A simple Jupyter notebook for demonstration purposes.",
        slots=[],
        raw_definition={},
    ),
    input=LaunchInput(),
    runtime_platform="https://replay.notebooks.egi.eu/",
)

print(json.dumps(RocrateBuilder.build_from_launch_request(request), indent=2))
