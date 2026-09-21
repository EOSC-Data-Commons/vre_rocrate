# 06 · Infrastructure profile

Two profiles share this wire format. They are **alternatives, not layers**: a
crate is one or the other, and a core-profile consumer is entitled to reject an
infrastructure crate outright rather than ignore the parts it does not model.

| | **core** | **infrastructure** |
|---|---|---|
| `runtimePlatform` | a URL string, or absent | a `{"@id": ...}` reference to a `RuntimePlatform` entity |
| `RuntimePlatform` entities in `@graph` | forbidden | required for the reference to resolve |
| schema | `generated/schema-core.json` | `generated/schema-infrastructure.json` |
| emitted by `RocrateBuilder`? | **yes — every example in this repo** | **no** |
| parsed by `VREPayloadBuilder`? | yes | yes |
| extra rules | — | W013 |

Which profile you are holding is **not declared**. `conformsTo` names the RO-Crate
base and the req-packager profile
([`01-conformance.md` §Profiles](01-conformance.md#profiles)) and says nothing
about
this axis — a builder-produced core crate and a hand-authored infrastructure
crate would both declare `https://w3id.org/eosc-vre/req-packager/1.0`. Detection
is therefore by inspection: does the workflow entity's `runtimePlatform` resolve
to a `RuntimePlatform` entity? This library does exactly that
(`building/payload.py:86-93`, `_resolve_runtime_platform`), returning a plain
`str` or a `RuntimePlatform` object accordingly. A producer **SHOULD NOT** rely
on a consumer guessing correctly from anything else.

For calibration on how little can be inferred from `conformsTo`: all four TOSCA
fixtures declare `"conformsTo": {"@id": "https://w3id.org/ro/crate/1.1"}` — a
bare object, not an array, and no profile URI at all. They predate the profile,
so W012 fires on all four and the linter is run against them with W012 withheld
rather than retroactively calling real producer data invalid.

## The core profile is the one that is emitted

`RocrateBuilder` writes `runtimePlatform` as a string, always — from
`VRELaunchRequest.runtime_platform`, falling back to
`VRE_TYPE_TO_DEFAULT_RUNTIME_PLATFORM`
([`05-vre-vocabulary.md` §`vre_type` never appears](05-vre-vocabulary.md#vre_type-never-appears-in-the-crate)).
There is no
code path that produces a `RuntimePlatform` entity.

That asymmetry is the whole point of this file. Four test fixtures
(`galaxy_tosca`, `galaxy_tosca_stage`, `oscar_tosca`, `scipion_tosca`) carry the
infrastructure shape, they parse correctly, and **nothing in this repository can
generate them**. They were authored by hand or came from another producer. A team
building a producer has therefore got no worked example of this profile to copy
from, which is why the inventory below is derived from the fixtures rather than
from the builder.

`plans/tosca-fixture-generation-support.md` proposes widening
`VRELaunchRequest.runtime_platform` from `str | None` to
`str | RuntimePlatform | None` so the builder can emit them. **That is not
implemented** — the annotation is still `str | None`. Treat that plan as a
proposal, and note that it also still uses the pre-rename names
`RequestPackageBuilder` and `building/package.py`.

## What a `RuntimePlatform` entity carries

All four fixtures agree on this shape, from `galaxy_tosca_stage`:

<!-- BEGIN GENERATED excerpt-tosca-runtime-platform -->
*Long free-text values shortened for readability; every `@id`, type and structure is verbatim.*

```json
{
  "@id": "#destination",
  "@type": "RuntimePlatform",
  "name": "Infrastructure Manager",
  "memoryRequirements": "4 GiB",
  "processorRequirements": [
    "2 vCPU",
    "1 GPU"
  ],
  "storageRequirements": "200 GiB",
  "installUrl": "https://raw.githubusercontent.com/grycap/tosca/refs/heads/eosc_dc/templa\u2026",
  "input": [
    {
      "@id": "#tosca_input_file"
    }
  ]
}
```
<!-- END GENERATED -->

`workflow.runtimePlatform` points at it:

<!-- BEGIN GENERATED excerpt-tosca-stage-root -->
```json
{
  "@id": "./",
  "@type": "Dataset",
  "name": "Galaxy Example Workflow",
  "description": "This is an example of a workflow using the Galaxy platform with TOSCA.",
  "datePublished": "2025-05-06T14:35:47+00:00",
  "license": {
    "@id": "https://spdx.org/licenses/GPL-3.0"
  },
  "creator": {
    "@id": "#author-dispatcher"
  },
  "mainEntity": {
    "@id": "https://dockstore.org/api/ga4gh/trs/v2/tools/%23workflow%2Fgithub.com%2Flaitanawe%2Fismb2024%2Fgalaxy_example/versions/main/PLAIN_GALAXY/descriptor//Galaxy-Workflow-reverse_file_galaxy_workflow.ga"
  },
  "hasPart": [
    {
      "@id": "https://dockstore.org/api/ga4gh/trs/v2/tools/%23workflow%2Fgithub.com%2Flaitanawe%2Fismb2024%2Fgalaxy_example/versions/main/PLAIN_GALAXY/descriptor//Galaxy-Workflow-reverse_file_galaxy_workflow.ga"
    },
    {
      "@id": "https://example-files.online-convert.com/document/txt/example.txt"
    }
  ]
}
```
<!-- END GENERATED -->

Every key is read by `parsing/infrastructure.py::runtime_platform_from_dict`, and
all of them are **unread by the core profile** — a core consumer never looks at
these keys, which is what makes the two profiles alternatives:

| key | becomes | notes |
|---|---|---|
| `name` | `RuntimePlatform.name` | defaults to the literal `"Infrastructure Manager"` when absent |
| `installUrl` | `.install_url` | the TOSCA template URL |
| `processorRequirements` | `.num_cpus`, `.num_gpus` | a **list** of strings like `"2 vCPU"`, `"1 GPU"`; `parse_cpu_requirements` parses them, so the strings are load-bearing text, not labels |
| `memoryRequirements` | `.memory` | opaque string, e.g. `"4 GiB"` |
| `storageRequirements` | `.storage` | opaque string |
| `input` | `.input_files` | see below — this is where W013 bites |

`RuntimePlatform` reaches a consumer as `VREPayload.workflow.runtime_platform`,
typed `str | RuntimePlatform | None`. There is **no** top-level
`VREPayload.runtime_platform`, so code written against the wrong level raises
`AttributeError` at runtime.

## W013 — `RuntimePlatform.input` entries are not references

This is the one rule that exists only in this profile, and the fixtures violate
it in real data. An entry is read for `@type` **off itself** and is never
dereferenced:

```python
if raw_file.get("@type") != "File":
    logger.warning("Input is not of type File, skipping.")
    return None
```

`parsing/infrastructure.py::parse_input_file`. The fixtures write the entry as a
reference to a file entity that exists elsewhere in `@graph`:

```json
"input": [{ "@id": "#tosca_input_file" }]
```

That entity carries `@type: "File"` — but the *entry* does not, so the parser
sees no `@type`, logs a warning, and returns `None`. Measured on the real
fixture: `RuntimePlatform.input` has one entry, and
`workflow.runtime_platform.input_files` comes back **empty**. Inlining the same
entity into `input` instead of referencing it yields one parsed file with
`destination: "/opt/data"` and clears W013. Nothing raises; a `logger.warning` is
the only signal, and a producer running without log capture sees nothing at all.

Note the exact `!= "File"` comparison: an entry typed
`["File", "SoftwareSourceCode"]` is skipped just as a reference is. Every other
`@type` check in this library is membership-based, so this is the single place
where a multi-typed entity is not "a File". Rule W013's text says *inline entity
carrying `@type` "File"`* and means it literally.

## The orphan file, in the same fixture

`galaxy_tosca_stage` also demonstrates W008 on real data, which is why this
fixture is worth reading end to end:

<!-- BEGIN GENERATED excerpt-tosca-orphan-file -->
```json
{
  "@id": "#tosca_input_file",
  "@type": "File",
  "name": "simpletext_input",
  "encodingFormat": "text/txt",
  "contentLocation": "/opt/data"
}
```
<!-- END GENERATED -->

`#tosca_input_file` is `File`-typed and is **not** in `root.hasPart`. Under the
core profile it is invisible: `VREPayload.files` never contains it. The
infrastructure profile is what gives it meaning, via `RuntimePlatform.input` —
and W013 then drops it anyway. The net effect for this crate is that the staged
input file reaches neither profile's file list. It is a well-formed crate that
loses a file in both readings.

## Reading guidance

**Consumers**: parse `runtimePlatform` permissively — string, reference, or
absent — and treat a `RuntimePlatform` entity you were not expecting as
something to ignore, not to reject, *unless* you have declared core-only support,
in which case reject explicitly and say why. Silent partial support is how the
`#tosca_input_file` situation becomes invisible.

**Producers**: unless you are the infrastructure-manager side of the protocol,
emit the core profile. If you are, inline your `RuntimePlatform.input` entries
with `@type: "File"`, keep the referenced files in `root.hasPart` as well if any
core consumer needs to see them, and run the linter — W008 and W013 were both
added because real crates in this repo's own fixtures hit them, not as
hypotheticals.
