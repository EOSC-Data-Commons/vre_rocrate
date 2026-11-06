import json

from vre_rocrate import (
    VRELaunchRequest, ToolMeta, LaunchInput,
    SlotDefinition, FileInput, RuntimePlatform,
    IMInputFile, RocrateBuilder,
)

GALAXY_TOSCA_URI = "https://dockstore.org/api/ga4gh/trs/v2/tools/%23workflow%2Fgithub.com%2Flaitanawe%2Fismb2024%2Fgalaxy_example/versions/main/PLAIN_GALAXY/descriptor//Galaxy-Workflow-reverse_file_galaxy_workflow.ga"

textfile = FileInput(
    name="simpletext_input",
    url="https://example-files.online-convert.com/document/txt/example.txt",
    mime_type="text/txt",
)

request = VRELaunchRequest(
    tool=ToolMeta(
        id="galaxy-example",
        version="1.0.0",
        name="Example galaxy workflow",
        uri=GALAXY_TOSCA_URI,
        types=["galaxy_workflow"],
        description="A simple Galaxy workflow for demonstration purposes.",
        slots=[
            SlotDefinition(id="textfile", name="simpletext_input",
                           slot_type="file"),
        ],
        raw_definition={},
    ),
    input=LaunchInput(
        files={"simpletext_input": textfile},
    ),
    runtime_platform=RuntimePlatform(
        name="Infrastructure Manager",
        memory="4 GiB",
        num_cpus=2,
        num_gpus=1,
        storage="200 GiB",
        install_url="https://raw.githubusercontent.com/grycap/tosca/refs/heads/eosc_dc/templates/galaxy.yaml",
        input_files=[
            IMInputFile(url="#tosca_input_file", destination="/opt/data"),
        ],
    ),
)

print(json.dumps(RocrateBuilder.build_from_launch_request(request), indent=2))
