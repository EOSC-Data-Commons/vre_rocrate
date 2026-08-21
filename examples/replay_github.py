from vre_rocrate import MinimalVRERequest, MinimalFileInput, RocrateBuilder
import json

# DataLens notebook hosted on GitHub, replayed via the EOSC Replay Binder service.
NOTEBOOK_REPO = "https://github.com/andrejcermak/DataLens"
REPLAY_RUNTIME = "https://replay.notebooks.egi.eu"

dataset = MinimalFileInput(
    name="dataset",
    url="https://github.com/EOSC-Data-Commons/dataplayer-example-dataset/blob/master/cernbox/CMSDimuon/MuRun2010B.csv",
    encoding_format="text/csv",
)

request = MinimalVRERequest(
    vre_type="binder",
    workflow=NOTEBOOK_REPO,
    files=[dataset],
    runtime_platform=REPLAY_RUNTIME,
)

crate = RocrateBuilder.build_from_minimal(request)

print(json.dumps(crate, indent=2))
