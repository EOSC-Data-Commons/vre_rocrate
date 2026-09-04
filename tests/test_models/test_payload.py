"""Tests for VREPayload model helpers and serialization."""

import pytest

from vre_rocrate import (
    VREPayloadBuilder,
    VREPayload,
    WorkflowDescriptor,
    FileReference,
    FormalParameter,
)
from conftest import load_json

SERIALIZATION_CASES = [
    "galaxy/ro-crate-metadata.json",
    "oscar/ro-crate-metadata.json",
    "simple-binder/ro-crate-metadata.json",
]


class TestVREPayloadSerialization:
    """Round-trip tests for VREPayload.to_dict() / from_dict()."""

    @pytest.mark.parametrize("fixture_path", SERIALIZATION_CASES)
    def test_to_dict_and_from_dict_roundtrip(self, fixtures_dir, fixture_path):
        source = load_json(fixtures_dir, fixture_path)
        package = VREPayloadBuilder.build(source)
        d = package.to_dict()
        restored = VREPayload.from_dict(d)
        assert restored.vre_type == package.vre_type
        assert restored.workflow_url == package.workflow_url
        assert len(restored.files) == len(package.files)
        if package.files:
            assert restored.files[0].name == package.files[0].name


class TestVREPayloadHelpers:
    """Tests for VREPayload helper properties and methods."""

    def test_local_vs_remote_files(self, fixtures_dir):
        source = load_json(fixtures_dir, "galaxy/ro-crate-metadata.json")
        package = VREPayloadBuilder.build(source)
        assert len(package.local_files) == 0
        assert len(package.remote_files) == 2

    def test_files_by_encoding_no_match(self, fixtures_dir):
        source = load_json(fixtures_dir, "galaxy/ro-crate-metadata.json")
        package = VREPayloadBuilder.build(source)
        result = package.files_by_encoding("application/octet-stream")
        assert result == []

    def test_file_by_id(self, fixtures_dir):
        source = load_json(fixtures_dir, "galaxy/ro-crate-metadata.json")
        package = VREPayloadBuilder.build(source)
        f = package.file_by_id(
            "https://example-files.online-convert.com/document/txt/example.txt"
        )
        assert f is not None
        assert f.name == "simpletext_input"

    def test_file_by_id_not_found(self, fixtures_dir):
        source = load_json(fixtures_dir, "galaxy/ro-crate-metadata.json")
        package = VREPayloadBuilder.build(source)
        f = package.file_by_id("https://nonexistent.example.com/file.txt")
        assert f is None

    def test_workflow_inputs_outputs(self, fixtures_dir):
        source = load_json(fixtures_dir, "galaxy/ro-crate-metadata.json")
        package = VREPayloadBuilder.build(source)
        assert len(package.workflow_inputs) == 1
        assert package.workflow_inputs[0].name == "simpletext_input"
        assert len(package.workflow_outputs) == 1
        assert package.workflow_outputs[0].name == "reversed_text"

    def test_root_metadata(self, fixtures_dir):
        source = load_json(fixtures_dir, "galaxy/ro-crate-metadata.json")
        package = VREPayloadBuilder.build(source)
        assert package.root_name == "Galaxy Example Workflow"
        assert "example of a workflow" in package.root_description

    def test_mixed_local_remote_files(self, fixtures_dir):
        """Verify local_files and remote_files partition correctly with mixed data."""
        source = load_json(fixtures_dir, "oscar/ro-crate-metadata.json")
        package = VREPayloadBuilder.build(source)
        assert len(package.local_files) >= 0
        assert len(package.remote_files) >= 0
        assert len(package.local_files) + len(package.remote_files) == len(
            package.files
        )

    def test_input_files_filters_by_workflow_inputs(self, fixtures_dir):
        """input_files returns only files whose @id matches a workflow input."""
        source = load_json(fixtures_dir, "galaxy/ro-crate-metadata.json")
        package = VREPayloadBuilder.build(source)
        # Galaxy fixture has input referencing the file entity directly
        assert len(package.workflow_inputs) == 1
        assert package.workflow_inputs[0].name == "simpletext_input"
        # input_files should only contain the file referenced by input
        assert len(package.input_files) == 1
        assert package.input_files[0].name == "simpletext_input"

    def test_input_files_falls_back_to_all_files(self, fixtures_dir):
        """input_files returns all data files when no workflow_inputs are declared."""
        source = load_json(fixtures_dir, "oscar/ro-crate-metadata.json")
        package = VREPayloadBuilder.build(source)
        # OSCAR fixture has no input parameter
        assert len(package.workflow_inputs) == 0
        # all files except the workflow descriptor itself
        assert {f.id for f in package.input_files} == {
            f.id for f in package.files if f.id != package.workflow.id
        }

    def test_input_files_vip_slot_files_only(self, fixtures_dir):
        """input_files returns the slot-bound input files, never the workflow descriptor."""
        source = load_json(fixtures_dir, "vip/ro-crate-metadata.json")
        package = VREPayloadBuilder.build(source)
        assert len(package.workflow_inputs) == 3
        assert len(package.input_files) == 3
        assert package.workflow.id not in {f.id for f in package.input_files}
        assert {f.name for f in package.input_files} == {
            "parameter_file",
            "data_file",
            "zipped_folder",
        }


