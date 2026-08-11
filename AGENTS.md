# AGENTS.md

RO-Crate parsing/building library for EOSC VRE dispatch. Python 3.10+, src layout, package `vre_rocrate`, installed editable into `.venv`.

## Commands

`uv` is used in docs but may not be on PATH — the repo-local `.venv` (Python 3.12) works directly:

```console
.venv/bin/python -m pytest                     # all tests (pyproject sets testpaths=["tests"])
.venv/bin/python -m pytest -k sciencemesh      # focused run
.venv/bin/python -m pytest tests/test_launch_request_assumptions.py -q
.venv/bin/python examples/galaxy.py | jq .     # print a generated crate (one example per VRE type)
```

Black (line-length 88) is configured in `pyproject.toml` but **not enforced** — no CI, no pre-commit, no lint/typecheck config. `black --check` currently fails on 3 files; reformatting everything creates diff noise.

## Architecture (three layers, per README)

- `models/` — plain `@dataclass` containers, no logic. `launch.py` = `VRELaunchRequest` & friends (the only input model), `package.py` = `RequestPackage` (the output consumed by external VRE handlers), `infrastructure.py` = `RuntimePlatform`.
- `parsing/` — `ValidationPipeline` (crate dict → raises `CrateValidationError`), `runtime_platform_from_dict`.
- `building/` — `RocrateBuilder.build_from_launch_request(req)` (VRELaunchRequest → crate dict) and `RequestPackageBuilder.build(crate)` (crate dict → RequestPackage). Despite the package name, `RequestPackageBuilder` is the *parser*; `RocrateBuilder` is the *generator*.

Note: models use stdlib dataclasses even though `pyproject.toml` declares `pydantic`, `fastapi`, `rocrate` — none are imported in `src/`. Follow the dataclass style; don't introduce pydantic.

## Invariants the tests enforce (easy to break)

`tests/test_launch_request_assumptions.py` encodes `plans/vre-launch-request-transformation.md`:

- **Round-trip**: `RocrateBuilder.build_from_launch_request()` output must pass `ValidationPipeline.validate_basic` and be consumable by `RequestPackageBuilder.build` with data preserved.
- **Every `@graph` entity must declare a non-empty `@id`** (RO-Crate 1.1); blank nodes are rejected at parse time by `ValidationPipeline._validate_entity_ids`. Downstream code relies on ids being present and unique — do not add silent tolerance for missing ids elsewhere.
- **Slots vs files**: `ToolMeta.slots` → `FormalParameter` entities (`#input-<slot.id>`); `LaunchInput.files` (free-form) → plain `File` entities in root `hasPart`, never `FormalParameter`. `RequestPackage.input_files` must return **both** slot-bound and free-form files — everything in `files` except the workflow descriptor (itself File-typed; excluded by id only when it has one, so id-less entities are always kept).
- `resolve_vre_type()` in `constants.py`: 3-layer fallback — `raw_definition["vre_type"]` → `tool.types` via `TOOL_TYPE_TO_VRE_TYPE` → URI pattern match; raises `ValueError` if unresolvable.
- `raw_definition` round-trips through the `#tool-metadata` entity; the `"Shared With"` slot additionally produces a `#receiver` Person (OCM/ScienceMesh sharing).
- `RequestPackage` changes must be **additive only** — external VRE handlers (in other repos) read it and must not break.
- The 4 `*_tosca*` fixtures are parse-only; `RocrateBuilder` intentionally cannot generate them (see `plans/fixture-generation-analysis.md`).

## Repo state gotchas

- **README usage snippets are stale** — they use the removed `MinimalVRERequest`/`build_from_minimal` API (tests assert its removal). Trust code + tests over README examples.
- **Test suite is green** (68/68 as of Aug 5 2026): input-files semantics implemented (slot-bound ∪ free-form, descriptor excluded); the sciencemesh `qa.cernbox→eosc.cernbox` test expectation was fixed in the same pass.
- `tests/fixtures/*/simple_example.json` files are legacy (old minimal-request format), unreferenced by current tests — not API examples.
- `build/` and `*.egg-info/` contain stale artifacts from an old flat-layout build; ignore them (gitignored).
- `plans/` holds design docs (untracked); new tests sometimes encode a plan as executable assumptions — check the referenced plan file.

## Testing conventions

Fixtures live in `tests/fixtures/<vre>/ro-crate-metadata.json`; load via `fixtures_dir` fixture / `load_json` from `tests/conftest.py`. Fixture-based tests parametrize over fixture paths (`BUILDER_CASES` in `test_building/test_package.py`).
