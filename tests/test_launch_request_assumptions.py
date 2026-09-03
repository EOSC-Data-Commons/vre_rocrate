"""Assumption tests for the VRELaunchRequest transformation.

These tests encode the behavioral assumptions stated in the design note
``docs/design/vre-launch-request-transformation.md`` against the public API.
Only the public API is exercised — no internal helpers, no private methods.
"""

import dataclasses

import pytest

from vre_rocrate import (
    VRELaunchRequest,
    ToolMeta,
    LaunchInput,
    SlotDefinition,
    FileInput,
    DatasetHandle,
    RocrateBuilder,
    VREPayloadBuilder,
    VREPayload,
    WorkflowDescriptor,
    ValidationPipeline,
)
from vre_rocrate.constants import (
    resolve_vre_type,
    VRE_TYPE_TO_DEFAULT_RUNTIME_PLATFORM,
)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

GALAXY_URI = "https://example.org/wf.ga"
BINDER_URI = "https://example.org/nb.ipynb"
SCIENCEMESH_URI = "https://example.org/nb.ipynb"
MDDASH_URI = "https://github.com/sb-ncbr/mddash-notebooks.git"
FILE_URL = "https://example.org/p.txt"
FREE_FILE_URL = "https://example.org/free.csv"
DATASET_URL = "https://example.org/dataset"


def _entity(graph, eid):
    return next(e for e in graph if e.get("@id") == eid)


def _tool(uri, types, slots=None, raw_definition=None, version="1", name="T", tid="t"):
    return ToolMeta(id=tid, version=version, name=name, uri=uri, types=types,
                    slots=slots or [], raw_definition=raw_definition or {})


@pytest.fixture
def galaxy_slot_request():
    """Galaxy request with one file-bound slot."""
    return VRELaunchRequest(
        tool=_tool(GALAXY_URI, ["galaxy_workflow"],
                   slots=[SlotDefinition(id="f", name="f", slot_type="file")]),
        input=LaunchInput(slots={
            "f": FileInput(name="f", url=FILE_URL),
        }),
    )


@pytest.fixture
def binder_files_request():
    """Binder request with one free-form file, no slots."""
    return VRELaunchRequest(
        tool=_tool(BINDER_URI, ["binder"]),
        input=LaunchInput(files={
            "data.csv": FileInput(name="data.csv", url=FREE_FILE_URL),
        }),
    )


@pytest.fixture
def galaxy_slot_and_free_file_request():
    """Galaxy request with both a slot-bound file and a free-form file."""
    return VRELaunchRequest(
        tool=_tool(GALAXY_URI, ["galaxy_workflow"],
                   slots=[SlotDefinition(id="slot_file", name="slot_file", slot_type="file")]),
        input=LaunchInput(
            slots={
                "slot_file": FileInput(name="slot_file",
                                       url="https://example.org/slot.txt"),
            },
            files={
                "free.csv": FileInput(name="free.csv", url=FREE_FILE_URL),
            },
        ),
    )


@pytest.fixture
def galaxy_empty_request():
    """Galaxy request with no slots, no files, no dataset."""
    return VRELaunchRequest(
        tool=_tool(GALAXY_URI, ["galaxy_workflow"]),
        input=LaunchInput(),
    )


@pytest.fixture
def sciencemesh_literal_slot_request():
    """ScienceMesh request with a literal-value slot (Shared With)."""
    return VRELaunchRequest(
        tool=_tool(SCIENCEMESH_URI, ["sciencemesh"],
                   slots=[SlotDefinition(id="Shared With", name="Shared With",
                                         slot_type="string")]),
        input=LaunchInput(slots={"Shared With": "user@e.org"}),
    )


@pytest.fixture
def galaxy_dataset_request():
    """Galaxy request with a DatasetHandle."""
    return VRELaunchRequest(
        tool=_tool(GALAXY_URI, ["galaxy_workflow"]),
        input=LaunchInput(dataset=DatasetHandle(
            url=DATASET_URL, title="DS", description="A dataset",
        )),
    )


