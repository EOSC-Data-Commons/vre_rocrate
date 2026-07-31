"""Assumption tests for the VRELaunchRequest transformation plan.

These tests encode the behavioral assumptions stated in
``plans/vre-launch-request-transformation.md`` against the *future* public API
(``VRELaunchRequest``, ``ToolMeta``, ``LaunchInput``, ``SlotDefinition``,
``SlotValue``, ``FileInput``, ``DatasetHandle``, ``RocrateBuilder.build_from_launch_request``,
``resolve_vre_type``).

They are written BEFORE the implementation exists. They are expected to FAIL
with ImportError / AttributeError until the plan is implemented. Their purpose
is to pin the plan's assumptions so that the implementation can be validated
against them, and so that any drift between plan and implementation is caught.

Only the public API is exercised — no internal helpers, no private methods.
"""

import pytest


# ---------------------------------------------------------------------------
# Imports — these names must exist in the public API after the transformation.
# ---------------------------------------------------------------------------

def test_public_api_exports_launch_types():
    """The package must export the new launch-request types."""
    import vre_rocrate

    for name in (
        "VRELaunchRequest",
        "ToolMeta",
        "LaunchInput",
        "SlotDefinition",
        "SlotValue",
        "FileInput",
        "DatasetHandle",
        "RocrateBuilder",
        "RequestPackageBuilder",
    ):
        assert hasattr(vre_rocrate, name), f"vre_rocrate must export {name}"


def test_minimal_vre_request_removed():
    """MinimalVRERequest and MinimalFileInput must be removed from the public API."""
    import vre_rocrate

    assert not hasattr(vre_rocrate, "MinimalVRERequest")
    assert not hasattr(vre_rocrate, "MinimalFileInput")


def test_build_from_minimal_removed():
    """RocrateBuilder.build_from_minimal must no longer exist."""
    from vre_rocrate import RocrateBuilder

    assert not hasattr(RocrateBuilder, "build_from_minimal")
    assert hasattr(RocrateBuilder, "build_from_launch_request")


# ---------------------------------------------------------------------------
# Dataclass shapes — the fields the plan specifies in §1.
# ---------------------------------------------------------------------------

def test_dataset_handle_fields():
    from vre_rocrate import DatasetHandle

    d = DatasetHandle(url="https://example.org/data", title="T", description="D")
    assert d.url == "https://example.org/data"
    assert d.title == "T"
    assert d.description == "D"


def test_slot_definition_fields():
    from vre_rocrate import SlotDefinition

    s = SlotDefinition(id="param_file", name="Parameter File", slot_type="file")
    assert s.id == "param_file"
    assert s.name == "Parameter File"
    assert s.slot_type == "file"
    assert s.is_optional is False  # default


def test_file_input_fields():
    from vre_rocrate import FileInput

    f = FileInput(name="data.csv")
    assert f.name == "data.csv"
    assert f.path is None
    assert f.url is None
    assert f.size_bytes is None
    assert f.mime_type is None
    assert f.checksum is None
    assert f.checksum_type is None
    assert f.onedata_domain is None
    assert f.onedata_file_id is None


def test_slot_value_is_value_or_file():
    from vre_rocrate import SlotValue, FileInput

    v_literal = SlotValue(value="hello")
    assert v_literal.value == "hello"
    assert v_literal.file is None

    v_file = SlotValue(file=FileInput(name="x.csv", url="https://e.org/x.csv"))
    assert v_file.file is not None
    assert v_file.file.url == "https://e.org/x.csv"
    assert v_file.value is None


def test_tool_meta_fields_and_defaults():
    from vre_rocrate import ToolMeta

    t = ToolMeta(id="t", version="1", name="T", uri="https://e.org/t", types=["galaxy"])
    assert t.id == "t"
    assert t.version == "1"
    assert t.name == "T"
    assert t.uri == "https://e.org/t"
    assert t.types == ["galaxy"]
    assert t.description == ""
    assert t.slots == []
    assert t.raw_definition == {}
    # ToolKind must NOT be a field on ToolMeta (plan constraint #7).
    assert not hasattr(t, "tool_kind")