# ---------------------------------------------------------------------------
# Input bindings accessors — name → file / scalar mapping
# ---------------------------------------------------------------------------


def _payload(inputs, files):
    return VREPayload(
        vre_type="http://example.org/vre",
        programming_language="http://example.org/vre",
        workflow=WorkflowDescriptor(id="https://example.org/wf", type="File"),
        files=files,
        workflow_inputs=inputs,
    )


class TestInputBindings:
    """Binding accessors resolve input params to files or literal values."""

    def test_file_slot_binds_file_and_not_literal(self):
        file = FileReference(id="https://example.org/p.txt",
                             name="p.txt",
                             url="https://example.org/p.txt")
        pkg = _payload(
            [FormalParameter(id="#input-input_file", name="input_file",
                             default_value={"@id": file.id})],
            [file],
        )
        assert pkg.input_file_bindings() == [("input_file", file)]
        assert pkg.input_literal_bindings() == []

    def test_literal_slot_binds_scalar_and_not_file(self):
        pkg = _payload(
            [FormalParameter(id="#input-pdb_id", name="pdb_id",
                             default_value="1L2Y")],
            [],
        )
        assert pkg.input_file_bindings() == []
        assert pkg.input_literal_bindings() == [("pdb_id", "1L2Y")]

    def test_dangling_ref_dropped_from_bindings(self):
        """A slot bound to a file @id absent from files produces no binding in
        any accessor: not file-bound (dangling ref), not literal-bound
        (dict-shaped default), hence absent from the combined view."""
        pkg = _payload(
            [FormalParameter(id="#input-input_file", name="input_file",
                             default_value={"@id": "https://example.org/missing"})],
            [],
        )
        assert pkg.input_file_bindings() == []
        assert pkg.input_literal_bindings() == []

    def test_valueless_param_omitted_from_bindings(self):
        """A declared input without defaultValue produces no binding in any
        accessor: not file-bound, not literal-bound (no scalar value), hence
        absent from the combined view."""
        pkg = _payload([FormalParameter(id="#input-input_file", name="input_file")], [])
        assert pkg.input_file_bindings() == []
        assert pkg.input_literal_bindings() == []

    def test_input_value_bindings_mixes_files_and_literals(self):
        file = FileReference(id="https://example.org/p.txt",
                             name="p.txt",
                             url="https://example.org/p.txt")
        pkg = _payload(
            [
                FormalParameter(id="#input-input_file", name="input_file",
                                default_value={"@id": file.id}),
                FormalParameter(id="#input-mode", name="mode",
                                default_value="qual"),
            ],
            [file],
        )
        pairs = dict(pkg.input_value_bindings())
        assert pairs["input_file"] is file   # FileReference for the file-bound slot
        assert pairs["mode"] == "qual"       # scalar passthrough for the literal slot

    def test_string_literal_matching_file_id_is_file_bound(self):
        """A string default colliding with a file @id is file-bound, not literal.

        Literals can be promoted by in-crate files: a pdb_id-style scalar is
        kept literal only because no file entity carries that @id. If one does,
        the input binds the file. The disjointness guard in
        input_literal_bindings exists for exactly this case.
        """
        file = FileReference(id="1L2Y", name="1L2Y", url="1L2Y")
        pkg = _payload(
            [FormalParameter(id="#input-pdb_id", name="pdb_id",
                             default_value="1L2Y")],
            [file],
        )
        assert [name for name, _ in pkg.input_file_bindings()] == ["pdb_id"]
        assert "pdb_id" not in [name for name, _ in pkg.input_literal_bindings()]