@pytest.fixture
def mddash_scalar_slot_request():
    """MDDash request with a scalar pdb_id slot (no files at all)."""
    return VRELaunchRequest(
        tool=_tool(MDDASH_URI, ["mddash"],
                   slots=[SlotDefinition(id="pdb_id", name="pdb_id",
                                          slot_type="string")]),
        input=LaunchInput(slots={"pdb_id": "1L2Y"}),
    )


def _build(request):
    return RocrateBuilder.build_from_launch_request(request)


def _graph(crate):
    return crate["@graph"]


# ---------------------------------------------------------------------------
# Dataclass defaults (design note §1) — defaults can change silently
# ---------------------------------------------------------------------------

def test_model_defaults():
    s = SlotDefinition(id="p", name="P", slot_type="file")
    assert s.is_optional is False

    f = FileInput(name="d.csv")
    assert all(getattr(f, a) is None for a in (
        "path", "url", "size_bytes", "mime_type", "checksum",
        "checksum_type", "onedata_domain", "onedata_file_id"))

    t = ToolMeta(id="t", version="1", name="T", uri="u", types=["galaxy"])
    assert (t.description, t.slots, t.raw_definition) == ("", [], {})
    assert t.slots is not ToolMeta(
        id="t2", version="1", name="T", uri="u", types=["galaxy"]).slots
    assert not hasattr(t, "tool_kind")  # design note constraint #7

    li = LaunchInput()
    assert li.dataset is None and li.slots == {} and li.files == {}

    req = VRELaunchRequest(tool=_tool("u", ["galaxy"]), input=LaunchInput())
    assert req.runtime_platform is None


# ---------------------------------------------------------------------------
# resolve_vre_type — three-layer resolution (design note §3)
# ---------------------------------------------------------------------------

def test_resolve_vre_type_from_raw_definition_override():
    t = _tool("u", ["unknown"], raw_definition={"vre_type": "galaxy"})
    assert resolve_vre_type(t) == "galaxy"


def test_resolve_vre_type_from_tool_types():
    for ttype, expected in {
        "galaxy_workflow": "galaxy", "vip": "vip", "boutique": "vip",
        "sciencemesh": "sciencemesh", "binder-launcher": "binder", "rrp": "rrp",
    }.items():
        assert resolve_vre_type(_tool("u", [ttype])) == expected, f"{ttype} -> {expected}"


def test_resolve_vre_type_falls_back_to_uri():
    assert resolve_vre_type(
        _tool("https://usegalaxy.eu/workflows/abc", [])) == "galaxy"


def test_resolve_vre_type_raises_when_unresolvable():
    with pytest.raises(ValueError):
        resolve_vre_type(_tool("https://example.org/x", []))


# ---------------------------------------------------------------------------
# Slots vs Files — core semantic distinction (design note §2)
# ---------------------------------------------------------------------------

def test_free_form_files_do_not_produce_formal_parameters(binder_files_request):
    graph = _graph(_build(binder_files_request))
    assert [e for e in graph if e.get("@type") == "FormalParameter"] == []


def test_slot_value_literal_becomes_default_value_literal(sciencemesh_literal_slot_request):
    fp = _entity(_graph(_build(sciencemesh_literal_slot_request)), "#input-Shared With")
    assert fp["defaultValue"] == "user@e.org"


def test_slot_value_file_becomes_default_value_id_ref(galaxy_slot_request):
    fp = _entity(_graph(_build(galaxy_slot_request)), "#input-f")
    assert fp["defaultValue"] == {"@id": FILE_URL}


def test_mddash_scalar_slot_produces_no_file_and_roundtrips(
    mddash_scalar_slot_request,
):
    """A scalar (string) slot produces no File entity; value survives the round-trip."""
    crate = _build(mddash_scalar_slot_request)
    file_entities = [e for e in _graph(crate) if e.get("@type") == "File"]
    assert file_entities == []
    pkg = VREPayloadBuilder.build(crate)
    param = pkg.input_by_name("pdb_id")
    assert param is not None
    assert param.default_value == "1L2Y"
    assert pkg.input_files == []


