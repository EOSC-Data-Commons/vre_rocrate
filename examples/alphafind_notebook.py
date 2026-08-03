"""Example: AlphaFind multi-domain search notebook on Binder/Replay.

Reproduces tests/fixtures/alphafind-notebook/ro-crate-metadata.json. The
notebook has no slots; requirements.txt is a free-form attachment.
"""

import json

from vre_rocrate import (
    VRELaunchRequest, ToolMeta, LaunchInput, FileInput, RocrateBuilder,
)

request = VRELaunchRequest(
    tool=ToolMeta(
        id="alphafind-notebook",
        version="1.0.0",
        name="AlphaFind multi-domain search notebook",
        uri="multi-domain-search.ipynb",
        types=["egi-replay"],
        description=(
            "A Jupyter notebook for AlphaFind multi-domain protein structure "
            "search."
        ),
        slots=[],
        raw_definition={},
    ),
    input=LaunchInput(
        files={
            "requirements.txt": FileInput(
                name="requirements.txt",
                mime_type="text/plain",
            ),
        },
    ),
    runtime_platform="https://replay.notebooks.egi.eu/v2",
)

print(json.dumps(RocrateBuilder.build_from_launch_request(request), indent=2))
