"""Generate the machine-readable artefacts under docs/spec/generated/.

The wire format this library emits is a contract with components that do not
use this library, so its description must not be hand-transcribed: the design
note in docs/design/ already drifted from the code (it documents root.name as
<tool.name> where the builder writes "Root dataset for tool: <name>"). This
module derives the normative tables by driving RocrateBuilder over a probe
matrix and observing which keys appear, which makes it self-correcting when
rocrate.py changes.

    .venv/bin/python tools/gen_wire_spec.py            # write artefacts
    .venv/bin/python tools/gen_wire_spec.py --check    # fail if stale (used by tests/test_spec)

Two things cannot be discovered by driving the builder and are hand-maintained,
both marked as such where they appear: the *meaning* of each reserved @id
pattern, and the consumer-side consequences quoted in LINT_RULES.
"""

from __future__ import annotations

import argparse
import ast
import datetime as _dt
import inspect
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
# ROOT as well as src/: derive_goldens imports examples/<name>.py as a namespace
# package so it can read each example's `request` object.
sys.path.insert(0, str(ROOT))

from vre_rocrate import (  # noqa: E402
    DatasetHandle,
    FileInput,
    LaunchInput,
    RocrateBuilder,
    SlotDefinition,
    ToolMeta,
    VRELaunchRequest,
    VREPayloadBuilder,
    WIRE_FORMAT_PROFILE,
    ROCRATE_BASE_PROFILE,
)
from vre_rocrate import constants
from vre_rocrate.building import rocrate as _rocrate_mod
from vre_rocrate.constants import VRE_TYPES

# The lint section now lives in tools/wire_spec_lint.py - a standalone, stdlib-only,
# importable-by-consumers module - and is re-exported here so generation and any
# in-repo caller keep a single source of truth for the rule table.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from wire_spec_lint import (  # noqa: E402
    DECIDED_AT,
    INSEPARABLE,
    LINT_RULES,
    WIRE_FORMAT_PROFILE as LINT_PROFILE,
    as_list,
    lint,
    lint_report,
)

# Two copies of a profile URI is exactly the drift this whole spec exists to
# prevent, so the duplication the consumer-facing linter needs is checked.
assert LINT_PROFILE == WIRE_FORMAT_PROFILE, (
    f"tools/wire_spec_lint.py says {LINT_PROFILE!r}, "
    f"vre_rocrate.constants says {WIRE_FORMAT_PROFILE!r}")

OUTPUT_DIR = ROOT / "docs" / "spec" / "generated"

# ---------------------------------------------------------------------------
# Determinism
#
# RocrateBuilder calls datetime.now(timezone.utc) twice per build - once for
# root datePublished (full ISO) and once for workflow dateCreated (date only).
# Two separate calls can straddle midnight UTC, so a generated crate would
# otherwise depend on the wall clock. Freezing the clock makes output
# byte-stable, which is stronger than scrubbing after the fact: the artefacts
# contain no sentinel placeholders, so they stay valid JSON crates that can be
# fed straight into a parser.
# ---------------------------------------------------------------------------

FROZEN_NOW = _dt.datetime(2000, 1, 1, 0, 0, 0, tzinfo=_dt.timezone.utc)


class _FrozenDateTime(_dt.datetime):
    @classmethod
    def now(cls, tz=None):
        return cls.fromtimestamp(FROZEN_NOW.timestamp(), tz or _dt.timezone.utc)


def freeze_clock() -> None:
    _rocrate_mod.datetime = _FrozenDateTime


# ---------------------------------------------------------------------------
# Probe matrix
#
# Each probe toggles exactly one optional input against a common baseline, so
# the set difference between the baseline observation and the probe
# observation identifies the condition that governs a key. `absent` names the
# variant the probe turns OFF - that is the condition under which a producer
# omits the key.
# ---------------------------------------------------------------------------

_WF_URI = "https://example.org/workflow.ga"
_FILE_URL = "https://example.org/data/input.fastq"
_FREE_URL = "https://example.org/data/attachment.csv"
_DATASET_URL = "https://example.org/dataset/doi/10.5072/test"


def _file(**over) -> FileInput:
    base = dict(name="input.fastq", url=_FILE_URL, size_bytes=1024,
                mime_type="application/fastq", checksum="0" * 64,
                checksum_type="sha256", onedata_domain="one.example.org",
                onedata_file_id="F1234")
    base.update(over)
    return FileInput(**base)


def _request(*, slots=(), values=None, files=None, dataset=None, raw=None,
             platform=None, uri=_WF_URI, description="A workflow.",
             types=("galaxy",)) -> VRELaunchRequest:
    return VRELaunchRequest(
        tool=ToolMeta(id="tool-1", version="1.2.3", name="Probe Tool", uri=uri,
                      types=list(types), description=description,
                      slots=list(slots), raw_definition=dict(raw or {})),
        input=LaunchInput(dataset=dataset, slots=dict(values or {}),
                          files=dict(files or {})),
        runtime_platform=platform,
    )


_SLOT_FILE = SlotDefinition(id="in1", name="Input 1", slot_type="data_file")
_SLOT_TEXT = SlotDefinition(id="lit", name="pdb_id", slot_type="string")
_SLOT_OPT = SlotDefinition(id="opt", name="optional", slot_type="string",
                           is_optional=True)

# Both files in the baseline carry every optional property. If only one did,
# a probe that removed that single carrier would be blamed for every property
# it owned - e.g. clearing slot values would look like the reason
# File.contentSize is conditional.
_BASELINE = _request(
    slots=[_SLOT_FILE, _SLOT_TEXT],
    values={"Input 1": _file(), "pdb_id": "1UBQ"},
    files={"attachment.csv": _file(name="attachment.csv", url=_FREE_URL,
                                   mime_type="text/csv")},
    dataset=DatasetHandle(url=_DATASET_URL, title="A dataset",
                          description="Dataset description"),
    raw={"vre_type": "galaxy"},
    platform="https://galaxy.example.org/",
)

import dataclasses as _dc


def _mutate(**changes) -> Any:
    """Return the baseline request with ONE thing changed.

    Single-variable probes matter: a probe that drops several features at once
    attributes every disappearance to whichever variable it happens to mention,
    which would put false rules in the spec.
    """
    tool = _BASELINE.tool
    inp = _BASELINE.input
    for key, value in changes.items():
        if key == "slots":
            tool = _dc.replace(tool, slots=list(value))
        elif key == "values":
            inp = _dc.replace(inp, slots=dict(value))
        elif key == "files":
            inp = _dc.replace(inp, files=dict(value))
        elif key == "dataset":
            inp = _dc.replace(inp, dataset=value)
        elif key == "raw":
            tool = _dc.replace(tool, raw_definition=dict(value))
        elif key == "uri":
            tool = _dc.replace(tool, uri=value)
        elif key == "types":
            tool = _dc.replace(tool, types=list(value))
        elif key == "platform":
            return _dc.replace(_BASELINE, tool=tool, input=inp,
                               runtime_platform=value)
        else:
            raise KeyError(key)
    return _dc.replace(_BASELINE, tool=tool, input=inp)


def _file_only(**over) -> dict:
    """Changes yielding a request carrying exactly ONE file.

    Exactly one so a per-file condition is not diluted by a second carrier;
    still carrying a filled literal slot so that FormalParameter.defaultValue
    survives the probe - otherwise clearing a file's checksum would be reported
    as a reason defaultValue goes missing.
    """
    return {"slots": [_SLOT_TEXT], "values": {"pdb_id": "1UBQ"},
            "files": {"a": _file(**over)}}


# (id, single change vs baseline, note) - note becomes the human-readable
# condition whenever the probe is what removed a key.
_PROBE_DEFS: list[tuple[str, dict, str]] = [
    ("baseline", {}, "every optional input present"),
    ("no_slots", {"slots": []}, "the tool declares no slots"),
    ("no_files_at_all", {"values": {"pdb_id": "1UBQ"}, "files": {}},
     "neither slot-bound nor free-form files are supplied"),
    ("no_free_form_files", {"files": {}},
     "LaunchInput.files is empty (only slot-bound files exist)"),
    ("file_no_size", _file_only(size_bytes=None),
     "FileInput.size_bytes is None"),
    ("file_no_mime", _file_only(mime_type=None), "FileInput.mime_type is None"),
    ("file_no_checksum", _file_only(checksum=None), "FileInput.checksum is None"),
    ("file_non_sha256_checksum", _file_only(checksum_type="md5"),
     "checksum_type is anything other than 'sha256' - the checksum is "
     "DISCARDED, not emitted under another key"),
    ("file_no_onedata", _file_only(onedata_domain=None, onedata_file_id=None),
     "no onedata placement hints are given"),
    ("file_local_no_url", _file_only(name="local.txt", url=None),
     "FileInput.url is None; the entity is then keyed by its bare name"),
    ("slot_unfilled", {"slots": [_SLOT_FILE], "values": {}},
     "the slot is declared by the tool but not filled by the request"),
    # Adds a third, optional slot rather than substituting one: substituting
    # would delete the baseline's other FormalParameters and make every key
    # they carry look conditionally absent.
    ("slot_optional", {"values": {"Input 1": _file(), "pdb_id": "1UBQ",
                                  "optional": "x"},
                       "slots": [_SLOT_FILE, _SLOT_TEXT, _SLOT_OPT]},
     "SlotDefinition.is_optional is true (emitted as required: false)"),
    ("no_dataset", {"dataset": None}, "LaunchInput.dataset is None"),
    ("no_raw_definition", {"raw": {}}, "ToolMeta.raw_definition is empty"),
    ("workflow_uri_without_extension",
     {"uri": "https://doi.org/10.5281/zenodo.1234567"},
     "the workflow uri has no extension in _EXTENSION_TO_MIME; this also drops "
     "'File' from @type, which stops the workflow appearing in VREPayload.files"),
    ("default_runtime_platform", {"platform": None},
     "VRELaunchRequest.runtime_platform is None; the defaults table supplies it"),
]

# The matrix derives key PRESENCE. Some documented behaviour is about VALUES,
# which presence cannot show, so those probes assert their own claim at
# generation time instead of contributing a condition. If the builder changes
# underneath one, generation fails rather than the prose quietly lying.
PROBE_CLAIMS = {
    "slot_optional": lambda c: any(
        p.get("required") is False for p in c["@graph"]
        if p.get("@type") == "FormalParameter"),
    "default_runtime_platform": lambda c: next(
        e for e in c["@graph"] if e["@id"] == _WF_URI
    )["runtimePlatform"] == constants.VRE_TYPE_TO_DEFAULT_RUNTIME_PLATFORM["galaxy"],
    "file_non_sha256_checksum": lambda c: not any(
        "sha256" in e and e["sha256"] == "0" * 64 for e in c["@graph"]),
}

_PROBES: list[dict[str, Any]] = [
    {"id": pid, "absent": None if pid == "baseline" else note, "note": note,
     "request": _BASELINE if not changes else _mutate(**changes)}
    for pid, changes, note in _PROBE_DEFS
]

# role -> (@id pattern, meaning). Hand-written: driving the builder reveals
# which keys appear, never what an identifier MEANS to a consumer. This is the
# only genuinely hand-maintained table in the generator, and every entry is
# cross-checked two ways - the pattern must still exist as a literal in the
# builder (extract_id_patterns) and the role must still be observed by the
# probe matrix (test_every_known_role_is_observed). A stale entry fails loudly
# instead of rotting quietly, which is the failure mode that got README.md.
ROLES = {
    "root-descriptor": (
        "ro-crate-metadata.json",
        "Crate root descriptor. MUST be the first @graph entity. Declares the "
        "base RO-Crate profile and the wire format profile in conformsTo."),
    "root-dataset": (
        "./",
        "Root dataset. The anchor for the whole payload: mainEntity and hasPart "
        "are read from here and nowhere else."),
    "workflow": (
        "<tool.uri>",
        "The workflow / mainEntity. Its @id IS the workflow uri - there is no "
        "separate identifier - and it is also a root hasPart member."),
    "computer-language": (
        "#<vre_type>-lang",
        "ComputerLanguage carrying the VRE identity token in `identifier`. This "
        "is the ONLY place the target VRE is declared."),
    "formal-parameter": (
        "#input-<slot.id>",
        "A tool-declared input slot. @id derives from slot.id but values are "
        "looked up by slot.name, so id and name are different keys."),
    "file": (
        "<file.url, or the bare name when there is no url>",
        "A data file, reachable ONLY through root hasPart. Slot-bound and "
        "free-form files are structurally identical here and differ only in "
        "whether a FormalParameter's defaultValue points at them."),
    "input-dataset": (
        "<dataset.url>",
        "Optional Dataset for a browsed dataset. @id IS the dataset url."),
    "tool-metadata": (
        "#tool-metadata",
        "Opaque Thing carrying rawDefinition - the producer's own tool "
        "definition, round-tripped untouched."),
    "author-placeholder": (
        "#author-dispatcher",
        "Placeholder Person credited as root creator."),
    "publisher-placeholder": (
        "#workflow-hub",
        "Placeholder Organization carried as sdPublisher."),
    "license-placeholder": (
        "#license-unspecified",
        "Placeholder CreativeWork, emitted because a builder cannot assert a "
        "license on the producer's behalf. Never read by the parser and absent "
        "from every crate not built by this library - an emitter convention, "
        "not a protocol feature."),
}

KNOWN_ROLES = set(ROLES)


def _role(entity: dict, main_id: str, root_parts: set) -> str:
    """Classify an entity by ROLE, not by @type.

    Grouping on @type would merge the root dataset (always present) with the
    optional input-dataset entity (sometimes present) and report the root's
    required keys as conditional. Roles are therefore keyed structurally; the
    names themselves are hand-assigned in KNOWN_ROLES and cross-checked by
    test_every_known_role_is_observed so a new entity shape cannot slip past
    unlabelled.
    """
    eid = entity.get("@id")
    types = entity.get("@type")
    types = [types] if isinstance(types, str) else list(types)
    if eid == "ro-crate-metadata.json":
        return "root-descriptor"
    if eid == "./":
        return "root-dataset"
    if eid == main_id:
        return "workflow"
    if "ComputerLanguage" in types:
        return "computer-language"
    if isinstance(eid, str) and eid.startswith("#input-"):
        return "formal-parameter"
    if eid == "#tool-metadata":
        return "tool-metadata"
    if eid == "#author-dispatcher":
        return "author-placeholder"
    if eid == "#workflow-hub":
        return "publisher-placeholder"
    if isinstance(eid, str) and eid.startswith("#") and eid.endswith("-lang"):
        return "computer-language"
    if "File" in types and eid in root_parts:
        return "file"
    if "Dataset" in types:
        return "input-dataset"
    if "Person" in types:
        return "person"
    if "Organization" in types:
        return "organization"
    if "CreativeWork" in types:
        return "license-placeholder"
    if "Thing" in types:
        return "thing"
    return f"UNCLASSIFIED:{'|'.join(types)}"


def _observe(crate: dict) -> dict[str, dict[str, Any]]:
    """Per ROLE: which keys appear, and every shape seen for each."""
    graph = crate["@graph"]
    root = next(e for e in graph if e.get("@id") == "./")
    main_ref = root.get("mainEntity")
    main_id = main_ref.get("@id") if isinstance(main_ref, dict) else main_ref
    root_parts = {p.get("@id") if isinstance(p, dict) else p
                  for p in root.get("hasPart", [])}

    seen: dict[str, dict[str, Any]] = {}
    for entity in graph:
        role = _role(entity, main_id, root_parts)
        entry = seen.setdefault(role, {"keys": {}, "example_ids": [],
                                       "types": set()})
        t = entity.get("@type")
        entry["types"].add(t if isinstance(t, str) else "|".join(t))
        for k, v in entity.items():
            entry["keys"].setdefault(k, set()).add(_shape(v))
            if k == "@id" and len(entry["example_ids"]) < 3:
                entry["example_ids"].append(v)
    for entry in seen.values():
        entry["keys"] = {k: {"shapes": sorted(v)} for k, v in entry["keys"].items()}
    return seen


def _shape(value: Any) -> str:
    if isinstance(value, dict):
        if set(value) == {"@id"}:
            return "reference"
        return "object"
    if isinstance(value, list):
        if value and all(isinstance(v, dict) and set(v) == {"@id"}
                         for v in value):
            return "list_of_references"
        return f"list_of_{_shape(value[0]) if value else 'anything'}"
    return {str: "string", int: "integer", float: "number", bool: "boolean",
            type(None): "null"}[type(value)]


def derive_entities() -> dict[str, Any]:
    """Drive the probe matrix and derive the role/property catalogue.

    Every probe differs from the baseline in exactly one variable, so a probe
    that removes a key IS the condition for omitting that key.
    """
    freeze_clock()
    observations = {}
    crates = {}
    for probe in _PROBES:
        crates[probe["id"]] = RocrateBuilder.build_from_launch_request(
            probe["request"])
        observations[probe["id"]] = _observe(crates[probe["id"]])

    # Value-level behaviours the presence matrix cannot see. Asserting them here
    # means the prose cannot quietly become a lie.
    broken = sorted(pid for pid, claim in PROBE_CLAIMS.items()
                    if not claim(crates[pid]))
    if broken:
        raise AssertionError(
            "documented value-level claims no longer hold for: "
            + ", ".join(broken)
            + " - either the builder changed or PROBE_CLAIMS is stale")

    baseline = observations["baseline"]
    note_of = {p["id"]: p["note"] for p in _PROBES}
    unknown = sorted(r for r in baseline if r not in ROLES)
    if unknown:
        # The builder started emitting something the spec has no entry for.
        # Refuse to generate rather than write "UNRECOGNISED" into the contract.
        raise AssertionError(
            "probe matrix produced roles with no ROLES entry: "
            + ", ".join(unknown)
            + " - add them to ROLES in tools/gen_wire_spec.py and document them")
    entities: dict[str, Any] = {}
    for role, entry in baseline.items():
        props: dict[str, Any] = {}
        lost_by_whole_entity = [
            p["id"] for p in _PROBES[1:] if role not in observations[p["id"]]
        ]
        # Only probes that STILL emit this role can explain a property of it
        # going missing. A probe that removed the whole role removed its
        # carriers too, and blaming it would invent conditions like
        # "File.contentSize is omitted when the tool declares no slots".
        # Entity-level optionality is recorded separately in emitted_when.
        carriers = [p for p in _PROBES[1:] if role in observations[p["id"]]]
        for key, meta in entry["keys"].items():
            if key == "@id":
                continue
            lost_by = [p["id"] for p in carriers
                       if key not in observations[p["id"]][role]["keys"]]
            props[key] = {
                "status": "required" if not lost_by else "conditional",
                "shapes": meta["shapes"],
                "omitted_when": [note_of[p] for p in lost_by],
                "probes_that_drop_it": lost_by,
            }
        pattern, meaning = ROLES.get(role, (None, "UNRECOGNISED ROLE"))
        entities[role] = {
            "id_pattern": pattern,
            "meaning": meaning,
            "types_observed": sorted(entry["types"]),
            "example_ids": entry["example_ids"],
            "emitted_when": ("always" if not lost_by_whole_entity else
                             "conditional"),
            "omitted_when": sorted({note_of[p] for p in lost_by_whole_entity}),
            "properties": props,
        }
    return {
        "_generated_from": "probe matrix over RocrateBuilder.build_from_launch_request",
        "_probe_count": len(_PROBES),
        "emission_order": _emission_order(),
        "entities": entities,
    }


def _emission_order() -> list[str]:
    freeze_clock()
    crate = RocrateBuilder.build_from_launch_request(_BASELINE)
    return [e["@id"] for e in crate["@graph"]]


# ---------------------------------------------------------------------------
# Vocabulary tables
# ---------------------------------------------------------------------------

def _uri_patterns() -> list[list[str]]:
    """The fallback URI patterns live inside resolve_vre_type, so they have to
    come out of the AST - they are not importable as a module attribute."""
    tree = ast.parse(inspect.getsource(constants.resolve_vre_type))
    for node in ast.walk(tree):
        if isinstance(node, ast.For) and isinstance(node.iter, ast.List):
            return [[a.value, b.value] for a, b in
                    (el.elts for el in node.iter.elts)]
    raise AssertionError("URI fallback table not found in resolve_vre_type")


#: The four collections a consumer actually receives out of a parse. Every
#: probe in this file is judged on all four: measuring only `files` and
#: `input_files` would classify a mutation that empties the slot lists as
#: "tolerated, no loss", which is exactly the silent failure worth reporting.
_PAYLOAD_COUNTS = ("files", "input_files", "workflow_inputs", "workflow_outputs")

#: Distinguishes "no control supplied" from a control that is legitimately None.
_ABSENT = object()


def _describe(value: Any) -> str:
    """Short, stable name for a reference form, for the table's control column."""
    if isinstance(value, dict):
        return "object with @id"
    if isinstance(value, str):
        return "bare string"
    if isinstance(value, list):
        inner = {_describe(v) for v in value}
        return f"list of {len(value)} " + (
            inner.pop() if len(inner) == 1 else "mixed")
    return type(value).__name__


def lint_without(withheld: "str | list[str]", crate: dict) -> list[str]:
    """The linter's verdict on `crate` if those rules did not exist.

    Goes through the linter's own `rules` restriction rather than filtering its
    output, so the counterfactual is the real predicate set minus those rules.
    Filtering would also have to assume the withheld ids appear verbatim in the
    result, which is exactly the kind of string-coupled assumption this file
    exists to avoid: a renamed rule would silently produce a counterfactual
    identical to the real verdict, i.e. a table that quietly stops proving
    anything.
    """
    ids = [withheld] if isinstance(withheld, str) else list(withheld)
    known = {r["id"] for r in LINT_RULES}
    unknown = sorted(set(ids) - known)
    if unknown:
        raise AssertionError(
            f"cannot compute the counterfactual without {unknown}: no such "
            "rule(s) - they were renamed or removed, and a counterfactual that "
            "silently equals the real verdict would make the table meaningless")
    return lint(crate, rules=sorted(known - set(ids)))


def payload_counts(crate: dict) -> dict[str, int]:
    """The sizes of the four parse-path collections, for before/after probes."""
    p = VREPayloadBuilder.build(crate)
    return {"files": len(p.files), "input_files": len(p.input_files),
            "workflow_inputs": len(p.workflow_inputs),
            "workflow_outputs": len(p.workflow_outputs)}


