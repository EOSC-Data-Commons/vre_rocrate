# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

`AGENTS.md` holds the same role for other agents. It is good but has drifted in a few
places (see [Stale docs](#stale-docs-what-to-trust)); this file is the corrected copy, and
facts here were verified against the working tree. When the two disagree, believe this one —
and fix `AGENTS.md` rather than adding a third opinion.

## Setup

Nothing in the repo bootstraps itself, and `.venv/` is gitignored, so a fresh clone has no
interpreter. Either documented command fails until you create it:

```console
python3 -m venv .venv && .venv/bin/python -m pip install -e ".[dev]"
```

`uv` is referenced by README but is **not** on PATH here — don't prefix commands with `uv run`.
`uv.lock` exists but is stale (records version 0.1.0; `pyproject.toml` says 0.0.2).

## Commands

```console
.venv/bin/python -m pytest                                    # whole suite (100 tests, green)
.venv/bin/python -m pytest -k sciencemesh                     # by keyword
.venv/bin/python -m pytest tests/test_launch_request_assumptions.py -q          # one file
.venv/bin/python -m pytest tests/test_building/test_payload.py::TestVREPayloadBuilder        # one class
.venv/bin/python -m pytest "tests/test_building/test_payload.py::TestVREPayloadBuilder::test_build_package[galaxy/ro-crate-metadata.json-https://galaxyproject.org/]"  # one param case
.venv/bin/python examples/galaxy.py | jq .                    # print a generated crate
```

Parametrized node IDs are built from the fixture-path tuples in `BUILDER_CASES`
(`tests/test_building/test_payload.py:8`), so quote them — they contain `[`.

Test classes are all `Test*` prefixed. A mistyped node ID exits 4 and a `-k` expression that
matches nothing exits 5 — both non-zero, so nothing passes vacuously, but `--collect-only` is
still the fastest way to find the exact ID.

### Do not run formatters

Black is configured (`line-length = 88`, `target-version = ["py310"]`) but **not enforced** —
no CI, no pre-commit, no lint or typecheck config at all. `black --check .` currently wants
to rewrite **20 of 39 files** — 13 of the 14 scripts in `examples/`, plus both
spec tools (`tools/gen_wire_spec.py`, `tools/wire_spec_lint.py`), which are
"unformatted" alongside deliberately hand-styled code, not because anyone added
noise. Running it
buries your actual change in hundreds of lines of noise.

**Write new and edited lines in the surrounding hand style and leave the rest alone.** The
import-block convention (see `examples/sciencemesh.py:3`) groups several names per line —
black would explode these to one-per-line, so that file is itself "unformatted" on purpose:

```python
from vre_rocrate import (
    VRELaunchRequest, ToolMeta, LaunchInput,
    SlotDefinition, FileInput, RocrateBuilder,
)
```

Import only the names the file actually uses. Only run black when formatting *is* the task.

## What this library is

Pure-stdlib Python (dataclasses; no pydantic, no framework) that sits at the serialization
boundary of the EOSC VRE dispatch stack. There is no CLI, no console script, and **no config
system** — no env vars (`89ed74c "Remove all env var support"` deleted them deliberately),
no config files. Behavior comes entirely from the `VRELaunchRequest` you pass in plus the
hardcoded tables in `constants.py`.

```
req-packager ──VRELaunchRequest──▶ RocrateBuilder ──RO-Crate JSON──▶ dispatcher
                                                                            │
        VRE handlers (separate Dispatcher repo) ◀──VREPayload◀── VREPayloadBuilder
```

The two ends are **separate repos**. `VREPayload` is the contract with external handlers, so
changes to it must be **additive only** — never rename or remove a field or accessor.

Both entry points are static methods:

- `RocrateBuilder.build_from_launch_request(req)` — `VRELaunchRequest` → crate dict
- `VREPayloadBuilder.build(crate_dict, file_bytes_map=None)` — crate dict → `VREPayload`
  (runs `ValidationPipeline.validate_basic` first; raises `CrateValidationError`)

## Architecture traps

These need several files to notice and are the ones that cost the most time.

**The `building/` package contains the parser.** `RocrateBuilder` is the generator,
`VREPayloadBuilder` is the *parser*, despite living under `building/`. `parsing/` holds only
validation (`ValidationPipeline`) and `runtime_platform_from_dict`.

**`vre_type` means two different things.** On the build side it is the short name (`"galaxy"`);
`VREPayload.vre_type` on the parse side is the `ComputerLanguage.identifier` **URL**
(`"https://galaxyproject.org/"`). Verified at runtime — don't compare the two.

**Adding a VRE type = editing `constants.py` tables, not subclassing.** There are no base
classes, registries, or strategy patterns. `resolve_vre_type(tool)`
(`constants.py:83`) is the whole "strategy": 3-layer fallback of
`raw_definition["vre_type"]` → `tool.types` via `TOOL_TYPE_TO_VRE_TYPE` → URI substring
match, raising `ValueError` if unresolvable.

The tables must be kept in sync, and one of them already isn't: **`rrp` is in
`TOOL_TYPE_TO_VRE_TYPE` and `VRE_TYPE_TO_DEFAULT_RUNTIME_PLATFORM` but missing from
`VRE_TYPE_TO_PROGRAMMING_LANGUAGE`** (which defines `VRE_TYPES`). `resolve_vre_type` returns
`"rrp"`, and the builder then silently emits `{"@id": "#rrp-lang", "identifier": "", "name":
"", "url": ""}` — no error, just an empty crate language entity. If you widen these tables,
check every one of them.

**Constructing a `RocrateBuilder` can raise.** `__init__` calls `resolve_vre_type` eagerly
(`building/rocrate.py:73`), before `build()`. `VREPayloadBuilder.__init__` likewise raises a
plain `ValueError` for a missing `mainEntity` — a different exception type from the
`CrateValidationError` that `build()` raises for the same situation via `validate_basic`.

**`SlotValue` is a type alias, not a dataclass** — `str | int | float | bool | FileInput`
(`models/launch.py:47`). The design doc still shows it as `@dataclass(value, file)`; the
"remove slot value dataclass" commit flattened it. `examples/sciencemesh.py` passes bare
strings: `"Shared With": "rwelande@..."`.

**File-bound vs literal slot is decided by resolution, not by `slot_type`.** In
`VREPayload.file_for_input` (`models/payload.py:71`), a *string* `defaultValue` that happens
to equal a file's `@id` is reinterpreted as a file binding.

**A `FileInput` with no `url` is keyed by its bare name** (`building/rocrate.py:55`), so local
files get `@id`s like `notebook.ipynb` (see `examples/jupyter.py`).

`RocrateBuilder` also emits fixed placeholder entities into every crate: `#author-dispatcher`,
`#workflow-hub` ("Example Workflow Hub", `http://example.com/workflows/`), and
`#license-unspecified` — every generated crate asserts an unspecified license.

## Invariants tests enforce

`tests/test_launch_request_assumptions.py` is the executable spec for
`docs/design/vre-launch-request-transformation.md` (status: implemented). It was written
TDD-first against the API before the API existed, and exercises **only the public surface** —
no internal helpers. Keep it that way.

- **Round-trip**: builder output must pass `ValidationPipeline.validate_basic` and be
  consumable by `VREPayloadBuilder.build` with data preserved.
- **Every `@graph` entity needs a non-empty `@id`** (RO-Crate 1.1). Blank nodes are rejected
  at parse time by `ValidationPipeline._validate_entity_ids`. Downstream code depends on ids
  being present and unique — do not add silent tolerance for missing ids elsewhere.
- **Slots vs files.** `ToolMeta.slots` → `FormalParameter` entities (`#input-<slot.id>`),
  referenced from `workflow.input[]`. `LaunchInput.files` → plain `File` entities in root
  `hasPart`, **never** `FormalParameter`. `VREPayload.input_files` must return **both**
  kinds, minus the workflow descriptor. This was originally specified as "slot-referenced
  only" and that was *wrong* — sciencemesh is a slots-and-files tool and needs both.
- `LaunchInput.slots` is keyed by slot **name**, not id; the id only feeds the `@id`.
- `raw_definition` round-trips through the `#tool-metadata` entity. The library builds **no**
  `#receiver` entity and carries **no** `OCMData` — "Shared With" is a plain
  `FormalParameter`, and named domain conventions live on the consumer side.

## Fixture rules

Crates live at `tests/fixtures/<vre>/ro-crate-metadata.json`; load via the `fixtures_dir`
fixture or the `load_json` helper in `tests/conftest.py`. Test subpackages import it as
`from conftest import load_json` (works because `tests/` itself has no `__init__.py`).

The 4 `*_tosca*` fixtures are **parse-only** — `RocrateBuilder` intentionally cannot generate
them, because their `runtimePlatform` is a `{"@id": "#destination"}` entity reference
carrying `processorRequirements`/`memoryRequirements`/staging, whereas the builder always
emits a plain URL string. Planned in `plans/tosca-fixture-generation-support.md`.

`tests/fixtures/*/simple_example.json` are **legacy** old-minimal-request-format files,
unreferenced by any test. They are not API examples — don't copy from them (one still
contains the pre-rename `qa.cernbox` domain).

## `plans/` vs `docs/design/`

`plans/` = pending designs; a plan moves to `docs/design/` once it lands. New tests sometimes
encode a plan as executable assumptions before its implementation exists — check whether the
plan you're reading is in `plans/` before assuming the behavior it describes is real. Both
current plans are unimplemented: `data-centric-launch-request.md` proposes making `tool`
optional (`tool: ToolMeta` is still required) and is internally ambiguous between two
options; `tosca-fixture-generation-support.md` proposes widening `runtime_platform` to
`str | RuntimePlatform | None` (still `str | None`).

## Stale docs — what to trust

**Trust code and tests. README is not an example file.**

- `README.md` is largely stale: its module table lists deleted modules (`models/minimal.py`,
  `models/rocrate.py`, `parsing/rocrate.py`, `building/package.py`) and removed types
  (`MinimalVRERequest`, `MinimalFileInput`, `ROCrateParser`, `ParsedCrate`, `OCMData`), and
  all three usage snippets call `build_from_minimal()` / `ROCrateParser.parse()`, which no
  longer exist. Only the "run examples" command and the layer principles are current.
  `pyproject.toml`'s description still says "minimal-VRE request handling" for the same
  reason.
- `AGENTS.md` is accurate on architecture and invariants. It was verified-stale on the
  test count and the `black --check` scope; both are **corrected here as of Aug 2026**
  (now 100 tests, 20 of 39 files). Still stale on one point: `BUILDER_CASES`
  (says `test_building/test_package.py`; that file is now `test_payload.py`) — left
  as-is because editing `AGENTS.md` for other agents is out of scope for a code
  change, so fix it in its own pass. An earlier version of this list also claimed
  `AGENTS.md`'s `SlotValue` description was out of date; that was wrong — `AGENTS.md`
  does not mention `SlotValue` at all (verified: zero occurrences). The real
  `SlotValue` fact is documented above and in the code.
- `plans/*.md` still use the pre-rename names `RequestPackageBuilder` /
  `building/package.py`.
- `build/` and `src/*.egg-info/` hold stale flat-layout build artifacts (gitignored);
  `PKG-INFO` inside them is an old README and quotes the removed API.

Commit `04ff146 "Transformation to req-packager domain language (#16)"` is the source of most
of this drift. Canonical vocabulary now: `VRELaunchRequest`/`ToolMeta`/`LaunchInput`/
`SlotDefinition`/`FileInput`/`DatasetHandle`, `VREPayload` (was `RequestPackage`),
`VREPayloadBuilder` (was `RequestPackageBuilder`), `models/payload.py` (was
`models/package.py`).

`pyproject.toml` declares `pydantic`, `fastapi`, and `rocrate`, none of which are imported
anywhere in `src/`. They are dead dependencies — leave them, and keep models as stdlib
dataclasses. Don't introduce pydantic.
