"""Tests for RocrateBuilder.build_from_minimal()."""

from vre_rocrate import (
    RocrateBuilder,
    ROCrateParser,
    GALAXY_PROGRAMMING_LANGUAGE,
    OSCAR_PROGRAMMING_LANGUAGE,
    SCIPION_PROGRAMMING_LANGUAGE,
)


def _entity_by_id(graph: list[dict], eid: str) -> dict:
    """Return the first entity in *graph* whose ``@id`` matches *eid*."""
    return next(e for e in graph if e.get("@id") == eid)


class TestRocrateBuilder:
    """Tests for RocrateBuilder.build_from_minimal()."""

    def test_galaxy_rocrate_structure(self):
        """Verify a galaxy minimal request produces a valid ROCrate structure."""
        workflow_url = "https://dockstore.org/api/ga4gh/trs/v2/tools/test"
        data = {
            "vre_type": "galaxy",
            "workflow": workflow_url,
            "files": [
                {
                    "name": "sample.fastq",
                    "url": "https://data.example.org/sample.fastq",
                    "encoding_format": "application/fastq",
                }
            ],
        }
        crate = RocrateBuilder.build_from_minimal(data)

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
        data = {
            "vre_type": "oscar",
            "workflow": workflow_url,
            "files": [
                {
                    "name": "script.sh",
                    "url": "https://raw.githubusercontent.com/grycap/oscar/master/examples/cowsay/script.sh",
                    "encoding_format": "text/x-shellscript",
                }
            ],
        }
        crate = RocrateBuilder.build_from_minimal(data)

        graph = crate["@graph"]

        lang = _entity_by_id(graph, "#oscar-lang")
        assert lang["identifier"] == OSCAR_PROGRAMMING_LANGUAGE

        workflow = _entity_by_id(graph, workflow_url)
        assert "ComputationalWorkflow" in workflow["@type"]

    def test_scipion_rocrate_no_workflow(self):
        """Verify a scipion request without workflow produces valid ROCrate."""
        data = {
            "vre_type": "scipion",
            "workflow": "workflow.json",
            "files": [],
        }
        crate = RocrateBuilder.build_from_minimal(data)

        graph = crate["@graph"]
        lang = _entity_by_id(graph, "#scipion-lang")
        assert lang["identifier"] == SCIPION_PROGRAMMING_LANGUAGE

        workflow = _entity_by_id(graph, "workflow.json")
        assert "ComputationalWorkflow" in workflow["@type"]

    def test_runtime_platform_override(self):
        """Verify runtime_platform override appears in the ROCrate."""
        workflow_url = "https://example.com/workflow.ga"
        data = {
            "vre_type": "galaxy",
            "workflow": workflow_url,
            "runtime_platform": "https://custom-galaxy.example.org/",
            "files": [],
        }
        crate = RocrateBuilder.build_from_minimal(data)

        workflow = _entity_by_id(crate["@graph"], workflow_url)
        assert workflow["runtimePlatform"] == "https://custom-galaxy.example.org/"

    def test_onedata_file_in_rocrate(self):
        """Verify onedata file attributes appear in the ROCrate."""
        data = {
            "vre_type": "galaxy",
            "workflow": "https://example.com/workflow.ga",
            "files": [
                {
                    "name": "onedata_file",
                    "url": None,
                    "encoding_format": "image/tiff",
                    "onedata_domain": "demo.onedata.org",
                    "onedata_file_id": "00000000007EADF37368",
                }
            ],
        }
        crate = RocrateBuilder.build_from_minimal(data)

        file_entity = _entity_by_id(crate["@graph"], "onedata_file")
        assert file_entity["onedata:onezoneDomain"] == "demo.onedata.org"
        assert file_entity["onedata:fileId"] == "00000000007EADF37368"

    def test_rocrate_has_required_entities(self):
        """Verify the generated ROCrate contains all required supporting entities."""
        data = {
            "vre_type": "binder",
            "workflow": "notebook.ipynb",
            "files": [],
        }
        crate = RocrateBuilder.build_from_minimal(data)

        graph = crate["@graph"]
        ids = {e["@id"] for e in graph}

        assert "ro-crate-metadata.json" in ids
        assert "./" in ids
        assert "notebook.ipynb" in ids
        assert "#binder-lang" in ids
        assert "#author-dispatcher" in ids
        assert "https://spdx.org/licenses/GPL-3.0" in ids

    def test_rocrate_can_be_parsed_back(self):
        """Verify the generated ROCrate can be parsed by ROCrateParser."""
        workflow_url = "https://dockstore.org/api/ga4gh/trs/v2/tools/test"
        data = {
            "vre_type": "galaxy",
            "workflow": workflow_url,
            "files": [
                {
                    "name": "sample.fastq",
                    "url": "https://data.example.org/sample.fastq",
                    "encoding_format": "application/fastq",
                }
            ],
        }
        crate = RocrateBuilder.build_from_minimal(data)

        parsed = ROCrateParser.parse(crate)
        assert parsed.root_id == "./"
        assert parsed.main_entity is not None
        assert parsed.main_entity.id == workflow_url