def derive_reference_forms() -> dict[str, Any]:
    """What the parser does when a reference is not the object form it expects.

    JSON-LD permits bare strings and inline objects as well as `{"@id": ...}`, so
    none of these rows is hypothetical. Hand-transcribing the answer is how a spec
    ends up saying "the parser accepts both" - which is what an earlier draft of
    this document claimed - while `hasPart` silently yields zero files. Every row
    below is measured against the real parser during generation, so a change in
    behaviour moves the table or fails here.
    """
    freeze_clock()
    base = RocrateBuilder.build_from_launch_request(_BASELINE)
    main_id = next(e["mainEntity"]["@id"] for e in base["@graph"]
                   if e.get("@id") == "./")

    def measure(entity_id: str, prop: str, value: Any) -> dict[str, Any]:
        import copy as _copy
        crate = _copy.deepcopy(base)
        target = next(e for e in crate["@graph"] if e.get("@id") == entity_id)
        target[prop] = value
        try:
            p = VREPayloadBuilder.build(crate)
            # Counts alone cannot answer "did the form change the DATA". A
            # reference carrying its own name/defaultValue could keep the count
            # identical and still swap the slot's value, which for a workflow
            # payload is the worse bug. Values, not just sizes, are compared.
            slots = sorted([x.name, repr(x.default_value)]
                           for x in [*p.workflow_inputs, *p.workflow_outputs])
            return {"outcome": "parsed",
                    "counts": {"files": len(p.files),
                               "input_files": len(p.input_files),
                               "workflow_inputs": len(p.workflow_inputs),
                               "workflow_outputs": len(p.workflow_outputs)},
                    "slots": slots, "violations": lint(crate)}
        except Exception as exc:  # noqa: BLE001 - the exception IS the result
            return {"outcome": f"{type(exc).__name__}",
                    "detail": str(exc)[:80], "violations": lint(crate)}

    def probe(label: str, entity_id: str, prop: str, value: Any, note: str,
              control: Any = _ABSENT, claim: str | None = None,
              expect: str | None = None) -> dict[str, Any]:
        """One reference form, judged against the object form of the same value.

        The control is what makes "does this form lose data" answerable: the
        identical crate with the identical references spelled `{"@id": ...}`,
        written into its own copy. Comparing against the untouched crate instead
        measures the probe's own bookkeeping - an early version of this table
        scored `input` as a bare string against a one-element list and reported
        2->1, which was the two slots the probe had replaced, not anything the
        string form cost. A row whose counts and slot values both match its
        control is a form the parser genuinely tolerates.

        `control` defaults to the property's current value in the crate, which is
        already the object form for everything the builder writes. Passing one is
        for keys the builder never writes (`output`), and for rows where the
        builder's value differs from the probe in more than the one variable under
        test.

        `claim`/`expect` pin a documented assertion to this row's measurement.
        Without them a row can only ever be descriptive, and a table that merely
        describes today's parser cannot tell a producer that a behaviour it is
        relying on has quietly changed.
        """
        import copy as _copy
        if control is _ABSENT:
            control = _copy.deepcopy(
                next(e for e in base["@graph"]
                     if e.get("@id") == entity_id).get(prop))
        row = {"property": prop, "entity": entity_id, "form": label,
               "note": note, "control_form": _describe(control)}
        ctl = measure(entity_id, prop, control)
        alt = measure(entity_id, prop, value)
        if claim is not None:
            row["claim"] = claim
            outcome = ("identical to control"
                       if ctl.get("slots") == alt.get("slots")
                       and ctl.get("counts") == alt.get("counts") else "differs")
            row["claim_verified"] = (outcome == expect)
            row["measured"] = outcome
            assert row["claim_verified"], (
                f"documented claim {claim!r} for `{prop}` ({label}) no longer "
                f"holds: measured {outcome}, documented {expect!r}. Control slots "
                f"{ctl.get('slots')} vs {alt.get('slots')}. Re-derive the prose "
                "in 04-slots-and-files.md before shipping this table.")
        row["control_counts"] = ctl.get("counts", ctl["outcome"])
        row["outcome"] = alt["outcome"]
        if "detail" in alt:
            row["detail"] = alt["detail"]
        else:
            row["counts"] = alt["counts"]
            if isinstance(ctl["counts"], dict):
                row["lost"] = {k: [ctl["counts"][k], v]
                               for k, v in alt["counts"].items()
                               if v < ctl["counts"][k]}
                # Same size, different data: reported separately from `lost`
                # because a dropped slot and a silently re-labelled slot are
                # different failures and need different wording.
                if ctl.get("slots") != alt.get("slots"):
                    row["changed"] = {"control": ctl.get("slots"),
                                      "alternative": alt.get("slots")}
        row["violations"] = alt["violations"]
        return row

    lang_id = next(e["programmingLanguage"]["@id"] for e in base["@graph"]
                   if e.get("@id") == main_id)
    part_ids = [p["@id"] for p in next(
        e for e in base["@graph"] if e.get("@id") == "./")["hasPart"]]
    param_ids = sorted(
        e["@id"] for e in base["@graph"]
        if "FormalParameter" in ([e["@type"]] if isinstance(e.get("@type"), str)
                                 else e.get("@type") or []))
    assert len(param_ids) >= 2, (
        f"reference-form probes need 2+ real FormalParameters, found {param_ids}")

    rows = [
        probe("bare string", "./", "mainEntity", main_id, "root mainEntity"),
        probe("bare strings", "./", "hasPart", part_ids,
              "root hasPart, all four entries as bare ids"),
        probe("bare string", main_id, "programmingLanguage", lang_id,
              "workflow programmingLanguage"),
        # Each of these passes an explicit control so that exactly one thing
        # changes between the two crates: the form, never the number of
        # references or whether they resolve.
        probe("bare string inside the array", main_id, "input", param_ids[0],
              "workflow input, one slot, as a bare id instead of an object",
              control=[{"@id": param_ids[0]}]),
        probe("bare strings", main_id, "input", param_ids,
              "workflow input, both slots, as bare ids",
              control=[{"@id": i} for i in param_ids]),
        probe("reference to a @id that is not in @graph", main_id, "input",
              [{"@id": "#input-invented"}],
              "workflow input pointing at a missing FormalParameter",
              control=[{"@id": param_ids[0]}]),
        probe("reference to a @id that is not in @graph", main_id, "output",
              [{"@id": "#output-invented"}],
              "workflow output pointing at a missing FormalParameter",
              control=[{"@id": i} for i in param_ids]),
        # Control is the same single reference WITHOUT the inline properties, so
        # the only difference is whether the reference carries name/defaultValue.
        # The claim under test is that those properties are ignored: only `@id` is
        # read, and the graph entity with that @id supplies every value. Asserted
        # below rather than left to the table, because "inline properties are
        # ignored" is a wire-format promise a producer could rely on, and if the
        # parse path ever started honouring them this document would be wrong.
        probe("inline object carrying the properties itself", main_id, "input",
              [{"@id": param_ids[0], "name": "OVERRIDDEN-INLINE",
                "defaultValue": "inline-value"}],
              "input reference that also carries name/defaultValue",
              control=[{"@id": param_ids[0]}],
              claim="inline properties ignored",
              expect="identical to control"),
    ]
    # A control that fails to parse means the row is measuring the harness.
    bad = [f"{r['property']} ({r['form']})" for r in rows
           if not isinstance(r["control_counts"], dict)]
    assert not bad, (
        f"these probes have an unparseable control crate, so their counts mean "
        f"nothing: {bad} - the baseline request no longer emits the shapes the "
        "probes assume")
    # Silence is judged per row against its own control: parses, drops data the
    # control kept, and trips no rule. Derived, so the wording cannot outrun the
    # measurement.
    def lost(r):
        return r.get("lost", {})

    parsed = [r for r in rows if r.get("outcome") == "parsed"]
    loss = [r for r in parsed if lost(r)]
    # Parsed, nothing dropped, but the surviving slots carry different values
    # than under the object form. Counting these as "tolerated" would be the
    # exact mistake the previous version of this table made, one level up.
    altered = [r for r in parsed if not lost(r) and r.get("changed")]
    crashes = [r for r in rows if r.get("outcome") != "parsed"]
    tolerated = [r for r in parsed if not lost(r) and not r.get("changed")]
    silent = [r for r in loss if not r["violations"]]
    silent += [r for r in altered if not r["violations"]]
    # Three categories are load-bearing for the table's argument and must be
    # exercised: a form that is tolerated, a form that fails outright, and a form
    # that parses but loses data. If a parser change ever made every row
    # "tolerated" - plausible, since accepting bare strings is an easy upstream
    # fix - the table would stop carrying information while still rendering as a
    # tidy column, and failing here is the signal to delete it rather than to
    # weaken the check.
    #
    # `silent` is deliberately NOT in that list. An earlier version of this
    # assertion demanded an unreported-loss row exist, which asked the parser to
    # keep a bug so the table would stay interesting: once W011 was widened to
    # cover `output`, every measured loss became reported, and the correct reading
    # of that is "the spec now covers them all", not "a category is missing".
    # Silent losses are reported as a finding; their absence is good news.
    for kind, group in (("tolerated", tolerated), ("fatal", crashes),
                        ("data loss", loss)):
        assert group, (
            f"the reference-form table has no {kind} row, so the distinction it "
            "draws is no longer exercised: either the parser changed shape (good "
            "news - re-derive the prose) or a probe stopped mutating (bad news - "
            "fix the probe)")
    return {
        "_note": "Measured, not asserted. Each row writes one reference form into "
                 "a built crate and runs the real VREPayloadBuilder over it, then "
                 "does the same for the object form of the identical value "
                 "('control_counts'); 'lost' is the difference. Bare-string "
                 f"references are tolerated in {len(tolerated)} position(s) and "
                 f"fatal in {len(crashes)}, which is why a producer MUST use the "
                 "object form everywhere: the acceptance is incidental, not a "
                 "promise, and JSON-LD itself does not distinguish them.",
        "conclusion": {
            "tolerated": [f"{r['property']} on {r['entity']} ({r['form']})"
                          for r in tolerated],
            "fatal": [f"{r['property']} on {r['entity']} ({r['form']})"
                      for r in crashes],
            # Loss is split by whether the linter notices it. A row that loses
            # data AND fires a rule is a documented diagnostic; a row that loses
            # data and fires nothing is the hazard, and the two must not share a
            # key or a reader cannot tell which rows to worry about.
            "data_loss_reported": [f"{r['property']} on {r['entity']} "
                                   f"({r['form']}) -> "
                                   + ", ".join(f"{k} {v[0]}->{v[1]}"
                                               for k, v in lost(r).items())
                                   + f" [{', '.join(r['violations'])}]"
                                   for r in loss if r["violations"]],
            "data_loss_unreported": [f"{r['property']} on {r['entity']} "
                                     f"({r['form']}) -> "
                                     + ", ".join(f"{k} {v[0]}->{v[1]}"
                                                 for k, v in lost(r).items())
                                     for r in silent if lost(r)],
            "values_altered": [f"{r['property']} on {r['entity']} "
                               f"({r['form']}): control slots "
                               f"{r['changed']['control']} become "
                               f"{r['changed']['alternative']}"
                               for r in altered],
        },
        "baseline_counts": payload_counts(base),
        "baseline_main_entity": main_id,
        # Rows are emitted as measured. `lost` is present only on rows that
        # parsed, because a row that raised lost nothing measurable - it lost
        # everything, which `outcome` already says.
        "forms": rows,
        # A table like this one is only evidence if it can fail. These counts are
        # asserted non-trivial so a future change that made every row "tolerated"
        # - e.g. a parser that suddenly resolves bare strings - shows up here as
        # a shrinking number rather than a silently all-green table.
        "non_vacuity": {"rows": len(rows), "tolerated": len(tolerated),
                        "fatal": len(crashes), "data_loss": len(loss),
                        "values_altered": len(altered),
                        "unreported_loss": len(silent)},
    }


def _crate_paths(value: Any, prefix: str = "") -> dict[str, Any]:
    """Flatten a crate to {json-path: scalar} so two builds can be diffed."""
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            out.update(_crate_paths(v, f"{prefix}/{k}"))
        return out
    if isinstance(value, list):
        out = {}
        for i, v in enumerate(value):
            out.update(_crate_paths(v, f"{prefix}[{i}]"))
        return out
    return {prefix: value}


#: Producer-side fields whose serialization is worth pinning, each with the
#: replacement value used to probe it. The probe changes ONE field to a value
#: unlike the baseline's; whatever moves in the crate is the answer to "where does
#: this field go", and nothing moving at all means it is never serialized.
#:
#: A list of (dataclass, attribute, replacement) rather than a table of expected
#: outcomes, so the artefact cannot encode a guess. Every field of every model the
#: producer constructs is included - omitting one would make the absence of a row
#: read as "this one is fine", which is the claim a reader most needs to be true
#: and the one an incomplete list cannot support.
_FIELD_PROBES: list[tuple[str, str, Any]] = [
    ("FileInput", "name", "renamed-by-probe.fastq"),
    ("FileInput", "url", "https://example.org/probe/renamed.fastq"),
    ("FileInput", "path", "/changed/by/probe"),
    ("FileInput", "size_bytes", 999999),
    ("FileInput", "mime_type", "application/x-probe"),
    ("FileInput", "checksum", "a" * 64),
    ("FileInput", "checksum_type", "md5"),
    ("FileInput", "onedata_domain", "probe.onedata.org"),
    ("FileInput", "onedata_file_id", "PROBEFILEID"),
    ("ToolMeta", "id", "tool-renamed-by-probe"),
    ("ToolMeta", "name", "Probed Tool Name"),
    ("ToolMeta", "version", "9.9.9-probe"),
    ("ToolMeta", "uri", "https://example.org/probed-workflow"),
    ("ToolMeta", "description", "Changed by probe."),
    ("SlotDefinition", "id", "probed-slot-id"),
    ("SlotDefinition", "name", "Probed Slot Name"),
    ("SlotDefinition", "slot_type", "probed_type"),
    ("SlotDefinition", "is_optional", True),
    ("DatasetHandle", "url", "https://example.org/probe/dataset"),
    ("DatasetHandle", "title", "Probe dataset title"),
    ("DatasetHandle", "description", "Probe dataset description"),
]


def _payload_surface(crate: dict[str, Any]) -> dict[str, Any]:
    """The parsed payload as {named-field-path: scalar}, for diffing.

    Reuses `_named_field_projection`, whose dropping of `raw_crate`,
    `raw_definition` and the `properties` catch-all dicts is exactly the point
    here: `properties` holds every key in the crate, so diffing it would report
    every serialized field as promoted and collapse the distinction this column
    exists to draw.
    """
    try:
        return _crate_paths(_named_field_projection(crate))
    except Exception as exc:  # noqa: BLE001 - a probe that cannot be parsed IS a finding
        return {"__parse_error__": type(exc).__name__}


#: Shortest probe value allowed to count as reachable when found INSIDE a longer
#: string. `SlotDefinition.id="probed-slot-id"` only ever exists inside the
#: composed `#input-probed-slot-id`, so exact matching would call it unreadable;
#: but a 3-character value like `"md5"` could turn up inside any number of
#: unrelated strings, and an accidental hit would advertise a route that no
#: consumer can actually use. 8 characters is longer than every short probe value
#: that must NOT be matched this way and shorter than the one that must.
_EMBEDDED_MIN = 8


def _via(row: dict[str, Any], route: str) -> bool:
    """True if a probe row's value is reachable through `route`.

    Prefix match, because a route can carry a qualifier - "properties
    (inverted)" is still a route through `properties`, and excluding it would
    file a readable field under "not readable".
    """
    return any(r == route or r.startswith(route + " ")
               for r in row["reachable_via"])


def _value_reachable_via(crate: dict[str, Any], needle: Any) -> list[str]:
    """Every route a consumer could use to get `needle` out of a parsed payload.

    Three routes, in descending order of how much a consumer should trust them,
    and the distinction matters because "not a named field" is NOT "unreadable":

      named field - the parser copied it somewhere documented
      properties  - the per-entity dict the parser fills with `dict(entity)`,
                    so it holds whatever the crate happened to say
      raw_crate   - a verbatim copy of the whole crate, reachable but undocumented

    For a boolean, the complement counts, with a note. `is_optional=True` is
    nowhere in the payload but `required: false` is, and a consumer that reads
    and flips it has the information - reporting that as lost would advertise a
    data-loss bug that a reader could not reproduce.
    """
    from vre_rocrate.models.payload import FormalParameter, FileReference

    probes: list[tuple[Any, bool]] = [(needle, False)]
    if isinstance(needle, bool):
        probes.append((not needle, False))
    # Long values only: a 3-character field could be "found" inside half the
    # crate, and an accidental hit would claim reachability that no consumer has.
    if isinstance(needle, str) and len(needle) >= _EMBEDDED_MIN:
        probes.append((needle, True))

    payload = None
    logging = __import__("logging")
    logging.disable(logging.WARNING)
    try:
        payload = VREPayloadBuilder.build(crate)
    except Exception:  # noqa: BLE001 - unparseable crates report only raw routes
        payload = None
    finally:
        logging.disable(logging.NOTSET)

    routes: list[str] = []
    if payload is not None:
        entities = [payload.workflow, *payload.files, *payload.workflow_inputs,
                    *payload.workflow_outputs]
        containers = [("properties", [p.properties for p in entities]),
                      ("raw_definition", [payload.raw_definition]),
                      ("raw_crate", [payload.raw_crate])]
        for name, blobs in containers:
            for value, embedded in probes:
                if not any(_contains(b, value, embedded=embedded)
                           for b in blobs):
                    continue
                if value is needle and not embedded:
                    routes.append(name)
                elif embedded:
                    routes.append(f"{name} (within a longer value)")
                else:
                    routes.append(f"{name} (inverted)")
                break
    return routes


def _contains(haystack: Any, needle: Any, *, embedded: bool = False) -> bool:
    """Whether `needle` occurs in `haystack`, optionally as part of a string.

    `embedded` exists because some producer fields are CONSUMED INTO a longer
    string on the way out: `SlotDefinition.id="probed-slot-id"` appears nowhere
    as itself, only inside the composed `#input-probed-slot-id`. Searching exactly
    would report that value unreadable through `raw_crate` when the crate plainly
    contains it, and under-reporting reach is the wrong direction to err in - a
    reader told "unreadable" may go copy the field somewhere it already is. A
    route found this way is labelled, because getting the producer's value back
    out of it takes parsing, and only the prefix rule makes that safe.
    """
    if haystack is needle or haystack == needle:
        return True
    if embedded and isinstance(haystack, str) and isinstance(needle, str) \
            and needle and needle in haystack and haystack != needle:
        return True
    if isinstance(haystack, dict):
        return any(_contains(v, needle, embedded=embedded)
                   for v in haystack.values())
    if isinstance(haystack, list):
        return any(_contains(v, needle, embedded=embedded) for v in haystack)
    return False


def _replace_on_baseline(carrier: str, mutations: dict[str, Any]) -> Any:
    """The baseline request with ONE field of ONE nested model replaced.

    Applied to EVERY instance of the carrier, not the first. The baseline carries
    two files, so a probe that poked one of them would report `contentSize` as
    changing while `sha256` did not - which reads like a rule about those two
    properties and is really an artefact of where the probe poked. An empty
    `mutations` dict returns the carrier's own baseline, which is what every row
    is diffed against.
    """
    tool = _BASELINE.tool
    inp = _BASELINE.input

    def patch(obj: Any) -> Any:
        return _dc.replace(obj, **mutations) if mutations else obj

    if carrier == "FileInput":
        # Files live in two places - free inputs, and slot values bound to a
        # file - and a property emitted from either is emitted the same way, so
        # both have to move together for the diff to mean "this field".
        inp = _dc.replace(
            inp,
            files={k: patch(v) for k, v in inp.files.items()},
            slots={k: (patch(v) if isinstance(v, FileInput) else v)
                   for k, v in inp.slots.items()},
        )
    elif carrier == "ToolMeta":
        tool = patch(tool)
    elif carrier == "SlotDefinition":
        tool = _dc.replace(tool, slots=[patch(s) for s in tool.slots])
    elif carrier == "DatasetHandle":
        inp = _dc.replace(inp, dataset=patch(inp.dataset))
    else:  # pragma: no cover - a typo in _FIELD_PROBES
        raise KeyError(f"unknown carrier {carrier!r}")
    return _dc.replace(_BASELINE, tool=tool, input=inp)


