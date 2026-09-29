"""A dependency-free linter for the req-packager wire format.

This module IS part of the specification. Copy it into a consumer component and
it checks crates your own producer emitted, with no install step: pure stdlib,
nothing else, no imports from this repo. It exists because JSON Schema cannot
express the six cross-entity rules - and those are the ones that fail silently
(W002 loses an entity, W006 yields vre_type "unknown", W008 hides a file, W011
drops a slot). A schema-valid crate can still violate all six.

    from wire_spec_lint import lint          # -> ["W008", "W012"]
    lint_report(crate)                        # -> {"violations": [...], "undecidable": [...]}

    .venv/bin/python tools/wire_spec_lint.py docs/spec/generated/examples/galaxy.json

LINT_RULES is the table docs/spec/generated/lint-rules.json is generated from,
so each rule's file:line provenance and its machine-readable encoding stay
together. `tools/gen_wire_spec.py` refuses to run if WIRE_FORMAT_PROFILE below
drifts from vre_rocrate.constants.WIRE_FORMAT_PROFILE.
"""

from __future__ import annotations

import json
import re
import sys
from typing import Any

# The profile URI a conforming crate must declare (rule W012). Duplicated from
# vre_rocrate.constants on purpose - this file must stay importable by someone
# who has not installed the library - and asserted equal at generation time.
WIRE_FORMAT_PROFILE = "https://w3id.org/eosc-vre/req-packager/1.0"

# Where each rule's enforcement actually lives. Rule text says "the parser
# skips this silently"; that claim is only true of specific code, and a rule
# whose cited code has moved is worse than no rule. `decided_at` is resolved
# from (file, symbol) at generation time by tools/gen_wire_spec.py, so the
# line numbers in docs/spec/generated/lint-rules.json are never hand-typed and
# generation FAILS if a cited symbol is renamed or deleted.
#
# An anchor names the code that CREATES the consequence, which is not always
# the code that detects the problem: W001 is detected by validation but the
# consequence worth documenting is the by-id matching downstream.
DECIDED_AT: dict[str, tuple[str, str]] = {
    "W001": ("parsing/validator.py", "_validate_entity_ids"),
    "W002": ("parsing/validator.py", "_find_entity"),
    "W003": ("parsing/validator.py", "_validate_main_entity"),
    "W004": ("building/payload.py", "_get_main_entity"),
    "W005": ("parsing/validator.py", "_validate_programming_language"),
    "W006": ("building/payload.py", "_resolve_language_id"),
    "W007": ("building/payload.py", "_extract_files"),
    "W008": ("building/payload.py", "_extract_files"),
    "W009": ("models/payload.py", "input_files"),
    "W010": ("building/rocrate.py", "_build_file_entity"),
    "W011": ("building/payload.py", "_extract_parameters"),
    "W012": ("building/rocrate.py", "_add_metadata_descriptor"),
    "W013": ("parsing/infrastructure.py", "parse_input_file"),
    "W014": ("building/payload.py", "_extract_parameters"),
}

