"""Tests for MinimalVRERequest validation."""

import pytest

from vre_rocrate import (
    MinimalVRERequest,
    MinimalFileInput,
)

VALID_REQUEST_CASES = [
    ("galaxy", "https://dockstore.org/api/ga4gh/trs/v2/tools/test", None),
    ("oscar", "https://raw.githubusercontent.com/example/fdl.json", None),
    ("scipion", "workflow.json", [MinimalFileInput(name="workflow.json")]),
    ("binder", "notebook.ipynb", [MinimalFileInput(name="notebook.ipynb")]),
    ("jupyter", "notebook.ipynb", [MinimalFileInput(name="notebook.ipynb")]),
]

MISSING_WORKFLOW_CASES = ["galaxy", "oscar", "scipion", "binder", "jupyter"]


class TestMinimalVRERequest:
    """Validation of the MinimalVRERequest dataclass."""

    @pytest.mark.parametrize("vre_type,workflow,files", VALID_REQUEST_CASES)
    def test_valid_request(self, vre_type, workflow, files):
        kwargs = {"vre_type": vre_type, "workflow": workflow}
        if files is not None:
            kwargs["files"] = files
        req = MinimalVRERequest(**kwargs)
        assert req.vre_type == vre_type
        assert req.workflow == workflow

    @pytest.mark.parametrize("vre_type", MISSING_WORKFLOW_CASES)
    def test_missing_workflow_raises(self, vre_type):
        with pytest.raises(ValueError, match="workflow is required"):
            MinimalVRERequest(vre_type=vre_type)

    def test_unknown_vre_type_raises(self):
        with pytest.raises(ValueError):
            MinimalVRERequest(vre_type="unknown")

    def test_with_files(self):
        req = MinimalVRERequest(
            vre_type="galaxy",
            workflow="https://example.com/workflow.ga",
            files=[
                MinimalFileInput(
                    name="sample.fastq",
                    url="https://data.example.org/sample.fastq",
                    encoding_format="application/fastq",
                )
            ],
        )
        assert len(req.files) == 1
        assert req.files[0].name == "sample.fastq"

    def test_with_runtime_platform_override(self):
        req = MinimalVRERequest(
            vre_type="galaxy",
            workflow="https://example.com/workflow.ga",
            runtime_platform="https://custom-galaxy.example.org/",
        )
        assert req.runtime_platform == "https://custom-galaxy.example.org/"
