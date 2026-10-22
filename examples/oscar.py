"""Example: OSCAR service from a remote FDL JSON.

Reproduces tests/fixtures/oscar/ro-crate-metadata.json. The workflow has no
declared slots; the input file is a free-form attachment.
"""

import json

from vre_rocrate import (
    VRELaunchRequest, ToolMeta, LaunchInput, FileInput, RocrateBuilder,
)

WORKFLOW_URL = (
    "https://github.com/grycap/oscar-hub/tree/main/crates/fish-detector"
)

request = VRELaunchRequest(
    tool=ToolMeta(
        id="fish-detector",
        version="1.0.0",
        name="Fish Detector Service (by OBSEA)",
        uri=WORKFLOW_URL,
        types=["oscar"],
        description="OSCAR service that deploys the Fish Detector workflow by OBSEA.",
        slots=[],
        raw_definition={},
    ),
    input=LaunchInput(
        files={
            "image_input": FileInput(
                name="image_input",
                url="https://raw.githubusercontent.com/grycap/oscar-hub/refs/heads/main/crates/fish-detector/input.jpg",
                mime_type="image/jpeg",
            ),
        },
    ),
    runtime_platform="https://oscar.vre.eosc-data-commons.eu",
)

print(json.dumps(RocrateBuilder.build_from_launch_request(request), indent=2))