def derive_field_visibility() -> dict[str, Any]:
    """Which producer-side fields survive the round trip, and how far they get.

    Written because a hand-typed version of this table got it wrong: it said
    `FileInput.size_bytes` and `checksum` are "not read back", which is true of
    the NAMED fields on FileReference and false of reality, because
    `properties=dict(entity)` copies the whole entity onto every reference. A
    consumer can reach `contentSize` and `sha256` today; a document saying
    otherwise would talk readers out of a dependency that already works.

    Four distances a field can travel, which mean different things to a
    producer:

      absent      - changing the input changes no byte of the crate
      consumed    - the crate changed, but the value is not readable back at all
      properties  - readable, but only through the parser's catch-all dict
      promoted    - readable through a named field of the payload

    "Readable" is measured by searching the parsed payload for the probe value,
    never by reading the parser: a value can be undocumented in the dataclasses
    and still be perfectly reachable, and it can also be dropped outright by a
    conditional nobody documented. `promoted` is measured by diffing parsed
    payload fields, never by matching names - `mime_type` becomes
    `encoding_format`, so name matching would report a real promotion as
    unreadable.

    The tiers are computed, but they are NOT the whole story, and the artefact
    ships `transitions` alongside them because a tier can be technically true and
    still mislead. `SlotDefinition.is_optional` lands in "consumed, not
    serialized" - which sounds like a bug - because the probe value `True` is
    nowhere in the payload. It isn't: the builder negated it into
    `required: false`, which the probe cannot see because it searches for the
    value the producer sent, not for its complement. Read the transitions.
    """
    freeze_clock()
    carriers = ("FileInput", "ToolMeta", "SlotDefinition", "DatasetHandle")
    base_crate = {c: RocrateBuilder.build_from_launch_request(
        _replace_on_baseline(c, {})) for c in carriers}
    base_surface = {c: _payload_surface(cr) for c, cr in base_crate.items()}
    # A probe whose baseline cannot be parsed measures nothing: each row would
    # compare a real payload against a one-key error surface and report the
    # entire payload as "promoted".
    for carrier, surface in base_surface.items():
        assert "__parse_error__" not in surface, (
            f"the baseline crate for the {carrier} probes does not parse")

    # A probe whose replacement equals the baseline's value would report "never
    # serialized" truthfully about nothing - the crate cannot change when the
    # input did not. Cheap to check, and it is the one way this table could be
    # wrong without anything in it being false.
    for carrier, attr, replacement in _FIELD_PROBES:
        holder = {"FileInput": next(iter(_BASELINE.input.files.values())),
                  "ToolMeta": _BASELINE.tool,
                  "SlotDefinition": _BASELINE.tool.slots[0],
                  "DatasetHandle": _BASELINE.input.dataset}[carrier]
        current = getattr(holder, attr)
        assert current != replacement, (
            f"the {carrier}.{attr} probe replaces {current!r} with an equal "
            f"value, so its row would claim 'never serialized' vacuously")

    rows = []
    for carrier, attr, replacement in _FIELD_PROBES:
        crate = RocrateBuilder.build_from_launch_request(
            _replace_on_baseline(carrier, {attr: replacement}))
        before, after = _crate_paths(base_crate[carrier]), _crate_paths(crate)
        changed = sorted(k for k in set(before) | set(after)
                         if before.get(k, _ABSENT) != after.get(k, _ABSENT))
        # Before-and-after per crate path, not just "these paths moved". A
        # directionless diff reads as "this field does something", which cannot
        # tell a remap from a deletion or an inversion, and all three occur here:
        # `slot_type` renames to `additionalType`, `is_optional` is NEGATED into
        # `required` (`building/rocrate.py:221`), and `checksum_type="md5"` deletes
        # the checksum outright (`rocrate.py:202` emits `sha256` only when the type
        # already says sha256). So the transitions are printed and the tier lists
        # below are worded to match them, rather than my guess about them.
        transitions = []
        for k in changed:
            b, a = before.get(k, _ABSENT), after.get(k, _ABSENT)
            t = {
                "path": k,
                # "?" means the key was absent, which is a different claim from
                # "the key is present and holds null" - a crate could in principle
                # do either, and `removed` must not confuse them.
                "from": "?" if b is _ABSENT else b,
                "to": "?" if a is _ABSENT else a,
            }
            if a is _ABSENT:
                t["removed"] = True
            transitions.append(t)
        removed = [t for t in transitions if "removed" in t]
        surface = _payload_surface(crate)
        if "__parse_error__" in surface:
            # Recorded, not swallowed: a field whose new value makes the crate
            # unparseable is a producer-visible fact.
            promoted = [f"__parse_error__:{surface['__parse_error__']}"]
        else:
            base = base_surface[carrier]
            promoted = sorted(
                p for p in set(base) | set(surface)
                if base.get(p, _ABSENT) != surface.get(p, _ABSENT))
        # Where the NEW value can be read back, strongest route first. A field
        # with no route at all was consumed by the builder rather than
        # serialized: the crate changed, but the value did not survive in it.
        via = _value_reachable_via(crate, replacement)
        if promoted and not promoted[0].startswith("__"):
            via.insert(0, "named field")
        rows.append({
            "model": carrier, "field": attr,
            # Recorded so a reader can reproduce the row by hand. NOT _describe,
            # which collapses every str to "bare string" and would throw away the
            # exact value the probe used.
            "probe_value": json.dumps(replacement)[:40],
            "serialized": bool(changed),
            "value_readable_back": bool(via),
            "reachable_via": via,
            # Several crate paths can share a property name, so the names are the
            # readable summary and `transitions` the evidence.
            "crate_keys": sorted({p.rsplit("/", 1)[-1].split("[")[0]
                                  for p in changed}),
            "transitions": transitions[:8],
            "changed_path_count": len(changed),
            "removed_paths": [t["path"] for t in removed][:6],
            "promoted_to": promoted[:6],
            "promoted_count": len(promoted),
        })

    # The probe is only evidence if its outcomes are distinguishable: some fields
    # must appear in the crate and some must not, or the diff is not
    # discriminating and every "never serialized" row in the table is an artefact.
    assert any(r["serialized"] for r in rows), (
        "no probe field appeared in the crate - the builder stopped applying "
        "_replace_on_baseline's mutations, so every row would read 'never "
        "serialized' and the table would be fiction")
    assert any(r["promoted_to"] and not r["promoted_to"][0].startswith("__")
               for r in rows), (
        "no probe field reached a named payload field, which cannot be right "
        "(FileInput.name becomes FileReference.name) - _payload_surface is not "
        "reading the objects it claims to")
    # No assertion that a "consumed but unreadable" row exists: that is a finding
    # about the library, and if someone routes checksum through a named field the
    # right response is the row disappearing from the table, not a red build. The
    # discriminator that DOES need pinning is the route lookup itself - if it
    # matched everything, `reachable_via` would say "properties, raw_crate" for
    # every row including the never-serialized ones, and the strongest claim in
    # the table (named field) would be indistinguishable from the weakest.
    assert not any(not r["serialized"] and r["reachable_via"] for r in rows), (
        "a field that changed no byte of the crate was still reported readable, "
        "so _value_reachable_via is matching something other than the probe value "
        "and every 'reachable_via' in the table is untrustworthy")
    # (The positive direction needs no assertion here: "named field" is inserted
    # exactly when `promoted_to` is non-empty, which is already pinned above.)
    def tier(r: dict[str, Any]) -> str:
        if not r["serialized"]:
            return "never_serialized"
        if not r["value_readable_back"]:
            return "consumed_not_readable"
        if r["promoted_to"] and not r["promoted_to"][0].startswith("__"):
            return "promoted"
        return ("properties_only" if _via(r, "properties")
                or _via(r, "raw_definition") else "raw_crate_only")

    for r in rows:
        r["tier"] = tier(r)
    # The tiers must partition: a row counted twice would let the summary lists
    # contradict the table, and a row in no tier would be silently dropped from
    # every list a reader skims. This checks the classification, not the library,
    # so it fails on a bug in this file rather than on a change of behaviour.
    assert all(r["tier"] in ("promoted", "properties_only", "raw_crate_only",
                             "never_serialized", "consumed_not_readable")
               for r in rows)
    assert set(_tier(rows, "consumed_not_readable")) == {
        f"{r['model']}.{r['field']}" for r in rows
        if r["serialized"] and not r["value_readable_back"]}, (
        "the tier classifier and the readability measurement disagree, so the "
        "summary lists below do not describe the table")
    return {
        "_note": "Each row changes exactly one field of the baseline request and "
                 "diffs the crate that comes out, so 'never_serialized' means "
                 "'changed no byte', not 'nobody looked for it'. Reach is then "
                 "measured by searching the PARSED payload for the value, which "
                 "is a different question from whether a dataclass documents it: "
                 "the parser copies every entity wholesale into a `properties` "
                 "dict, so an undocumented value is usually still readable, and "
                 "'not a named field' must not be reported as 'lost'. That "
                 "conflation is what a hand-typed version of this table got "
                 "wrong. Read `transitions` per row - a tier is a summary of the "
                 "diff, and only the diff shows whether a value was renamed, "
                 "inverted or dropped.",
        "fields": rows,
        # Four tiers, strongest reach first. A producer deciding what to rely on
        # cares about the tier, not about the diff. `_via()` matches on prefix so
        # "properties (inverted)" counts as readable, the way it should.
        "promoted": _tier(rows, "promoted"),
        "properties_only": _tier(rows, "properties_only"),
        "raw_crate_only": _tier(rows, "raw_crate_only"),
        "never_serialized": _tier(rows, "never_serialized"),
        # In the crate, gone on the way back out: the builder read the field, the
        # crate reflects it, and no consumer can read the value.
        "consumed_not_readable": _tier(rows, "consumed_not_readable"),
        # Probes where the crate LOST a property. Only one occurs, but the list
        # is derived because "which fields lose data" is exactly the question a
        # producer cannot answer by reading the builder's conditionals.
        "drops_data": [f"{r['model']}.{r['field']}" for r in rows
                       if r["removed_paths"]],
    }


def _tier(rows: list[dict[str, Any]], name: str) -> list[str]:
    return [f"{r['model']}.{r['field']}" for r in rows if r["tier"] == name]


def derive_slot_bindings() -> dict[str, Any]:
    """How a slot's value is written and re-read, measured at the round trip.

    The producer-side rule "a file-bound slot gets defaultValue {\"@id\": ...}, a
    literal slot gets the literal" is obvious from `building/rocrate.py`. What is
    NOT obvious, and what a consumer implementing from the crate alone will get
    wrong, is that the parse path decides file-bound-ness by *resolution*: it
    takes `defaultValue`, and if that string names a file that exists in the
    crate, the slot reports a file - whatever `additionalType` claimed. Two
    requests below differ only in whether a colliding file is present, which is
    the whole of the difference. Both are built and parsed for real on every
    generation run, so this cannot drift into folklore.
    """
    freeze_clock()

    def roundtrip(req) -> dict[str, Any]:
        crate = RocrateBuilder.build_from_launch_request(req)
        payload = VREPayloadBuilder.build(crate)
        by_name = {p["@id"]: p for p in crate["@graph"]
                   if p.get("@type") == "FormalParameter"}
        out = []
        for fp in payload.workflow_inputs:
            bound = payload.file_for_input(fp)
            out.append({
                "name": fp.name,
                "declared_type": by_name[fp.id].get("additionalType"),
                "default_value": fp.default_value,
                "default_value_json": json.dumps(fp.default_value),
                "file_for_input": bound.id if bound else None,
                "has_defaultValue_key": "defaultValue" in by_name[fp.id],
            })
        return {"slots": out, "input_files": [f.id for f in payload.input_files],
                "violations": lint(crate)}

    file_url = _FILE_URL

    # Case 1: the baseline - one file-bound slot, one literal slot. The intended
    # reading of the format, and the control for everything below.
    intended = roundtrip(_BASELINE)

    # Case 2: a slot DECLARED as a plain string, filled with a string that happens
    # to equal a file's @id, with that file present in the crate.
    collider = roundtrip(_request(
        slots=[SlotDefinition(id="lit", name="looks_literal",
                              slot_type="string")],
        values={"looks_literal": file_url},
        files={"input.fastq": _file()},
        raw={"vre_type": "galaxy"}))

    # Case 3: byte-identical request minus the file. Same slot, same string, same
    # declared type; only the file's presence changes what the slot means.
    no_collider = roundtrip(_request(
        slots=[SlotDefinition(id="lit", name="looks_literal",
                              slot_type="string")],
        values={"looks_literal": file_url},
        files={},
        raw={"vre_type": "galaxy"}))

    # Case 4: a declared slot with no value supplied. The FormalParameter is still
    # emitted and still referenced from workflow.input; only defaultValue is
    # missing, so "absent" and "empty" are indistinguishable downstream.
    unfilled = roundtrip(_request(slots=[_SLOT_FILE, _SLOT_TEXT],
                                  values={"pdb_id": "1UBQ"}, files={},
                                  raw={"vre_type": "galaxy"}))

    def slot(case, name):
        return next(s for s in case["slots"] if s["name"] == name)

    colliding = slot(collider, "looks_literal")
    missing = slot(no_collider, "looks_literal")
    # The two cases exist only to demonstrate the reinterpretation, so they must
    # differ in exactly the file's presence. If a builder change made the emitted
    # JSON identical for both, the claim below would be vacuous.
    assert colliding["default_value_json"] == missing["default_value_json"], (
        "the collider probe no longer isolates one variable: the emitted "
        f"defaultValue differs ({colliding['default_value_json']} vs "
        f"{missing['default_value_json']}) once the file is absent, so the "
        "difference in `file_for_input` is no longer evidence about resolution")
    assert colliding["file_for_input"] and not missing["file_for_input"], (
        "the documented reinterpretation no longer happens: a string "
        "defaultValue equal to a file @id resolved to "
        f"{colliding['file_for_input']!r} with the file present and "
        f"{missing['file_for_input']!r} without it - if the parse path now "
        "consults additionalType, update 04-slots-and-files.md")
    return {
        "_note": "Cases 2 and 3 emit the identical FormalParameter JSON and are "
                 "parsed back differently, because `VREPayload.file_for_input` "
                 "resolves the defaultValue against the crate's files rather than "
                 "reading additionalType. A consumer that decides 'is this slot a "
                 "file?' from the declared type will disagree with this library on "
                 "case 2.",
        "intended": intended,
        "collider_with_file_present": collider,
        "collider_with_file_absent": no_collider,
        "unfilled_slot": unfilled,
        # Each finding is a claim the prose makes, recorded as a boolean so the
        # prose can render "confirmed" without the generator asserting what it
        # observed. A false one renders visibly rather than being dropped.
        "findings": [
            {"claim": "`additionalType` (the declared `slot_type`) is carried "
                      "through to the consumer but never consulted when deciding "
                      "whether a slot is file-bound",
             "confirmed": colliding["declared_type"] == "string"
             and colliding["file_for_input"] is not None},
            {"claim": "two crates with byte-identical `defaultValue` JSON mean "
                      "different things depending on whether a file with that "
                      "`@id` is present",
             "confirmed": colliding["default_value_json"]
             == missing["default_value_json"]
             and bool(colliding["file_for_input"])
             != bool(missing["file_for_input"])},
            {"claim": "a declared slot with no value is still emitted and still "
                      "referenced from `workflow.input`; only `defaultValue` is "
                      "absent, so an unfilled slot and an empty one are "
                      "indistinguishable downstream",
             "confirmed": not slot(unfilled, "Input 1")["has_defaultValue_key"]
             and slot(unfilled, "Input 1")["default_value"] is None},
        ],
    }


def derive_array_forms() -> dict[str, Any]:
    """What happens when a list-valued property is emitted as a single object.

    Serialisers that drop the wrapper for a one-element list are common enough
    that this is a realistic producer bug, and the consequence is not uniform:
    some positions tolerate it, some crash, and some silently return an empty
    collection. Measured here against the real parser so the prose can state
    which is which.

    Also measures the counterfactual - what a consumer would see if W014 did not
    exist - because a table that only ever says "nothing is silent" is
    indistinguishable from a table that failed to notice something, and gives a
    future editor no reason to keep the rule.
    """
    freeze_clock()
    base = RocrateBuilder.build_from_launch_request(_BASELINE)
    main_id = next(e["mainEntity"]["@id"] for e in base["@graph"]
                   if e.get("@id") == "./")

    counts_of = payload_counts      # shared with the reference-form probes

    def probe(prop: str, entity_id: str, note: str,
              seed: Any = None) -> dict[str, Any]:
        import copy as _copy
        # Two crates, one measurement each: the SAME value wrapped as a list
        # (the correct form) and collapsed to a lone element (the bug). Silence
        # is judged between these two, not against the untouched baseline - the
        # `output` row has to seed its own list form first (the builder never
        # emits one), so its correct-form count exists only inside this probe and
        # a shared baseline of 0 would report the collapse as no change.
        list_crate = _copy.deepcopy(base)
        target = next(e for e in list_crate["@graph"]
                      if e.get("@id") == entity_id)
        if seed is not None:
            target[prop] = seed
        original = target[prop]
        row = {"property": prop, "entity": entity_id, "note": note,
               "emitted_as": "list of %d" % len(original)}

        try:
            row["as_list"] = counts_of(list_crate)
        except Exception as exc:  # noqa: BLE001 - the exception IS the result
            row["as_list"] = f"{type(exc).__name__}"
            row["collapsed"] = "not attempted"
            row["violations"] = lint(list_crate)
            return row

        collapsed = _copy.deepcopy(list_crate)
        next(e for e in collapsed["@graph"]
             if e.get("@id") == entity_id)[prop] = original[0]
        try:
            payload_counts = counts_of(collapsed)
            row["collapsed"] = payload_counts
            row["outcome"] = "parsed"
        except Exception as exc:  # noqa: BLE001
            row["collapsed"] = f"{type(exc).__name__}"
            row["outcome"] = f"{type(exc).__name__}"
            row["detail"] = str(exc)[:80]
            row["violations"] = lint(collapsed)
            return row

        row["lost"] = {k: [row["as_list"][k], v]
                       for k, v in payload_counts.items()
                       if v < row["as_list"][k]}
        row["violations"] = lint(collapsed)
        # The same crate judged by a linter that has no W014, i.e. the spec as it
        # stood before this rule. Everything in `lost` that that linter calls
        # clean is a hole W014 closes; the counterfactual is reported so the
        # rule's value stays measurable after the rule itself became load-bearing.
        row["violations_without_W014"] = lint_without("W014", collapsed)
        row["silent_without_W014"] = bool(row["lost"]) and not row["violations_without_W014"]
        return row

    # The `output` row has to be seeded, since the builder never writes the key.
    # The seed addresses real FormalParameter entities from this crate: seeding
    # with a plausible-looking invented id would make the row measure a dangling
    # reference (W011) instead of an array collapse, and would understate the
    # intact-array count, so the collapse would look smaller than it is.
    param_ids = sorted(
        e["@id"] for e in base["@graph"]
        if "FormalParameter" in ([e["@type"]] if isinstance(e.get("@type"), str)
                                 else e.get("@type") or []))
    assert len(param_ids) >= 2, (
        f"the array-forms `output` row needs two real FormalParameters to seed "
        f"with and found {param_ids} - the baseline request no longer declares "
        "at least two slots, so this row would measure one-element collapse "
        "rather than two-to-one")
    rows = [
        probe("hasPart", "./", "root file enumeration"),
        probe("input", main_id, "workflow input slots"),
        probe("output", main_id, "workflow output slots - the builder never "
                                 "emits one, so the list form is seeded here "
                                 "with two real FormalParameter references",
              seed=[{"@id": i} for i in param_ids[:2]]),
        probe("conformsTo", "ro-crate-metadata.json", "root descriptor profiles"),
    ]
    # Silent = accepted, reported clean by the linter, AND strictly less data than
    # the same crate with the array wrapper intact.
    silent = [r for r in rows
              if r.get("outcome") == "parsed" and not r["violations"]
              and r.get("lost")]
    return {
        "_note": "Each row takes one list-valued property and parses the same crate "
                 "twice: with the array wrapper intact ('as_list') and with the "
                 "single element substituted for the array ('collapsed'). 'lost' "
                 "names the parse-path collections that shrank, and 'violations' is "
                 "what the dependency-free linter reports for the mutated crate - an "
                 "empty list beside a non-empty 'lost' means the fault is SILENT at "
                 "every layer this spec controls.",
        "baseline": counts_of(base),
        "silent_after_collapse": [f"{r['property']} on {r['entity']}"
                                  for r in silent],
        "holes_W014_closes": [
            f"{r['property']} on {r['entity']}: workflow data "
            + ", ".join(f"{k} {v[0]}->{v[1]}" for k, v in r["lost"].items())
            for r in rows if r.get("silent_without_W014")],
        "forms": rows,
    }


def derive_unemitted() -> dict[str, Any]:
    """Keys the parser reads off the workflow entity that no request can produce.

    Derived rather than listed by hand: the parser's `.get("key")` calls are
    collected from the AST of the parse path and compared against every key the
    builder emitted anywhere in the probe matrix. A key in the first set and not
    the second is a feature a consumer might implement against and a producer
    could never satisfy, which is worth saying out loud.
    """
    freeze_clock()
    emitted: set[str] = set()
    for probe in _PROBES:
        crate = RocrateBuilder.build_from_launch_request(probe["request"])
        for entity in crate["@graph"]:
            emitted |= set(entity)
    read: set[str] = set()
    for rel in ("building/payload.py", "parsing/validator.py",
                "parsing/infrastructure.py"):
        tree = ast.parse((SRC / rel).read_text())
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "get" and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)):
                key = node.args[0].value
                if key[:1].isalpha() and not key.startswith("onedata:"):
                    read.add((key, rel, node.lineno))
    never = sorted(k for k in read if k[0] not in emitted)
    return {
        "_note": "Keys this library READS from a crate that RocrateBuilder never "
                 "writes, computed by diffing the parse path's `.get(...)` calls "
                 "against every key emitted anywhere in the probe matrix. A "
                 "consumer may implement against these and a producer may still "
                 "never send them, so both sides must treat them as optional. "
                 "They are also how the infrastructure profile stays reachable "
                 "from a crate this builder cannot emit.",
        "read_but_never_emitted": [
            {"key": k, "read_at": f"src/vre_rocrate/{rel}:{ln}"}
            for k, rel, ln in never],
    }


def derive_vocabulary() -> dict[str, Any]:
    lang = constants.VRE_TYPE_TO_PROGRAMMING_LANGUAGE
    return {
        "_note": (
            "programmingLanguage.identifier is the VRE identity token. For "
            "sciencemesh it is an OpenCloudMesh domain, NOT a notebook URL, "
            "while the same language entity's name/url say 'Jupyter Notebook' "
            "- keying on those routes sciencemesh to the wrong handler."),
        "wire_format_profile": WIRE_FORMAT_PROFILE,
        "rocrate_base_profile": ROCRATE_BASE_PROFILE,
        "vre_types": list(VRE_TYPES),
        "programming_language_identifier": lang,
        "language_name": constants.VRE_TYPE_TO_DISPLAY_NAME,
        "language_url": constants.VRE_TYPE_TO_LANGUAGE_URL,
        "default_runtime_platform":
            constants.VRE_TYPE_TO_DEFAULT_RUNTIME_PLATFORM,
        "tool_type_aliases": constants.TOOL_TYPE_TO_VRE_TYPE,
        "uri_fallback_patterns": _uri_patterns(),
        "resolution_order": [
            "raw_definition['vre_type'] if it names a known vre_type",
            "first entry of tool.types present in tool_type_aliases",
            "first uri substring match in uri_fallback_patterns",
            "otherwise the producer raises - no crate is emitted",
        ],
        "known_gaps": _gaps(lang),
    }


