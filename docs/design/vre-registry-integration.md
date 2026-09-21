# Design: Registry-driven VRE resolution via EOSC-Data-Commons/vre-registry

**Status:** implemented (2026-09-16). Remaining upstream: merge of branch
`add-remaining-vre-types` on `EOSC-Data-Commons/vre-registry` (adds the 7 new
instance entries below), plus the schema-extension proposals at the end.

This document describes how `vre_rocrate` consumes the vre-registry so VRE
instance knowledge no longer needs to be hardcoded in `constants.py`.

## Motivation

All VRE instance knowledge currently lives in `src/vre_rocrate/constants.py`:

- `TOOL_TYPE_TO_VRE_TYPE` — requester tool-type → VRE type (mixes real tool
  ecosystems like `boutique`→`vip`, `cernbox`→`sciencemesh`, and *instance ids*
  like `egi-replay`, `mybinder` → `binder`).
- `VRE_TYPE_TO_DEFAULT_RUNTIME_PLATFORM` — type → default instance URL.
- `resolve_vre_type()` — hardcoded URI-pattern fallback list (substrings like
  `usegalaxy.eu`, `cernbox.cern.ch` → VRE type).

Adding or re-pointing a VRE instance today means a code change + release. The
[EOSC-Data-Commons/vre-registry](https://github.com/EOSC-Data-Commons/vre-registry)
repo ("a static list of VREs supported by Data Commons") is the natural home
for this data instead.

## The registry today

Upstream `vres.json` is a flat array of **service instances** (not types).
Schema per entry (observed, no formal schema exists yet):

| field | notes |
|---|---|
| `id` | stable slug, e.g. `usegalaxy-eu`, `egi-replay` |
| `type` | coarse VRE type — `galaxy`, `binder`, ... |
| `name`, `url` | display name + base URL of the instance |
| `apiUrl` | optional (galaxy instances) |
| `buildUrlTemplate` | optional (binder: `https://mybinder.org/v2/{provider}/{repository}/{ref}`) |
| `accepts` | payload vocabulary: `galaxy-workflow`, `notebook-repository`, ... |
| `authentication` | vocab: `anonymous`, `account`, `api-key`, `egi-check-in` |
| `operator`, `provider` | org names; `provider` optional (federation over operator) |
| `status` | only `active` used so far |

## Inspiration: how aiidateam/aiida-registry does it

The [AiiDA plugin registry](https://github.com/aiidateam/aiida-registry) is the
mature reference for "static registry in git consumed programmatically":

1. **Source of truth is a static file in a git repo, edited by fork-and-PR.**
   `plugins.yaml` is hand-edited; a PR is the registration mechanism.
2. **The registry repo carries its own tooling package + tests; CI validates
   every PR** with explicit warning/error codes (W001–W020, E001–E004):
   unparseable `pyproject.toml`/`setup.json`, unreachable docs links,
   entry-point prefix convention violations, etc. Bad entries never land.
3. **A scheduled (daily) pipeline enriches entries** — fetches each plugin's
   PyPI metadata, `plugin_info` JSON and entry points — and **publishes a
   compiled `plugins_metadata.json` to GitHub Pages**
   (`aiidateam.github.io/aiida-registry/plugins_metadata.json`). Stable,
   cacheable URL; consumers don't parse the repo.
4. **Consumers fetch over HTTP.** The browser UI at aiida.net/plugin-registry
   is just a client of the published JSON.
5. **Deprecation discipline:** keys evolve explicitly (e.g. `development_status`
   deprecated in favour of PyPI trove classifiers).

### What we borrow vs. adapt

| aiida-registry | vre-registry / vre_rocrate |
|---|---|
| PR-edited static file as source of truth | already true for `vres.json` |
| CI validation in registry repo | *propose*: JSON Schema for `vres.json` + validate workflow (see "Upstream proposals") |
| daily pipeline → published, versioned artifact on gh-pages | *propose*: optional gh-pages publish; not required — we fetch the raw file |
| consumers fetch over HTTP | *adapt*: vre_rocrate is a library embedded in services (req-packager, Dispatcher) → **hybrid: fetch with env-override + vendored snapshot fallback** |
| daily rebuild cadence | 24h in-process cache on the client side |

The hybrid (network fetch + packaged fallback) is the adaptation on top of the
aiida model — crate building must stay deterministic and offline-capable, and
the test suite must never touch the network.

## Deliverables already done

1. **Vendored snapshot**: `src/vre_rocrate/data/vres.json` — upstream's 4
   entries verbatim + 7 new ones (one instance per VRE type from
   `VRE_TYPES`/`TOOL_TYPE_TO_VRE_TYPE` that the registry lacked):

   | id | type | url |
   |---|---|---|
   | egi-notebooks | jupyter | https://notebooks.egi.eu/ |
   | oscar-data-commons | oscar | https://oscar.vre.eosc-data-commons.eu/ |
   | vip-creatis | vip | https://vip.creatis.insa-lyon.fr/ |
   | scipion-i2pc | scipion | http://scipion.i2pc.es/ |
   | mddash-cerit-sc | mddash | https://mddash-edc-dev.dyn.cloud.e-infra.cz/ |
   | eosc-cernbox | sciencemesh | https://eosc.cernbox.cern.ch |
   | rrp-ethz | rrp | https://rrp-eosc.ethz.ch/ |

2. **Upstream change**: branch `add-remaining-vre-types` in a local clone of
   `EOSC-Data-Commons/vre-registry` with the same additions (commit ready to
   push from a fork → PR).

## Consumption design (implemented)

Deliberately minimal: no registry model classes, no lookup-object API.
Entries stay plain dicts (unknown upstream fields are simply ignored), and
**all resolution logic lives in `registry.py`** — `constants.py` is pure
data (no imports, no functions).

### `src/vre_rocrate/registry.py`

Loading:

- `load_registry(refresh=False)` — fetch + parse `vres.json`. Source
  precedence: `VRE_REGISTRY_URL` env var → default
  `https://raw.githubusercontent.com/EOSC-Data-Commons/vre-registry/main/vres.json`
  → vendored snapshot `vre_rocrate/data/vres.json`. In-process per-source
  cache with a 24h TTL (mirrors aiida's daily cadence); `clear_cache()` for
  tests. Only a broken vendored snapshot raises.

Resolution (public):

- `resolve_vre_type(tool) -> str` — the full mechanism:
  `raw_definition["vre_type"]` override → pure registry match (tool types
  against instance **id** / **`aliases`** / **type**, then tool URI
  **host-matched** against instance `url`/`apiUrl`) → `TOOL_TYPE_TO_VRE_TYPE`
  → `_URI_PATTERNS` list → `ValueError` if unresolvable. The registry is
  authoritative — when it can resolve at all, even by URL, it beats the
  constants maps; the maps only serve tools the registry doesn't know
  (synonyms like `boutique`) and offline operation.
- `default_runtime_platform(vre_type) -> str` — registry-first with a
  **stability rule**: the registry's default *active* instance URL wins when
  it names a *different* service (`"default": true` flagged entry beats
  document order); when registry and constants name the same instance (same
  URL modulo case/trailing slash) the constant's byte form is emitted, so
  existing crates stay byte-identical. Types missing from both yield `""`.

### `src/vre_rocrate/constants.py` — data only

- Offline fallback maps consumed by `registry.py`: `TOOL_TYPE_TO_VRE_TYPE`,
  `VRE_TYPE_TO_DEFAULT_RUNTIME_PLATFORM`, `VRE_TYPES` (validates the
  `raw_definition` override).
- **Stays hardcoded** (out of registry scope): `VRE_TYPE_TO_PROGRAMMING_LANGUAGE`,
  `VRE_TYPE_TO_DISPLAY_NAME`, `VRE_TYPE_TO_LANGUAGE_URL` — per-*type* semantic
  identifiers (schema.org `ComputerLanguage`), not per-instance facts.
- Import direction is one-way: `registry.py` → `constants.py`. `constants.py`
  has no imports and no functions.

### Wiring / packaging

- `pyproject.toml`: `[tool.setuptools.package-data]` ships `data/vres.json` in
  the wheel.
- Callers: `RocrateBuilder` imports `resolve_vre_type` /
  `default_runtime_platform` from `registry.py`. No new top-level package
  exports.

### Test strategy

- No network in tests: `tests/conftest.py` sets `VRE_REGISTRY_URL` to the
  vendored snapshot for the whole suite; registry-specific tests redirect it
  to tmp files via monkeypatch + `registry.clear_cache()`.
- `tests/test_registry.py` (19 tests) covers snapshot loading, the 24h
  cache, fallback to the vendored snapshot on broken env source, registry-
  driven `resolve_vre_type` (instance id/`aliases`/type/URL host match —
  including a type absent from every constants map), constants' fallback
  order (registry → maps), offline degradation, and the
  `default_runtime_platform` stability/divergence/inactive rules incl.
  end-to-end builder checks.
- Existing suite round-trips unchanged; total went 66 → 85 tests.

## Upstream proposals (vre-registry repo — future PRs, aiida-style)

1. **JSON Schema for `vres.json`** (`vres.schema.json`) + a GitHub workflow
   validating PRs — the aiida-registry W/E-code pattern, minimal version.
2. **Optional gh-pages publish** of `vres.json` (stable URL, cached artifact);
   trivial workflow since the file needs no enrichment.
3. **Schema extensions** enabling full de-hardcoding of `TOOL_TYPE_TO_VRE_TYPE`:
   - `aliases`: per-instance tool-type synonyms, e.g. `vip-creatis` →
     `["boutique"]`, `eosc-cernbox` → `["cernbox"]`, binder entries →
     `["mybinder", "binder-launcher"]`.
   - `"default": true` per type to pin the default runtime platform instance.
   - Document the `accepts` payload vocabulary (currently implicit).

## Open TODOs / flagged with the data

- **New `accepts` vocabulary** (`oscar-service`, `vip-workflow`,
  `scipion-workflow`, `ocm-share`) is our proposal — needs maintainer sign-off
  in the upstream PR.
- ~~**`mddash.cerit-sc.cz`** did not respond to HTTP probing~~ — resolved:
  the production instance is not reachable; the only mddash deployment for
  Data Commons is currently the **dev instance**
  `https://mddash-edc-dev.dyn.cloud.e-infra.cz/` (confirmed live 2026-09-16).
  Registry entry and `VRE_TYPE_TO_DEFAULT_RUNTIME_PLATFORM["mddash"]` point
  there; when a production instance appears, flip the registry entry (and
  mark one `status`) without touching the lib.
- **`rrp` inconsistency**: resolvable via `TOOL_TYPE_TO_VRE_TYPE["rrp"]` and has
  a default platform, but is missing from `VRE_TYPES` (first `resolve_vre_type`
  layer silently rejects it). Either add `rrp` to `VRE_TYPES` (+ programming
  language maps) or drop it. Registry entry currently has `status: "inactive"`.

## Non-goals

- No changes to `VREPayload` (Dispatcher contract).
- No runtime dependency on the network in the default path.
- No schema-breaking change to `vres.json` (extensions are proposals only).
