"""Example: OSCAR service from a remote FDL JSON.

Reproduces tests/fixtures/oscar/ro-crate-metadata.json. The workflow has no
declared slots; the input file is a free-form attachment.
"""

import json

from vre_rocrate import (
    VRELaunchRequest, ToolMeta, LaunchInput, FileInput, RocrateBuilder,
)

WORKFLOW_URL = (
    "https://raw.githubusercontent.com/micafer/Dispatcher/refs/heads/"
    "oscar-vre/test/oscar/cowsay.json"
)

request = VRELaunchRequest(
    tool=ToolMeta(
        id="cowsay-oscar",
        version="1.0.0",
        name="Cowsay OSCAR FDL",
        uri=WORKFLOW_URL,
        types=["oscar"],
        description="A simple OSCAR service using the cowsay example.",
        slots=[],
        raw_definition={},
    ),
    input=LaunchInput(
        files={
            "simpletext_input": FileInput(
                name="simpletext_input",
                url="https://example-files.online-convert.com/document/txt/example.txt",
                mime_type="text/plain",
            ),
        },
    ),
    runtime_platform="https://oscar.vre.eosc-data-commons.eu",
)

print(json.dumps(RocrateBuilder.build_from_launch_request(request), indent=2))