def _gaps(lang: dict) -> list[dict[str, str]]:
    """Table desynchronisation is invisible until a consumer sees vre_type
    'unknown', so surface it in the artefact rather than in prose.

    Tables are named by their `constants.py` symbol, not by a friendly label: a
    reader acting on this entry has to go and edit that dict, and a name they can
    grep for is the difference between a two-minute fix and a hunt.
    """
    gaps = []
    for vre in sorted(set(constants.TOOL_TYPE_TO_VRE_TYPE.values())
                      | set(constants.VRE_TYPE_TO_DEFAULT_RUNTIME_PLATFORM)):
        missing = [
            name for name, table in (
                ("VRE_TYPE_TO_PROGRAMMING_LANGUAGE", lang),
                ("VRE_TYPE_TO_DISPLAY_NAME",
                 constants.VRE_TYPE_TO_DISPLAY_NAME),
                ("VRE_TYPE_TO_LANGUAGE_URL", constants.VRE_TYPE_TO_LANGUAGE_URL),
                ("VRE_TYPE_TO_DEFAULT_RUNTIME_PLATFORM",
                 constants.VRE_TYPE_TO_DEFAULT_RUNTIME_PLATFORM),
            ) if vre not in table
        ]
        if missing:
            gaps.append({
                "vre_type": vre,
                "missing_from": missing,
                "consequence": (
                    "the builder emits an empty identifier, validation still "
                    "passes (an empty string is not missing), and consumers "
                    "receive vre_type 'unknown'"),
            })
    return gaps


def derive_mime() -> dict[str, Any]:
    """The extension table, plus proof of what it does and does not govern.

    The claim below was originally hand-written and was WRONG - it said this
    table sets File.encodingFormat on data files. It does not: files copy
    FileInput.mime_type verbatim and nothing ever consults an extension for
    them. So the note is now derived, by building two crates that separate the
    two paths, rather than transcribed.

    """
    freeze_clock()
    # mime_type MUST be withheld here or the probe proves nothing - _file()'s
    # baseline sets it, and a value copied from the request would look exactly
    # like a value inferred from the extension.
    no_mime = RocrateBuilder.build_from_launch_request(_request(
        files={"a": _file(name="a.csv", url=_FILE_URL, mime_type=None)}))
    csv_entity = next(e for e in no_mime["@graph"]
                      if e.get("@id") == _FILE_URL)
    assert "encodingFormat" not in csv_entity, (
        "mime note is stale: a data file DID pick encodingFormat from its "
        "extension, so the extension table now governs files too - update the "
        "note and 02-envelope.md")
    assert csv_entity["@id"].endswith(".fastq"), csv_entity

    unknown_ext = RocrateBuilder.build_from_launch_request(
        _request(uri="https://example.org/wf.weird"))
    wf = next(e for e in unknown_ext["@graph"]
              if e.get("@id") == "https://example.org/wf.weird")
    assert "File" not in wf["@type"], wf["@type"]
    assert "encodingFormat" not in wf, wf
    assert [f.id for f in VREPayloadBuilder.build(unknown_ext).files
            ] == [], "with no File type the workflow must be absent from .files"

    return {
        "_note": ("Applied ONLY to the workflow uri, never to data files. It "
                  "sets the workflow's encodingFormat AND decides whether 'File' "
                  "is prepended to the workflow @type; a uri whose extension is "
                  "absent or unknown yields no 'File' type, which then drops the "
                  "workflow out of VREPayload.files entirely (that list is built "
                  "from hasPart members whose @type includes File). Data files "
                  "take encodingFormat from FileInput.mime_type verbatim and are "
                  "File-typed unconditionally."),
        "applies_to": "workflow uri only",
        "extension_to_mime": dict(_rocrate_mod._EXTENSION_TO_MIME),
    }