LINT_RULES: list[dict[str, Any]] = [
    {"id": "W001", "rule": "every @graph entity declares a non-empty string @id",
     "consequence": "ValidationPipeline rejects the crate",
     "needs": [],
     "enforced_by": "entity"},
    {"id": "W002", "rule": "@id values are unique across @graph",
     "consequence": "validation does NOT catch this: dereferencing returns the "
                    "first match and the shadowed entity is silently lost",
     "needs": [],
     "enforced_by": "none"},
    {"id": "W003", "rule": "a root dataset with @id './' exists and declares mainEntity",
     "consequence": "ValidationPipeline rejects the crate",
     "needs": [],
     "enforced_by": "graph"},
    {"id": "W004", "rule": "mainEntity resolves to an entity that exists in @graph",
     "consequence": "ValidationPipeline rejects the crate",
     "needs": ["W003"],
     "enforced_by": "none"},
    {"id": "W005", "rule": "the workflow declares programmingLanguage as an "
     "object with @id",
     "consequence": "a bare string passes validation but crashes the parser; "
                    "an array crashes both",
     "needs": ["W004"],
     "enforced_by": "entity"},
    {"id": "W006", "rule": "programmingLanguage resolves to an entity with a "
     "non-empty identifier",
     "consequence": "validation requires the key but not that it be non-empty; "
                    "an empty value yields vre_type 'unknown' downstream",
     "needs": ["W005"],
     "enforced_by": "none"},
    {"id": "W007", "rule": "root dataset declares hasPart (an empty list is legal)",
     "consequence": "a missing hasPart raises TypeError deep in the parser, "
                    "with no useful message",
     "needs": ["W003"],
     "enforced_by": "entity"},
    {"id": "W008", "rule": "every File entity appears in root hasPart",
     "consequence": "hasPart is the ONLY enumeration source for files; a File "
                    "entity absent from it is invisible to consumers. "
                    "RocrateBuilder never emits this shape, but the "
                    "TOSCA-authored galaxy_tosca_stage fixture does, so the "
                    "rule is about hand-authored producers",
     "needs": ["W007"],
     "enforced_by": "none"},
    {"id": "W009", "rule": "no File entity shares its @id with the workflow",
     "consequence": "VREPayload.input_files excludes the descriptor by @id, so "
                    "a colliding file is dropped from the data files. A crate "
                    "cannot make this mistake without ALSO duplicating an @id, "
                    "so W002 always fires alongside it",
     "needs": ["W004"],
     "enforced_by": "none"},
    {"id": "W010", "rule": "a sha256 property, when present, is a 64-character "
     "lowercase hex digest",
     "consequence": "this library copies FileInput.checksum verbatim and does "
                    "not check its shape, so a truncated or non-hex digest is "
                    "published as-is and only fails a consumer that verifies it",
     "needs": [],
     "enforced_by": "entity"},
    {"id": "W011", "rule": "every reference in workflow.input and workflow.output "
     "resolves to an entity in @graph",
     "consequence": "unresolvable references are skipped, so the slot silently "
                    "never exists for the consumer. Note that an inline "
                    "FormalParameter object is NOT a substitute for a graph "
                    "entity: only its @id is read, and the entity with that @id "
                    "supplies every property, so inline properties are ignored",
     "needs": ["W004"],
     "enforced_by": "none"},
    {"id": "W012", "rule": "the root descriptor declares the wire format profile",
     "consequence": "consumers cannot detect a payload shape change",
     "needs": [],
     "enforced_by": "entity"},
    {"id": "W014", "rule": "every hasPart, input and output value is a list, "
     "even with exactly one element",
     "consequence": "the parse path iterates these values directly, so a single "
                    "object instead of a one-element array iterates its members "
                    "and yields nothing: the slot list or file list comes back "
                    "EMPTY with no exception and no other rule firing. Serialisers "
                    "that omit the wrapper for a lone element are common, which "
                    "makes this the cheapest way to lose a whole payload section "
                    "in a non-Python producer",
     "needs": [],
     "enforced_by": "entity"},
    {"id": "W013", "rule": "INFRASTRUCTURE PROFILE ONLY: each entry in a "
     "RuntimePlatform's input array is a full inline entity carrying @type "
     "\"File\", not a \"{\"@id\": \"...\"}\" reference to one",
     "consequence": "parsing/infrastructure.py reads @type off the entry itself "
                    "and never dereferences a reference, so a reference logs "
                    "\"Input is not of type File, skipping.\" and the input "
                    "file silently does not exist in RuntimePlatform.input_files",
     "needs": [],
     "enforced_by": "entity"},
]

# Rules whose violation is inseparable from another rule's, so a negative fixture
# for them is expected to report both. Without this the conformance test would
# have to assert something the wire format cannot actually do.
INSEPARABLE = {"W009": ["W002"]}

_HEX64 = re.compile(r"[0-9a-f]{64}\Z")

# The two slot lists on the main entity. Both are read by the same code path
# (`_extract_parameters`), so every rule about slots applies to both - `output`
# included, even though this library never populates it.
_SLOT_LIST_KEYS = ("input", "output")

# Positions the parse path iterates directly, so a single object instead of a
# one-element array iterates the object's members and yields nothing. Derived
# from the parse path, not guessed: see docs/spec/generated/array-forms.json,
# which measures each of these against the real parser on every generation run.
_ITERATED_LIST_KEYS = ("hasPart", *_SLOT_LIST_KEYS)


def lint(crate: dict[str, Any], *, profile: str | None = WIRE_FORMAT_PROFILE,
         rules: list[str] | None = None) -> list[str]:
    """Return the ids of the rules `crate` violates. Pure stdlib, no deps.

    See `lint_report` for the meaning of `profile` and `rules`.
    """
    return lint_report(crate, profile=profile, rules=rules)["violations"]


