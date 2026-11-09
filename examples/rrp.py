import json

from vre_rocrate import (
    VRELaunchRequest,
    ToolMeta,
    LaunchInput,
    SlotDefinition,
    FileInput,
    DatasetHandle,
    RocrateBuilder,
)

request = VRELaunchRequest(
    tool=ToolMeta(
        id="::st:002",
        version="v0",
        name="Reproducible Research Platform (RRP)",
        uri="https://gitlab.ethz.ch/Reproducible-Research-Platform/tools/Cell-Doubling-Time",
        types=["general", "rrp"],
        description="RRP as general tool",
        docker_image="reproducibleresearchplatform/rrp-eosc:cell-doubling-time_1.0.1",
        slots=[
            SlotDefinition(id="image_0.tif", name="Image 0 (TIF)", slot_type="file"),
            SlotDefinition(id="image_1.tif", name="Image 1 (TIF)", slot_type="file"),
        ],
    ),
    input=LaunchInput(
        dataset=DatasetHandle(
            url="https://doi.org/10.5281/zenodo.20507550",
            title="Cell doubling time dataset",
            description="Microscopy images for cell doubling time analysis",
        ),
        slots={
            "Image 0 (TIF)": FileInput(
                name="image_0.tif",
                url="https://zenodo.org/records/20507550/files/image_0.tif",
                mime_type="image/tiff",
            ),
            "Image 1 (TIF)": FileInput(
                name="image_1.tif",
                url="https://zenodo.org/records/20507550/files/image_1.tif",
                mime_type="image/tiff",
            ),
        },
    ),
)

print(json.dumps(RocrateBuilder.build_from_launch_request(request), indent=2))