def extract_id_patterns() -> dict[str, Any]:
    """Verify each reserved @id shape still exists as a literal in the builder.

    A pattern that no longer appears means either the builder renamed it (a
    breaking protocol change nobody announced) or this table went stale. Both
    are worth failing over.
    """
    source = Path(_rocrate_mod.__file__).read_text(encoding="utf-8")
    literals = {n.value for n in ast.walk(ast.parse(source))
                if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    patterns = []
    for role, (shape, meaning) in ROLES.items():
        probe = shape.split("<")[0]
        patterns.append({
            "role": role,
            "pattern": shape,
            "meaning": meaning,
            "verified_in_builder": any(probe in lit for lit in literals),
        })
    return {
        "reserved": patterns,
        "allocation_rules": [
            "a File's @id is its url, falling back to its bare name when it "
            "has no url - so two nameless-url files sharing a name collide",
            "a File's @id MUST differ from the workflow @id, otherwise the "
            "file disappears from VREPayload.input_files",
            "@id MUST be unique across the whole @graph; duplicates are NOT "
            "rejected by validation",
        ],
    }




# ---------------------------------------------------------------------------
# Negative fixtures - one deliberately-broken crate per rule.
#
# These exist so a consumer team can test THEIR validator, and so this repo can
# prove the linter has teeth: a rule nothing ever violates is indistinguishable
# from a rule that cannot be violated. Each entry states what the crate asserts
# about itself and `derive_negatives` refuses to generate unless the linter
# agrees, which is what stops a predicate from being quietly weakened to always
# pass.
#
# Two of them (W002, W009) are produced by the builder from a plausible request
# rather than by editing JSON. That is deliberate: they demonstrate that the
# mistake is reachable through the public API, which is the whole reason the
# rule is in the spec.
# ---------------------------------------------------------------------------

def _edit(fn):
    """Wrap a mutation of the baseline crate into a zero-arg crate factory."""
    def make() -> dict[str, Any]:
        crate = RocrateBuilder.build_from_launch_request(_BASELINE)
        fn(crate)
        return crate
    return make


def _build_files(**files) -> Any:
    """Build the baseline request with `files` replacing LaunchInput.files."""
    def make() -> dict[str, Any]:
        import dataclasses as dc
        inp = dc.replace(_BASELINE.input, files=dict(files))
        return RocrateBuilder.build_from_launch_request(
            dc.replace(_BASELINE, input=inp))
    return make


def _entity(crate: dict, entity_id: str) -> dict:
    for e in crate["@graph"]:
        if e.get("@id") == entity_id:
            return e
    raise AssertionError(f"baseline crate has no entity {entity_id!r} - the "
                         "builder changed and a negative fixture is stale")


# (rule, label, factory, rules the linter cannot judge once this fault is
#  present). Any additional violation that MUST appear alongside `rule` comes
#  from INSEPARABLE, so that fact is stated once rather than per-fixture.
_NEGATIVE_DEFS: list[tuple[str, str, Any, list[str]]] = [
    ("W001", "a support entity whose @id is the empty string",
     _edit(lambda c: _entity(c, "#license-unspecified").__setitem__("@id", "")),
     []),
    ("W002", "two FileInputs with no url and the same name, so both get "
             "@id = name (reachable through the public API)",
     _build_files(a=FileInput(name="same.txt"), b=FileInput(name="same.txt"),
                  keep=_file(name="keep.txt",
                             url="https://example.org/data/keep.txt")),
     []),
    ("W003", "the root dataset './' is absent entirely",
     _edit(lambda c: c["@graph"].remove(_entity(c, "./"))),
     ["W004", "W005", "W006", "W007", "W008", "W009", "W011"]),
    ("W004", "mainEntity references an entity that is not in @graph",
     _edit(lambda c: _entity(c, "./").__setitem__(
         "mainEntity", {"@id": "#workflow-gone"})),
     ["W005", "W006", "W009", "W011"]),
    ("W005", "programmingLanguage written as a bare string instead of "
             "{\"@id\": ...}",
     _edit(lambda c: _entity(c, _main_id(c)).__setitem__(
         "programmingLanguage", "Python")),
     ["W006"]),
    ("W006", "the language entity exists but its identifier is empty - "
             "validation passes and the consumer gets vre_type 'unknown'",
     _edit(lambda c: _entity(c, "#galaxy-lang").__setitem__("identifier", "")),
     []),
    ("W007", "the root dataset omits hasPart",
     _edit(lambda c: _entity(c, "./").pop("hasPart")),
     ["W008"]),
    ("W008", "a File entity present in @graph but absent from root hasPart. "
             "This is what the TOSCA-authored fixture "
             "galaxy_tosca_stage/ro-crate-metadata.json really contains "
             "(#tosca_input_file); RocrateBuilder never produces it, so a "
             "producer only hits it by hand-rolling the graph",
     _edit(lambda c: _entity(c, "./").__setitem__(
         "hasPart", [p for p in _entity(c, "./")["hasPart"]
                     if p.get("@id") != _baseline_file_id(c)])),
     []),
    ("W009", "a FileInput whose url is the workflow uri, so the file and the "
             "workflow share one @id (reachable through the public API)",
     _build_files(a=FileInput(name="wf.txt", url=_BASELINE.tool.uri),
                  keep=_file(name="keep.txt",
                             url="https://example.org/data/keep.txt")),
     []),
    ("W010", "sha256 truncated to 63 characters",
     _edit(lambda c: _entity(c, _baseline_file_id(c)).__setitem__(
         "sha256", "0" * 63)),
     []),
    ("W011", "workflow.input references a FormalParameter that is not in @graph",
     _edit(lambda c: _entity(c, _main_id(c))["input"].append(
         {"@id": "#input-ghost"})),
     []),
    ("W012", "conformsTo lists only the RO-Crate base profile, so the wire "
             "format version is undeclared",
     _edit(lambda c: _entity(c, "ro-crate-metadata.json").__setitem__(
         "conformsTo", [{"@id": ROCRATE_BASE_PROFILE}])),
     []),
    # RocrateBuilder emits no RuntimePlatform at all, so this one can only be
    # demonstrated by writing the entity the infrastructure profile calls for -
    # which is exactly how the galaxy_tosca_* fixtures came to contain it.
    ("W013", "a RuntimePlatform whose input lists \"{\"@id\": \"#file\"}\" "
             "instead of the file's properties inline; the parser reads @type "
             "off the entry, finds none, and skips it",
     _edit(lambda c: c["@graph"].append({
         "@id": "#destination", "@type": "RuntimePlatform",
         "name": "Infrastructure Manager",
         "input": [{"@id": _baseline_file_id(c)}]})),
     []),
    # Not a hand-authored curiosity: this is what a non-Python serialiser does to
    # a one-element list, which is how a crate ends up with zero slots while
    # looking entirely well-formed to a schema validator.
    ("W014", "workflow.input collapses from a one-element array to the bare "
             "object; the parser iterates the object's members, finds no @id, and "
             "returns no input slots at all",
     _edit(lambda c: _entity(c, _main_id(c)).__setitem__(
         "input", _entity(c, _main_id(c))["input"][0])),
     []),
]


def _main_id(crate: dict) -> str:
    return _entity(crate, "./")["mainEntity"]["@id"]


def _baseline_file_id(crate: dict) -> str:
    """The @id of the first file that is neither the workflow nor the dataset.

    Addressed by role rather than hard-coded, so a change to the baseline
    fixture fails loudly instead of silently retargeting the mutation at some
    other entity.
    """
    parts = [p.get("@id") for p in _entity(crate, "./")["hasPart"]]
    for pid in parts[1:]:
        if pid != _main_id(crate) and "doi" not in pid:
            return pid
    raise AssertionError("baseline crate carries no ordinary file - "
                         "the W008/W010 fixtures cannot be derived")


def derive_negatives() -> dict[str, Any]:
    """Build each broken crate and CONFIRM the linter catches exactly that.

    The assertions here are the point of the function. Returning the crates
    without checking them would produce a fixture directory that looks like
    coverage while proving nothing.
    """
    freeze_clock()
    by_rule = {r["id"]: r for r in LINT_RULES}
    entries: dict[str, Any] = {}
    crates: dict[str, dict[str, Any]] = {}
    for rule, label, factory, undecidable in _NEGATIVE_DEFS:
        if rule not in by_rule:
            raise AssertionError(
                f"negative fixture {rule} has no LINT_RULES entry")
        crate = factory()
        report = lint_report(crate)
        expected = sorted([rule] + INSEPARABLE.get(rule, []))
        if report["violations"] != expected:
            raise AssertionError(
                f"{rule} ({label}): expected violations {expected}, linter "
                f"reported {report['violations']} - either the predicate was "
                "weakened or this fixture no longer demonstrates the rule")
        if sorted(report["undecidable"]) != sorted(undecidable):
            raise AssertionError(
                f"{rule} ({label}): expected undecidable {sorted(undecidable)}, "
                f"linter reported {sorted(report['undecidable'])} - the rule "
                "dependency graph in LINT_RULES is stale")
        entries[rule] = {
            "file": f"negatives/{rule}.json",
            "label": label,
            "expected_violations": expected,
            "expected_undecidable": sorted(undecidable),
        }
        crates[rule] = crate
    return {"entries": entries, "crates": crates}


# ---------------------------------------------------------------------------
# JSON Schema
#
# Two profiles, because one crate either is or is not carrying the
# infrastructure-manager entity, and a consumer wants a single document to point
# at. Both are generated from the same tables as entities.json, so the prose, the
# tables and the schema cannot disagree by accident.
#
# What this artifact CANNOT do, and why the rule linter exists. JSON Schema
# validates one value at a time; six of the rules compare one entity against
# another:
#
#   W002 duplicate @id            W004 mainEntity resolves
#   W006 language has identifier  W008 File listed in hasPart
#   W009 file @id != workflow @id W011 workflow.input references resolve
#
# So a crate can validate against the schema and still be unreadable, and the
# spec says so instead of implying schema-valid means conformance.
# ---------------------------------------------------------------------------

_LINK = {"type": "object", "required": ["@id"],
         "properties": {"@id": {"type": "string", "minLength": 1}},
         "additionalProperties": True}
# runtimePlatform is the one reference-ish key that also accepts a bare URL:
# _resolve_runtime_platform (building/payload.py:86) returns a string as-is and
# dereferences an object. Both occur in the corpus - 22 strings, 4 references -
# and both parse, so both are legal. Every other reference key in the dialect is
# link-only, measured over all 27 goldens.
_RUNTIME_PLATFORM_REF = {"anyOf": [{"type": "string", "minLength": 1}, _LINK]}
# A key that holds one link or a list of them. Measured: creator is a single link
# in 53 places and a list in 1 (galaxy_and_onedata credits two authors), and the
# parser walks either, so both are valid - not an anomaly to be flagged.
_ONE_OR_MORE_LINKS = {"anyOf": [_LINK, {"type": "array", "minItems": 1,
                                        "items": _LINK}]}
_TYPES = {"anyOf": [{"type": "string", "minLength": 1},
                    {"type": "array", "minItems": 1,
                     "items": {"type": "string", "minLength": 1}}]}


def _has_type(name: str) -> dict[str, Any]:
    """Match an entity whose @type IS or CONTAINS `name`.

    Membership, not equality, because that is how this library identifies
    entities: `rocrate.py` writes @type lists ("File", "SoftwareSourceCode",
    "ComputationalWorkflow" for one workflow) and `building/payload.py` tests
    membership when reading them back.

    W013's input items are the deliberate exception - there the parser compares
    @type to the exact string "File", so an item typed ["File"] is skipped. The
    asymmetry is the parser's, and the schema reproduces it rather than tidying
    it away, because a producer needs the schema to fail exactly where the code
    would.
    """
    return {"anyOf": [{"const": name},
                      {"type": "array", "contains": {"const": name}}]}


def _entity_schema(required: list[str], **props: Any) -> dict[str, Any]:
    """An entity that must carry @id/@type plus `required`, and may carry anything.

    additionalProperties is true throughout, not as an afterthought: the fixtures
    carry keys the builder has never emitted (alternateName, onedata:spaceId,
    userid, output, contentLocation, ...). A closed schema would reject real
    crates, which is worse than a loose one - it teaches a producer that valid
    input is invalid.
    """
    return {
        "type": "object",
        "required": sorted({"@id", "@type", *required}),
        "properties": {"@id": {"type": "string", "minLength": 1},
                       "@type": _TYPES, **props},
        "additionalProperties": True,
    }


# Rules no JSON Schema draft can express, because they compare one entity
# against another and a validator only ever sees one value at a time.
GRAPH_ONLY_RULES = {"W002", "W004", "W006", "W008", "W009", "W011"}


def derive_schemas() -> dict[str, Any]:
    """Build both profile schemas.

    Shape rules are the ones that hold for the END-TO-END path, which is
    deliberately stricter than what this library's own validator accepts.
    `programmingLanguage` as a bare string is the clearest case: validate_basic
    passes it and VREPayloadBuilder then crashes, so permitting it in the schema
    would certify a crate that cannot be parsed.
    """
    # Rules are stated as if/then clauses keyed on OBSERVABLE properties, not as
    # one anyOf over "which role might this entity be". A role-guessing anyOf
    # looks equivalent and is not: a permissive catch-all branch (needed for
    # Person/Organization/Thing, which carry almost nothing mandatory) would
    # satisfy the union and let every other branch's constraint go unchecked.
    # Checking all applicable clauses is also the right semantics here - an
    # entity is a File AND carries a sha256, not one or the other.
    def then_(when: dict[str, Any], must: dict[str, Any]) -> dict[str, Any]:
        return {"if": when, "then": must}

    def has_type(name: str) -> dict[str, Any]:
        return {"properties": {"@type": _has_type(name)},
                "required": ["@type"]}
    has_key = lambda name: {"required": [name]}  # noqa: E731

    descriptor_rules = _entity_schema(
        ["about", "conformsTo"],
        about=_LINK,
        # W012 expressed as a constraint rather than left to the linter: a
        # producer that emits a schema-valid crate has declared the profile.
        conformsTo={"type": "array", "minItems": 2,
                    "contains": {"type": "object",
                                 "properties": {"@id": {"const":
                                                        WIRE_FORMAT_PROFILE}},
                                 "required": ["@id"]}})

    # The workflow's required set is NOT taken from the probe matrix: "the builder
    # always writes this" is a fact about the emitter, not about what a parser
    # needs. These are the keys whose absence actually breaks parsing.
    workflow_rules = _entity_schema(
        ["name", "programmingLanguage"],
        # W005. Link ONLY, deliberately stricter than this library's own
        # validator, which accepts a bare string here and then crashes in
        # VREPayloadBuilder. Certifying that shape would validate a crate that
        # cannot be parsed.
        programmingLanguage=_LINK,
        conformsTo=_ONE_OR_MORE_LINKS, creator=_ONE_OR_MORE_LINKS,
        license=_ONE_OR_MORE_LINKS, sdPublisher=_LINK,
        runtimePlatform=_RUNTIME_PLATFORM_REF,
        dateCreated={"type": "string", "format": "full-date"})

    root_rules = _entity_schema(
        # W007: hasPart required, and empty is legal - the builder emits [] for a
        # tool with no files and the parser reads that as zero files.
        ["mainEntity", "hasPart", "datePublished"],
        mainEntity=_LINK, hasPart={"type": "array", "items": _LINK},
        creator=_ONE_OR_MORE_LINKS, license=_ONE_OR_MORE_LINKS,
        datePublished={"type": "string", "format": "date-time"})

    file_rules = _entity_schema(
        ["name"],
        # W010: the rule a producer gets wrong invisibly, because the builder
        # copies FileInput.checksum verbatim and never checks its shape.
        sha256={"type": "string", "pattern": "^[0-9a-f]{64}$"},
        datePublished={"type": "string", "format": "date-time"})

    language_rules = _entity_schema(["identifier", "name", "url"])

    # Every @graph entity, whatever it is: W001 as a shape rule.
    item_base = _entity_schema([])

    # W014: the parse path iterates hasPart/input/output directly, so on ANY
    # entity that carries one of them it MUST be an array. Expressed as its own
    # clause rather than folded into root_rules/workflow_rules because the linter
    # checks these keys wherever they appear - a workflow with a non-list
    # `hasPart`, or a RuntimePlatform with a non-list `input`, is the same bug.
    # Keeping it here also means the schemas and lint_report agree on scope
    # without either one having to enumerate which entity "should" own the key.
    core_clauses = [
        *[then_(has_key(key), {"properties": {key: {"type": "array"}}})
          for key in ("hasPart", "input", "output")],
        then_({"properties": {"@id": {"const": "ro-crate-metadata.json"}},
               "required": ["@id"]}, descriptor_rules),
        then_({"properties": {"@id": {"const": "./"}}, "required": ["@id"]},
              root_rules),
        then_(has_key("programmingLanguage"), workflow_rules),
        then_(has_key("sha256"), file_rules),
        then_(has_type("File"), file_rules),
        then_(has_type("ComputerLanguage"), language_rules),
    ]
    base_graph_item = {"allOf": [item_base, *core_clauses]}

    def must_contain(identifies: dict[str, Any],
                     requires: dict[str, Any]) -> dict[str, Any]:
        """@graph MUST hold at least one entity that IS this thing and IS valid.

        `contains` rather than a length or index: the rest of @graph stays
        unconstrained, and a crate with 20 entities is as valid as one with 8.
        `identifies` picks the entity out by @id or @type; `requires` is what it
        must then carry. Kept apart deliberately - if the identification clause
        also demanded the required keys, a crate whose descriptor is merely
        incomplete would fail with "no matching element found", which points the
        reader at the wrong problem.
        """
        return {"contains": {"allOf": [identifies, requires]},
                "minContains": 1}

    def envelope(extra_clauses: list[dict[str, Any]],
                 extra_contains: list[tuple[dict[str, Any], dict[str, Any]]],
                 defs: dict[str, Any]) -> dict[str, Any]:
        return {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "required": ["@context", "@graph"],
            "properties": {
                "@context": {"const": "https://w3id.org/ro/crate/1.1/context"},
                "@graph": {
                    "type": "array", "minItems": 2,
                    "items": {"allOf": [*base_graph_item["allOf"],
                                        *extra_clauses]},
                    "allOf": [must_contain(i, r) for i, r in [
                        ({"properties": {"@id":
                                         {"const": "ro-crate-metadata.json"}},
                          "required": ["@id"]},
                         {"required": ["about", "conformsTo"]}),
                        ({"properties": {"@id": {"const": "./"}},
                          "required": ["@id"]},
                         {"required": ["mainEntity"]}),
                        (has_type("ComputerLanguage"), {}),
                        *extra_contains]],
                },
            },
            "additionalProperties": True,
            "$defs": defs,
        }

    core_defs = {"descriptor": descriptor_rules, "root": root_rules,
                 "file": file_rules, "link": _LINK,
                 "workflow": workflow_rules, "language": language_rules}
    # The infrastructure profile is recognised by the entity the core emitter
    # cannot produce. Its input array is where W013 bites, and W013 IS
    # expressible here because it constrains the shape of each item, not whether
    # the item resolves.
    runtime_platform_rules = _entity_schema(
        ["name"],
        input={"type": "array",
               "items": {"type": "object", "required": ["@type"],
                         "properties": {
                             # EXACT "File", not a membership test: parsing/
                             # infrastructure.py:40 compares @type != "File", so
                             # an item typed ["File"] is silently skipped. This
                             # is the one place the dialect is not list-tolerant.
                             "@type": {"const": "File"},
                             "contentLocation": {"type": "string"}},
                         "additionalProperties": True}})
    # The two profiles are ALTERNATIVES, deliberately. core forbids a
    # RuntimePlatform outright, so a TOSCA-shaped crate cannot validate against
    # "core" and be pronounced fine while escaping W013, which only the
    # infrastructure schema carries. That is the whole reason there are two
    # documents: one permissive schema would either let TOSCA shapes through
    # unexamined or impose infrastructure rules on crates that have none.
    #
    # A consequence a consumer must know: schema-infrastructure.json REQUIRES a
    # RuntimePlatform, so an ordinary crate fails it. Pick the schema matching the
    # crate; validating against both is not meaningful.
    core = envelope(
        [{"not": has_type("RuntimePlatform")}],
        [], core_defs)
    core["title"] = "req-packager wire format - core profile"
    infra_defs = dict(core_defs, runtimePlatform=runtime_platform_rules)
    infra = envelope(
        [then_(has_type("RuntimePlatform"), runtime_platform_rules)],
        [(has_type("RuntimePlatform"), {})],
        infra_defs)
    infra["title"] = "req-packager wire format - infrastructure profile"
    infra["description"] = (
        "For crates carrying an infrastructure-manager RuntimePlatform. This "
        "profile is PARSEABLE by this library and NOT emittable by it: no "
        "RocrateBuilder input produces a RuntimePlatform entity. Schema "
        "failures here are expected for older TOSCA-authored crates - see "
        "examples.json, whose entries record which crate violates which rule.")

    # Where each rule is enforced, per profile. Three distinct answers, and a
    # checker needs all three:
    #   "entity" - the per-entity clauses reject the broken entity
    #   "graph"  - a @graph `contains` clause rejects the crate (no single entity
    #              is at fault, so testing entities would pass a crate whose root
    #              descriptor is simply absent)
    #   "none"   - needs cross-entity resolution; no draft can express it
    # Rules are then filtered by which profiles they apply to at all: W013
    # constrains a RuntimePlatform, and core REJECTS such entities for being
    # there, which is not the same as enforcing W013.
    graph_only = GRAPH_ONLY_RULES
    applies_to = {r["id"]: ("infrastructure",) if r["id"] == "W013"
                  else ("core", "infrastructure") for r in LINT_RULES}
    enforcement = {
        r["id"]: {"level": r["enforced_by"],
                  "profiles": list(applies_to[r["id"]])
                  if r["enforced_by"] != "none" else []}
        for r in LINT_RULES
    }
    encodable = {
        p: sorted(rid for rid, e in enforcement.items() if p in e["profiles"])
        for p in ("core", "infrastructure")
    }
    all_ids = [r["id"] for r in LINT_RULES]
    return {
        "schema-core.json": {
            **core,
            "description": "The profile RocrateBuilder emits. Validating against "
                           "this is necessary but NOT sufficient: "
                           f"{', '.join(sorted(graph_only))} need cross-entity "
                           "resolution and so cannot be expressed in JSON Schema "
                           "at all. Run the linter too "
                           "(07-producer-checklist.md).",
        },
        "schema-infrastructure.json": infra,
        "schemas.json": {
            "_note": "Which rules JSON Schema can encode, per profile, and which "
                     "it structurally cannot. Schema-valid does NOT mean "
                     "conformant: run the linter as well. 'encodable' and "
                     "'enforcement' are derived from the linter's own rule "
                     "table, and generation refuses to write these schemas "
                     "unless each rule actually behaves the way 'enforcement' "
                     "says at the level it claims, tested against every shipped "
                     "golden and negative. The check needs `jsonschema` and is "
                     "re-derived independently by tests/test_spec.",
            "requires_graph_resolution": sorted(graph_only),
            # rule -> {level: entity|graph|none, profiles: [...]}. `level` says
            # which part of the schema carries the rule, because a checker that
            # only knows "encodable: true" tests entity clauses for a rule that
            # lives in @graph and concludes the schema is broken when it is not.
            "enforcement": enforcement,
            "encodable": encodable,
            "not_encodable_in_any_profile": sorted(
                rid for rid, e in enforcement.items() if not e["profiles"]),
            "rules": all_ids,
            "profiles": {
                "core": "schema-core.json - what RocrateBuilder emits",
                "infrastructure": "schema-infrastructure.json - parseable, "
                                  "not emittable",
            },
        },
    }


def verify_schemas(artefacts: dict[str, Any], goldens: dict[str, Any],
                   negatives: dict[str, Any]) -> dict[str, Any]:
    """Run both schemas over every golden and negative; a mismatch fails generation.

    This is a gate on the artefacts, not content of them: it proves the shipped
    schemas behave the way schemas.json declares BEFORE anything is written, so a
    schema that stopped encoding its rule cannot be committed and left for a test
    to discover later. Its result is printed, never committed - committing it made
    the artefacts depend on the generating machine.

    Generation still never imports jsonschema at module level, so the layer-1
    guarantees (linter, negatives, round-trips) run on a bare interpreter; with
    the dep absent this returns checked=False and generation only notes it.
    """
    try:
        from importlib.metadata import version as _pkg_version
        from jsonschema import Draft202012Validator
        _schema_version = _pkg_version("jsonschema")
    except ImportError:
        return {"checked": False, "checked_against": 0,
                "jsonschema_version": None, "mismatches": [],
                "reason": "jsonschema is not installed, so the schemas are "
                          "shipped but not cross-checked. Install the dev extra "
                          "to populate this. The rule linter is unaffected and "
                          "always runs."}

    schemas = {"core": artefacts["schema-core.json"],
               "infrastructure": artefacts["schema-infrastructure.json"]}
    for schema in schemas.values():
        Draft202012Validator.check_schema(schema)

    enforcement = artefacts["schemas.json"]["enforcement"]

    def crate_error_paths(name: str, crate: dict) -> list[str]:
        return sorted(e.json_path for e in Draft202012Validator(
            schemas[name]).iter_errors(crate))

    def crate_rejected(name: str, crate: dict) -> bool:
        return bool(crate_error_paths(name, crate))

    def entity_rejected(name: str, entity: dict) -> bool:
        item = schemas[name]["properties"]["@graph"]["items"]
        return bool(list(Draft202012Validator(item).iter_errors(entity)))

    mismatches: list[str] = []

    # Each rule is tested at the level schemas.json says carries it, against only
    # the profiles it applies to. Both halves matter: an encoded rule must reject
    # its own negative, and a rule claimed unencoded must NOT be rejected -
    # otherwise the table could claim enforcement nothing provides, and a
    # rejection caused by an unrelated clause would be credited to the rule.
    #
    # Level matters because the two are not interchangeable. W003 ("a root
    # dataset './' exists") is a @graph `contains` clause: no entity in that crate
    # is individually invalid, so checking entities finds nothing and reports the
    # schema as broken when it is working correctly.
    for rule, meta in negatives["entries"].items():
        crate = negatives["crates"][rule]
        graph = crate.get("@graph", [])
        spec = enforcement[rule]
        for name in schemas:
            if name not in spec["profiles"]:
                continue
            if spec["level"] == "graph":
                caught = crate_rejected(name, crate)
            elif spec["level"] == "entity":
                caught = any(entity_rejected(name, e) for e in graph)
            else:
                caught = crate_rejected(name, crate)
            claimed = spec["level"] != "none"
            if caught != claimed:
                mismatches.append(
                    f"{rule} in profile {name}: the schema {spec['level']} "
                    f"clauses {'rejected' if caught else 'accepted'} it, but the "
                    f"rule is claimed {'encoded' if claimed else 'not encoded'}")

    # The goldens, cross-checked the same way tests/test_spec does it: the schema
    # rejects a crate IF AND ONLY IF the linter sees a rule that profile can
    # encode. Catching a divergence here stops a bad schema from ever being
    # committed, instead of leaving it for a test run later.
    encodable = artefacts["schemas.json"]["encodable"]
    for slug, meta in goldens["entries"].items():
        crate = goldens["crates"][slug.split("/", 1)[1]]
        profile = meta["profile"]
        rejected = crate_rejected(profile, crate)
        # Judged under the SAME standard the schema applies - the real profile -
        # because that is what makes the comparison mean anything. examples.json
        # records the separate legacy view as violations_pre_profile; here the
        # question is "do two implementations agree on this crate as shipped",
        # and a fixture that predates the profile URI is non-conformant in both.
        judgable = [v for v in lint(crate) if v in encodable[profile]]
        if rejected != bool(judgable):
            mismatches.append(
                f"{slug}: the {profile} schema rejects it but the linter sees "
                f"{judgable} of the rules that profile encodes ({encodable[profile]})"
                if rejected else
                f"{slug}: the linter sees {judgable}, all encodable in {profile}, "
                "yet its schema accepts the crate")

    # Only the return value that a gate needs. What the goldens looked like is
    # already committed in examples.json; re-committing a per-run judgement of it
    # is what made the artefacts machine-dependent.
    return {
        "checked": True,
        "checked_against": len(negatives["crates"]) + len(goldens["entries"]),
        "jsonschema_version": _schema_version,
        "mismatches": mismatches,
    }


# ---------------------------------------------------------------------------
# Golden example crates
#
# A consumer team that does not use Python cannot run this builder, so the spec
# must ship real crates they can point their parser at. Two kinds, and the
# difference matters: a builder-output golden shows what to EMIT, a fixture
# golden shows what a producer OUT THERE actually SENT. Both are called goldens
# because both are things a consumer's parser must handle.
#
# Provenance is recorded on three axes rather than one boolean, because a single
# `reproducible_by_builder` flag has to mean two unrelated things at once (was
# this file captured from the builder? could the builder express these shapes?)
# and then means neither. Each axis below is DERIVED from observable evidence,
# not asserted by hand.
# ---------------------------------------------------------------------------

# The two keys that carry timestamps, and the shape each takes. Recorded here
# because it is a normative claim about the wire format (section 03) and because
# the schema encodes it: datePublished is an ISO 8601 date-time, dateCreated is
# a date. Verified across all 27 goldens, 13 of each, no exceptions.
TIMESTAMP_KEYS = {"datePublished": "date-time", "dateCreated": "full-date"}


def _sorted_copy(crate: dict[str, Any]) -> dict[str, Any]:
    """Deep copy with @graph sorted by @id.

    Timestamps are NOT scrubbed. The clock is frozen instead, which makes
    builder output byte-stable AND keeps the goldens valid crates - a golden
    carrying "<TIMESTAMP>" would be a string where the spec says date-time, so
    it could not be validated against the schema, which is the main thing a
    non-Python consumer does with these files.

    Sorting is still applied because it costs no validity: @graph order is not
    semantics in JSON-LD, and the normative emission order is published
    separately in entities.json.
    """
    out = json.loads(json.dumps(crate))  # deep copy via JSON, keeps it plain
    out["@graph"] = sorted(out.get("@graph", []),
                          key=lambda e: str(e.get("@id")))
    return out


def _with_timestamps_replaced(crate: dict[str, Any]) -> dict[str, Any]:
    """Same crate with both timestamp keys set to a fixed value."""
    out = json.loads(json.dumps(crate))
    for entity in out.get("@graph", []):
        for key in TIMESTAMP_KEYS:
            if key in entity:
                entity[key] = "2000-01-01"
    return out


def _named_field_projection(crate: dict[str, Any]) -> Any:
    """Parse `crate` and reduce it to named fields only.

    The raw_crate / raw_definition / properties copies are dropped because they
    hold the crate verbatim: comparing them would show a difference for every
    scrubbed timestamp and prove nothing. Comparing only the named fields asks
    the question that matters - did normalisation change any MEANING.
    """
    import dataclasses as dc
    import logging

    # The library warns on its own logger while parsing some fixtures (e.g. the
    # infrastructure parser skipping a RuntimePlatform input). That noise is the
    # subject of section 06, not a generation error, and a --check run that
    # prints it looks like a failure.
    logging.disable(logging.WARNING)
    try:
        payload = VREPayloadBuilder.build(crate)
    finally:
        logging.disable(logging.NOTSET)
    d = dc.asdict(payload)
    d.pop("raw_crate", None)
    d.pop("raw_definition", None)
    if isinstance(d.get("workflow"), dict):
        d["workflow"].pop("properties", None)
    for coll in ("files", "workflow_inputs", "workflow_outputs"):
        for entry in d.get(coll, []):
            entry.pop("properties", None)
    return d


def _types_in(crate: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    for e in crate.get("@graph", []):
        t = e.get("@type")
        out.update([t] if isinstance(t, str) else list(t or []))
    return out


def _emittable_types() -> set[str]:
    """Every @type the builder has ever been observed to emit.

    Gathered by driving it, not by listing what it is supposed to emit, so the
    inventory cannot drift from the code.
    """
    freeze_clock()
    seen: set[str] = set()
    for probe in _PROBES:
        seen |= _types_in(
            RocrateBuilder.build_from_launch_request(probe["request"]))
    return seen


def _capture_examples() -> dict[str, dict[str, Any]]:
    """Rebuild each example's crate in-process, and PROVE it is what the example prints.

    Rebuilt rather than captured from stdout, because a subprocess cannot inherit
    the frozen clock - a golden captured that way would carry a real timestamp and
    `--check` would fail the next day for no reason anyone could read off the
    diff. Freezing the clock here makes the golden both stable and a real crate.

    The subprocess is still run, and its output compared modulo timestamps, so
    "rebuilt from examples/x.py's request" stays an established fact instead of an
    assumption. If an example ever stops going through
    RocrateBuilder.build_from_launch_request, this is where it gets caught.
    """
    import contextlib
    import importlib
    import io
    import subprocess

    freeze_clock()
    captured: dict[str, dict[str, Any]] = {}
    for path in sorted((ROOT / "examples").glob("*.py")):
        module_name = f"examples.{path.stem}"
        try:
            # Every example is a script whose last act is print(json.dumps(...)),
            # so importing it writes a whole crate to stdout. That is the proof we
            # want from the subprocess below, not from the import.
            with contextlib.redirect_stdout(io.StringIO()):
                module = importlib.import_module(module_name)
        except Exception as exc:
            raise AssertionError(
                f"{path.name} cannot be imported: {type(exc).__name__}: {exc}"
                " - every example must expose its request so the golden can be "
                "rebuilt deterministically") from exc
        request = getattr(module, "request", None)
        if request is None:
            raise AssertionError(
                f"{path.name} exposes no module-level `request`, so its crate "
                "cannot be rebuilt under a frozen clock")
        golden = RocrateBuilder.build_from_launch_request(request)

        printed = subprocess.run([sys.executable, str(path)], cwd=str(ROOT),
                                capture_output=True, text=True)
        if printed.returncode != 0:
            raise AssertionError(
                f"{path.name} exited {printed.returncode} when run: "
                f"{printed.stderr.strip().splitlines()[-1:]}")
        try:
            stdout_crate = json.loads(printed.stdout)
        except json.JSONDecodeError as exc:
            raise AssertionError(
                f"{path.name} did not print exactly one JSON object, so the "
                "golden and the example would disagree") from exc
        if _with_timestamps_replaced(golden) != _with_timestamps_replaced(
                stdout_crate):
            raise AssertionError(
                f"{path.name} prints a crate that differs from what "
                "RocrateBuilder.build_from_launch_request(request) returns, "
                "ignoring timestamps - the example does something the golden "
                "cannot capture, so document it as fixture-input instead")

        captured[path.stem] = golden
    return captured


def _iter_fixtures() -> Any:
    """Yield (output-slug, real-repo-path, crate) for every fixture crate.

    The slug keeps the whole path (directory AND filename, "/" folded to "__")
    rather than abbreviating the common case, because "galaxy" as a directory
    name is also the name of examples/galaxy.py - shortening one side made the
    two collide and overwrite each other's golden.

    The real path is yielded alongside it, NOT derived from the slug. Folding
    "/" to "__" is not reversible (`galaxy/ro-crate-metadata.json` and a
    hypothetical `galaxy_rocrate/…` would be indistinguishable), and the slug is
    an output filename, not a location. Reconstructing `tests/fixtures/<slug>`
    from it produced a path that exists nowhere in the repo, which the spec's own
    path-citation test rejected once the golden index started printing sources.
    """
    for path in sorted((ROOT / "tests" / "fixtures").glob(
            "**/ro-crate-metadata*.json")):
        rel = path.relative_to(ROOT / "tests" / "fixtures").as_posix()
        yield (rel.replace("/", "__"), path.relative_to(ROOT).as_posix(),
               json.loads(path.read_text(encoding="utf-8")))


def derive_goldens() -> dict[str, Any]:
    """Produce every golden crate plus its provenance sidecar.

    Generation FAILS rather than proceeds if a golden does not parse, or if
    normalising one changes its meaning. A golden that a consumer's parser
    rejects would teach the consumer the wrong lesson.
    """
    emittable = _emittable_types()
    # The baseline probe request, as a golden. It exists because two documented
    # entities - input-dataset and tool-metadata - appear in NO example: all 14
    # scripts pass raw_definition={} and none passes a DatasetHandle, so the spec
    # would otherwise document two shapes with nothing to point at. A consumer
    # reading "rawDefinition round-trips untouched" with no example has to trust
    # us; with one they can diff against it.
    sources: list[tuple[str, str, str, dict[str, Any]]] = [
        (name, "builder-output", f"examples/{name}.py", crate)
        for name, crate in _capture_examples().items()
    ] + [
        ("probe_every_optional_input", "builder-output",
         "tools/gen_wire_spec.py::_BASELINE (the probe matrix's superset case)",
         RocrateBuilder.build_from_launch_request(_BASELINE)),
    ] + [
        # `real` verbatim, not rebuilt from the slug - see _iter_fixtures.
        (slug, "fixture-input", real, crate)
        for slug, real, crate in _iter_fixtures()
    ]
    seen_names = [n for n, _, _, _ in sources]
    if len(set(seen_names)) != len(seen_names):
        dupes = sorted({n for n in seen_names
                        if seen_names.count(n) > 1})
        raise AssertionError(
            "two goldens want the same filename: " + ", ".join(dupes)
            + " - a collision would silently drop one of them")

    entries: dict[str, Any] = {}
    crates: dict[str, dict[str, Any]] = {}
    for name, origin, source, crate in sources:
        # Fixture names arrive as "dir/ro-crate-metadata[-x].json"; example
        # names are bare module stems. Normalise both to one .json filename.
        slug = name if name.endswith(".json") else f"{name}.json"
        types = _types_in(crate)
        unemittable = sorted(types - emittable)
        # The infrastructure profile is defined by the shape the core emitter
        # cannot produce - a RuntimePlatform entity - not by the file's name.
        profile = "infrastructure" if unemittable else "core"
        try:
            original_projection = _named_field_projection(crate)
        except Exception as exc:
            raise AssertionError(
                f"golden {name} does not parse: {type(exc).__name__}: {exc}") from exc

        # Two separate claims, both worth asserting, because they fail for
        # different reasons and a consumer needs to know which one broke.
        #   (a) @graph order carries no meaning - the goldens are sorted, so if
        #       this fails, sorting one would mislead a consumer.
        #   (b) the timestamp VALUES carry no meaning - which is what lets a
        #       golden be replayed against a fixture captured on another day.
        golden = _sorted_copy(crate)
        try:
            sorted_projection = _named_field_projection(golden)
        except Exception as exc:
            raise AssertionError(
                f"golden {name} parses but its @graph-sorted copy does not: "
                f"{type(exc).__name__}: {exc} - this dialect's semantics depend "
                "on @graph order, which contradicts section 02") from exc
        if sorted_projection != original_projection:
            raise AssertionError(
                f"sorting @graph changed the named-field projection of golden "
                f"{name}, so @graph order IS load-bearing and the goldens must "
                "stop being sorted")
        # Checked positively. "The projection is unchanged when the timestamps
        # are rewritten" cannot fail while no projection field holds a date at
        # all, and a check that cannot fail is not evidence. What is falsifiable -
        # and fails the day someone maps a date into the payload - is that no
        # named field carries a date, which is exactly what makes the two
        # timestamps descriptive for anyone consuming VREPayload.
        if re.search(r"20\d\d-\d\d-\d\d", json.dumps(original_projection)):
            raise AssertionError(
                f"golden {name} surfaces a date in a NAMED field of VREPayload, "
                "so datePublished/dateCreated are not purely descriptive - "
                "section 03 must stop calling them metadata, and 01 must say "
                "whether a consumer may compare them")

        # hasPart ORDER is a different matter from @graph order, and the opposite
        # answer: _extract_files walks hasPart, so the array's order is the order
        # VREPayload.files comes back in. Perturbing it MUST change the
        # projection. If it ever stops changing it, hasPart has become a set
        # somewhere in the parser and section 04 needs rewriting - which is why
        # this is asserted rather than written down once and believed.
        # State the rule directly instead of perturbing and hoping to notice:
        # VREPayload.files is hasPart, filtered to File-typed entities, in order.
        # An equality says exactly what a producer must get right, whereas "a
        # reversal changed something" fired on replay_github, whose hasPart holds
        # the workflow plus a single file - swapping those cannot reorder a list
        # that contains one of them.
        parts = next((e.get("hasPart") for e in crate.get("@graph", [])
                      if e.get("@id") == "./"), [])
        by_id = {e.get("@id"): e for e in crate.get("@graph", [])}
        expected_order = []
        for ref in parts if isinstance(parts, list) else [parts]:
            pid = ref.get("@id") if isinstance(ref, dict) else ref
            entity = by_id.get(pid) or {}
            t = entity.get("@type")
            if "File" in ([t] if isinstance(t, str) else list(t or [])):
                expected_order.append(pid)
        actual_order = [f["id"] for f in original_projection["files"]]
        if actual_order != expected_order:
            raise AssertionError(
                f"golden {name}: VREPayload.files came back as {actual_order} "
                f"but hasPart lists {expected_order} - the rule 'files follows "
                "hasPart order' is wrong, or this crate needs localising first")

        if origin == "builder-output":
            clean = lint_report(crate)
            if clean["violations"]:
                raise AssertionError(
                    f"golden {name} comes from the builder yet violates "
                    f"{clean['violations']} - the spec would then document a "
                    "crate its own emitter produces and its own rules forbid")
        entries[f"examples/{slug}"] = {
            "origin": origin,
            "source": source,
            "profile": profile,
            # True when nothing in this crate is beyond the builder's reach, so
            # `origin: fixture-input` + True means "observed, and we could have
            # written it too".
            "builder_can_emit_all_types": not unemittable,
            "types_not_emittable": unemittable,
            "declares_wire_profile": WIRE_FORMAT_PROFILE in [
                (c.get("@id") if isinstance(c, dict) else c)
                for c in as_list(next(
                    (e for e in crate.get("@graph", [])
                     if e.get("@id") == "ro-crate-metadata.json"), {})
                    .get("conformsTo"))],
            "violations_pre_profile": lint_report(crate, profile=None)[
                "violations"],
            # Both proven during generation, not assumed: see the assertions
            # above. A consumer can therefore treat @graph order and the two
            # timestamp values as non-semantic.
            # Asserted during generation, not assumed. Note the asymmetry: @graph
            # order and the two timestamp values are ignored by this library's
            # parser, while hasPart ORDER is not - it fixes VREPayload.files order.
            "ignored_by_this_library": ["@graph order", "datePublished value",
                                        "dateCreated value"],
            "order_is_meaningful": ["root hasPart -> VREPayload.files order"],
        }
        crates[slug] = golden
    return {"entries": entries, "crates": crates,
            "emittable_types": sorted(emittable)}


# ---------------------------------------------------------------------------
# Source provenance
#
# Every normative claim in the spec points at code. Hand-typed line numbers rot
# silently - the design note in docs/design/ is the cautionary example - so
# rules cite (file, symbol) and the line is resolved from the live tree here.
# Generation raises if a cited symbol no longer exists, which converts "the
# spec drifted" into a build failure instead of a misleading document.
# ---------------------------------------------------------------------------

SRC = ROOT / "src" / "vre_rocrate"


def resolve_symbol(rel_path: str, symbol: str) -> dict[str, Any]:
    """Locate `symbol` (a module, class, or method) in a source file."""
    path = SRC / rel_path
    tree = ast.parse(path.read_text())
    name = symbol.split(".")[-1]
    found = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name == name:
                found = node
                break
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == name:
                    found = node
                    break
        if found is not None:
            break
    if found is None:
        raise AssertionError(
            f"DECIDED_AT cites {symbol!r} in {rel_path}, which no longer exists - "
            f"the rule's stated consequence is now unverified. Fix the anchor, "
            f"not the assertion.")
    return {
        "file": f"src/vre_rocrate/{rel_path}",
        "line": found.lineno,
        "symbol": symbol,
        "declared_through_line": getattr(found, "end_lineno", found.lineno),
    }


def derive_lint_rules() -> dict[str, Any]:
    rules = []
    for rule in LINT_RULES:
        rel, symbol = DECIDED_AT[rule["id"]]
        rules.append({**rule, "decided_at": resolve_symbol(rel, symbol)})
    return {
        "_note": "Machine-readable form of the producer conformance rules. "
                 "Enforced by tools/wire_spec_lint.py, which is dependency-free "
                 "and meant to be copied by consumers; this generator only "
                 "resolves the 'decided_at' provenance below. Each rule is "
                 "exercised by negatives/<rule>.json, and generation fails if a "
                 "linter predicate stops firing on its negative or if a cited "
                 "symbol disappears. 'needs' lists the rules this one cannot be "
                 "judged without; a rule that needs another is reported in "
                 "'undecidable', never silently passed.",
        "rules": rules,
    }


#: The crate `derive_must_enforcement` measures on: the one golden that carries
#: every documented role at once, built from examples/probe_every_optional_input.py.
MUST_PROBE_CRATE = "examples/probe_every_optional_input.json"


def _schema_if_matches(entity: dict[str, Any], condition: dict[str, Any]) -> bool:
    """Does an entity satisfy a schema `if` clause that `derive_schemas` emits?

    A deliberately tiny evaluator, not a JSON Schema implementation. It handles
    exactly the three constructs this generator ever writes into an `if` -
    `required`, `properties.@type` as produced by `_has_type`, and
    `properties.@id` as a `const` - and raises on anything else, so a future
    clause this function cannot judge fails generation instead of quietly
    reporting a deletion as unnoticed.

    Why not call jsonschema: generation must run on a bare interpreter (see
    `verify_schemas`), and the schema-under-test is itself a committed artefact,
    so reading its clauses is reading the shipped spec, not re-deriving it.
    `verify_must_enforcement` then cross-checks this against the real validator
    whenever the dev extra is installed - two independent implementations of the
    same question, which is the same argument for having the linter at all.
    """
    for key, spec in condition.items():
        if key == "required":
            if any(k not in entity for k in spec):
                return False
        elif key == "properties":
            for prop, sub in spec.items():
                if "const" in sub:
                    if entity.get(prop) != sub["const"]:
                        return False
                elif "@type" == prop and "anyOf" in sub:
                    # `_has_type(name)`: {"anyOf": [{"const": n},
                    #              {"type": "array", "contains": {"const": n}}]}
                    names = [c["const"] for c in sub["anyOf"] if "const" in c]
                    if not names:
                        raise AssertionError(f"unhandled @type clause: {sub}")
                    want = names[0]
                    have = entity.get("@type")
                    have = have if isinstance(have, list) else [have]
                    if want not in have:
                        return False
                else:
                    raise AssertionError(
                        f"derive_must_enforcement cannot judge the `if` clause "
                        f"{key}.{prop}: {sub}. Extend _schema_if_matches or stop "
                        "using it in a required-key clause.")
        else:
            raise AssertionError(
                f"derive_must_enforcement cannot judge the `if` keyword {key!r}")
    return True


def _schema_rejects_entity(entity: dict[str, Any], item_schema: dict) -> bool:
    """Would the shipped profile schema call this one entity invalid?

    Only the entity-level clauses are consulted: the graph-level `contains`
    clauses ask about the whole @graph, and every key they demand
    (`about`/`conformsTo`/`mainEntity`) is also demanded by the corresponding
    per-entity clause, so a single-entity deletion is decided here anyway.
    `verify_must_enforcement` checks the whole-crate verdict against the real
    validator, which would notice if that reasoning stopped holding.
    """
    for clause in item_schema["allOf"]:
        if "not" in clause:
            # core's `{"not": has_type("RuntimePlatform")}`.
            names = [c["const"] for c in clause["not"].get("anyOf", [])
                     if "const" in c]
            have = entity.get("@type")
            have = have if isinstance(have, list) else [have]
            if names and names[0] in have:
                return True
        if "if" not in clause:
            # item_base: every entity needs a non-empty @id and an @type.
            if any(k not in entity for k in clause.get("required", [])):
                return True
            continue
        if not _schema_if_matches(entity, clause["if"]):
            continue
        then = clause.get("then", {})
        if any(k not in entity for k in then.get("required", [])):
            return True
    return False


def derive_must_enforcement(artefacts: dict[str, Any]) -> dict[str, Any]:
    """For each MUST-marked property, does deleting it trip any shipped checker?

    01-conformance.md tells producers that most `MUST`s are unenforced, and a
    claim that shapes what people emit has to be a MEASURED number, not a
    remembered one - the sentence this replaces had drifted to "32 of the 58
    deletions on a 14-entity crate", a crate size that appears nowhere and a row
    count 12 higher than the tables contain.

    So: take the probe crate, delete one MUST-marked property at a time, and run
    the two checkers that ship as code (`validate_basic`, the linter) against the
    result. A deletion nothing reports is `unnoticed`.

    The profile schema is deliberately NOT evaluated here. `jsonschema` is a dev
    extra and generation must stay runnable without it, so recording a per-run
    schema verdict would make the artefact depend on the machine that built it -
    the exact failure `verify_schemas` exists to avoid. The schema's side of the
    claim is asserted instead, as a gate, in `verify_must_enforcement`.

    Property names come from `entities.json`, whose `status` is what renders the
    `MUST`/`MAY` column in 03; a property the probe crate happens not to carry is
    reported as `unprobed` rather than silently shrinking the denominator.
    """
    from vre_rocrate.parsing.validator import ValidationPipeline
    import copy as _copy

    entities = artefacts["entities.json"]["entities"]
    must_of = {role: [p for p, m in e["properties"].items()
                      if m["status"] == "required"]
               for role, e in entities.items()}

    crate = artefacts[MUST_PROBE_CRATE]
    graph = crate["@graph"]
    root = next(e for e in graph if e.get("@id") == "./")
    main_id = root["mainEntity"]
    main_id = main_id if isinstance(main_id, str) else main_id["@id"]
    parts = {p if isinstance(p, str) else p.get("@id")
             for p in root.get("hasPart", [])}
    role_of = {idx: _role(e, main_id, parts) for idx, e in enumerate(graph)}

    item_schema = artefacts["schema-core.json"]["properties"]["@graph"]["items"]

    def reported(entity: dict[str, Any],
                 c: dict[str, Any]) -> tuple[bool, bool, list[str]]:
        """What each of the three shipped checkers says about a mutation.

        Returns (validate_basic rejected the crate, the schema rejects the edited
        entity, rule ids the linter now reports). The schema is asked about the
        ENTITY rather than the crate because that is the level its required-key
        clauses live at; `verify_must_enforcement` cross-checks the whole-crate
        verdict against the real validator.
        """
        try:
            ValidationPipeline.validate_basic(c)
            rejected = False
        except Exception:
            rejected = True
        return rejected, _schema_rejects_entity(entity, item_schema), \
            sorted(lint_report(c)["violations"])

    base_violations = sorted(lint_report(crate)["violations"])
    assert not base_violations and not any(
            _schema_rejects_entity(e, item_schema) for e in graph), (
        f"{MUST_PROBE_CRATE} is not clean on the linter/schema, so it cannot be "
        "the baseline for a deletion experiment")
    try:
        ValidationPipeline.validate_basic(crate)
    except Exception as exc:
        raise AssertionError(
            f"{MUST_PROBE_CRATE} fails validate_basic ({exc}), so it cannot be "
            "the baseline for a deletion experiment") from exc

    deletions: list[dict[str, Any]] = []
    unprobed: list[str] = []
    for idx, entity in enumerate(graph):
        role = role_of[idx]
        for prop in must_of.get(role, ()):
            if prop not in entity:
                unprobed.append(f"{role}.{prop}")
                continue
            mutated = _copy.deepcopy(crate)
            del mutated["@graph"][idx][prop]
            rejected, schema_caught, violations = reported(
                mutated["@graph"][idx], mutated)
            caught_by = (["schema"] if schema_caught else [])
            if rejected:
                caught_by.append("validate_basic")
            caught_by += [f"W{v[1:]}" for v in violations]
            deletions.append({
                "index": idx,
                "role": role,
                "property": prop,
                "entity": entity.get("@id"),
                "caught_by": caught_by,
                "unnoticed": not caught_by,
            })

    unnoticed = [d for d in deletions if d["unnoticed"]]
    return {
        "_note": "Every documented MUST property, deleted once from the probe "
                 "crate, judged by the two checkers that ship as code. "
                 "'unnoticed' means validate_basic passed AND the linter "
                 "reported no violation. The profile schema's agreement is "
                 "asserted at generation time by verify_must_enforcement, which "
                 "needs the dev extra; it is not recorded here because a "
                 "per-run verdict would make this file machine-dependent. "
                 "Re-runs on every generation, so the counts in "
                 "01-conformance.md cannot go stale.",
        "probe_crate": MUST_PROBE_CRATE,
        "probe_entities": len(graph),
        "probe_roles": len(set(role_of.values())),
        "must_rows": sum(len(v) for v in must_of.values()),
        "deletions": len(deletions),
        "unnoticed": len(unnoticed),
        # Property NAMES, deduplicated. Per-deletion counts over-report to a
        # reader: the probe crate carries two FormalParameters and two Files, so
        # `license` appears three times. Prose quoting these must say whether it
        # means rows or distinct properties.
        "unnoticed_properties": sorted({d["property"] for d in unnoticed}),
        "caught_properties": sorted({d["property"] for d in deletions
                                     if not d["unnoticed"]}),
        # Which checker caught each caught property, so 01's table of "enforced
        # by ..." is generated rather than asserted.
        "caught_by_property": {
            prop: sorted({c for d in deletions if d["property"] == prop
                          for c in d["caught_by"]})
            for prop in sorted({d["property"] for d in deletions
                                if not d["unnoticed"]})},
        "unprobed_properties": sorted(set(unprobed)),
        "rows": sorted(deletions, key=lambda d: (d["role"], d["property"])),
        # Deleting whole entities, not properties. 01 and 03 both tell producers
        # that a crate with no provenance at all is byte-clean, which is a strong
        # enough claim that it should not rest on someone having tried it once.
        # Every reference is scrubbed too, so this measures "no provenance", not
        # "dangling provenance" (which W004/W011 would rightly catch).
        "provenance_deletion": _probe_provenance_deletion(crate, item_schema),
    }


#: The three entities `RocrateBuilder` emits unconditionally with fixed values.
PLACEHOLDER_IDS = frozenset({"#author-dispatcher", "#workflow-hub",
                             "#license-unspecified"})


def strip_provenance(crate: dict[str, Any]) -> dict[str, Any]:
    """Drop the three placeholder entities AND every reference to them.

    Both halves matter. Removing the entities alone leaves dangling references,
    which W004/W011 rightly report, and would make "you can ship a crate with no
    provenance" look false when the real claim is "you can ship one with no
    provenance and no pointers at the provenance you did not write".
    """
    import copy as _copy

    def scrub(value: Any) -> Any:
        if isinstance(value, dict):
            if value.get("@id") in PLACEHOLDER_IDS:
                return None
            out = {}
            for key, sub in value.items():
                if isinstance(sub, dict) and sub.get("@id") in PLACEHOLDER_IDS:
                    continue
                if isinstance(sub, list) and any(
                        isinstance(x, dict) and x.get("@id") in PLACEHOLDER_IDS
                        for x in sub):
                    kept = [x for x in (scrub(i) for i in sub)
                            if x is not None]
                    if kept:
                        out[key] = kept
                    continue
                scrubbed = scrub(sub)
                if scrubbed is not None:
                    out[key] = scrubbed
            return out
        if isinstance(value, list):
            return [v for v in (scrub(i) for i in value) if v is not None]
        return value

    stripped = scrub(_copy.deepcopy(crate))
    stripped["@graph"] = [e for e in stripped["@graph"]
                          if e.get("@id") not in PLACEHOLDER_IDS]
    return stripped


def _probe_provenance_deletion(crate: dict[str, Any],
                               item_schema: dict) -> dict[str, Any]:
    """Judge the provenance-stripped crate with the two dependency-free checkers."""
    from vre_rocrate.parsing.validator import ValidationPipeline

    stripped = strip_provenance(crate)
    residual = sum(json.dumps(stripped).count(t) for t in
                   ("author-dispatcher", "workflow-hub", "license-unspecified",
                    "Dispatcher System", "Example Workflow Hub",
                    "Unspecified license"))
    try:
        ValidationPipeline.validate_basic(stripped)
        validator_ok = True
    except Exception:
        validator_ok = False
    return {
        "entities_removed": len(crate["@graph"]) - len(stripped["@graph"]),
        # Must be 0. A non-zero count means the scrub left a name behind and the
        # "no provenance at all" sentence would be describing a different crate.
        "residual_mentions": residual,
        "validate_basic_passes": validator_ok,
        "linter_violations": sorted(lint_report(stripped)["violations"]),
        "schema_rejects_any_entity": any(
            _schema_rejects_entity(e, item_schema)
            for e in stripped["@graph"]),
    }


def verify_must_enforcement(must: dict[str, Any],
                            artefacts: dict[str, Any]) -> list[str]:
    """Cross-check the dependency-free schema verdict against the real one.

    `derive_must_enforcement` decides the schema half with `_schema_rejects_entity`,
    a ~40-line reader of the shipped clauses, because generation must run without
    `jsonschema`. This is where that shortcut pays for itself: for every deletion
    the two implementations are asked the same question - does the shipped
    `schema-core.json` reject the mutated crate - and any disagreement fails
    generation in either direction.

    The comparison is entity-level verdict against whole-crate verdict, so a
    divergence also means the two levels have come apart: a required key that the
    per-entity clauses miss but a graph-level `contains` clause happens to catch,
    which is a fact 01 needs to state differently.
    """
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        return []
    import copy as _copy

    crate = artefacts[must["probe_crate"]]
    validator = Draft202012Validator(artefacts["schema-core.json"])
    bad = []
    for row in must["rows"]:
        mutated = _copy.deepcopy(crate)
        del mutated["@graph"][row["index"]][row["property"]]
        claimed = "schema" in row["caught_by"]
        actual = not validator.is_valid(mutated)
        if claimed == actual:
            continue
        bad.append(
            f"deleting {row['property']} from {row['role']} ({row['entity']}): "
            f"the shipped clauses {'reject' if claimed else 'accept'} the entity "
            f"but jsonschema {'rejects' if actual else 'accepts'} the crate - so "
            f"{'01 overstates' if claimed else '01 understates'} what the schema "
            "catches")

    # The provenance claim, whole-crate, against the real validator. 01/03 say a
    # crate with no placeholders and no references to them is byte-clean; that is
    # the kind of sentence a producer acts on, so it is checked rather than
    # remembered.
    # The provenance claim. 01 and 03 both tell producers that a crate with the
    # placeholders and their references removed is byte-clean, which is the kind
    # of sentence a producer acts on, so the schema half is verified rather than
    # remembered. Note this compares an entity-level verdict against a whole-crate
    # one: agreement means no graph-level `contains` clause is what would have
    # caught the removal, which is exactly the assumption the census makes.
    prov = must["provenance_deletion"]
    claimed = prov["schema_rejects_any_entity"]
    actual = not Draft202012Validator(
        artefacts["schema-core.json"]).is_valid(strip_provenance(crate))
    if claimed != actual:
        bad.append(
            "the provenance-stripped probe crate: the shipped per-entity clauses "
            f"{'reject' if claimed else 'accept'} it but jsonschema "
            f"{'rejects' if actual else 'accepts'} it, so the whole-crate verdict "
            "is not decided by the clauses the census reads - check whether a "
            "graph-level `contains` clause now fires and correct 01")
    if prov["residual_mentions"]:
        bad.append(
            f"the provenance scrub left {prov['residual_mentions']} mention(s) of "
            "the placeholders behind, so 'a crate with no provenance at all' "
            "describes a different crate from the one measured")
    return bad


def derive_additional_types(artefacts: dict[str, Any]) -> dict[str, Any]:
    """Every `additionalType` value that appears on a FormalParameter, and where.

    `FormalParameter.additionalType` is documented as free text carried verbatim
    from the producer, which means the ONLY way to know what a consumer will
    actually meet is to count the crates. The hand-written table this feeds had
    counted 16 and 4 reference values where the goldens hold 8 and 2, and had
    omitted that the values split cleanly by crate origin - the builder emits a
    string, real inbound crates emit an EDAM reference, and no producer does both.

    `VREPayload` annotates the parsed field `additional_type: str | None` while
    the parse path copies the entity value verbatim, so the dict form arrives as a
    `dict`. That is asserted against the live parser rather than restated, so a
    future narrowing of the parse path fails here instead of invalidating 03.
    """
    counts: dict[str, dict[str, int]] = {}
    crates: dict[str, set[str]] = {}
    for slug, meta in artefacts["examples.json"]["entries"].items():
        crate = artefacts[slug]
        for entity in crate.get("@graph", []):
            if "additionalType" not in entity:
                continue
            value = entity["additionalType"]
            shape = "reference" if isinstance(value, dict) else "string"
            origin = meta["origin"]
            key = f"{origin}|{shape}"
            rendered = value if shape == "string" else value.get("@id", value)
            per_value = counts.setdefault(key, {})
            per_value[str(rendered)] = per_value.get(str(rendered), 0) + 1
            crates.setdefault(key, set()).add(slug)

    # The parse path, not the annotation, is the authority on what arrives.
    from vre_rocrate import VREPayloadBuilder

    shapes_seen = set()
    for slug, meta in artefacts["examples.json"]["entries"].items():
        if meta["origin"] != "fixture-input":
            continue
        try:
            payload = VREPayloadBuilder.build(artefacts[slug])
        except Exception:
            continue
        for param in payload.workflow_inputs:
            if param.additional_type is not None:
                shapes_seen.add(type(param.additional_type).__name__)

    return {
        "_note": "Observed FormalParameter.additionalType values across every "
                 "golden, keyed by `origin|shape`. Free text by contract: nothing "
                 "validates it and nothing on the parse side reads it. The "
                 "`python_types_seen` list is measured through VREPayloadBuilder, "
                 "which is what proves the model's `str | None` annotation is "
                 "narrower than the data.",
        "counts": {k: dict(sorted(v.items())) for k, v in sorted(counts.items())},
        "crates": {k: sorted(v) for k, v in sorted(crates.items())},
        "python_types_seen": sorted(shapes_seen),
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def build_artefacts() -> dict[str, Any]:
    negatives = derive_negatives()
    artefacts: dict[str, Any] = {
        "entities.json": derive_entities(),
        "vocabulary.json": derive_vocabulary(),
        "mime-extensions.json": derive_mime(),
        "unemitted.json": derive_unemitted(),
        "reference-forms.json": derive_reference_forms(),
        "array-forms.json": derive_array_forms(),
        "slot-bindings.json": derive_slot_bindings(),
        "field-visibility.json": derive_field_visibility(),
        "id-patterns.json": extract_id_patterns(),
        "lint-rules.json": derive_lint_rules(),
        "negatives.json": {
            "_note": "One deliberately-broken crate per rule, for a consumer team "
                     "to test their own validator against. Each entry records what "
                     "the linter is expected to say about the file, so a weakened "
                     "predicate fails generation rather than passing quietly. "
                     "expected_undecidable lists rules that cannot be judged once "
                     "this fault is present - NOT rules the crate passes.",
            "entries": negatives["entries"],
        },
    }
    for rule, crate in negatives["crates"].items():
        artefacts[f"negatives/{rule}.json"] = crate

    artefacts.update(derive_schemas())

    goldens = derive_goldens()
    # Counted, never typed: the fixture crates are the ones that predate the
    # profile URI, so "they all fail only W012" is the sentence a consumer most
    # needs and the one a typed count would rot into a lie. Measured the same way
    # the golden-index column measures it, so the note and the table cannot drift.
    #
    # `declares_wire_profile` is used as the proxy for "the schema rejects this",
    # which is sound only because the cross-check in derive_schemas asserts
    # schema-rejects iff the linter sees an ENCODABLE rule, and W012 is encodable
    # in BOTH profiles - so a crate that omits the profile URI is rejected by
    # whichever schema judges it. If W012 ever stops being encodable in a profile,
    # that equivalence breaks and this note over-reports; assert it here rather
    # than leaving the reasoning in a comment three hundred lines away.
    assert "W012" in artefacts["schemas.json"]["encodable"]["core"], (
        "examples.json's _note treats a missing profile URI as a schema "
        "rejection, which requires W012 in the core profile")
    assert "W012" in artefacts["schemas.json"]["encodable"]["infrastructure"], (
        "examples.json's _note treats a missing profile URI as a schema "
        "rejection, which requires W012 in the infrastructure profile")
    fixtures = [m for m in goldens["entries"].values()
                if m["origin"] == "fixture-input"]
    w012_only = [m for m in fixtures if not m["violations_pre_profile"]]
    declares = [m for m in fixtures if m["declares_wire_profile"]]
    artefacts["examples.json"] = {
        "_note": "Real crates for a consumer team to point their parser at. "
                 "'builder-output' is what RocrateBuilder emits (rebuilt from "
                 "examples/*.py under a frozen clock and checked against what "
                 "each example actually prints); 'fixture-input' is a crate some "
                 "producer actually sent. @graph is sorted by @id; emission order "
                 "is normative and lives in entities.json. Timestamps are real "
                 "ISO 8601 values, not placeholders. Every 'builder-output' file "
                 f"validates against the schema for its profile; "
                 f"{len(fixtures) - len(declares)} of the {len(fixtures)} "
                 f"'fixture-input' files do not, and {len(w012_only)} of those fail "
                 "W012 and nothing else - they predate the profile URI, which W012 "
                 "and the schemas both require. So `profile` on a 'fixture-input' "
                 "row classifies its SHAPE (which schema describes it) and is not a "
                 "conformance verdict; read the index's violates column, which "
                 "withholds W012, for what a fixture does besides predating it.",
        "timestamp_keys": TIMESTAMP_KEYS,
        "emittable_types": goldens["emittable_types"],
        "entries": goldens["entries"],
    }
    for slug, crate in goldens["crates"].items():
        artefacts[f"examples/{slug}"] = crate

    # Built last because it reads two other artefacts: the MUST set from
    # entities.json and the probe crate from the goldens. It is the only
    # artefact that measures the CHECKERS rather than the builder.
    must = derive_must_enforcement(artefacts)
    artefacts["must-enforcement.json"] = must
    artefacts["additional-types.json"] = derive_additional_types(artefacts)

    # The schema cross-check is a GATE on generation, never content of the
    # artefacts. Writing its result into schemas.json made that file depend on
    # which machine generated it - the jsonschema version and the pass/fail of
    # this particular run both landed in committed JSON, so the drift test could
    # not pass on a machine without the dev extra. Spec content is derived from
    # source only; where the cross-check actually ran is reported here instead,
    # and tests/test_spec re-derives it from the shipped files.
    verification = verify_schemas(artefacts, goldens, negatives)
    if verification.get("mismatches"):
        raise AssertionError(
            "the schemas do not behave as schemas.json claims:\n  "
            + "\n  ".join(verification["mismatches"]))
    if not verification.get("checked"):
        print("NOTE: schemas not cross-checked - " + verification["reason"],
              file=sys.stderr)
    else:
        print(f"NOTE: schemas cross-checked against {verification['checked_against']} "
              f"crates with jsonschema {verification['jsonschema_version']}; "
              "0 mismatches", file=sys.stderr)

    # Same gate relationship for the MUST census: the artefact records only what
    # the two dependency-free checkers saw, and this asserts the third agrees.
    # Without it, "unnoticed by all three" would be an assertion about a checker
    # nothing consulted.
    must_gaps = verify_must_enforcement(must, artefacts)
    if must_gaps:
        raise AssertionError(
            "the MUST enforcement census disagrees with schema-core.json:\n  "
            + "\n  ".join(must_gaps))
    return artefacts


# ---------------------------------------------------------------------------
# Prose regions
#
# docs/spec/*.md is hand-written - the reasoning, the ordering, the warnings are
# the part a generator could not produce. But its TABLES are exactly the part
# that goes stale, and README.md is the existing proof that hand-copied tables
# rot into active misinformation. So the prose contains marked regions and
# generation rewrites only what is between them:
#
#     <!-- BEGIN GENERATED region-name -->
#     <!-- END GENERATED -->
#
# A region whose name is unknown, or one whose markers are unbalanced, fails
# generation. The prose therefore cites derived facts it did not have to type,
# which is what lets 03-entities.md carry 88 property rows without 88 chances to
# be wrong.
# ---------------------------------------------------------------------------

PROSE_DIR = ROOT / "docs" / "spec"
BEGIN_MARK = "<!-- BEGIN GENERATED {} -->"
END_MARK = "<!-- END GENERATED -->"
BEGIN_RE = re.compile(r"<!-- BEGIN GENERATED ([a-z0-9-]+) -->")

#: Inline tokens, for a GENERATED scalar that sits mid-sentence.
#:
#: Regions cannot express these: a region replaces whole lines, and a count like
#: "8 of 14 rules" lives inside a paragraph. Hand-typed counts are exactly the bug
#: that happened here - W014 was added, the generated rule table moved to 14 on
#: its own, and nine sentences across four files went on saying 13 while sitting
#: two lines from a table that said otherwise.
#:
#: The marker STAYS in the committed file, which is the whole design. Substituting
#: a `{{token}}` away would fix the number once and then lose the claim, so the
#: next edit could put anything there and nothing would notice. An HTML comment
#: renders as nothing, sits immediately before the value it governs, and is
#: re-checked on every run - the same property regions have, at the granularity of
#: one scalar. It covers one value with no spaces in it, which is all a count is;
#: "8 of 14" is two markers.
#:
#: The value runs up to whitespace or sentence punctuation, so `...14.` and
#: `...14,` both read as `14` and stay stable across runs. A value containing one
#: of those characters would be re-added ahead of the punctuation and then read
#: back short, marking the file stale forever - loud, but wrong, so token values
#: are checked against this charset where they are defined.
INLINE_MARK = "<!-- GEN:{} -->"
INLINE_RE = re.compile(r"<!-- GEN:([a-z0-9-]+) -->([^\s,;:.!?)]*)")
INLINE_VALUE_RE = re.compile(r"^[A-Za-z0-9/_-]+$")


# Prose excerpts, addressed by ROLE rather than by @id. A prose citation like
# `excerpt-galaxy-file` stays meaningful when an example's URLs change, whereas
# citing `excerpt-galaxy-https://raw.githubusercontent.com/...` would be both
# unreadable and wrong the moment someone edits examples/galaxy.py. Each entry is
# resolved through the same role inference that builds entities.json, so an
# excerpt whose subject has disappeared fails generation rather than printing a
# stale example - which is the only reason it is safe to put JSON in prose.
EXCERPTS: dict[str, tuple[str, str, int]] = {
    "galaxy-descriptor": ("examples/galaxy.json", "root-descriptor", 0),
    "galaxy-root": ("examples/galaxy.json", "root-dataset", 0),
    "galaxy-workflow": ("examples/galaxy.json", "workflow", 0),
    "galaxy-language": ("examples/galaxy.json", "computer-language", 0),
    "galaxy-file": ("examples/galaxy.json", "file", 0),
    "galaxy-parameter": ("examples/galaxy.json", "formal-parameter", 0),
    "mddash-parameter": ("examples/mddash.json", "formal-parameter", 0),
    "sciencemesh-parameter": ("examples/sciencemesh.json", "formal-parameter", 0),
    "sciencemesh-root": ("examples/sciencemesh.json", "root-dataset", 0),
    "sciencemesh-language": ("examples/sciencemesh.json", "computer-language", 0),
    # A file with no url: @id falls back to the bare name, so this entity is
    # addressed as "requirements.txt" rather than as a URL. sciencemesh's file,
    # by contrast, has no `url` property but a full-URL @id - the two cases are
    # easy to conflate, so both are shown.
    "alphafind-local-file": ("examples/alphafind_notebook.json", "file", 0),
    # The workflow uri's extension is absent from the table (.git), so @type
    # carries no "File" and the workflow is NOT in VREPayload.files.
    "mddash-workflow": ("examples/mddash.json", "workflow", 0),
    # sciencemesh is the slots-AND-files case: its one FormalParameter holds a
    # literal ("Shared With"), the notebook is the workflow, and this is a
    # free-form file beside them - the shape that proved input_files must return
    # both kinds, not just slot-referenced ones.
    "sciencemesh-file": ("examples/sciencemesh.json", "file", 0),
    "tosca-runtime-platform": ("examples/galaxy_tosca_stage__ro-crate-metadata.json",
                               "runtime-platform", 0),
    "tosca-orphan-file": ("examples/galaxy_tosca_stage__ro-crate-metadata.json",
                          "orphan-file", 0),
    "tosca-stage-root": ("examples/galaxy_tosca_stage__ro-crate-metadata.json",
                         "root-dataset", 0),
    # The two entities no example produces: every example passes
    # raw_definition={} and none passes a DatasetHandle.
    "probe-dataset": ("examples/probe_every_optional_input.json",
                      "input-dataset", 0),
    "probe-tool-metadata": ("examples/probe_every_optional_input.json",
                            "tool-metadata", 0),
    "probe-file": ("examples/probe_every_optional_input.json", "file", 0),
    # The three placeholders are documented as "emitted with fixed values", and
    # for a producer that is the only fact that matters - but 03 described the
    # requirement without ever stating the values, and nothing else in the
    # sandbox-readable tree did either. A producer therefore had to copy them out
    # of a crate to emit them correctly, which is exactly the kind of implicit
    # knowledge a spec is supposed to make explicit. Excerpted, so the values in
    # the prose cannot drift from the values the builder writes.
    "author-placeholder": ("examples/galaxy.json", "author-placeholder", 0),
    "publisher-placeholder": ("examples/galaxy.json", "publisher-placeholder", 0),
    "license-placeholder": ("examples/galaxy.json", "license-placeholder", 0),
    # additionalType as a reference object, not a string: the one shape a
    # core-profile producer emits and no builder can. Cited from a fixture so the
    # claim "real inbound crates do this" is checkable in place.
    "edam-parameter": ("examples/galaxy_and_onedata__ro-crate-metadata.json",
                       "formal-parameter", 0),
    # The prose claims a file can carry a full-URL @id AND no `url` property, and
    # cited excerpt-sciencemesh-file as the proof - but that entity DOES have a
    # `url`, so the example refuted the sentence attached to it. This is a real
    # inbound crate's file that actually has the claimed shape.
    "url-file-without-url": ("examples/vip__ro-crate-metadata.json", "file", 0),
}


def _by_role(crate: dict) -> dict[str, list]:
    """Group a crate's entities by role, in graph order.

    Adds two roles the builder-oriented inference in `_role` has no concept of,
    because they only ever occur in hand-authored crates: `runtime-platform` and
    `orphan-file` (a File that root hasPart does not list - rule W008's subject).
    """
    graph = crate["@graph"]
    root = next((e for e in graph if e.get("@id") == "./"), {})
    main_ref = root.get("mainEntity")
    main_id = main_ref.get("@id") if isinstance(main_ref, dict) else main_ref
    parts = {p.get("@id") if isinstance(p, dict) else p
             for p in root.get("hasPart", [])}
    out: dict[str, list] = {}

    def add(role: str, entity: dict) -> None:
        out.setdefault(role, []).append(entity)

    for entity in graph:
        t = entity.get("@type")
        types = [t] if isinstance(t, str) else list(t)
        if "RuntimePlatform" in types:
            add("runtime-platform", entity)
            continue
        if ("File" in types and entity.get("@id") not in parts
                and entity.get("@id") != main_id):
            add("orphan-file", entity)
        add(_role(entity, main_id, parts), entity)
    return out


def _trimmed(entity: dict, limit: int = 72) -> tuple[dict, bool]:
    """Shorten long *prose* values so an excerpt stays readable in a terminal.

    Returns the shortened entity and whether anything was shortened, so the
    excerpt can say so rather than passing itself off as verbatim.

    Identifiers are never shortened, at any nesting depth. An earlier version
    truncated `@id` values over the limit, which produced two defects at once:
    the same URL appeared whole inside `hasPart` and elided inside `mainEntity`
    of the *same* entity, and a reader who copied the elided line into a test
    fixture got a silently wrong `@id` - the precise class of bug this whole
    document is trying to prevent. `name`/`description` carry no such risk, so
    they are what gets shortened.

    `url` is an address too and is exempt for the same reason, with a second
    argument on top: on a File the builder writes `url` as exactly the value it
    writes into `@id` (`_file_id`), so eliding one and not the other made
    `excerpt-sciencemesh-file` print the address whole and then truncated, which
    reads as "these are different values" and is the opposite of what the prose
    around it claims. A dry-run producer copied that excerpt and could not tell
    which of the two it was meant to emit.
    """
    changed = False

    def shorten(value: Any, key: str | None) -> Any:
        nonlocal changed
        identifier = key is not None and (key.startswith("@") or key == "url")
        if (isinstance(value, str) and not identifier
                and len(value) > limit):
            changed = True
            return value[:limit] + "…"
        if isinstance(value, dict):
            return {k: shorten(v, k) for k, v in value.items()}
        if isinstance(value, list):
            return [shorten(v, key) for v in value]
        return value

    return {k: shorten(v, k) for k, v in entity.items()}, changed


def _regions_in(text: str):
    """Yield (name, start, end, matched_text) for each marked region.

    Scanned by index rather than with one big regex on purpose: a lazy
    `(.*?)` spanning a region's whole body makes CPython's backtracker recurse
    once per character skipped, so a region over ~1 KB raises RecursionError.
    This file's own test-spec region hit exactly that.
    """
    pos = 0
    while True:
        begin = BEGIN_RE.search(text, pos)
        if begin is None:
            return
        end = text.find(END_MARK, begin.end())
        if end == -1:
            raise AssertionError(
                f"region {begin.group(1)!r} is opened but never closed")
        yield (begin.group(1), begin.start(), end + len(END_MARK),
               text[begin.start():end + len(END_MARK)])
        pos = end + len(END_MARK)





def _status_phrase(status: str) -> str:
    return {"required": "MUST", "conditional": "MAY"}.get(status, status.upper())


def _md_table(header: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(header) + " |",
           "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(c.replace("|", "\\|") for c in row) + " |"
            for row in rows]
    return "\n".join(out)


_TIER_LABELS = {
    "promoted": "named field",
    "properties_only": "`properties` only",
    "raw_crate_only": "`raw_crate` only",
    "consumed_not_readable": "**unreadable**",
    "never_serialized": "**never serialized**",
}


def _transition_summary(row: dict[str, Any]) -> str:
    """What the crate did with the probe value, in one cell.

    Reports the observed transition and nothing else. It deliberately does NOT
    say "renamed", "inverted" or "dropped by a conditional": a rename would be
    an inference from comparing the model's field name to the crate's property
    name, and a cause would be a reading of the builder's source. The cell shows
    `required` going `true` to `false` and leaves the negation to the reader's
    eyes, which is the most either of us can claim from a diff.
    """
    transitions = row["transitions"]
    if not transitions:
        return "*no byte of the crate changed*"
    by_key: dict[str, list[dict[str, Any]]] = {}
    for t in transitions:
        by_key.setdefault(t["path"].rsplit("/", 1)[-1].split("[")[0],
                          []).append(t)
    parts = []
    for key, ts in sorted(by_key.items()):
        # Partitioned, not decided per key: `ToolMeta.uri` moves @type in three
        # places, two by changing a value and one by dropping it. Summarising the
        # key as "removed" because one of them was would overstate the loss, and
        # understating a loss is the direction that hurts a reader.
        # Partitioned, not decided per key: ToolMeta.uri moves @type in three
        # places, two by changing a value and one by dropping it. Calling the key
        # "removed" because one of them was would overstate a loss - and
        # overstating a loss is the direction that sends a reader to fix something
        # that is not broken. There is deliberately no "added" case: _BASELINE
        # populates every optional property, so a probe can only change or delete
        # a value, never introduce one.
        gone = [t for t in ts if "removed" in t]
        moved = [t for t in ts if "removed" not in t]
        chunks = []
        if moved:
            # One `from` → `to` per DISTINCT pair, first-seen order, two at most.
            # "@type 2 different values" is true and useless; the two pairs are
            # short enough to print and answer the question the cell is for, which
            # is what the value turned into.
            pairs: list[tuple[Any, Any]] = []
            for t in moved:
                if (t["from"], t["to"]) not in pairs:
                    pairs.append((t["from"], t["to"]))
            shown = "; ".join(f"`{_cell(f)}`→`{_cell(t)}`" for f, t in pairs[:2])
            chunks.append(shown + (f" (+{len(pairs) - 2} more)"
                                   if len(pairs) > 2 else ""))
        if gone:
            chunks.append("**removed**")
        # Count attached to the PROPERTY NAME, not to the last chunk: "@type
        # changed; **removed** (3 places)" reads as three removals when two of the
        # three were value changes.
        where = f" ({len(ts)} places)" if len(ts) > 1 else ""
        parts.append(f"`{key}`{where} " + "; ".join(chunks))
    return "; ".join(parts) + (" *(and more)*"
                               if row["changed_path_count"] > len(transitions)
                               else "")


def _cell(value: Any) -> str:
    """A scalar as it appears in the crate, short enough for a table cell.

    Truncates from the MIDDLE, keeping both ends. Head-truncating was fine until
    this was used in a before/after column: URLs differ at the tail, so two
    different `https://example.org/...` values both rendered as
    `https://example.org…` and the row read as "nothing changed" - the one thing
    this column must never claim about a change the diff did detect.
    """
    if value == "?":
        return "*(absent)*"
    text = value if isinstance(value, str) else json.dumps(value)
    if len(text) <= 26:
        return text
    head, tail = 15, 8
    return text[:head] + "…" + text[-tail:]


def _fmt_counts(value: Any) -> str:
    """Render a payload-count dict (or an exception name) as markdown."""
    if not isinstance(value, dict):
        return f"*{value}*"
    return ", ".join(f"{k}=`{n}`" for k, n in value.items())


def inline_tokens(artefacts: dict[str, Any]) -> dict[str, str]:
    """Scalar values prose cites mid-sentence, as `<!-- GEN:name -->` markers.

    Each of these was previously a typed digit in a paragraph, and the rule
    counts had all drifted to 13 when W014 made the set 14.

    The bar for adding one: a number belongs here if it is a count OF A GENERATED
    ARTEFACT, because then there is exactly one place that knows the answer.
    Counts of checked-in files are deliberately absent - `negatives/` and
    `generated/examples/` can be listed, and a token would add a layer between the
    reader and the thing being counted. The example counts below are the
    borderline case and are kept because they travel with a claim: "all 13
    fixture crates predate the profile URI" is not verifiable by listing a
    directory, which is why the assert above pairs the count with the property.
    """
    # `rules` is a list of rule RECORDS (id, rule, consequence, decided_at...);
    # the counts below want ids, and `set()` on the records raises.
    rules = [r["id"] for r in artefacts["lint-rules.json"]["rules"]]
    schemas = artefacts["schemas.json"]
    unencodable = schemas["not_encodable_in_any_profile"]
    union = sorted(set(schemas["encodable"]["core"])
                   | set(schemas["encodable"]["infrastructure"]))
    examples = artefacts["examples.json"]["entries"]
    fixture_input = [k for k, v in examples.items()
                     if v.get("origin") == "fixture-input"]
    # The prose says every fixture-input crate predates the profile URI and so
    # fails W012. That is a claim about the crates behind this count, so it is
    # pinned here: a fixture updated to declare the profile would make the
    # sentence wrong while leaving the number correct.
    assert not any(examples[k].get("declares_wire_profile")
                   for k in fixture_input), (
        "a fixture-input crate now declares the wire profile, so 'all "
        f"{len(fixture_input)} predate it and fail W012' is no longer true")
    assert set(union) | set(unencodable) == set(rules), (
        f"{set(union) | set(unencodable) ^ set(rules)} are neither schema-"
        "encodable nor declared unencodable, so 'N of M rules' cannot be "
        "computed without lying about one of them")
    # The MUST-deletion census. 01-conformance.md's "a MUST is not a check"
    # section quotes these mid-sentence, and the sentence it replaced had drifted
    # to a crate size and a row count that matched nothing. They are counts of
    # THIS artefact's own measurement, so there is one place that knows them.
    must = artefacts["must-enforcement.json"]
    out = {
        "rule-count": str(len(rules)),
        "schema-encodable-count": str(len(union)),
        "core-encodable-count": str(len(schemas["encodable"]["core"])),
        "unencodable-count": str(len(unencodable)),
        "fixture-input-count": str(len(fixture_input)),
        "builder-output-count": str(len(examples) - len(fixture_input)),
        "golden-count": str(len(examples)),
        # The dry-run record asserts "every negative is rejected"; a typed count
        # there would rot the moment a rule gained or lost a negative, and the
        # sentence would stay looking confident while lying about the gate.
        "negative-count": str(len(artefacts["negatives.json"]["entries"])),
        "must-probe-entities": str(must["probe_entities"]),
        "must-probe-roles": str(must["probe_roles"]),
        "must-deletion-count": str(must["deletions"]),
        "must-unnoticed-count": str(must["unnoticed"]),
        "must-unnoticed-prop-count": str(len(must["unnoticed_properties"])),
    }
    # A value carrying whitespace or sentence punctuation cannot round-trip
    # through INLINE_RE (see its comment), so reject it here instead of shipping
    # a token that reports the spec as permanently stale.
    assert all(INLINE_VALUE_RE.match(v) for v in out.values()), (
        "an inline token value contains a character the prose scanner cannot "
        f"read back: {out}")
    return out


def prose_regions(artefacts: dict[str, Any]) -> dict[str, str]:
    """Every fillable region's name and the markdown that belongs in it."""
    entities = artefacts["entities.json"]["entities"]
    rules = artefacts["lint-rules.json"]["rules"]
    vocab = artefacts["vocabulary.json"]
    regions: dict[str, str] = {}

    for role, ent in sorted(entities.items()):
        rows = []
        for prop, spec in sorted(ent["properties"].items()):
            why = "; ".join(spec["omitted_when"]) or "-"
            rows.append([f"`{prop}`", "/".join(f"`{sh}`" for sh in spec["shapes"]),
                         _status_phrase(spec["status"]), why])
        head = [f"**`@id` pattern**: `{ent['id_pattern']}`  ",
                f"**`@type`**: {', '.join('`' + t + '`' for t in ent['types_observed'])}  ",
                f"**Emitted**: {ent['emitted_when']}"
                + ("" if not ent["omitted_when"]
                   else " - omitted when " + "; ".join(ent["omitted_when"])),
                "", ent["meaning"]]
        regions[f"entity-{role}"] = ("\n".join(head) + "\n\n"
                                     + _md_table(["property", "shape", "producer", "present unless"], rows))

    regions["rule-table"] = _md_table(
        ["rule", "requirement", "if you don't", "checked by", "decided at"],
        [[r["id"], r["rule"], r["consequence"],
          {"entity": "schema + linter", "graph": "schema + linter",
           "none": "**linter only**"}[r["enforced_by"]],
          f'`{r["decided_at"]["file"]}:{r["decided_at"]["line"]}`']
         for r in rules])

    regions["rule-counts"] = (
        f"{len(rules)} rules. "
        f"{len(artefacts['schemas.json']['encodable']['infrastructure'])} are encoded in the "
        f"JSON Schema; **{len(artefacts['schemas.json']['not_encodable_in_any_profile'])} are "
        "not expressible in JSON Schema at all** "
        f"({', '.join(artefacts['schemas.json']['not_encodable_in_any_profile'])}) - they need "
        "resolution across entities, so a schema-valid crate can still violate every one of "
        "them. Run the linter.")

    vt = sorted(vocab["programming_language_identifier"])
    regions["vocab-identity"] = _md_table(
        ["`vre_type`", "`programmingLanguage.identifier` (the token that routes)",
         "`name`", "`url`", "default `runtimePlatform`"],
        [[f"`{k}`", f'`{vocab["programming_language_identifier"][k]}`',
          f'`{vocab["language_name"].get(k, "—")}`',
          f'`{vocab["language_url"].get(k, "—")}`',
          f'`{vocab["default_runtime_platform"][k]}`'] for k in vt])

    regions["vocab-tool-types"] = _md_table(
        ["`tool.types[]` value", "resolves to"],
        sorted(([f'`{k}`', f'`{v}`']
                for k, v in vocab["tool_type_aliases"].items()), key=lambda r: r[0]))

    regions["vocab-gaps"] = "\n".join(
        f"- **`{g['vre_type']}`** has no entry in "
        f"{', '.join('`' + m + '`' for m in g['missing_from'])}. "
        f"{g['consequence']}." for g in vocab["known_gaps"])

    regions["uri-resolution"] = "\n".join(
        f"{i+1}. {step}" for i, step in enumerate(vocab["resolution_order"]))
    # Order is normative here: the resolver takes the FIRST substring that
    # matches, so sorting this table alphabetically would document a different
    # function than the one that runs.
    regions["uri-fallbacks"] = _md_table(
        ["#", "substring in the tool uri", "`vre_type`"],
        [[str(i + 1), f'`{p}`', f'`{v}`']
         for i, (p, v) in enumerate(vocab["uri_fallback_patterns"])])

    mime = artefacts["mime-extensions.json"]
    regions["mime-table"] = _md_table(
        ["extension", "`encodingFormat`"],
        sorted(([f'`{k}`', f'`{v}`'] for k, v in
                mime["extension_to_mime"].items()), key=lambda r: r[0]))

    rf = artefacts["reference-forms.json"]
    regions["reference-forms"] = _md_table(
        ["property", "alternative form", "same value as an object (control)",
         "difference vs control", "linter says"],
        [[f'`{r["property"]}` — {r["note"]}',
          f'{r["form"]} → {_fmt_counts(r.get("counts")) if isinstance(r.get("counts"), dict) else "*" + r["outcome"] + "*"}',
          f'{r["control_form"]} → {_fmt_counts(r.get("control_counts"))}',
          (", ".join(f"**{k}** {v[0]}→{v[1]}" for k, v in r["lost"].items())
           if r.get("lost") else "")
          + ("; " if r.get("lost") and r.get("changed") else "")
          + ("**slot values differ**" if r.get("changed") else "")
          or ("—" if r.get("outcome") == "parsed" else "*rejected*"),
          ", ".join(r["violations"]) or "**nothing**"]
         for r in rf["forms"]])
    _c = rf["conclusion"]
    regions["reference-forms-verdict"] = (
        f"- **tolerated, no loss**: "
        f"{', '.join(f'`{t}`' for t in _c['tolerated']) or 'none'}\n"
        f"- **fatal**: {', '.join(f'`{t}`' for t in _c['fatal']) or 'none'}\n"
        f"- **data loss, and the linter says so**: "
        f"{'; '.join(_c['data_loss_reported']) or 'none'}\n"
        f"- **data loss with NO rule firing** — the rows a consumer can't detect: "
        f"{'; '.join(_c['data_loss_unreported']) or '**none**'}"
        f"\n\nControl row (all four counts at their healthy values): "
        + _fmt_counts(rf["baseline_counts"]) + ".")

    af = artefacts["array-forms.json"]
    regions["array-forms"] = _md_table(
        ["list-valued property", "builder emits", "array intact",
         "array wrapper dropped", "lost", "linter today", "…without W014"],
        [[f'`{r["property"]}` on `{r["entity"]}`', r["emitted_as"],
          _fmt_counts(r.get("as_list")),
          _fmt_counts(r.get("collapsed")) if r.get("collapsed") != "not attempted"
          else "*not attempted*",
          ", ".join(f"**{k}** {v[0]}→{v[1]}" for k, v in r["lost"].items())
          if r.get("lost") else ("—" if r.get("outcome") == "parsed"
                                 else "*rejected*"),
          ", ".join(r["violations"]) or "**nothing**",
          ("**silence**" if r.get("silent_without_W014")
           else (", ".join(r["violations_without_W014"])
                 if r.get("violations_without_W014") else "—"))
          if "violations_without_W014" in r else "—"]
         for r in af["forms"]])
    regions["array-forms-verdict"] = (
        "Producer baseline: " + _fmt_counts(af["baseline"]) + ".\n\n"
        "**Silently emptied today** - accepted by the parser, no linter rule "
        "fires, and the count is lower than the same crate with the array "
        "wrapper intact: "
        + (", ".join(f"`{t}`" for t in af["silent_after_collapse"])
           or "**nothing**; every collapse in the table trips at least one rule")
        + ".\n\n"
        "**What rule W014 is for.** Re-running the same crates against a linter "
        "without W014 leaves these losses completely undetected, which is the "
        "state this spec was in before the rule existed:\n\n"
        + "\n".join(f"- {h}" for h in af["holes_W014_closes"])
        + "\n\n(`hasPart` is not in that list only because W008 happens to fire "
        "there as well. The `input` and `output` collapses had no other cover: a "
        "dropped array wrapper there returns a **successfully parsed** crate with "
        "an empty slot list, no exception, and no diagnostic of any kind.)")

    sb = artefacts["slot-bindings.json"]
    regions["slot-binding-cases"] = _md_table(
        ["case", "`@type` declared", "`defaultValue` as written",
         "`file_for_input()`", "in `input_files`?"],
        [[label, f"`{s['declared_type']}`", f"`{s['default_value_json']}`",
          f"`{s['file_for_input']}`" if s["file_for_input"] else "**None**",
          "yes" if s["file_for_input"]
          and s["file_for_input"] in case["input_files"] else "no"]
         for label, case, want in (
             ("file-bound slot (intended)", sb["intended"], "Input 1"),
             ("literal slot (intended)", sb["intended"], "pdb_id"),
             ("string slot, value collides with a file `@id`, **file present**",
              sb["collider_with_file_present"], "looks_literal"),
             ("same slot, same string, **file absent**",
              sb["collider_with_file_absent"], "looks_literal"),
             ("declared slot, no value supplied", sb["unfilled_slot"],
              "Input 1"))
         for s in [next(x for x in case["slots"] if x["name"] == want)]])
    regions["slot-binding-findings"] = "\n".join(
        f"- {f['claim']} - **{'confirmed' if f['confirmed'] else 'NOT CONFIRMED'}**"
        for f in sb["findings"])

    fv = artefacts["field-visibility.json"]
    regions["field-visibility"] = _md_table(
        ["producer-side field", "reach", "what the crate does with it",
         "readable through"],
        [[f'`{r["model"]}.{r["field"]}`', _TIER_LABELS[r["tier"]],
          _transition_summary(r),
          " · ".join(f'`{v}`' for v in r["reachable_via"]) or "**nothing**"]
         for r in fv["fields"]])
    # Written as a region because the hand-written version of this note named
    # checksum_type as "the only row where the crate loses something", which was
    # true when written and became false as soon as the probe list grew to cover
    # ToolMeta.uri and SlotDefinition.name. A claim about the SHAPE of a result
    # rots exactly like a count of it.
    def lost(p: str) -> str:
        # `/@graph[6]/defaultValue/@id` -> `defaultValue/@id`. The @graph index is
        # positional and means nothing to a reader, but the last segment alone
        # (`@id`) reads like a claim about the identity of an entity.
        return re.sub(r"^/@graph\[\d+\]/", "", p)

    regions["field-visibility-losses"] = "\n".join(
        f"- setting `{r['model']}.{r['field']}` to {r['probe_value']} removes "
        # Deduplicated: the baseline carries two files, so a probe that drops
        # sha256 from both printed "`sha256`, `sha256`" - which read as two
        # different properties and hid that it was one property on two entities.
        + ", ".join(f'`{name}`' for name in
                    dict.fromkeys(lost(p) for p in r["removed_paths"]))
        for r in fv["fields"] if r["removed_paths"])
    # Counts and definitions only. An earlier version re-listed every field under
    # its tier, which just reprinted column 1 of the table against column 2 - the
    # table is the per-field authority and repeating it made the section twice as
    # long to disagree with itself later.
    regions["field-visibility-tiers"] = "\n".join(
        f"- **{label}** ({len(fv[key])}) - {desc}"
        for key, label, desc in (
            ("promoted", "named field",
             "the parser copies it onto a field of the payload"),
            ("properties_only", "`properties` only",
             "no field of its own, but present in the dict the parser fills "
             "from the whole entity, so it IS readable"),
            ("raw_crate_only", "`raw_crate` only",
             "not on any parsed object; only in the verbatim copy of the crate "
             "that `VREPayload.raw_crate` holds"),
            ("consumed_not_readable", "unreadable",
             "the builder used it and the crate shows the effect, but the value "
             "itself cannot be recovered by any consumer"),
            ("never_serialized", "never serialized",
             "changing it alters no byte of the crate"))
        if fv[key])

    regions["unemitted-keys"] = "\n".join(
        f"- `{e['key']}` - read at `{e['read_at']}`"
        for e in artefacts["unemitted.json"]["read_but_never_emitted"])

    idp = artefacts["id-patterns.json"]
    regions["id-table"] = _md_table(
        ["`@id`", "role", "meaning"],
        [[f'`{r["pattern"]}`', r["role"], r["meaning"]] for r in idp["reserved"]])
    regions["id-rules"] = "\n".join(f"- {r}" for r in idp["allocation_rules"])

    order = artefacts["entities.json"]["emission_order"]
    regions["emission-order"] = (
        "```json\n" + "\n".join(f"{i+1}. {e}" for i, e in enumerate(order)) + "\n```")

    for name, (golden, role, index) in sorted(EXCERPTS.items()):
        crate = artefacts[golden]
        by_role = _by_role(crate)
        if role not in by_role or index >= len(by_role[role]):
            raise AssertionError(
                f"EXCERPTS['{name}'] wants role {role!r} (index {index}) from "
                f"{golden}, which has {sorted(by_role)} - the example changed or "
                f"the role no longer exists; fix the table, do not hand-write "
                f"the JSON back into the prose")
        excerpt, shortened = _trimmed(by_role[role][index])
        regions[f"excerpt-{name}"] = (
            ("*Long free-text values shortened for readability; every `@id`, "
             "type and structure is verbatim.*\n\n" if shortened else "")
            + "```json\n" + json.dumps(excerpt, indent=2) + "\n```")

    descriptor = [e for e in artefacts["examples/galaxy.json"]["@graph"]
                  if e.get("@id") == "ro-crate-metadata.json"][0]
    regions["profile-literals"] = ("```json\n"
                                   + json.dumps(descriptor, indent=2)
                                   + "\n```")

    goldens = artefacts["examples.json"]["entries"]
    regions["golden-index"] = _md_table(
        ["file", "source", "profile", "builder can emit all its types?",
         "violates, W012 withheld"],
        # BOTH path columns are repo-root-relative, so a reader resolves either
        # the same way and the spec's path-citation test can check the golden's
        # own location too. Keys are relative to generated/, which read fine until
        # they sat beside repo-root sources and did not.
        [[f'`{rel}`', f'`{m["source"]}`', m["profile"],
          "yes" if m["builder_can_emit_all_types"] else "no: " + ", ".join(m["types_not_emittable"]),
          ", ".join(m["violations_pre_profile"]) or "-"]
         for slug, m in sorted(goldens.items())
         for rel in [(OUTPUT_DIR / slug).relative_to(ROOT).as_posix()]])

    schemas = artefacts["schemas.json"]
    regions["encodability"] = "\n".join([
        f"- `schema-core.json` enforces: {', '.join(schemas['encodable']['core'])}",
        f"- `schema-infrastructure.json` enforces: "
        f"{', '.join(schemas['encodable']['infrastructure'])}",
        f"- **no schema can enforce**: "
        f"{', '.join(schemas['not_encodable_in_any_profile'])} - each needs a lookup "
        "across `@graph`, which JSON Schema `contains` cannot express",
    ])
    # FormalParameter.additionalType, counted rather than recalled. The prose
    # around this table explains WHY the two shapes never overlap; the counts and
    # the value lists come from the crates so they cannot drift from them.
    at = artefacts["additional-types.json"]
    def _shape_rows(shape: str, who: str) -> list[list[str]]:
        key = next((k for k in at["counts"] if k.endswith("|" + shape)), None)
        if key is None:
            return []
        values = at["counts"][key]
        listed = ", ".join(
            f"`{v}` ×{n}" if shape == "string"
            else '`{"@id": "' + v + '"}` ×' + str(n)
            for v, n in sorted(values.items(), key=lambda kv: -kv[1]))
        return [[shape, listed, who, str(len(at["crates"][key]))]]

    regions["additional-type-census"] = _md_table(
        ["shape", "observed values (count)", "who writes it", "crates"],
        [r for r in [
            *_shape_rows("string", "RocrateBuilder, verbatim from "
                                  "`SlotDefinition.slot_type`"),
            *_shape_rows("reference", "a producer outside this repo "
                                      "(`fixture-input` crates)"),
        ] if r])
    regions["negative-index"] = _md_table(
        ["file", "what it does wrong", "linter must report"],
        [[f'`{e["file"]}`', e["label"], ", ".join(e["expected_violations"])]
         for _, e in sorted(artefacts["negatives.json"]["entries"].items())])

    # Which checker notices the deletion of each MUST-marked property. Grouped by
    # property with the ROLE carried, because the answer is per (role, property)
    # and a property-level list would lie: `name` is schema-required on file,
    # workflow and computer-language and unnoticed on root-dataset,
    # input-dataset, FormalParameter and the three placeholders. The hand-written
    # table this replaced claimed `name` on "file/workflow/root", which is the
    # one role where deleting it is invisible.
    # One cell per (property, role): the probe crate carries two Files and two
    # FormalParameters, so a per-deletion list would repeat `license` three times
    # and read as three different findings. The count is shown where a role has
    # more than one such entity, because that is the case a reader would
    # otherwise miscount.
    rows = artefacts["must-enforcement.json"]["rows"]
    cells: dict[tuple[str, str], list[str]] = {}
    for row in rows:
        cells.setdefault((row["property"], row["role"]), []).append(row)
    by_prop: dict[str, dict[str, list[str]]] = {}
    for (prop, role), group in cells.items():
        bucket = by_prop.setdefault(prop, {"hit": [], "miss": []})
        n = len(group)
        label = f"`{role}`" + (f" ×{n}" if n > 1 else "")
        caught = sorted({c for r in group for c in r["caught_by"]})
        if all(r["unnoticed"] for r in group):
            bucket["miss"].append(label)
        elif not any(r["unnoticed"] for r in group):
            bucket["hit"].append(f"{label} ({', '.join(caught)})")
        else:
            # Same property, same role, different verdicts - only possible if the
            # entities differ, which is worth surfacing rather than averaging.
            bucket["hit"].append(f"{label} (PARTIAL: {', '.join(caught)})")
    regions["must-enforcement"] = _md_table(
        ["property", "deleting it is caught, by", "deleting it goes unnoticed on"],
        [[f"`{prop}`",
          "; ".join(sorted(v["hit"])) or "- nothing -",
          "; ".join(sorted(v["miss"])) or "- nowhere -"]
         for prop, v in sorted(by_prop.items())])
    return regions


def sync_prose(regions: dict[str, str], *, write: bool,
               tokens: "dict[str, str] | None" = None) -> list[str]:
    """Rewrite every marked region and inline token in docs/spec/*.md.

    Returns the stale files. Runs in both modes so `--check` reports prose drift
    with the same precision it reports JSON drift; a region that only got filled
    on a write would let a table go stale and be invisible to CI.

    A token whose value appears in the text is only evidence if it could have
    been wrong, so an unknown token is an error rather than a passthrough: a typo
    would otherwise leave the hand-typed number in place and looking maintained.
    """
    tokens = tokens or {}
    unknown: set[str] = set()
    stale: list[str] = []
    for path in sorted(PROSE_DIR.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        for match in INLINE_RE.finditer(text):
            if match.group(1) not in tokens:
                unknown.add(f"{path.name}: {match.group(0)}")
        opened = len(BEGIN_RE.findall(text))
        closed = text.count(END_MARK)
        if opened != closed:
            raise AssertionError(
                f"{path.name}: {opened} BEGIN markers but {closed} END "
                "- a region is unclosed or a marker is stray")
        spans = []
        for name, start, stop, matched in _regions_in(text):
            if name not in regions:
                unknown.add(f"{path.name}: {name}")
                continue
            filled = (BEGIN_MARK.format(name) + "\n" + regions[name]
                      + "\n" + END_MARK)
            if matched != filled:
                stale.append(path.name)
                spans.append((start, stop, filled))
        # Splice back-to-front so the earlier offsets stay valid.
        for start, stop, filled in reversed(spans):
            text = text[:start] + filled + text[stop:]
        # Tokens name values in HAND-WRITTEN prose. A generated region never
        # needs one - it interpolates the Python value directly - and allowing
        # one inside a region body would oscillate: the splice would write the
        # token form, this pass would substitute it, and the next run would call
        # that stale forever. Refuse the combination instead of debugging it.
        for body in regions.values():
            if INLINE_RE.search(body):
                raise AssertionError(
                    "a generated region body contains an inline token marker; "
                    "interpolate the value in the generator instead")
        # The marker is kept and only the value after it is rewritten - dropping
        # the marker would fix the number once and delete the claim, which is how
        # the 13s got here in the first place.
        def fill(match: "re.Match[str]") -> str:
            name, current = match.group(1), match.group(2)
            if name not in tokens:
                # Left verbatim so the reporter at the end of the loop can list
                # every unknown in every file at once, rather than crashing on the
                # first one. It is already in `unknown`.
                return match.group(0)
            want = tokens[name]
            if current != want:
                stale.append(path.name)
            return INLINE_MARK.format(name) + want

        text = INLINE_RE.sub(fill, text)
        if write:
            path.write_text(text, encoding="utf-8")
    if unknown:
        raise AssertionError(
            "prose cites generated values nothing produces: "
            + ", ".join(sorted(unknown))
            + "\nknown regions: " + ", ".join(sorted(regions))
            + "\nknown tokens: " + ", ".join(sorted(tokens)))
    return sorted(set(stale))


def _dump(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true",
                        help="fail if the committed artefacts differ")
    args = parser.parse_args(argv)

    artefacts = build_artefacts()
    stale = []
    for name, value in artefacts.items():
        text = _dump(value)
        path = OUTPUT_DIR / name
        if args.check:
            if not path.is_file() or path.read_text(encoding="utf-8") != text:
                stale.append(name)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            print(f"wrote {path.relative_to(ROOT)}")

    stale += [f"{name} (prose)" for name in sync_prose(
        prose_regions(artefacts), write=not args.check,
        tokens=inline_tokens(artefacts))]

    if args.check and stale:
        print("stale artefacts: " + ", ".join(sorted(stale)), file=sys.stderr)
        print("regenerate with: .venv/bin/python tools/gen_wire_spec.py",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
