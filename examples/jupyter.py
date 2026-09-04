"""Example: Jupyter notebook on a JupyterHub instance.

Reproduces tests/fixtures/jupyter/ro-crate-metadata.json. A local notebook
file with no inputs.
"""

import json

from vre_rocrate import (
    VRELaunchRequest, ToolMeta, LaunchInput, RocrateBuilder,
)

request = VRELaunchRequest(
    tool=ToolMeta(
        id="jupyter-example",
        version="1.0.0",
        name="Example jupyter notebook",
        uri="notebook.ipynb",
        types=["jupyter"],
        description="A simple Jupyter notebook for demonstration purposes.",
        slots=[],
        raw_definition={},
    ),
    input=LaunchInput(),
    runtime_platform="https://notebooks-dev.egi.zcu.cz",
)

print(json.dumps(RocrateBuilder.build_from_launch_request(request), indent=2))
