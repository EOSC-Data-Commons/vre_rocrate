from vre_rocrate import MinimalVRERequest, MinimalFileInput, RocrateBuilder
import json

minimal = MinimalVRERequest(
    vre_type="galaxy",
    workflow="https://dockstore.org/api/ga4gh/trs/v2/tools/%23workflow%2Fgithub.com%2Flaitanawe%2Fismb2024%2Fgalaxy_example/versions/main/PLAIN_GALAXY/descriptor/Galaxy-Workflow-reverse_file_galaxy_workflow.ga",
    files=[
        MinimalFileInput(
            name="simpletext_input",
            url="https://example-files.online-convert.com/document/txt/example.txt",
            encoding_format="txt",
        )
    ],
)

ro_crate = RocrateBuilder.build_from_minimal(minimal)
dump = json.dumps(ro_crate, indent=2)
print(dump)
