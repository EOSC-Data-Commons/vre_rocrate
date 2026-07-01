from vre_rocrate import RocrateBuilder, MinimalVRERequest, MinimalFileInput

WORKFLOW_URL = (
    "https://raw.githubusercontent.com/dpiparo/swanExamples/"
    "refs/heads/master/notebooks/CMSDimuon_py.ipynb"
)

DATA_FILE = MinimalFileInput(
    name="MuRun2010B.csv",
    url="https://raw.githubusercontent.com/dpiparo/swanExamples/master/notebooks/MuRun2010B.csv",
    encoding_format="text/csv",
)

request = MinimalVRERequest(
    vre_type="sciencemesh",
    workflow=WORKFLOW_URL,
    files=[DATA_FILE],
    runtime_platform="https://eosc.cernbox.cern.ch",
    receiver_userid="rwelande@cernbox.cern.ch",
)

print(RocrateBuilder.build_from_minimal(request))