def test_launch_input_has_slots_and_files_maps():
    from vre_rocrate import LaunchInput

    li = LaunchInput()
    assert li.dataset is None
    assert li.slots == {}
    assert li.files == {}


def test_vre_launch_request_fields():
    from vre_rocrate import VRELaunchRequest, ToolMeta, LaunchInput

    req = VRELaunchRequest(
        tool=ToolMeta(id="t", version="1", name="T", uri="u", types=["galaxy"]),
        input=LaunchInput(),
    )
    assert req.tool is not None
    assert req.input is not None
    assert req.runtime_platform is None  # default: infer from vre_type


# ---------------------------------------------------------------------------
# resolve_vre_type — the three-layer resolution in §3.
# ---------------------------------------------------------------------------

def test_resolve_vre_type_from_raw_definition_override():
    from vre_rocrate import ToolMeta
    from vre_rocrate.constants import resolve_vre_type

    t = ToolMeta(id="t", version="1", name="T", uri="u", types=["unknown"],
                 raw_definition={"vre_type": "galaxy"})
    assert resolve_vre_type(t) == "galaxy"


def test_resolve_vre_type_from_tool_types():
    from vre_rocrate import ToolMeta
    from vre_rocrate.constants import resolve_vre_type

    cases = {
        "galaxy_workflow": "galaxy",
        "vip": "vip",
        "boutique": "vip",
        "sciencemesh": "sciencemesh",
        "binder-launcher": "binder",
        "rrp": "rrp",
    }
    for ttype, expected in cases.items():
        t = ToolMeta(id="t", version="1", name="T", uri="u", types=[ttype])
        assert resolve_vre_type(t) == expected, f"{ttype} -> {expected}"


def test_resolve_vre_type_falls_back_to_uri():
    from vre_rocrate import ToolMeta
    from vre_rocrate.constants import resolve_vre_type

    t = ToolMeta(id="t", version="1", name="T",
                 uri="https://usegalaxy.eu/workflows/abc", types=[])
    assert resolve_vre_type(t) == "galaxy"


def test_resolve_vre_type_raises_when_unresolvable():
    from vre_rocrate import ToolMeta
    from vre_rocrate.constants import resolve_vre_type

    t = ToolMeta(id="t", version="1", name="T", uri="https://example.org/x", types=[])
    with pytest.raises(ValueError):
        resolve_vre_type(t)


# ---------------------------------------------------------------------------
# Slots vs Files — the core semantic distinction (plan §2).
# Slots produce FormalParameter entities; free-form files do not.
# ---------------------------------------------------------------------------

def _galaxy_request(slots=None, files=None, dataset=None, runtime_platform=None):
    """Build a minimal galaxy VRELaunchRequest for crate-building tests."""
    from vre_rocrate import (
        VRELaunchRequest, ToolMeta, LaunchInput, SlotDefinition,
    )

    tool = ToolMeta(
        id="galaxy-test",
        version="1",
        name="Galaxy Test",
        uri="https://example.org/wf.ga",
        types=["galaxy_workflow"],
        slots=slots or [],
    )
    return VRELaunchRequest(
        tool=tool,
        input=LaunchInput(dataset=dataset, slots=slots and {} or {}, files=files or {}),
        runtime_platform=runtime_platform,
    )


def test_slots_produce_formal_parameters_named_by_slot_id():
    """input.slots entries must produce #input-<slot.id> FormalParameters."""
    from vre_rocrate import (
        VRELaunchRequest, ToolMeta, LaunchInput, SlotDefinition,
        SlotValue, FileInput, RocrateBuilder,
    )

    req = VRELaunchRequest(
        tool=ToolMeta(
            id="t", version="1", name="T", uri="https://example.org/w.ga",
            types=["galaxy_workflow"],
            slots=[SlotDefinition(id="param_file", name="param_file", slot_type="file")],
        ),
        input=LaunchInput(slots={
            "param_file": SlotValue(file=FileInput(name="param_file",
                                                    url="https://example.org/p.txt")),
        }),
    )
    crate = RocrateBuilder.build_from_launch_request(req)
    ids = {e["@id"] for e in crate["@graph"]}
    assert "#input-param_file" in ids


