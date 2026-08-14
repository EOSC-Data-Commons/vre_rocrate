"""Example: DataLens notebook (GitHub repo, no Dockerfile) replayed via EGI Replay.

Reproduces tests/fixtures/replay-github-datahugger-no-dockerfile/ro-crate-metadata.json.
Same as the dockerfile variant but the repo URL points at a different fork
(recap/DataLens) that has no Dockerfile.
"""

import json

from vre_rocrate import (
    VRELaunchRequest, ToolMeta, LaunchInput, FileInput, RocrateBuilder,
)

request = VRELaunchRequest(
    tool=ToolMeta(
        id="datalens-notebook",
        version="unknown",
        name="DataLens",
        uri="https://github.com/recap/DataLens",
        types=["egi-replay"],
        description=(
            "An RO-Crate describing the DataLens notebook, its Binder "
            "execution environment, staged input data and non-sensitive "
            "launch parameters."
        ),
        slots=[],
        raw_definition={},
    ),
    input=LaunchInput(
        files={
            "dataset": FileInput(
                name="dataset",
                url=(
                    "https://github.com/EOSC-Data-Commons/dataplayer-example-dataset"
                    "/blob/master/cernbox/CMSDimuon/MuRun2010B.csv"
                ),
                mime_type="text/csv",
            ),
        },
    ),
    runtime_platform="https://replay.notebooks.egi.eu",
)

print(json.dumps(RocrateBuilder.build_from_launch_request(request), indent=2))
