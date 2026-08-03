import json

from vre_rocrate import (
    VRELaunchRequest, ToolMeta, LaunchInput,
    SlotDefinition, SlotValue, FileInput, RocrateBuilder,
)

PDB_NAME = "1L2Y"

request = VRELaunchRequest(
    tool=ToolMeta(
        id="mddash-example",
        version="1.0.0",
        name="MDDash notebook",
        uri="https://github.com/sb-ncbr/mddash-notebooks.git",
        types=["mddash"],
        description="MDDash notebook for PDB file analysis.",
        slots=[
            SlotDefinition(
                id=PDB_NAME,
                name=PDB_NAME,
                slot_type="file",
                is_optional=False,
            ),
        ],
        raw_definition={},
    ),
    input=LaunchInput(
        slots={
            PDB_NAME: SlotValue(
                file=FileInput(
                    name=PDB_NAME,
                    url="https://www.ebi.ac.uk/pdbe/entry-files/download/pdb1l2y.ent",
                    mime_type="chemical/x-pdb",
                )
            ),
        },
    ),
)

print(json.dumps(RocrateBuilder.build_from_launch_request(request), indent=2))
