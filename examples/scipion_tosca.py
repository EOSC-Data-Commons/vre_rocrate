import json

from vre_rocrate import (
    VRELaunchRequest, ToolMeta, LaunchInput,
    SlotDefinition, DatasetHandle, RocrateBuilder, RuntimePlatform,
)

WORKFLOW_URL = (
    "https://workflowhub.eu/workflows/2169/git/1/raw/"
    "workflow_2D_xmipp.json.template"
)

SCIPION_TOSCA_URI = "https://workflowhub.eu/workflows/2169/git/1/raw/workflow_2D_xmipp.json.template"

# The empiar_dataset slot is filled by an entire remote collection — a
# DatasetHandle, not a FileInput: the builder emits a Dataset entity
# (name/description) referenced from defaultValue and root hasPart,
# mirroring slot-bound files.
empiar = DatasetHandle(
    url="rsync://ftp.ebi.ac.uk/empiar/world_availability/10305/",
    title="empiar_dataset",
    description="",
)

request = VRELaunchRequest(
    tool=ToolMeta(
        id="scipion-xmipp",
        version="1.0.0",
        name="Example scipion workflow",
        uri=WORKFLOW_URL,
        types=["scipion"],
        description="An Xmipp workflow run on Scipion with Infrastructure Manager.",
        slots=[
            SlotDefinition(
                id="empiar_dataset",
                name="empiar_dataset",
                slot_type="data_collection",
            ),
            SlotDefinition(
                id="streaming",
                name="streaming",
                slot_type="Boolean"
            ),
        ],
        raw_definition={},
    ),
    input=LaunchInput(
        dataset=empiar,
        slots={"streaming": False},
    ),
    runtime_platform=RuntimePlatform(
        name="Infrastructure Manager",
        install_url=(
            "https://raw.githubusercontent.com/grycap/tosca/"
            "refs/heads/eosc_beyond/templates/scipion.yaml"
        ),
        memory="4 GiB",
        num_cpus=2,
        storage="200 GiB",
    ),
)

if __name__ == "__main__":
    print(json.dumps(RocrateBuilder.build_from_launch_request(request), indent=2))



request = VRELaunchRequest(
    tool=ToolMeta(
        id="scipion-example",
        version="1.0.0",
        name="Example scipion workflow",
        uri=SCIPION_TOSCA_URI,
        types=["scipion"],
        description="A simple Scipion workflow for demonstration purposes.",
        slots=[
            SlotDefinition(id="empiar-dataset", name="empiar_dataset",
                           slot_type="data_collection"),
            SlotDefinition(id="streaming", name="streaming",
                           slot_type="Boolean"),
        ],
        raw_definition={},
    ),
    input=LaunchInput(
        slots={
            "empiar_dataset": empiar,
            "streaming": False,
        },
    ),
    runtime_platform=RuntimePlatform(
        name="Infrastructure Manager",
        memory="4 GiB",
        num_cpus=2,
        storage="200 GiB",
        install_url="https://raw.githubusercontent.com/grycap/tosca/refs/heads/eosc_beyond/templates/scipion.yaml",
    ),
)

print(json.dumps(RocrateBuilder.build_from_launch_request(request), indent=2))