def test_free_form_files_do_not_produce_formal_parameters():
    """input.files entries must NOT produce FormalParameter entities."""
    from vre_rocrate import (
        VRELaunchRequest, ToolMeta, LaunchInput, FileInput, RocrateBuilder,
    )

    req = VRELaunchRequest(
        tool=ToolMeta(id="t", version="1", name="T", uri="https://example.org/nb.ipynb",
                      types=["binder"]),
        input=LaunchInput(files={
            "data.csv": FileInput(name="data.csv", url="https://example.org/data.csv"),
        }),
    )
    crate = RocrateBuilder.build_from_launch_request(req)
    formal_params = [e for e in crate["@graph"] if e.get("@type") == "FormalParameter"]
    assert formal_params == []


def test_slot_value_literal_becomes_default_value_literal():
    """SlotValue::Value must produce a literal defaultValue on the FormalParameter."""
    from vre_rocrate import (
        VRELaunchRequest, ToolMeta, LaunchInput, SlotDefinition,
        SlotValue, RocrateBuilder,
    )

    req = VRELaunchRequest(
        tool=ToolMeta(id="t", version="1", name="T", uri="https://example.org/w",
                      types=["sciencemesh"],
                      slots=[SlotDefinition(id="Shared With", name="Shared With",
                                            slot_type="string")]),
        input=LaunchInput(slots={"Shared With": SlotValue(value="user@e.org")}),
    )
    crate = RocrateBuilder.build_from_launch_request(req)
    fp = next(e for e in crate["@graph"] if e.get("@id") == "#input-Shared With")
    assert fp["defaultValue"] == "user@e.org"


def test_slot_value_file_becomes_default_value_id_ref():
    """SlotValue::File must produce defaultValue: {"@id": file.url}."""
    from vre_rocrate import (
        VRELaunchRequest, ToolMeta, LaunchInput, SlotDefinition,
        SlotValue, FileInput, RocrateBuilder,
    )

    req = VRELaunchRequest(
        tool=ToolMeta(id="t", version="1", name="T", uri="https://example.org/w.ga",
                      types=["galaxy_workflow"],
                      slots=[SlotDefinition(id="f", name="f", slot_type="file")]),
        input=LaunchInput(slots={
            "f": SlotValue(file=FileInput(name="f", url="https://example.org/f.txt")),
        }),
    )
    crate = RocrateBuilder.build_from_launch_request(req)
    fp = next(e for e in crate["@graph"] if e.get("@id") == "#input-f")
    assert fp["defaultValue"] == {"@id": "https://example.org/f.txt"}


def test_free_form_file_appears_as_standalone_file_entity():
    """input.files entries must appear as standalone File entities in @graph."""
    from vre_rocrate import (
        VRELaunchRequest, ToolMeta, LaunchInput, FileInput, RocrateBuilder,
    )

    req = VRELaunchRequest(
        tool=ToolMeta(id="t", version="1", name="T", uri="https://example.org/nb.ipynb",
                      types=["binder"]),
        input=LaunchInput(files={
            "data.csv": FileInput(name="data.csv", url="https://example.org/data.csv"),
        }),
    )
    crate = RocrateBuilder.build_from_launch_request(req)
    file_entity = next(e for e in crate["@graph"]
                       if e.get("@id") == "https://example.org/data.csv")
    assert file_entity["@type"] == "File"


# ---------------------------------------------------------------------------
# runtimePlatform — always present, resolved or overridden (plan §3, §7).
# ---------------------------------------------------------------------------

def test_runtime_platform_inferred_when_not_set():
    """When runtime_platform is None, the builder emits the vre_type default."""
    from vre_rocrate import (
        VRELaunchRequest, ToolMeta, LaunchInput, RocrateBuilder,
    )
    from vre_rocrate.constants import VRE_TYPE_TO_DEFAULT_RUNTIME_PLATFORM

    req = VRELaunchRequest(
        tool=ToolMeta(id="t", version="1", name="T", uri="https://example.org/w.ga",
                      types=["galaxy_workflow"]),
        input=LaunchInput(),
    )
    crate = RocrateBuilder.build_from_launch_request(req)
    wf = next(e for e in crate["@graph"]
              if e.get("@id") == "https://example.org/w.ga")
    assert wf["runtimePlatform"] == VRE_TYPE_TO_DEFAULT_RUNTIME_PLATFORM["galaxy"]


