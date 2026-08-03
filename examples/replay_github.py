import json

from vre_rocrate import (
    VRELaunchRequest, ToolMeta, LaunchInput, FileInput, RocrateBuilder,
)

REPLAY_RUNTIME = "https://replay.notebooks.egi.eu"

request = VRELaunchRequest(
    tool=ToolMeta(
        id="datalens-notebook",
        version="unknown",
        name="DataLens notebook",
        uri="https://github.com/andrejcermak/DataLens",
        types=["egi-replay"],
        description="DataLens notebook hosted on GitHub.",
        slots=[],
        raw_definition={},
    ),
    input=LaunchInput(
        files={
            "MuRun2010B.csv": FileInput(
                name="MuRun2010B.csv",
                url="https://github.com/EOSC-Data-Commons/dataplayer-example-dataset"
                    "/blob/master/cernbox/CMSDimuon/MuRun2010B.csv",
                mime_type="text/csv",
            ),
        },
    ),
    runtime_platform=REPLAY_RUNTIME,
)

print(json.dumps(RocrateBuilder.build_from_launch_request(request), indent=2))
