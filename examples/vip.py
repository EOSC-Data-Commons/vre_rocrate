import json

from vre_rocrate import (
    VRELaunchRequest, ToolMeta, LaunchInput,
    SlotDefinition, FileInput, RocrateBuilder,
)

parameter_file = FileInput(
    name="parameter_file",
    url="https://www.creatis.insa-lyon.fr/~abonnet/quest_param_117T_A.txt",
    mime_type="text/plain",
)
data_file = FileInput(
    name="data_file",
    url="https://www.creatis.insa-lyon.fr/~abonnet/Rec003_Vox1.mrui",
    mime_type="application/octet-stream",
)
zipped_folder = FileInput(
    name="zipped_folder",
    url="https://www.creatis.insa-lyon.fr/~abonnet/basis_11_7.zip",
    mime_type="application/zip",
)

request = VRELaunchRequest(
    tool=ToolMeta(
        id="cquest-pipeline",
        version="0.6",
        name="CQUEST Pipeline",
        uri="https://vip.creatis.insa-lyon.fr/rest/pipelines/CQUEST/0.6",
        types=["boutique", "vip"],
        description="CQUEST pipeline for VIP platform.",
        slots=[
            SlotDefinition(id="parameter_file", name="parameter_file", slot_type="file"),
            SlotDefinition(id="data_file", name="data_file", slot_type="file"),
            SlotDefinition(id="zipped_folder", name="zipped_folder", slot_type="file"),
        ],
        raw_definition={},
    ),
    input=LaunchInput(
        slots={
            "parameter_file": parameter_file,
            "data_file": data_file,
            "zipped_folder": zipped_folder,
        },
    ),
)

print(json.dumps(RocrateBuilder.build_from_launch_request(request), indent=2))
