import json

from vre_rocrate import (
    VRELaunchRequest, ToolMeta, LaunchInput,
    SlotDefinition, SlotValue, FileInput, RocrateBuilder,
)

WORKFLOW_URL = (
    "https://raw.githubusercontent.com/dpiparo/swanExamples/"
    "refs/heads/master/notebooks/CMSDimuon_py.ipynb"
)

request = VRELaunchRequest(
    tool=ToolMeta(
        id="cms-dimuon-notebook",
        version="1.0.0",
        name="CMS Dimuon py notebook",
        uri=WORKFLOW_URL,
        types=["sciencemesh"],
        description="Jupyter notebook for analyzing research data in ScienceMesh environment.",
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
        slots={"Shared With": SlotValue(value="rwelande@eosc.cernbox.cern.ch")},
        files={
            "MuRun2010B.csv": FileInput(
                name="MuRun2010B.csv",
                url="https://raw.githubusercontent.com/dpiparo/swanExamples/master/notebooks/MuRun2010B.csv",
                mime_type="text/csv",
            ),
        },
    ),
)

print(json.dumps(RocrateBuilder.build_from_launch_request(request), indent=2))
