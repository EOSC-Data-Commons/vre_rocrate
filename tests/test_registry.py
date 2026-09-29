"""Tests for VRE resolution in registry.py — registry-first with the
constant maps in ``constants.py`` as offline fallback.

No network: ``tests/conftest.py`` points ``VRE_REGISTRY_URL`` at the vendored
package snapshot; custom registries are written to tmp files.
"""

import json

import pytest

from vre_rocrate import (
    VRELaunchRequest,
    ToolMeta,
    LaunchInput,
    RocrateBuilder,
)
from vre_rocrate import registry
from vre_rocrate.constants import VRE_TYPE_TO_DEFAULT_RUNTIME_PLATFORM
from vre_rocrate.registry import (
    REGISTRY_URL_ENV_VAR,
    clear_cache,
    default_runtime_platform,
    load_registry,
    resolve_vre_type,
)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _entry(id, type, url, **kw):
    return {"id": id, "type": type, "name": id, "url": url, **kw}


def _tool(uri, types, raw_definition=None):
    return ToolMeta(id="t", version="1", name="T", uri=uri, types=types,
                    slots=[], raw_definition=raw_definition or {})


@pytest.fixture
def registry_source(tmp_path, monkeypatch):
    """Point the default registry source at a json file we control."""
    def _write(entries):
        path = tmp_path / "vres.json"
        path.write_text(json.dumps(entries), encoding="utf-8")
        monkeypatch.setenv(REGISTRY_URL_ENV_VAR, str(path))
        clear_cache()
        return str(path)

    yield _write
    clear_cache()


# ---------------------------------------------------------------------------
# Loading + caching
# ---------------------------------------------------------------------------


def test_load_vendored_snapshot():
    entries = load_registry()
    assert len(entries) >= 11
    by_id = {e["id"]: e for e in entries}
    assert by_id["egi-replay"]["type"] == "binder"
    assert by_id["mybinder-org"]["buildUrlTemplate"] == \
        "https://mybinder.org/v2/{provider}/{repository}/{ref}"


def test_load_is_cached(registry_source):
    registry_source([_entry("x", "galaxy", "https://x.example.org")])
    first = load_registry()
    assert load_registry() is first
    refreshed = load_registry(refresh=True)
    assert refreshed is not first
    assert load_registry() is refreshed  # refresh replaced the cache entry


def test_broken_default_source_falls_back_to_vendored(tmp_path, monkeypatch):
    # Connection refused on loopback — fast, no real network.
    monkeypatch.setenv(REGISTRY_URL_ENV_VAR, "http://127.0.0.1:1/vres.json")
    clear_cache()
    assert any(e["id"] == "egi-replay" for e in load_registry())
    clear_cache()


def test_non_list_source_falls_back_to_vendored(registry_source):
    registry_source({"not": "a list"})
    assert any(e["id"] == "egi-replay" for e in load_registry())


# ---------------------------------------------------------------------------
# resolve_vre_type — registry in front of the constants fallbacks
# ---------------------------------------------------------------------------


def test_resolve_vre_type_via_registry_instance_id(registry_source):
    registry_source([_entry("my-hub", "galaxy", "https://hub.example.org/")])
    assert resolve_vre_type(_tool("u", ["my-hub"])) == "galaxy"


def test_resolve_vre_type_via_registry_alias(registry_source):
    registry_source([_entry("my-hub", "galaxy", "https://hub.example.org/",
                            aliases=["my-ecosystem"])])
    assert resolve_vre_type(_tool("u", ["my-ecosystem"])) == "galaxy"


def test_resolve_vre_type_unknown_to_all_constants_maps(registry_source):
    # The whole point of the registry: a type absent from every hardcoded
    # map (VRE_TYPES, TOOL_TYPE_TO_VRE_TYPE, pattern list) resolves anyway.
    registry_source([_entry("x1", "quantumlab", "https://x1.example.org")])
    assert resolve_vre_type(_tool("u", ["quantumlab"])) == "quantumlab"


def test_resolve_vre_type_via_registry_url_match(registry_source):
    registry_source([_entry("oscar-dc", "oscar", "https://oscar.example.org/")])
    assert resolve_vre_type(
        _tool("https://oscar.example.org/services/fdl", [])) == "oscar"


