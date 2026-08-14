"""Example: Simple local Jupyter notebook for Binder.

Reproduces tests/fixtures/simple-binder/ro-crate-metadata.json. A local
notebook file with no inputs.
"""

import json

from vre_rocrate import (
    VRELaunchRequest, ToolMeta, LaunchInput, RocrateBuilder,
)

request = VRELaunchRequest(
    tool=ToolMeta(
        id="binder-example",
        version="1.0.0",
        name="Example jupyter notebook",
        uri="notebook.ipynb",
        types=["binder"],
        description="A simple Jupyter notebook for demonstration purposes.",
        slots=[],
        raw_definition={},
    ),
    input=LaunchInput(),
    runtime_platform="https://replay.notebooks.egi.eu",
)

print(json.dumps(RocrateBuilder.build_from_launch_request(request), indent=2))
