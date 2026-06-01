"""Tests for MinimalVRERequest validation and RequestPackageBuilder.build_from_minimal()."""

import pytest

from vre_rocrate import (
    MinimalVRERequest,
    MinimalFileInput,
    RequestPackageBuilder,
    GALAXY_PROGRAMMING_LANGUAGE,
    OSCAR_PROGRAMMING_LANGUAGE,
    SCIPION_PROGRAMMING_LANGUAGE,
    BINDER_PROGRAMMING_LANGUAGE,
    JUPYTER_PROGRAMMING_LANGUAGE,
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


class TestRequestPackageFromMinimal:
    """Building a RequestPackage from minimal VRE payload data via RequestPackageBuilder."""

    def test_galaxy_package(self):
        request = MinimalVRERequest(
            vre_type="galaxy",
            workflow="https://dockstore.org/api/ga4gh/trs/v2/tools/test",
            files=[
                MinimalFileInput(
                    name="sample.fastq",
                    url="https://data.example.org/sample.fastq",
                    encoding_format="application/fastq",
                )
            ],
        )
        package = RequestPackageBuilder.build_from_minimal(request, file_bytes_map={})

        assert package.programming_language == GALAXY_PROGRAMMING_LANGUAGE
        assert (
            package.workflow.url == "https://dockstore.org/api/ga4gh/trs/v2/tools/test"
        )
        assert len(package.files) == 1
        assert package.files[0].name == "sample.fastq"
        assert package.files[0].url == "https://data.example.org/sample.fastq"

    def test_oscar_package(self):
        request = MinimalVRERequest(
            vre_type="oscar",
            workflow="https://raw.githubusercontent.com/example/fdl.json",
        )
        package = RequestPackageBuilder.build_from_minimal(request, file_bytes_map={})

        assert package.programming_language == OSCAR_PROGRAMMING_LANGUAGE
        assert (
            package.workflow.url == "https://raw.githubusercontent.com/example/fdl.json"
        )
        assert len(package.files) == 0

    def test_scipion_package(self):
        request = MinimalVRERequest(
            vre_type="scipion",
            workflow="workflow.json",
            files=[MinimalFileInput(name="workflow.json")],
        )
        package = RequestPackageBuilder.build_from_minimal(request, file_bytes_map={})

        assert package.programming_language == SCIPION_PROGRAMMING_LANGUAGE
        assert package.workflow.url == "workflow.json"

    def test_binder_package_with_uploaded_files(self):
        request = MinimalVRERequest(
            vre_type="binder",
            workflow="notebook.ipynb",
            files=[
                MinimalFileInput(name="notebook.ipynb"),
                MinimalFileInput(name="requirements.txt"),
            ],
        )
        package = RequestPackageBuilder.build_from_minimal(
            request,
            file_bytes_map={
                "notebook.ipynb": b'{"cells": []}',
                "requirements.txt": b"numpy==1.21.0",
            },
        )

        assert package.programming_language == BINDER_PROGRAMMING_LANGUAGE
        assert len(package.files) == 2
        assert package.files[0].properties["content"] == b'{"cells": []}'
        assert package.files[1].properties["content"] == b"numpy==1.21.0"

    def test_jupyter_package_with_uploaded_notebook(self):
        request = MinimalVRERequest(
            vre_type="jupyter",
            workflow="notebook.ipynb",
            files=[MinimalFileInput(name="notebook.ipynb")],
        )
        package = RequestPackageBuilder.build_from_minimal(
            request,
            file_bytes_map={"notebook.ipynb": b'{"cells": []}'},
        )

        assert package.programming_language == JUPYTER_PROGRAMMING_LANGUAGE
        assert len(package.files) == 1
        assert package.files[0].properties["content"] == b'{"cells": []}'

    def test_runtime_platform_override(self):
        request = MinimalVRERequest(
            vre_type="galaxy",
            workflow="https://example.com/workflow.ga",
            runtime_platform="https://custom-galaxy.example.org/",
        )
        package = RequestPackageBuilder.build_from_minimal(request, file_bytes_map={})

        assert package.workflow.runtime_platform == "https://custom-galaxy.example.org/"

    def test_onedata_file(self):
        request = MinimalVRERequest(
            vre_type="galaxy",
            workflow="https://example.com/workflow.ga",
            files=[
                MinimalFileInput(
                    name="onedata_file",
                    encoding_format="image/tiff",
                    onedata_domain="demo.onedata.org",
                    onedata_file_id="00000000007EADF37368",
                )
            ],
        )
        package = RequestPackageBuilder.build_from_minimal(request, file_bytes_map={})

        assert package.files[0].onedata_domain == "demo.onedata.org"
        assert package.files[0].onedata_file_id == "00000000007EADF37368"