def test_free_form_file_appears_as_standalone_file_entity(binder_files_request):
    fe = _entity(_graph(_build(binder_files_request)), FREE_FILE_URL)
    assert fe["@type"] == "File"


def test_free_form_file_stated_in_dataset_haspart(binder_files_request):
    """Free-form files must be listed in the root dataset's hasPart."""
    crate = _build(binder_files_request)
    root = _entity(_graph(crate), "./")
    haspart_ids = {ref["@id"] for ref in root.get("hasPart", [])}
    assert FREE_FILE_URL in haspart_ids


# ---------------------------------------------------------------------------
# runtimePlatform — always present, resolved or overridden (design note §3, §7)
# ---------------------------------------------------------------------------

def test_runtime_platform_inferred_when_not_set(galaxy_empty_request):
    wf = _entity(_graph(_build(galaxy_empty_request)), GALAXY_URI)
    assert wf["runtimePlatform"] == VRE_TYPE_TO_DEFAULT_RUNTIME_PLATFORM["galaxy"]


def test_runtime_platform_override_used_directly():
    req = VRELaunchRequest(
        tool=_tool(GALAXY_URI, ["galaxy_workflow"]),
        input=LaunchInput(),
        runtime_platform="https://custom-galaxy.example.org/",
    )
    wf = _entity(_graph(_build(req)), GALAXY_URI)
    assert wf["runtimePlatform"] == "https://custom-galaxy.example.org/"


# ---------------------------------------------------------------------------
# Dataset entity — only when input.dataset is provided (design note §4)
# ---------------------------------------------------------------------------

def test_dataset_entity_present_when_dataset_provided(galaxy_dataset_request):
    ds = _entity(_graph(_build(galaxy_dataset_request)), DATASET_URL)
    assert ds["@type"] == "Dataset" and ds["name"] == "DS"


def test_no_dataset_entity_when_dataset_none(galaxy_empty_request):
    datasets = [e for e in _graph(_build(galaxy_empty_request))
                if e.get("@type") == "Dataset" and e.get("@id") != "./"]
    assert datasets == []


# ---------------------------------------------------------------------------
# #tool-metadata entity (design note §4)
# ---------------------------------------------------------------------------

def test_tool_metadata_entity_carries_raw_definition():
    raw = {"custom": "value", "nested": {"a": 1}}
    req = VRELaunchRequest(
        tool=_tool(GALAXY_URI, ["galaxy_workflow"], raw_definition=raw),
        input=LaunchInput(),
    )
    tm = _entity(_graph(_build(req)), "#tool-metadata")
    assert tm["rawDefinition"] == raw


# ---------------------------------------------------------------------------
# Round-trip: build_from_launch_request -> VREPayloadBuilder.build
# ---------------------------------------------------------------------------

def test_roundtrip_galaxy_slots(galaxy_slot_request):
    pkg = VREPayloadBuilder.build(_build(galaxy_slot_request))
    assert pkg.workflow.id == GALAXY_URI
    assert any(f.id == FILE_URL for f in pkg.files)


def test_roundtrip_raw_definition_preserved():
    raw = {"k": "v"}
    req = VRELaunchRequest(
        tool=_tool(GALAXY_URI, ["galaxy_workflow"], raw_definition=raw),
        input=LaunchInput(),
    )
    pkg = VREPayloadBuilder.build(_build(req))
    assert pkg.raw_definition == raw


def test_roundtrip_workflow_version():
    req = VRELaunchRequest(
        tool=_tool(GALAXY_URI, ["galaxy_workflow"], version="2.3.1"),
        input=LaunchInput(),
    )
    pkg = VREPayloadBuilder.build(_build(req))
    assert pkg.workflow.tool_version == "2.3.1"


# ---------------------------------------------------------------------------
# VREPayload stays additive (design note §5)
# ---------------------------------------------------------------------------

