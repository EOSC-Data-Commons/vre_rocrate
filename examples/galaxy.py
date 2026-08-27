import json

from vre_rocrate import (
    VRELaunchRequest, ToolMeta, LaunchInput,
    SlotDefinition, FileInput, RocrateBuilder,
)

WORKFLOW_URL = (
    "https://dockstore.org/api/ga4gh/trs/v2/tools/%23workflow%2Fgithub.com"
    "%2Flaitanawe%2Fismb2024%2Fgalaxy_example/versions/main/PLAIN_GALAXY"
    "/descriptor/Galaxy-Workflow-reverse_file_galaxy_workflow.ga"
)

request = VRELaunchRequest(
    tool=ToolMeta(
        id="galaxy-reverse-file",
        version="main",
        name="Galaxy reverse file workflow",
        uri=WORKFLOW_URL,
        types=["galaxy_workflow"],
        description="A simple Galaxy workflow for demonstration purposes.",
        slots=[
            SlotDefinition(
                id="simpletext_input",
                name="simpletext_input",
                slot_type="file",
                is_optional=False,
            ),
        ],
        raw_definition={},
    ),
    input=LaunchInput(
        slots={
            "simpletext_input": FileInput(
                name="simpletext_input",
                url="https://example-files.online-convert.com/document/txt/example.txt",
                mime_type="text/plain",
            ),
        },
    ),
)

print(json.dumps(RocrateBuilder.build_from_launch_request(request), indent=2))