def test_resolve_vre_type_falls_back_to_constants_maps(registry_source):
    registry_source([_entry("my-hub", "galaxy", "https://hub.example.org/")])
    assert resolve_vre_type(_tool("u", ["boutique"])) == "vip"
    assert resolve_vre_type(
        _tool("https://usegalaxy.eu/workflows/abc", [])) == "galaxy"


def test_resolve_vre_type_unknown_still_raises(registry_source):
    registry_source([_entry("my-hub", "galaxy", "https://hub.example.org/")])
    with pytest.raises(ValueError):
        resolve_vre_type(_tool("https://nohost.example/x", ["unknown"]))


def test_resolve_vre_type_offline_registry_falls_back_to_constants(
    registry_source, monkeypatch,
):
    registry_source([_entry("my-hub", "galaxy", "https://hub.example.org/")])
    def _broken(refresh=False):
        raise RuntimeError("registry dead")
    monkeypatch.setattr(registry, "load_registry", _broken)
    assert resolve_vre_type(_tool("u", ["boutique"])) == "vip"
    assert resolve_vre_type(
        _tool("https://usegalaxy.eu/workflows/abc", [])) == "galaxy"


# ---------------------------------------------------------------------------
# default_runtime_platform — registry wins on divergence, constants' form kept
# ---------------------------------------------------------------------------


def test_default_runtime_platform_skips_inactive(registry_source):
    registry_source([
        _entry("g1", "galaxy", "https://g1.example.org", status="inactive"),
        _entry("g2", "galaxy", "https://g2.example.org"),
    ])
    assert default_runtime_platform("galaxy") == "https://g2.example.org"


def test_default_runtime_platform_flag_wins(registry_source):
    registry_source([
        _entry("g1", "galaxy", "https://g1.example.org"),
        _entry("g2", "galaxy", "https://g2.example.org", **{"default": True}),
    ])
    assert default_runtime_platform("galaxy") == "https://g2.example.org"


def test_default_runtime_platform_inactive_only_falls_back_to_constants():
    # vendored snapshot: rrp's single entry is inactive → registry abstains,
    # the constants default (which does exist) is emitted.
    clear_cache()
    assert default_runtime_platform("rrp") == \
        VRE_TYPE_TO_DEFAULT_RUNTIME_PLATFORM["rrp"]


def test_default_runtime_platform_keeps_constant_form_when_equivalent():
    # Vendored snapshot and constants name the same galaxy instance;
    # the constant's byte form (trailing slash) is preserved.
    assert default_runtime_platform("galaxy") == \
        VRE_TYPE_TO_DEFAULT_RUNTIME_PLATFORM["galaxy"]


def test_default_runtime_platform_registry_wins_on_divergence(registry_source):
    registry_source([_entry("g-new", "galaxy", "https://galaxy.example.org/")])
    assert default_runtime_platform("galaxy") == "https://galaxy.example.org/"


def test_default_runtime_platform_unknown_type_is_empty(registry_source):
    registry_source([_entry("g1", "galaxy", "https://g.example.org/")])
    assert default_runtime_platform("bogus") == ""


# ---------------------------------------------------------------------------
# End-to-end through the crate builder
# ---------------------------------------------------------------------------


def test_built_crate_uses_registry_default_platform(registry_source):
    registry_source([
        _entry("vip-creatis", "vip", "https://vip.creatis.insa-lyon.fr/"),
    ])
    request = VRELaunchRequest(
        tool=_tool("https://example.org/pipeline", ["vip"]),
        input=LaunchInput(),
    )
    crate = RocrateBuilder.build_from_launch_request(request)
    wf = next(e for e in crate["@graph"] if e["@id"] == request.tool.uri)
    assert wf["runtimePlatform"] == "https://vip.creatis.insa-lyon.fr/"


def test_built_crate_constant_default_unchanged_with_vendored_snapshot():
    # End-to-end byte-stability: same instance in registry and constants
    # produces the historical constant's runtimePlatform value.
    request = VRELaunchRequest(
        tool=_tool("https://example.org/wf.ga", ["galaxy_workflow"]),
        input=LaunchInput(),
    )
    crate = RocrateBuilder.build_from_launch_request(request)
    wf = next(e for e in crate["@graph"] if e["@id"] == request.tool.uri)
    assert wf["runtimePlatform"] == VRE_TYPE_TO_DEFAULT_RUNTIME_PLATFORM["galaxy"]
