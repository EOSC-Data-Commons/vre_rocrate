"""Tests for RocrateBuilder.build_from_minimal()."""

from vre_rocrate import (
    MinimalVRERequest,
    MinimalFileInput,
    RocrateBuilder,
    RequestPackageBuilder,
    GALAXY_PROGRAMMING_LANGUAGE,
    OSCAR_PROGRAMMING_LANGUAGE,
    SCIPION_PROGRAMMING_LANGUAGE,
    SCIENCEMESH_PROGRAMMING_LANGUAGE,
)


def _entity_by_id(graph: list[dict], eid: str) -> dict:
    """Return the first entity in *graph* whose ``@id`` matches *eid*."""
    return next(e for e in graph if e.get("@id") == eid)


class TestRocrateBuilder:
    """Tests for RocrateBuilder.build_from_minimal()."""

    def test_galaxy_rocrate_structure(self):
        """Verify a galaxy minimal request produces a valid ROCrate structure."""
        workflow_url = "https://dockstore.org/api/ga4gh/trs/v2/tools/test"
        request = MinimalVRERequest(
            vre_type="galaxy",
            workflow=workflow_url,
            files=[
                MinimalFileInput(
                    name="sample.fastq",
                    url="https://data.example.org/sample.fastq",
                    encoding_format="application/fastq",
                )
            ],
        )
        crate = RocrateBuilder.build_from_minimal(request)

        assert crate["@context"] == "https://w3id.org/ro/crate/1.1/context"
        assert isinstance(crate["@graph"], list)

        graph = crate["@graph"]

        root = _entity_by_id(graph, "./")
        assert root["@type"] == "Dataset"
        assert root["mainEntity"] == {"@id": workflow_url}

        workflow = _entity_by_id(graph, workflow_url)
        assert "ComputationalWorkflow" in workflow["@type"]
        assert workflow["programmingLanguage"] == {"@id": "#galaxy-lang"}

        lang = _entity_by_id(graph, "#galaxy-lang")
        assert lang["@type"] == "ComputerLanguage"
        assert lang["identifier"] == GALAXY_PROGRAMMING_LANGUAGE

        file_entity = _entity_by_id(graph, "https://data.example.org/sample.fastq")
        assert file_entity["@type"] == "File"
        assert file_entity["name"] == "sample.fastq"
        assert file_entity["encodingFormat"] == "application/fastq"

    def test_oscar_rocrate_structure(self):
        """Verify an oscar minimal request produces a valid ROCrate structure."""
        workflow_url = "https://raw.githubusercontent.com/example/fdl.json"
        request = MinimalVRERequest(
            vre_type="oscar",
            workflow=workflow_url,
            files=[
                MinimalFileInput(
                    name="script.sh",
                    url="https://raw.githubusercontent.com/grycap/oscar/master/examples/cowsay/script.sh",
                    encoding_format="text/x-shellscript",
                )
            ],
        )
        crate = RocrateBuilder.build_from_minimal(request)

        graph = crate["@graph"]

        lang = _entity_by_id(graph, "#oscar-lang")
        assert lang["identifier"] == OSCAR_PROGRAMMING_LANGUAGE

        workflow = _entity_by_id(graph, workflow_url)
        assert "ComputationalWorkflow" in workflow["@type"]

    def test_scipion_rocrate_no_workflow(self):
        """Verify a scipion request with a local workflow file produces valid ROCrate."""
        request = MinimalVRERequest(
            vre_type="scipion",
            workflow="workflow.json",
            files=[MinimalFileInput(name="workflow.json")],
        )
        crate = RocrateBuilder.build_from_minimal(request)

        graph = crate["@graph"]
        lang = _entity_by_id(graph, "#scipion-lang")
        assert lang["identifier"] == SCIPION_PROGRAMMING_LANGUAGE

        workflow = _entity_by_id(graph, "workflow.json")
        assert "ComputationalWorkflow" in workflow["@type"]

    def test_runtime_platform_override(self):
        """Verify runtime_platform override appears in the ROCrate."""
        workflow_url = "https://example.com/workflow.ga"
        request = MinimalVRERequest(
            vre_type="galaxy",
            workflow=workflow_url,
            runtime_platform="https://custom-galaxy.example.org/",
        )
        crate = RocrateBuilder.build_from_minimal(request)

        workflow = _entity_by_id(crate["@graph"], workflow_url)
        assert workflow["runtimePlatform"] == "https://custom-galaxy.example.org/"

    def test_onedata_file_in_rocrate(self):
        """Verify onedata file attributes appear in the ROCrate."""
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
        crate = RocrateBuilder.build_from_minimal(request)

        file_entity = _entity_by_id(crate["@graph"], "onedata_file")
        assert file_entity["onedata:onezoneDomain"] == "demo.onedata.org"
        assert file_entity["onedata:fileId"] == "00000000007EADF37368"

    def test_rocrate_has_required_entities(self):
        """Verify the generated ROCrate contains all required supporting entities."""
        request = MinimalVRERequest(
            vre_type="binder",
            workflow="notebook.ipynb",
            files=[MinimalFileInput(name="notebook.ipynb")],
        )
        crate = RocrateBuilder.build_from_minimal(request)

        graph = crate["@graph"]
        ids = {e["@id"] for e in graph}

        assert "ro-crate-metadata.json" in ids
        assert "./" in ids
        assert "notebook.ipynb" in ids
        assert "#binder-lang" in ids
        assert "#author-dispatcher" in ids
        assert "https://spdx.org/licenses/GPL-3.0" in ids

    def test_rocrate_can_be_built_into_package(self):
        """Verify the generated ROCrate can be consumed by RequestPackageBuilder."""
        workflow_url = "https://dockstore.org/api/ga4gh/trs/v2/tools/test"
        request = MinimalVRERequest(
            vre_type="galaxy",
            workflow=workflow_url,
            files=[
                MinimalFileInput(
                    name="sample.fastq",
                    url="https://data.example.org/sample.fastq",
                    encoding_format="application/fastq",
                )
            ],
        )
        crate_dict = RocrateBuilder.build_from_minimal(request)

        package = RequestPackageBuilder.build(crate_dict)
        assert package.vre_type == GALAXY_PROGRAMMING_LANGUAGE
        assert package.workflow.id == workflow_url

    def test_sciencemesh_rocrate_structure(self):
        """Verify a sciencemesh minimal request produces a valid ROCrate structure."""
        workflow_url = "https://raw.githubusercontent.com/example/notebook.ipynb"
        request = MinimalVRERequest(
            vre_type="sciencemesh",
            workflow=workflow_url,
            files=[
                MinimalFileInput(
                    name="data.csv",
                    url="https://raw.githubusercontent.com/example/data.csv",
                    encoding_format="text/csv",
                )
            ],
            runtime_platform="https://qa.cernbox.cern.ch",
            receiver_userid="user@cernbox.cern.ch",
        )
        crate = RocrateBuilder.build_from_minimal(request)

        assert crate["@context"] == "https://w3id.org/ro/crate/1.1/context"
        assert isinstance(crate["@graph"], list)

        graph = crate["@graph"]

        root = _entity_by_id(graph, "./")
        assert root["@type"] == "Dataset"
        assert root["mainEntity"] == {"@id": workflow_url}

        lang = _entity_by_id(graph, "#sciencemesh-lang")
        assert lang["@type"] == "ComputerLanguage"
        assert lang["identifier"] == SCIENCEMESH_PROGRAMMING_LANGUAGE
        assert lang["name"] == "Jupyter Notebook"
        assert lang["url"] == "https://jupyter.org/"

        receiver = _entity_by_id(graph, "#receiver")
        assert receiver["@type"] == "Person"
        assert receiver["userid"] == "user@cernbox.cern.ch"

    def test_sciencemesh_workflow_entity_details(self):
        """Verify the sciencemesh workflow entity has all enriched properties."""
        workflow_url = (
            "https://raw.githubusercontent.com/dpiparo/swanExamples/"
            "refs/heads/master/notebooks/CMSDimuon_py.ipynb"
        )
        request = MinimalVRERequest(
            vre_type="sciencemesh",
            workflow=workflow_url,
            runtime_platform="https://qa.cernbox.cern.ch",
        )
        crate = RocrateBuilder.build_from_minimal(request)

        workflow = _entity_by_id(crate["@graph"], workflow_url)
        assert "ComputationalWorkflow" in workflow["@type"]
        assert workflow["name"] == "CMSDimuon_py.ipynb"
        assert workflow["version"] == "1.0.0"
        assert workflow["conformsTo"] == {
            "@id": "https://bioschemas.org/profiles/ComputationalWorkflow/0.5-DRAFT-2020_07_21/"
        }
        assert workflow["sdPublisher"] == {"@id": "#workflow-hub"}
        assert workflow["creator"] == {"@id": "#author-dispatcher"}
        assert workflow["license"] == {"@id": "https://spdx.org/licenses/GPL-3.0"}
        assert workflow["runtimePlatform"] == "https://qa.cernbox.cern.ch"
        assert workflow["encodingFormat"] == "application/x-ipynb+json"
        assert "dateCreated" in workflow
        assert "description" in workflow

    def test_sciencemesh_rocrate_all_entities(self):
        """Verify a sciencemesh ROCrate has all expected entities."""
        workflow_url = "https://example.com/notebook.ipynb"
        request = MinimalVRERequest(
            vre_type="sciencemesh",
            workflow=workflow_url,
            files=[
                MinimalFileInput(
                    name="data.csv",
                    url="https://example.com/data.csv",
                    encoding_format="text/csv",
                )
            ],
            receiver_userid="user@cernbox.cern.ch",
        )
        crate = RocrateBuilder.build_from_minimal(request)

        ids = {e["@id"] for e in crate["@graph"]}
        assert "ro-crate-metadata.json" in ids
        assert "./" in ids
        assert workflow_url in ids
        assert "https://example.com/data.csv" in ids
        assert "#sciencemesh-lang" in ids
        assert "#author-dispatcher" in ids
        assert "#workflow-hub" in ids
        assert "#receiver" in ids
        assert "#input-0" in ids
        assert "https://spdx.org/licenses/GPL-3.0" in ids

    def test_sciencemesh_without_receiver(self):
        """Verify #receiver is omitted when receiver_userid is not provided."""
        workflow_url = "https://example.com/notebook.ipynb"
        request = MinimalVRERequest(
            vre_type="sciencemesh",
            workflow=workflow_url,
        )
        crate = RocrateBuilder.build_from_minimal(request)

        ids = {e["@id"] for e in crate["@graph"]}
        assert "#receiver" not in ids

    def test_sciencemesh_can_be_built_into_package(self):
        """Verify the generated sciencemesh ROCrate round-trips through RequestPackageBuilder."""
        workflow_url = "https://example.com/notebook.ipynb"
        request = MinimalVRERequest(
            vre_type="sciencemesh",
            workflow=workflow_url,
            files=[
                MinimalFileInput(
                    name="data.csv",
                    url="https://example.com/data.csv",
                    encoding_format="text/csv",
                )
            ],
            runtime_platform="https://qa.cernbox.cern.ch",
            receiver_userid="user@cernbox.cern.ch",
        )
        crate_dict = RocrateBuilder.build_from_minimal(request)

        package = RequestPackageBuilder.build(crate_dict)
        assert package.vre_type == SCIENCEMESH_PROGRAMMING_LANGUAGE
        assert package.workflow.id == workflow_url
