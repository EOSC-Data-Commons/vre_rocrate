import json

from vre_rocrate import (
    VRELaunchRequest,
    ToolMeta,
    LaunchInput,
    SlotDefinition,
    SlotValue,
    RocrateBuilder,
)

PDB_ID = "1L2Y"

request = VRELaunchRequest(
    tool=ToolMeta(
        id="mddash-example",
        version="1.0.0",
        name="MDDash notebook",
        uri="https://github.com/sb-ncbr/mddash-notebooks.git",
        types=["mddash"],
        description="MDDash notebook for PDB analysis.",
        slots=[
            SlotDefinition(
                id="pdb_id",
                name="pdb_id",
                slot_type="string",
                is_optional=False,
            ),
        ],
        raw_definition={},
    ),
    input=LaunchInput(
        slots={"pdb_id": SlotValue(value=PDB_ID)},
    ),
)

print(json.dumps(RocrateBuilder.build_from_launch_request(request), indent=2))
