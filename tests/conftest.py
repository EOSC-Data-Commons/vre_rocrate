import json
import os
from pathlib import Path

import pytest

# The test suite must never hit the network: resolve the default VRE
# registry source to the snapshot vendored in the package.
os.environ.setdefault(
    "VRE_REGISTRY_URL",
    str(Path(__file__).parent.parent / "src" / "vre_rocrate" / "data" / "vres.json"),
)


@pytest.fixture
def fixtures_dir() -> Path:
    """Return the directory containing ROCrate fixture files."""
    return Path(__file__).parent / "fixtures"


def load_json(fixtures_dir: Path, file_name: str) -> dict:
    """Load a JSON fixture file from the fixtures directory."""
    with open(fixtures_dir / file_name, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def galaxy_rocrate_source(fixtures_dir) -> dict:
    """Load the galaxy ROCrate fixture as a raw dict."""
    return load_json(fixtures_dir, "galaxy/ro-crate-metadata.json")
