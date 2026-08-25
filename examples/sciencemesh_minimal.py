import json

from vre_rocrate import (
    VRELaunchRequest, ToolMeta, LaunchInput,
    SlotDefinition, SlotValue, FileInput, RocrateBuilder,
)

RECEIVER = "rwelande@eosc.cernbox.cern.ch"

# Minimal tool information required by RocrateBuilder to produce a
# structurally valid crate — just enough for the shared dataset.
# The mainEntity is named after the share itself, not a real workflow.
request = VRELaunchRequest(
    tool=ToolMeta(
        id="sciencemesh-data-share",
        version="1.0.0",
        name="ScienceMesh data share",
        uri="dummy-tool",
        types=["sciencemesh"],
        description="Shared research data for ScienceMesh federation.",
        slots=[
            SlotDefinition(
                id="Shared With",
                name="Shared With",
                slot_type="string",
                is_optional=False,
            ),
        ],
        raw_definition={},
    ),
    input=LaunchInput(
        dataset=None,
        slots={"Shared With": SlotValue(value=RECEIVER)},
        files={
            "MuRun2010B.csv": FileInput(
                name="MuRun2010B.csv",
                url="https://raw.githubusercontent.com/dpiparo/swanExamples/master/notebooks/MuRun2010B.csv",
                mime_type="text/csv",
            )
        },
    ),
)

print(json.dumps(RocrateBuilder.build_from_launch_request(request), indent=2))