def test_runtime_platform_override_used_directly():
    from vre_rocrate import (
        VRELaunchRequest, ToolMeta, LaunchInput, RocrateBuilder,
    )

    req = VRELaunchRequest(
        tool=ToolMeta(id="t", version="1", name="T", uri="https://example.org/w.ga",
                      types=["galaxy_workflow"]),
        input=LaunchInput(),
        runtime_platform="https://custom-galaxy.example.org/",
    )
    crate = RocrateBuilder.build_from_launch_request(req)
    wf = next(e for e in crate["@graph"]
              if e.get("@id") == "https://example.org/w.ga")
    assert wf["runtimePlatform"] == "https://custom-galaxy.example.org/"


# ---------------------------------------------------------------------------
# Dataset entity — only when input.dataset is provided (plan §4).
# ---------------------------------------------------------------------------

def test_dataset_entity_present_when_dataset_provided():
    from vre_rocrate import (
        VRELaunchRequest, ToolMeta, LaunchInput, DatasetHandle, RocrateBuilder,
    )

    req = VRELaunchRequest(
        tool=ToolMeta(id="t", version="1", name="T", uri="https://example.org/w.ga",
                      types=["galaxy_workflow"]),
        input=LaunchInput(dataset=DatasetHandle(
            url="https://example.org/dataset", title="DS", description="A dataset",
        )),
    )
    crate = RocrateBuilder.build_from_launch_request(req)
    ds = next(e for e in crate["@graph"]
              if e.get("@id") == "https://example.org/dataset")
    assert ds["@type"] == "Dataset"
    assert ds["name"] == "DS"


def test_no_dataset_entity_when_dataset_none():
    from vre_rocrate import (
        VRELaunchRequest, ToolMeta, LaunchInput, RocrateBuilder,
    )

    req = VRELaunchRequest(
        tool=ToolMeta(id="t", version="1", name="T", uri="https://example.org/w.ga",
                      types=["galaxy_workflow"]),
        input=LaunchInput(dataset=None),
    )
    crate = RocrateBuilder.build_from_launch_request(req)
    datasets = [e for e in crate["@graph"]
                if e.get("@type") == "Dataset" and e.get("@id") != "./"]
    assert datasets == []


# ---------------------------------------------------------------------------
# #tool-metadata entity (plan §4).
# ---------------------------------------------------------------------------

def test_tool_metadata_entity_carries_raw_definition():
    from vre_rocrate import (
        VRELaunchRequest, ToolMeta, LaunchInput, RocrateBuilder,
    )

    raw = {"custom": "value", "nested": {"a": 1}}
    req = VRELaunchRequest(
        tool=ToolMeta(id="t", version="1", name="T", uri="https://example.org/w.ga",
                      types=["galaxy_workflow"], raw_definition=raw),
        input=LaunchInput(),
    )
    crate = RocrateBuilder.build_from_launch_request(req)
    tm = next(e for e in crate["@graph"] if e.get("@id") == "#tool-metadata")
    assert tm["rawDefinition"] == raw


# ---------------------------------------------------------------------------
# Round-trip: build_from_launch_request -> RequestPackageBuilder.build.
# The crate must still be parseable into a RequestPackage.
# ---------------------------------------------------------------------------

def test_roundtrip_galaxy_slots():
    from vre_rocrate import (
        VRELaunchRequest, ToolMeta, LaunchInput, SlotDefinition,
        SlotValue, FileInput, RocrateBuilder, RequestPackageBuilder,
    )

    req = VRELaunchRequest(
        tool=ToolMeta(
            id="galaxy-rt", version="1", name="Galaxy RT",
            uri="https://example.org/rt.ga", types=["galaxy_workflow"],
            slots=[SlotDefinition(id="param_file", name="param_file", slot_type="file")],
        ),
        input=LaunchInput(slots={
            "param_file": SlotValue(file=FileInput(
                name="param_file", url="https://example.org/p.txt",
                mime_type="text/plain",
            )),
        }),
    )
    crate = RocrateBuilder.build_from_launch_request(req)
    package = RequestPackageBuilder.build(crate)
    assert package.workflow.id == "https://example.org/rt.ga"
    # Slot-bound file must be in the package's files.
    assert any(f.id == "https://example.org/p.txt" for f in package.files)


