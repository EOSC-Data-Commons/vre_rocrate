"""Tests for ValidationPipeline — basic ROCrate structure validation."""

import pytest

from vre_rocrate import ValidationPipeline, CrateValidationError
from conftest import example_crate


class TestValidationPipeline:
    """Unit tests for ValidationPipeline.validate_basic()."""

    def test_valid_crate_passes(self):
        ValidationPipeline.validate_basic(example_crate("galaxy"))

    def test_missing_main_entity_raises(self):
        source = {
            "@context": "https://w3id.org/ro/crate/1.1/context",
            "@graph": [
                {"@id": "./", "@type": "Dataset"},
                {
                    "@id": "ro-crate-metadata.json",
                    "@type": "CreativeWork",
                    "about": {"@id": "./"},
                    "conformsTo": {"@id": "https://w3id.org/ro/crate/1.1"},
                },
            ],
        }
        with pytest.raises(CrateValidationError, match="Missing mainEntity"):
            ValidationPipeline.validate_basic(source)

    def test_missing_programming_language_raises(self):
        source = {
            "@context": "https://w3id.org/ro/crate/1.1/context",
            "@graph": [
                {"@id": "./", "@type": "Dataset", "mainEntity": {"@id": "#wf"}},
                {"@id": "#wf", "@type": "File"},
                {
                    "@id": "ro-crate-metadata.json",
                    "@type": "CreativeWork",
                    "about": {"@id": "./"},
                    "conformsTo": {"@id": "https://w3id.org/ro/crate/1.1"},
                },
            ],
        }
        with pytest.raises(CrateValidationError, match="programmingLanguage"):
            ValidationPipeline.validate_basic(source)

    def test_entity_without_id_raises(self):
        """RO-Crate requires every @graph entity to declare an @id."""
        source = {
            "@context": "https://w3id.org/ro/crate/1.1/context",
            "@graph": [
                {"@id": "./", "@type": "Dataset", "mainEntity": {"@id": "#wf"}},
                {
                    "@id": "#wf",
                    "@type": "File",
                    "programmingLanguage": {"@id": "#lang"},
                },
                {"@id": "#lang", "@type": "ComputerLanguage", "identifier": "x"},
                {"@type": "File", "name": "data.txt"},  # no @id
            ],
        }
        with pytest.raises(CrateValidationError, match="without @id"):
            ValidationPipeline.validate_basic(source)

    def test_entity_with_empty_id_raises(self):
        source = {
            "@context": "https://w3id.org/ro/crate/1.1/context",
            "@graph": [
                {"@id": "./", "@type": "Dataset", "mainEntity": {"@id": "#wf"}},
                {
                    "@id": "#wf",
                    "@type": "File",
                    "programmingLanguage": {"@id": "#lang"},
                },
                {"@id": "#lang", "@type": "ComputerLanguage", "identifier": "x"},
                {"@id": "", "@type": "File", "name": "data.txt"},
            ],
        }
        with pytest.raises(CrateValidationError, match="without @id"):
            ValidationPipeline.validate_basic(source)

    def test_duplicate_entity_id_raises(self):
        """Two @graph entities sharing an @id make the crate ill-defined
        (e.g. two file slots bound to the same download URL — see
        EOSC-Data-Commons/Dispatcher#166)."""
        source = {
            "@context": "https://w3id.org/ro/crate/1.1/context",
            "@graph": [
                {"@id": "./", "@type": "Dataset", "mainEntity": {"@id": "#wf"}},
                {
                    "@id": "#wf",
                    "@type": "File",
                    "programmingLanguage": {"@id": "#lang"},
                },
                {"@id": "#lang", "@type": "ComputerLanguage", "identifier": "x"},
                {"@id": "https://example.org/a.zip", "@type": "File", "name": "a"},
                {"@id": "https://example.org/a.zip", "@type": "File", "name": "b"},
            ],
        }
        with pytest.raises(CrateValidationError, match="Duplicate @id"):
            ValidationPipeline.validate_basic(source)

    def test_missing_language_identifier_raises(self):
        source = {
            "@context": "https://w3id.org/ro/crate/1.1/context",
            "@graph": [
                {"@id": "./", "@type": "Dataset", "mainEntity": {"@id": "#wf"}},
                {
                    "@id": "#wf",
                    "@type": "File",
                    "programmingLanguage": {"@id": "#lang"},
                },
                {"@id": "#lang", "@type": "ComputerLanguage", "name": "Test"},
                {
                    "@id": "ro-crate-metadata.json",
                    "@type": "CreativeWork",
                    "about": {"@id": "./"},
                    "conformsTo": {"@id": "https://w3id.org/ro/crate/1.1"},
                },
            ],
        }
        with pytest.raises(CrateValidationError, match="identifier"):
            ValidationPipeline.validate_basic(source)