def test_vre_payload_existing_fields_unchanged():
    names = {f.name for f in dataclasses.fields(VREPayload)}
    assert {"vre_type", "programming_language", "workflow", "files",
            "workflow_inputs", "workflow_outputs", "raw_crate",
            "raw_definition"}.issubset(names)
    assert "ocm_data" not in names  # OCMData dropped; parties travel as input slots


def test_workflow_descriptor_tool_version_is_new_and_optional():
    f = {f.name: f for f in dataclasses.fields(WorkflowDescriptor)}["tool_version"]
    assert f.default is None


# ---------------------------------------------------------------------------
# input_files property behavior under the new crate format (design note §6)
# ---------------------------------------------------------------------------

def test_input_files_returns_slot_files_when_slots_present(galaxy_slot_request):
    pkg = VREPayloadBuilder.build(_build(galaxy_slot_request))
    assert FILE_URL in {f.id for f in pkg.input_files}


def test_input_files_returns_all_files_when_no_slots(binder_files_request):
    pkg = VREPayloadBuilder.build(_build(binder_files_request))
    assert {f.id for f in pkg.input_files} == {FREE_FILE_URL}


def test_input_files_returns_both_slot_and_free_form_files(
    galaxy_slot_and_free_file_request,
):
    """SlotsAndFiles tools (e.g. sciencemesh/cernbox) carry both slot parameters
    and free-form data attachments. input_files must return both, not just the
    slot-bound ones. Shared With is the slot; the CSV is the free-form file."""
    pkg = VREPayloadBuilder.build(_build(galaxy_slot_and_free_file_request))
    input_ids = {f.id for f in pkg.input_files}
    assert "https://example.org/slot.txt" in input_ids   # slot-bound file
    assert FREE_FILE_URL in input_ids                    # free-form file, included


# ---------------------------------------------------------------------------
# Input bindings accessors (design note §6) — name → file / scalar mapping
# ---------------------------------------------------------------------------

def test_input_file_bindings_pairs_named_inputs_with_files(galaxy_slot_request):
    pkg = VREPayloadBuilder.build(_build(galaxy_slot_request))
    bindings = pkg.input_file_bindings()
    assert len(bindings) == 1
    name, f = bindings[0]
    assert name == "f"
    assert (f.id, f.url) == (FILE_URL, FILE_URL)


def test_input_file_bindings_skips_literal_slots(sciencemesh_literal_slot_request):
    pkg = VREPayloadBuilder.build(_build(sciencemesh_literal_slot_request))
    assert pkg.input_file_bindings() == []


def test_input_literal_bindings_returns_scalar_slots(mddash_scalar_slot_request):
    pkg = VREPayloadBuilder.build(_build(mddash_scalar_slot_request))
    assert pkg.input_literal_bindings() == [("pdb_id", "1L2Y")]


def test_input_literal_bindings_skips_file_slots(galaxy_slot_request):
    pkg = VREPayloadBuilder.build(_build(galaxy_slot_request))
    assert pkg.input_literal_bindings() == []


def test_input_value_bindings_mixes_files_and_literals():
    req = VRELaunchRequest(
        tool=_tool(GALAXY_URI, ["galaxy_workflow"],
                   slots=[SlotDefinition(id="f", name="f", slot_type="file"),
                          SlotDefinition(id="n", name="n", slot_type="string")]),
        input=LaunchInput(slots={
            "f": FileInput(name="f", url=FILE_URL),
            "n": "literal",
        }),
    )
    pkg = VREPayloadBuilder.build(_build(req))
    pairs = dict(pkg.input_value_bindings())
    assert pairs["f"].id == FILE_URL   # FileReference for the file-bound slot
    assert pairs["n"] == "literal"     # scalar passthrough for the literal slot
    assert pkg.input_value_bindings() == (
        pkg.input_literal_bindings() + pkg.input_file_bindings()
    )


# ---------------------------------------------------------------------------
# Validation — the new crate must pass ValidationPipeline (design note §6)
# ---------------------------------------------------------------------------

def test_built_crate_passes_validation(galaxy_slot_request):
    ValidationPipeline.validate_basic(_build(galaxy_slot_request))  # must not raise