def test_roundtrip_binder_free_form_files():
    from vre_rocrate import (
        VRELaunchRequest, ToolMeta, LaunchInput, FileInput,
        RocrateBuilder, RequestPackageBuilder,
    )

    req = VRELaunchRequest(
        tool=ToolMeta(id="b-rt", version="1", name="Binder RT",
                      uri="https://example.org/nb.ipynb", types=["binder"]),
        input=LaunchInput(files={
            "data.csv": FileInput(name="data.csv",
                                  url="https://example.org/data.csv",
                                  mime_type="text/csv"),
        }),
    )
    crate = RocrateBuilder.build_from_launch_request(req)
    package = RequestPackageBuilder.build(crate)
    assert any(f.id == "https://example.org/data.csv" for f in package.files)


def test_roundtrip_raw_definition_preserved():
    from vre_rocrate import (
        VRELaunchRequest, ToolMeta, LaunchInput, RocrateBuilder, RequestPackageBuilder,
    )

    raw = {"k": "v"}
    req = VRELaunchRequest(
        tool=ToolMeta(id="t", version="1", name="T", uri="https://example.org/w.ga",
                      types=["galaxy_workflow"], raw_definition=raw),
        input=LaunchInput(),
    )
    crate = RocrateBuilder.build_from_launch_request(req)
    package = RequestPackageBuilder.build(crate)
    assert package.raw_definition == raw


def test_roundtrip_workflow_version():
    from vre_rocrate import (
        VRELaunchRequest, ToolMeta, LaunchInput, RocrateBuilder, RequestPackageBuilder,
    )

    req = VRELaunchRequest(
        tool=ToolMeta(id="t", version="2.3.1", name="T",
                      uri="https://example.org/w.ga", types=["galaxy_workflow"]),
        input=LaunchInput(),
    )
    crate = RocrateBuilder.build_from_launch_request(req)
    package = RequestPackageBuilder.build(crate)
    assert package.workflow.tool_version == "2.3.1"


# ---------------------------------------------------------------------------
# RequestPackage stays additive — existing fields unchanged (plan §5).
# ---------------------------------------------------------------------------

def test_request_package_existing_fields_unchanged():
    """All pre-existing RequestPackage fields must still be present."""
    from vre_rocrate import RequestPackage

    import dataclasses
    field_names = {f.name for f in dataclasses.fields(RequestPackage)}
    expected = {
        "vre_type", "programming_language", "workflow", "files",
        "workflow_inputs", "workflow_outputs", "raw_crate", "ocm_data",
        "raw_definition",  # NEW — additive
    }
    assert expected.issubset(field_names), f"missing: {expected - field_names}"


def test_request_package_raw_definition_is_new_and_optional():
    from vre_rocrate import RequestPackage

    import dataclasses
    fields = {f.name: f for f in dataclasses.fields(RequestPackage)}
    assert "raw_definition" in fields
    # Must have a default (additive, not breaking existing construction).
    assert fields["raw_definition"].default is not None or \
           fields["raw_definition"].default_factory is not None


def test_workflow_descriptor_tool_version_is_new_and_optional():
    from vre_rocrate import WorkflowDescriptor

    import dataclasses
    fields = {f.name: f for f in dataclasses.fields(WorkflowDescriptor)}
    assert "tool_version" in fields
    assert fields["tool_version"].default is None


# ---------------------------------------------------------------------------
# input_files property behavior under the new crate format (plan §6).
# Plan assumption: slots produce FormalParameters; files-only does not.
# ---------------------------------------------------------------------------

