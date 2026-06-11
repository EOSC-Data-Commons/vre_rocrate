from vre_rocrate import RocrateBuilder, MinimalVRERequest, MinimalFileInput

PDB_NAME = "1L2Y"
PDB_URL = "https://www.ebi.ac.uk/pdbe/entry-files/download/pdb1l2y.ent"
PDB_ENCODING = "chemical/x-pdb"
NOTEBOOKS_REPO = "https://github.com/sb-ncbr/mddash-notebooks.git"

request = MinimalVRERequest(
    vre_type="mddash",
    workflow=NOTEBOOKS_REPO,
    files=[
        MinimalFileInput(
            name=PDB_NAME,
            url=PDB_URL,
            encoding_format=PDB_ENCODING,
        ),
    ],
)
RocrateBuilder.build_from_minimal(request)