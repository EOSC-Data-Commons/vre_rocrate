# vre_rocrate

A Python library for parsing, validating, and building RO-Crate metadata for Virtual Research Environment (VRE) requests.

## Architecture

The library is organized into three layers:

| Layer | Responsibility | Modules |
|-------|---------------|---------|
| **models/** | Pure data containers — `@dataclass` definitions with no logic | `package`, `rocrate`, `minimal`, `infrastructure` |
| **parsing/** | Input processing — turning external formats into models | `rocrate`, `validator`, `infrastructure` |
| **building/** | Output generation — turning models into external formats | `package`, `rocrate` |

### models/

- **package.py** — [`RequestPackage`](src/vre_rocrate/models/package.py), [`WorkflowDescriptor`](src/vre_rocrate/models/package.py), [`FileReference`](src/vre_rocrate/models/package.py), [`FormalParameter`](src/vre_rocrate/models/package.py), [`OCMData`](src/vre_rocrate/models/package.py)
- **rocrate.py** — [`ParsedCrate`](src/vre_rocrate/models/rocrate.py), [`Entity`](src/vre_rocrate/models/rocrate.py)
- **minimal.py** — [`MinimalVRERequest`](src/vre_rocrate/models/minimal.py), [`MinimalFileInput`](src/vre_rocrate/models/minimal.py)
- **infrastructure.py** — [`RuntimePlatform`](src/vre_rocrate/models/infrastructure.py), [`IMInputFile`](src/vre_rocrate/models/infrastructure.py)

### parsing/

- **rocrate.py** — [`ROCrateParser`](src/vre_rocrate/parsing/rocrate.py): parses raw RO-Crate JSON dicts into [`ParsedCrate`](src/vre_rocrate/models/rocrate.py)
- **validator.py** — [`ValidationPipeline`](src/vre_rocrate/parsing/validator.py): validates that a [`ParsedCrate`](src/vre_rocrate/models/rocrate.py) has required fields (mainEntity, programmingLanguage, etc.)
- **infrastructure.py** — [`runtime_platform_from_dict()`](src/vre_rocrate/parsing/infrastructure.py): parses a RO-Crate RuntimePlatform entity dict into a [`RuntimePlatform`](src/vre_rocrate/models/infrastructure.py) dataclass

### building/

- **package.py** — [`RequestPackageBuilder`](src/vre_rocrate/building/package.py): builds [`RequestPackage`](src/vre_rocrate/models/package.py) from either a [`ParsedCrate`](src/vre_rocrate/models/rocrate.py) or a [`MinimalVRERequest`](src/vre_rocrate/models/minimal.py)
- **rocrate.py** — [`RocrateBuilder`](src/vre_rocrate/building/rocrate.py): builds a complete RO-Crate JSON dict from a [`MinimalVRERequest`](src/vre_rocrate/models/minimal.py)

## Usage

### Parse an existing RO-Crate

```python
from vre_rocrate import ROCrateParser, RequestPackageBuilder

crate_dict = {"@context": "...", "@graph": [...]}
parsed = ROCrateParser.parse(crate_dict)
package = RequestPackageBuilder.build(parsed)
```

### Build a RequestPackage from a minimal VRE request

```python
from vre_rocrate import MinimalVRERequest, MinimalFileInput, RequestPackageBuilder

request = MinimalVRERequest(
    vre_type="galaxy",
    workflow="https://example.com/workflow.ga",
    files=[MinimalFileInput(name="data.fastq", url="https://example.com/data.fastq")],
)
package = RequestPackageBuilder.build_from_minimal(request, file_bytes_map={})
```

### Build an RO-Crate from a minimal VRE request

```python
from vre_rocrate import MinimalVRERequest, RocrateBuilder

request = MinimalVRERequest(vre_type="galaxy", workflow="https://example.com/workflow.ga")
crate = RocrateBuilder.build_from_minimal(request)
```

## Design Principles

- **Models are pure data** — no construction logic, no parsing, no I/O
- **Parsing is separate** — all input transformation lives in `parsing/`
- **Building is separate** — all output construction lives in `building/`
- **No framework dependencies** — models use `@dataclass`, not Pydantic or any web framework
