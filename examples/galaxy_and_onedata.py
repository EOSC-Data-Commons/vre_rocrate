"""Example: Galaxy workflow with Onedata-hosted input files.

Reproduces tests/fixtures/galaxy_and_onedata/ro-crate-metadata.json.
The workflow declares two input slots (Input Image, Upload Stopwords) but
the files are attached as free-form data, not bound to the slot parameters.
"""

import json

from vre_rocrate import (
    VRELaunchRequest, ToolMeta, LaunchInput,
    SlotDefinition, FileInput, RocrateBuilder,
)

WORKFLOW_URL = (
    "https://dockstore.org/api/ga4gh/trs/v2/tools/%23workflow%2Fgithub.com"
    "%2Fbwalkowi%2Fgalaxy-workflow-ocr-test%2Fmain/versions/main/PLAIN_GALAXY"
    "/descriptor//galaxy-workflow-ocr-test-DaSCH.ga"
)

request = VRELaunchRequest(
    tool=ToolMeta(
        id="ocr-dasch",
        version="1.0.0",
        name="OCR for a journal from DaSCH - PoC workflow",
        uri=WORKFLOW_URL,
        types=["galaxy_workflow"],
        description=(
            "A workflow to show how material from DaSch can be processed in "
            "Galaxy. The example used is a optical character recognition of a "
            "German newspaper from DaSch which will be made machine-readable, "
            "cleaned, stripped of punctuation and visualised in a Wordcloud."
        ),
        slots=[
            SlotDefinition(id="input-image", name="Input Image", slot_type="file"),
            SlotDefinition(id="input-stopwords", name="Upload Stopwords", slot_type="file"),
        ],
        raw_definition={},
    ),
    input=LaunchInput(
        files={
            "Input Image": FileInput(
                name="Input Image",
                url="https://example.com/input-image.tiff",
                mime_type="image/tiff",
                onedata_domain="demo.onedata.org",
                onedata_file_id=(
                    "00000000007EADF3736861726547756964233964613065396530393037"
                    "3031303930623564336239653566326438323531386368303864642336"
                    "653662323264366633326236336462333466636661633533653532653233"
                    "3363686438626123343765643463363333363839326439636162623931"
                    "6435636430623161663436636830343438"
                ),
            ),
            "Upload Stopwords": FileInput(
                name="Upload Stopwords",
                url="https://example.com/stopwords.txt",
                mime_type="text/plain",
                onedata_domain="demo.onedata.org",
                onedata_file_id=(
                    "00000000007E21F3736861726547756964233937316538386630666539"
                    "3937653364333530363538656636353636313037663263683038646423"
                    "366536623232643666333262363364623334666366616335336535326532"
                    "333363686438626123343765643463363333363839326439636162623931"
                    "6435636430623161663436636830343438"
                ),
            ),
        },
    ),
)

print(json.dumps(RocrateBuilder.build_from_launch_request(request), indent=2))