def test_input_files_returns_slot_files_when_slots_present():
    from vre_rocrate import (
        VRELaunchRequest, ToolMeta, LaunchInput, SlotDefinition,
        SlotValue, FileInput, RocrateBuilder, RequestPackageBuilder,
    )

    req = VRELaunchRequest(
        tool=ToolMeta(id="t", version="1", name="T", uri="https://example.org/w.ga",
                      types=["galaxy_workflow"],
                      slots=[SlotDefinition(id="f", name="f", slot_type="file")]),
        input=LaunchInput(slots={
            "f": SlotValue(file=FileInput(name="f", url="https://example.org/f.txt")),
        }),
    )
    crate = RocrateBuilder.build_from_launch_request(req)
    package = RequestPackageBuilder.build(crate)
    input_ids = {f.id for f in package.input_files}
    assert "https://example.org/f.txt" in input_ids


def test_input_files_returns_all_files_when_no_slots():
    from vre_rocrate import (
        VRELaunchRequest, ToolMeta, LaunchInput, FileInput,
        RocrateBuilder, RequestPackageBuilder,
    )

    req = VRELaunchRequest(
        tool=ToolMeta(id="t", version="1", name="T", uri="https://example.org/nb.ipynb",
                      types=["binder"]),
        input=LaunchInput(files={
            "a.csv": FileInput(name="a.csv", url="https://example.org/a.csv"),
            "b.csv": FileInput(name="b.csv", url="https://example.org/b.csv"),
        }),
    )
    crate = RocrateBuilder.build_from_launch_request(req)
    package = RequestPackageBuilder.build(crate)
    input_ids = {f.id for f in package.input_files}
    assert input_ids == {"https://example.org/a.csv", "https://example.org/b.csv"}


def test_input_files_with_slots_and_free_form_files_returns_slot_files_only():
    """When both slots and free-form files exist, input_files returns slot files only.

    This is the load-bearing assumption from plan §6: no current VRE handler
    that uses input_files also has free-form files, so the property returns
    slot-referenced files only.
    """
    from vre_rocrate import (
        VRELaunchRequest, ToolMeta, LaunchInput, SlotDefinition,
        SlotValue, FileInput, RocrateBuilder, RequestPackageBuilder,
    )

    req = VRELaunchRequest(
        tool=ToolMeta(id="t", version="1", name="T", uri="https://example.org/w.ga",
                      types=["galaxy_workflow"],
                      slots=[SlotDefinition(id="slot_file", name="slot_file",
                                            slot_type="file")]),
        input=LaunchInput(
            slots={
                "slot_file": SlotValue(file=FileInput(
                    name="slot_file", url="https://example.org/slot.txt",
                )),
            },
            files={
                "free.csv": FileInput(name="free.csv",
                                      url="https://example.org/free.csv"),
            },
        ),
    )
    crate = RocrateBuilder.build_from_launch_request(req)
    package = RequestPackageBuilder.build(crate)
    input_ids = {f.id for f in package.input_files}
    assert "https://example.org/slot.txt" in input_ids
    # Free-form file must NOT appear in input_files (it's in package.files but not
    # referenced by any FormalParameter).
    assert "https://example.org/free.csv" not in input_ids
    # But it must still be in package.files.
    all_ids = {f.id for f in package.files}
    assert "https://example.org/free.csv" in all_ids


# ---------------------------------------------------------------------------
# Validation — the new crate must pass ValidationPipeline (plan §6).
# ---------------------------------------------------------------------------

def test_built_crate_passes_validation():
    from vre_rocrate import (
        VRELaunchRequest, ToolMeta, LaunchInput, SlotDefinition,
        SlotValue, FileInput, RocrateBuilder, ValidationPipeline,
    )

    req = VRELaunchRequest(
        tool=ToolMeta(id="t", version="1", name="T", uri="https://example.org/w.ga",
                      types=["galaxy_workflow"],
                      slots=[SlotDefinition(id="f", name="f", slot_type="file")]),
        input=LaunchInput(slots={
            "f": SlotValue(file=FileInput(name="f", url="https://example.org/f.txt")),
        }),
    )
    crate = RocrateBuilder.build_from_launch_request(req)
    # Must not raise.
    ValidationPipeline.validate_basic(crate)
