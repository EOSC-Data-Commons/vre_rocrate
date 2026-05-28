# Test Migration Plan: Move Library Tests to vre-rocrate

## Current State

All tests live in the dispatcher repo under `test/unit/`. The following 5 files test only library code and should move to `vre-rocrate`:

| Dispatcher test file | What it tests | Library module |
|---------------------|---------------|----------------|
| `test/unit/test_rocrate_parser.py` | `ROCrateParser.parse()` | `vre_rocrate.parsing.parser` |
| `test/unit/test_rocrate_validator.py` | `ValidationPipeline.validate_basic()` | `vre_rocrate.parsing.validator` |
| `test/unit/test_request_package.py` | `RequestPackage` helpers & serialization | `vre_rocrate.models.package` |
| `test/unit/test_request_package_builder.py` | `RequestPackageBuilder.build()` | `vre_rocrate.building.package` |
| `test/unit/test_minimal_vre.py` | `MinimalVRERequest`, `RocrateBuilder`, `RequestPackage.from_minimal` | `vre_rocrate.models.minimal`, `vre_rocrate.building.rocrate` |

## Tests That Stay in Dispatcher

These test dispatcher-specific code (VRE implementations, services, zip parsing, factory):

- `test_sanity.py`
- `test_zip_parser.py`
- `test_binder.py`
- `test_galaxy.py`
- `test_oscar.py`
- `test_sciencemesh.py`
- `test_im.py`
- `test_vre_factory.py`
- `test_vre_registration.py`

## Fixture Files Needed in Library

The library tests load RO-Crate JSON fixtures. These must be copied:

```
test/
├── galaxy/ro-crate-metadata.json
├── oscar/ro-crate-metadata.json
├── galaxy_tosca/ro-crate-metadata.json
├── scipion_tosca/ro-crate-metadata.json
├── simple-binder/ro-crate-metadata.json
├── jupyter/ro-crate-metadata.json
├── sciencemesh/ro-crate-metadata.json
```

## Proposed Library Test Structure

```
vre-rocrate/
└── tests/
    ├── conftest.py              # Shared fixtures (fixtures_dir, _load_json, galaxy_rocrate_source)
    ├── fixtures/                # Copied RO-Crate JSON files
    │   ├── galaxy/
    │   ├── oscar/
    │   ├── galaxy_tosca/
    │   ├── scipion_tosca/
    │   ├── simple-binder/
    │   ├── jupyter/
    │   └── sciencemesh/
    ├── test_parsing/
    │   ├── test_parser.py       # from test_rocrate_parser.py
    │   └── test_validator.py    # from test_rocrate_validator.py
    ├── test_models/
    │   └── test_package.py      # from test_request_package.py
    └── test_building/
        ├── test_package.py      # from test_request_package_builder.py
        └── test_rocrate.py      # from test_minimal_vre.py (RocrateBuilder + MinimalVRERequest parts)
```

## Execution Steps

1. **Create `tests/` directory** in `vre-rocrate` with `conftest.py`.
2. **Copy fixture JSON files** from dispatcher `test/` to `vre-rocrate/tests/fixtures/`.
3. **Copy and rename test files**:
   - `test_rocrate_parser.py` → `tests/test_parsing/test_parser.py`
   - `test_rocrate_validator.py` → `tests/test_parsing/test_validator.py`
   - `test_request_package.py` → `tests/test_models/test_package.py`
   - `test_request_package_builder.py` → `tests/test_building/test_package.py`
   - `test_minimal_vre.py` → split into:
     - `tests/test_models/test_minimal.py` (MinimalVRERequest validation + RequestPackage.from_minimal)
     - `tests/test_building/test_rocrate.py` (RocrateBuilder tests)
4. **Update imports** in copied tests to use `vre_rocrate` subpackage imports (e.g., `from vre_rocrate.parsing import ROCrateParser`).
5. **Update `pyproject.toml`** to add `pytest` config pointing to `tests/`.
6. **Run library tests** with `pytest`.
7. **Delete the 5 test files** from dispatcher `test/unit/`.
8. **Run dispatcher tests** to confirm nothing is broken.
9. **Commit and push** both repos.

## Notes

- The `galaxy_rocrate_source` fixture (used by `test_rocrate_validator.py`) must be moved to `tests/conftest.py`.
- The `_load_json` helper and `fixtures_dir` fixture are duplicated in multiple test files; they should be consolidated in `conftest.py`.
- `test_minimal_vre.py` mixes model tests (`MinimalVRERequest`), building tests (`RocrateBuilder`), and integration tests (parse → build round-trip). It should be split across `test_models/test_minimal.py` and `test_building/test_rocrate.py`.
