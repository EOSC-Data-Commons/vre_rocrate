"""VRE resolution: which VRE type is this tool, and where does it run?

Answers the two resolution questions — :func:`resolve_vre_type` and
:func:`default_runtime_platform` — data-first from the EOSC Data Commons
vre-registry over a cached fetch of ``vres.json``, falling back to the
constant maps in ``constants.py`` when the registry is unavailable or has
no match.

Source precedence, first success wins:

1. ``VRE_REGISTRY_URL`` env var (local path or URL).
2. the upstream raw URL on GitHub (cached in-process for 24h).
3. the vendored snapshot ``vre_rocrate/data/vres.json`` — offline fallback;
   only a broken snapshot raises.

Tests must never hit the network: ``tests/conftest.py`` points the env var at
the vendored snapshot.
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from .constants import (
    TOOL_TYPE_TO_VRE_TYPE,
    VRE_TYPE_TO_DEFAULT_RUNTIME_PLATFORM,
    VRE_TYPES,
)
from .exceptions import VreRocrateError

logger = logging.getLogger(__name__)

DEFAULT_REGISTRY_URL = (
    "https://raw.githubusercontent.com/EOSC-Data-Commons/"
    "vre-registry/main/vres.json"
)
REGISTRY_URL_ENV_VAR = "VRE_REGISTRY_URL"
CACHE_TTL_SECONDS = 24 * 3600
_FETCH_TIMEOUT_SECONDS = 10

_SNAPSHOT = Path(__file__).parent / "data" / "vres.json"

# resolved source string -> (fetched-at epoch, parsed entries)
_cache: dict[str, tuple[float, list[dict]]] = {}


def _fetch(source: str, refresh: bool) -> list[dict]:
    cached = _cache.get(source)
    if not refresh and cached and (time.time() - cached[0]) < CACHE_TTL_SECONDS:
        return cached[1]
    if source.startswith(("http://", "https://")):
        request = urllib.request.Request(source, headers={"User-Agent": "vre-rocrate"})
        with urllib.request.urlopen(request, timeout=_FETCH_TIMEOUT_SECONDS) as response:
            data = json.load(response)
    else:
        data = json.loads(Path(source).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise VreRocrateError(
            f"VRE registry source {source!r} is not a JSON array of entries"
        )
    _cache[source] = (time.time(), data)
    return data


def load_registry(refresh: bool = False) -> list[dict]:
    """Return the vres.json entries for the configured default source."""
    source = os.environ.get(REGISTRY_URL_ENV_VAR, DEFAULT_REGISTRY_URL)
    try:
        return _fetch(source, refresh)
    except Exception as exc:  # network down, bad JSON, env var typo, ...
        logger.warning(
            "Loading VRE registry from %s failed (%s); "
            "falling back to the vendored snapshot at %s",
            source,
            exc,
            _SNAPSHOT,
        )
        return _fetch(str(_SNAPSHOT), refresh)


def clear_cache() -> None:
    _cache.clear()


def _try_load() -> list[dict] | None:
    try:
        return load_registry()
    except Exception as exc:  # even the vendored snapshot is broken
        logger.warning("VRE registry unavailable (%s)", exc)
        return None


def _registry_vre_type(tool) -> str | None:
    """Pure registry match: tool types against instance id/``aliases``/type,
    then tool URI host-matched against instance url/apiUrl."""
    entries = _try_load()
    if entries is None:
        return None
    for t in tool.types:
        for entry in entries:
            vre_type = entry.get("type")
            if vre_type and (
                t in (entry.get("id"), vre_type) or t in entry.get("aliases", [])
            ):
                return vre_type
    lowered = tool.uri.lower()
    for entry in entries:
        vre_type = entry.get("type")
        if not vre_type:
            continue
        for candidate in (entry.get("url"), entry.get("apiUrl")):
            host = urlparse(candidate).netloc.lower().removeprefix("www.") if candidate else ""
            if host and host in lowered:
                return vre_type
    return None


def resolve_vre_type(tool) -> str:
    """Resolve a vre_type: explicit override → registry → constants fallback.

    The registry is authoritative: whenever it can resolve at all — even by
    URL — it wins over the constant maps, which only serve tools the registry
    doesn't know (synonyms like ``boutique``) and offline operation.
    """
    if "vre_type" in tool.raw_definition:
        v = tool.raw_definition["vre_type"]
        if v in VRE_TYPES:
            return v
    vre_type = _registry_vre_type(tool)
    if vre_type is not None:
        return vre_type
    for t in tool.types:
        if t in TOOL_TYPE_TO_VRE_TYPE:
            return TOOL_TYPE_TO_VRE_TYPE[t]
    for pattern, vtype in _URI_PATTERNS:
        if pattern in tool.uri:
            return vtype
    raise ValueError(f"Cannot resolve vre_type from tool: {tool.id}")


def _registry_default_url(vre_type: str) -> str | None:
    """URL of the registry's default *active* instance for ``vre_type``.

    An entry flagged ``"default": true`` wins over document order; entries
    with any other status than "active" are skipped.
    """
    entries = _try_load()
    if entries is None:
        return None
    actives = [
        e
        for e in entries
        if e.get("type") == vre_type and e.get("status", "active") == "active"
    ]
    if not actives:
        return None
    return next((e for e in actives if e.get("default")), actives[0]).get("url")


def default_runtime_platform(vre_type: str) -> str:
    """Default runtimePlatform URL for a VRE type.

    The registry's default instance for the type wins when it points at a
    *different* service than the hardcoded constant; when both name the
    same instance (modulo trailing slash/case) the constant's form is
    kept for byte-stability of existing crates.
    """
    default = VRE_TYPE_TO_DEFAULT_RUNTIME_PLATFORM.get(vre_type)
    registry_url = _registry_default_url(vre_type)
    if registry_url is None:
        return default or ""
    if default is None:
        return registry_url
    if _normalize_url(registry_url) != _normalize_url(default):
        return registry_url
    return default


def _normalize_url(url: str) -> str:
    return url.lower().rstrip("/")


_URI_PATTERNS: tuple[tuple[str, str], ...] = (
    ("galaxyproject.org", "galaxy"),
    ("usegalaxy.eu", "galaxy"),
    ("usegalaxy.org", "galaxy"),
    ("jupyter.org", "jupyter"),
    ("oscar.grycap", "oscar"),
    ("vip.creatis", "vip"),
    ("cernbox.cern.ch", "sciencemesh"),
    ("rrp-eosc", "rrp"),
)