def lint_report(crate: dict[str, Any],
                *, profile: str | None = WIRE_FORMAT_PROFILE,
                rules: list[str] | None = None) -> dict[str, list[str]]:
    """Lint `crate`, reporting violations AND the rules that could not be judged.

    Every rule whose preconditions resolve is evaluated, so a crate with several
    problems reports all of them rather than the first. The rules that CANNOT be
    judged - because the entity they are stated about is missing - are returned
    in ``undecidable`` rather than being silently passed or silently failed. A
    conformance harness that conflated "clean" with "could not tell" would let a
    crate missing its root descriptor sail through fourteen checks looking
    spotless.

    ``profile`` is the profile URI a crate MUST declare (W012). Pass ``None`` to
    withhold that one rule, which is how pre-profile crates - all 13 fixtures,
    captured before the profile URI existed - are checked without being
    retroactively called invalid. Withheld rules land in ``undecidable``, never
    in a silent pass.

    ``rules`` restricts which rules are evaluated at all, for a caller that wants
    to test one predicate in isolation. A restricted run reports the excluded
    rules as undecidable rather than as passes, so it cannot be mistaken for a
    clean bill of health.
    """
    graph = crate.get("@graph", [])
    only = set(rules) if rules is not None else {r["id"] for r in LINT_RULES}
    ids = [e.get("@id") for e in graph]
    by_id: dict[Any, dict] = {}
    for e in graph:
        by_id.setdefault(e.get("@id"), e)

    violations: list[str] = []
    undecidable: list[str] = []

    def skip(*names: str) -> None:
        undecidable.extend(names)

    def fire(name: str) -> None:
        """Record a violation, or record that this run declined to judge it."""
        if name in only:
            violations.append(name)
        else:
            undecidable.append(name)

    def types(entity: dict) -> list[str]:
        t = entity.get("@type", [])
        return [t] if isinstance(t, str) else list(t)

    def ref_id(value: Any) -> Any:
        return value.get("@id") if isinstance(value, dict) else value

    if any(not isinstance(i, str) or not i for i in ids):
        fire("W001")
    if len(set(ids)) != len(ids):
        fire("W002")

    root = by_id.get("./")
    has_root = isinstance(root, dict) and root.get("mainEntity") is not None
    if not has_root:
        fire("W003")
        skip("W004", "W005", "W006", "W007", "W008", "W009", "W011")
        return _verdict(violations, undecidable)

    main_id = ref_id(root["mainEntity"])
    main = by_id.get(main_id)
    if not isinstance(main, dict):
        fire("W004")
        skip("W005", "W006", "W009", "W011")
    else:
        lang_ref = main.get("programmingLanguage")
        if not isinstance(lang_ref, dict) or "@id" not in lang_ref:
            fire("W005")
            skip("W006")
        else:
            lang = by_id.get(lang_ref["@id"])
            if lang is None or not lang.get("identifier"):
                fire("W006")

        if any(e is not main and "File" in types(e) and e.get("@id") == main_id
               for e in graph):
            fire("W009")

        # Both slot lists go through the same `continue`-on-unresolved code path,
        # so the rule covers both. Checking only `input` would leave a dangling
        # `output` reference - the one silent-drop shape a hand-authored crate is
        # likely to produce, since `output` has no builder-side guarantee - with no
        # rule firing and an empty workflow_outputs.
        referenced = {ref_id(i) for key in _SLOT_LIST_KEYS
                      for i in as_list(main.get(key))}
        if referenced - set(by_id):
            fire("W011")

    if "hasPart" not in root:
        fire("W007")
        skip("W008")
    else:
        part_ids = {ref_id(p) for p in as_list(root["hasPart"])}
        if any("File" in types(e) and e.get("@id") not in part_ids for e in graph):
            fire("W008")

    if any("sha256" in e and not _HEX64.match(str(e["sha256"])) for e in graph):
        fire("W010")

    for e in graph:
        if "RuntimePlatform" not in types(e):
            continue
        for item in as_list(e.get("input")):
            if isinstance(item, dict) and "File" not in types(item):
                fire("W013")

    # W014: a present-but-not-list value in a position the parser iterates.
    # Absence is not a violation here (hasPart is W007's business; input/output
    # are legitimately optional), so only a present value can fire this.
    for e in graph:
        for key in _ITERATED_LIST_KEYS:
            if key in e and not isinstance(e[key], list):
                fire("W014")

    if profile is None:
        skip("W012")
    else:
        desc = by_id.get("ro-crate-metadata.json")
        conforms = desc.get("conformsTo") if isinstance(desc, dict) else None
        members = [ref_id(c) for c in as_list(conforms)]
        if profile not in members:
            fire("W012")

    return _verdict(violations, undecidable)


def _verdict(violations: list[str], undecidable: list[str]) -> dict[str, list[str]]:
    """A rule that fired is never also reported as undecidable."""
    vs = sorted(set(violations))
    return {"violations": vs, "undecidable": sorted(set(undecidable) - set(vs))}


def as_list(value: Any) -> list:
    """Normalise a JSON-LD value that may be a single object or a list."""
    if value is None:
        return []
    return value if isinstance(value, list) else [value]

def main(argv: list[str]) -> int:
    """Lint each crate named on stdin and print its verdict. Exit 1 if any."""
    bad = False
    for path in argv:
        with open(path) as fh:
            crate = json.load(fh)
        report = lint_report(crate)
        print(f"{path}: "
              f"{'CLEAN' if not report['violations'] else 'VIOLATES ' + ', '.join(report['violations'])}"
              + (f"  (undecidable: {', '.join(report['undecidable'])})"
                 if report["undecidable"] else ""))
        bad = bad or bool(report["violations"])
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
