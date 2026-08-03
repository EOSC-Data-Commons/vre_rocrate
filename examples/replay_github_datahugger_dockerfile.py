"""Example: DataLens notebook (GitHub repo with Dockerfile) replayed via EGI Replay.

Reproduces tests/fixtures/replay-github-datahugger-dockerfile/ro-crate-metadata.json.
The workflow is a repository URL (no inferable encoding → SoftwareSourceCode
only, not staged as a data file). The dataset CSV is a free-form attachment.
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
        uri="https://github.com/andrejcermak/DataLens",
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
    runtime_platform="https://replay.notebooks.egi.eu/v2",
)

print(json.dumps(RocrateBuilder.build_from_launch_request(request), indent=2))
