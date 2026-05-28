# RO-Crate Fixture Cleanup Plan

## Goal
Move all RO-Crate example fixtures from the dispatcher repo to the `vre-rocrate` library, since they are the library's concern, not the dispatcher's.

## Current State

### Dispatcher `test/` RO-Crate fixture directories

| Directory | Used by dispatcher tests? | Used by library tests? | Action |
|-----------|--------------------------|------------------------|--------|
| `alphafind-notebook/` | No | No | **Delete** |
| `galaxy/` | No | Yes (parser, builder, package) | **Delete** (copied to library) |
| `galaxy_and_onedata/` | No | No | **Delete** |
| `galaxy_tosca/` | No | Yes (builder) | **Delete** (copied to library) |
| `galaxy_tosca_stage/` | No | No | **Delete** |
| `jupyter/` | No | Yes (builder) | **Delete** (copied to library) |
| `oscar/` | `cowsay.json` used by `test_oscar.py` | Yes (parser, builder) | **Partial delete**: keep `cowsay.json`, delete `ro-crate-metadata.json` and `simple_example.json` |
| `oscar_tosca/` | No | No | **Delete** |
| `sciencemesh/` | `test_sciencemesh_class.py` (manual script) | Yes (builder) | **Partial delete**: keep `sciencemesh_vre_stub.py` and `test_sciencemesh_class.py`, delete `ro-crate-metadata.json` and `simple_example.json` |
| `scipion_tosca/` | No | Yes (builder) | **Delete** (copied to library) |
| `simple-binder/` | No | Yes (builder, package) | **Delete** (copied to library) |

### Exception: `test/oscar/cowsay.json`

`test/unit/test_oscar.py` loads this file directly:
```python
fdl = load_json("../oscar/cowsay.json")
```

This is an OSCAR FDL (Function Definition Language) file, not an RO-Crate metadata file. It is used to mock the HTTP response when the OSCAR VRE fetches the FDL from a URL. This is dispatcher-specific test data and should stay in the dispatcher repo.

### Exception: `test/sciencemesh/sciencemesh_vre_stub.py` and `test_sciencemesh_class.py`

These are manual test scripts (not pytest tests) that run a Flask app to receive OCM shares. They are dispatcher-specific integration test helpers and should stay.

## Execution Steps

1. **Delete unused RO-Crate fixture directories from dispatcher:**
   ```bash
   rm -rf test/alphafind-notebook/
   rm -rf test/galaxy/
   rm -rf test/galaxy_and_onedata/
   rm -rf test/galaxy_tosca/
   rm -rf test/galaxy_tosca_stage/
   rm -rf test/jupyter/
   rm -rf test/oscar_tosca/
   rm -rf test/scipion_tosca/
   rm -rf test/simple-binder/
   ```

2. **Partial delete `test/oscar/`:**
   ```bash
   rm test/oscar/ro-crate-metadata.json
   rm test/oscar/simple_example.json
   # Keep: test/oscar/cowsay.json
   ```

3. **Partial delete `test/sciencemesh/`:**
   ```bash
   rm test/sciencemesh/ro-crate-metadata.json
   rm test/sciencemesh/simple_example.json
   # Keep: test/sciencemesh/sciencemesh_vre_stub.py, test/sciencemesh/test_sciencemesh_class.py
   ```

4. **Run dispatcher tests** to confirm nothing breaks.

5. **Commit and push** dispatcher repo.

## Result

After cleanup, the dispatcher `test/` directory will only contain:
- Dispatcher-specific test code (`test/unit/`, `test/e2e/`, `test/fixtures/dummy_crate.py`)
- One RO-Crate-unrelated fixture (`test/oscar/cowsay.json`)
- Manual test scripts (`test/sciencemesh/*.py`)
- Integration test helpers (`test/post_zip.py`, `test/README.md`)

All RO-Crate metadata JSON fixtures will live exclusively in `vre-rocrate/tests/fixtures/`.
