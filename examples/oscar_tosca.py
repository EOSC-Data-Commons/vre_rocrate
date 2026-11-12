import json

from vre_rocrate import (
    VRELaunchRequest, ToolMeta, LaunchInput,
    FileInput, RuntimePlatform, RocrateBuilder,
)

textfile = FileInput(
    name="simpletext_input",
    url="https://example-files.online-convert.com/document/txt/example.txt",
    mime_type="text/txt",
)

request = VRELaunchRequest(
    tool=ToolMeta(
        id="oscar-cowsay",
        version="1.0.0",
        name="Cowsay OSCAR FDL",
        uri="https://raw.githubusercontent.com/micafer/Dispatcher/refs/heads/oscar-vre/test/oscar/cowsay.json",
        types=["oscar"],
        description="A simple OSCAR service using the cowsay example.",
        raw_definition={},
    ),
    input=LaunchInput(
        files={"simpletext_input": textfile},
    ),
    runtime_platform=RuntimePlatform(
        name="Infrastructure Manager",
        memory="4 GiB",
        num_cpus=2,
        install_url="https://raw.githubusercontent.com/grycap/tosca/refs/heads/eosc_dc/templates/oscar.yaml",
    ),
)

print(json.dumps(RocrateBuilder.build_from_launch_request(request), indent=2))
