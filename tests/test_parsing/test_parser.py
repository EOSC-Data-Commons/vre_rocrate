"""Tests for ROCrateParser — parsing ROCrate JSON into ParsedCrate."""

import pytest

from vre_rocrate import ROCrateParser
from conftest import load_json

PARSER_CASES = [
    ("galaxy/ro-crate-metadata.json", "https://dockstore.org/"),
    ("oscar/ro-crate-metadata.json", "https://raw.githubusercontent.com/"),
]


class TestROCrateParser:
    """Unit tests for ROCrateParser.parse()."""

    @pytest.mark.parametrize("fixture_path,expected_prefix", PARSER_CASES)
    def test_parse_crate(self, fixtures_dir, fixture_path, expected_prefix):
        source = load_json(fixtures_dir, fixture_path)
        parsed = ROCrateParser.parse(source)
        assert parsed.root_id == "./"
        assert parsed.main_entity is not None
        assert parsed.main_entity.id.startswith(expected_prefix)

    def test_parse_resolves_references(self, fixtures_dir):
        source = load_json(fixtures_dir, "galaxy/ro-crate-metadata.json")
        parsed = ROCrateParser.parse(source)
        lang_ref = parsed.main_entity.get("programmingLanguage")
        assert isinstance(lang_ref, dict)
        assert lang_ref.get("@id") == "#galaxy-lang"
        lang = parsed.get("#galaxy-lang")
        assert lang is not None
        assert lang.get("identifier") == "https://galaxyproject.org/"
