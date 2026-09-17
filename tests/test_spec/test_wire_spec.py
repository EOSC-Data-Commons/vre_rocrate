"""Guard the wire-format spec in docs/spec/ against drifting from the code.

The spec exists for teams who do NOT use this library, so the failure mode that
matters is not "a test is red" but "the document says something the code does
not do". These tests close the two ways that happens:

  * the generated artefacts go stale because someone edited the builder and did
    not regenerate (covered by test_committed_artefacts_match_the_generator);
  * a rule's stated consequence stops being true because the cited code was
    renamed, moved, or changed behaviour (covered by the decided_at anchors and
    the behavioural checks below).

Every test here is dependency-free. The jsonschema-backed checks are the only
exception and they report a skip with a visible reason rather than passing,
because a spec test that silently skips is how AGENTS.md ended up claiming 68
tests and 3 unformatted files.
"""

import json
import re
import sys
import unicodedata
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
TOOLS = ROOT / "tools"
SPEC = ROOT / "docs" / "spec" / "generated"

for p in (SRC, TOOLS):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import gen_wire_spec  # noqa: E402
from wire_spec_lint import DECIDED_AT, LINT_RULES, lint, lint_report  # noqa: E402

from vre_rocrate import WIRE_FORMAT_PROFILE  # noqa: E402


def _artefact(name: str):
    return json.loads((SPEC / name).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# The artefacts on disk are what the generator writes
# ---------------------------------------------------------------------------

def test_committed_artefacts_match_the_generator():
    """Regenerate in memory and diff against the committed files.

    Runs the generator rather than comparing hashes, so the message names the
    exact files to rewrite. This is the test that makes "update the builder
    and forget the spec" impossible instead of merely unlucky.
    """
    artefacts = gen_wire_spec.build_artefacts()
    stale = []
    for name, value in artefacts.items():
        text = gen_wire_spec._dump(value)
        path = SPEC / name
        if not path.is_file() or path.read_text(encoding="utf-8") != text:
            stale.append(name)
    assert not stale, (
        "docs/spec/generated is stale; regenerate with:\n"
        "    .venv/bin/python tools/gen_wire_spec.py\n"
        f"offending: {', '.join(sorted(stale))}")


def test_every_generated_file_is_accounted_for():
    """Catch the other direction: an artefact nobody regenerates any more."""
    produced = set(gen_wire_spec.build_artefacts())
    on_disk = {str(p.relative_to(SPEC)) for p in SPEC.rglob("*.json")}
    assert on_disk - produced == set(), (
        f"{sorted(on_disk - produced)} are committed but no longer generated - "
        "delete them or teach build_artefacts() to write them")


# ---------------------------------------------------------------------------
# The profile URI, which is the only version signal a consumer gets
# ---------------------------------------------------------------------------

def test_profile_uri_is_declared_in_one_place_per_consumer():
    from vre_rocrate import constants

    assert constants.WIRE_FORMAT_PROFILE == WIRE_FORMAT_PROFILE
    # tools/wire_spec_lint.py repeats the literal so consumers can copy the
    # file without installing anything. That duplication is deliberate and
    # generation asserts it; asserting it here too means the test suite catches
    # it even when nobody runs the generator.
    import wire_spec_lint

    assert wire_spec_lint.WIRE_FORMAT_PROFILE == WIRE_FORMAT_PROFILE


def test_builder_output_declares_the_profile():
    """The producer-side promise: every emitted crate carries the profile."""
    crate = _artefact("examples/galaxy.json")
    desc = [e for e in crate["@graph"]
            if e.get("@id") == "ro-crate-metadata.json"][0]
    members = [c.get("@id") if isinstance(c, dict) else c
               for c in as_list_of(desc["conformsTo"])]
    assert WIRE_FORMAT_PROFILE in members
    # Base RO-Crate MUST come first: the list is an ordered set of profiles and
    # a consumer that reads [0] to pick a parser would otherwise pick ours.
    assert "https://w3id.org/ro/crate/1.1" in members
    assert members.index("https://w3id.org/ro/crate/1.1") < members.index(
        WIRE_FORMAT_PROFILE)


def as_list_of(value):
    return value if isinstance(value, list) else [value]


# ---------------------------------------------------------------------------
# Rule provenance: does the cited code still exist, and does it still do that?
# ---------------------------------------------------------------------------

def test_rule_anchors_point_at_existing_symbols():
    """The anchors are (file, symbol); resolve them from the live tree."""
    for rule_id, (rel, symbol) in sorted(DECIDED_AT.items()):
        resolved = gen_wire_spec.resolve_symbol(rel, symbol)
        assert resolved["symbol"] == symbol
        assert (ROOT / resolved["file"]).is_file()

    committed = {r["id"]: r["decided_at"]
                 for r in _artefact("lint-rules.json")["rules"]}
    assert committed == {
        rid: gen_wire_spec.resolve_symbol(rel, sym)
        for rid, (rel, sym) in DECIDED_AT.items()}, (
        "decided_at lines moved; regenerate docs/spec/generated/lint-rules.json")


def test_lint_rule_table_is_self_consistent():
    ids = [r["id"] for r in LINT_RULES]
    assert len(ids) == len(set(ids))
    assert set(ids) == set(DECIDED_AT)
    for rule in LINT_RULES:
        # A rule is only useful to a producer if they can see what breaks.
        assert rule["consequence"], rule["id"]
        assert rule["enforced_by"] in ("entity", "graph", "none")
        for need in rule["needs"]:
            assert need in ids, f"{rule['id']} needs unknown rule {need}"


def test_vocabulary_tables_stay_in_step_with_the_documented_gap():
    """`constants.py` keeps five dicts in step by hand; pin the one place it fails.

    A vre_type that is resolvable but has no language entry produces a crate with
    `identifier: ""`, which validates, parses, and reaches a handler as
    `vre_type == "unknown"` — silently. That is not hypothetical: `rrp` does it
    today. This test does not forbid that (closing it needs an identity URI that
    only the vocabulary owners can choose), but it makes any *new* instance of the
    mistake a test failure, and makes fixing `rrp` a deliberate edit here rather
    than a surprise.
    """
    from vre_rocrate import constants

    resolvable = (set(constants.TOOL_TYPE_TO_VRE_TYPE.values())
                  | set(constants.VRE_TYPE_TO_DEFAULT_RUNTIME_PLATFORM))
    tables = {
        "VRE_TYPE_TO_PROGRAMMING_LANGUAGE":
            constants.VRE_TYPE_TO_PROGRAMMING_LANGUAGE,
        "VRE_TYPE_TO_DISPLAY_NAME": constants.VRE_TYPE_TO_DISPLAY_NAME,
        "VRE_TYPE_TO_LANGUAGE_URL": constants.VRE_TYPE_TO_LANGUAGE_URL,
        "VRE_TYPE_TO_DEFAULT_RUNTIME_PLATFORM":
            constants.VRE_TYPE_TO_DEFAULT_RUNTIME_PLATFORM,
    }
    found = {
        vre: sorted(name for name, table in tables.items() if vre not in table)
        for vre in sorted(resolvable)
        if any(vre not in table for table in tables.values())
    }

    # The document lists gaps in the same breath as the tables, from the same
    # artefact; compare against what 05-vre-vocabulary.md will render.
    documented = {g["vre_type"]: sorted(g["missing_from"])
                  for g in gen_wire_spec.build_artefacts()["vocabulary.json"]["known_gaps"]}
    assert found == documented, (
        f"vocabulary table desynchronisation changed: code says {found}, the "
        f"spec documents {documented}. If a type was added, register it in every "
        "table; if `rrp` was fixed, update docs/spec/05-vre-vocabulary.md §gaps "
        "and this test's expectation together.")
    # Pinned literally, so that fixing rrp — or adding a second hole — cannot be
    # waved through as "the test still matches the document".
    assert found == {"rrp": ["VRE_TYPE_TO_DISPLAY_NAME",
                             "VRE_TYPE_TO_LANGUAGE_URL",
                             "VRE_TYPE_TO_PROGRAMMING_LANGUAGE"]}, (
        "the rrp gap is expected to be the only one, missing exactly the three "
        "language tables; see docs/spec/05-vre-vocabulary.md §gaps")


@pytest.mark.parametrize("rule_id", [r["id"] for r in LINT_RULES])
def test_negative_fixture_still_trips_its_rule(rule_id):
    """The linter's teeth, re-proved on the committed files.

    Generation refuses to write these fixtures unless the linter agrees, but a
    committed crate could also be edited by hand into something that no longer
    demonstrates anything. Re-running the linter over the shipped bytes is what
    makes "every rule has a proven counterexample" a fact about the release
    rather than about the last time someone ran the generator.
    """
    entries = _artefact("negatives.json")["entries"]
    entry = entries[rule_id]
    crate = _artefact(entry["file"])
    report = lint_report(crate)
    assert report["violations"] == entry["expected_violations"], (
        f"{rule_id}'s negative now reports {report['violations']}, expected "
        f"{entry['expected_violations']}")
    assert report["undecidable"] == entry["expected_undecidable"]


def test_negatives_are_not_vacuously_clean():
    """A negative that reports nothing proves nothing.

    Redundant with the test above in the happy path; its job is to fail loudly
    if the parametrised list above ever becomes empty, which is the way a
    check like that rots.
    """
    entries = _artefact("negatives.json")["entries"]
    assert len(entries) == len(LINT_RULES)
    for rule_id, entry in entries.items():
        assert rule_id in entry["expected_violations"], (
            f"{rule_id}'s fixture does not violate {rule_id}")


def test_golden_crates_are_clean_under_their_own_profile():
    goldens = _artefact("examples.json")["entries"]
    # Not a magic number: the same set of sources the generator enumerates, so
    # adding an example or a fixture cannot silently drop a golden (the slug
    # collision that once silently overwrote five of them is what this guards).
    import gen_wire_spec

    expected = (len(list((ROOT / "examples").glob("*.py")))
                + 1  # the probe-matrix superset golden
                + len(list(gen_wire_spec._iter_fixtures())))
    assert len(goldens) == expected, (
        f"{len(goldens)} goldens committed but {expected} sources exist - a "
        "name collision or a skipped source silently dropped one")
    for slug, meta in sorted(goldens.items()):
        crate = _artefact(slug)
        if meta["origin"] == "builder-output":
            assert lint(crate) == [], f"{slug} violates a rule"
        else:
            # All 13 fixtures predate the profile URI, so W012 is withheld and
            # whatever is left is what the golden recorded. galaxy_tosca_stage
            # genuinely violates W008 and W013 in real producer data - a
            # hand-authored crate can be parseable and still non-conformant.
            assert lint(crate, profile=None) == meta["violations_pre_profile"], (
                f"{slug} now violates {lint(crate, profile=None)} but "
                f"examples.json records {meta['violations_pre_profile']}")
            assert not meta["declares_wire_profile"]


def test_undecidable_is_never_simultaneously_a_violation():
    """The report's two lists must stay disjoint or the whole design is a lie."""
    for name in sorted((SPEC / "negatives").glob("*.json")):
        report = lint_report(json.loads(name.read_text()))
        assert not set(report["violations"]) & set(report["undecidable"]), name
    missing_root = {"@graph": [{"@id": "x", "@type": "File"}]}
    report = lint_report(missing_root)
    assert report["violations"] == ["W003"]
    # The rules stated about the root descriptor cannot be judged without it,
    # and saying so is the difference between a harness and a rubber stamp.
    assert {"W004", "W007", "W008", "W011"} <= set(report["undecidable"])
    assert "W003" not in report["undecidable"]


# ---------------------------------------------------------------------------
# Layer 2: JSON Schema. Optional dependency, so it skips LOUDLY.
# ---------------------------------------------------------------------------

# Layer 2 is optional, so it has to skip per-test rather than at import. A
# module-level pytest.importorskip would abort the whole FILE during collection
# and take the dependency-free Layer-1 tests with it - which is precisely the
# "test suite that quietly stops checking anything" failure this file exists to
# catch. The fixture below skips four tests and says why, and leaves the other
# twenty-two running on a machine with nothing but the stdlib.
@pytest.fixture(scope="module")
def jsonschema():
    return pytest.importorskip(
        "jsonschema",
        reason="jsonschema is not installed, so Layer-2 schema checks are "
               "skipped; the dependency-free linter tests still ran. Install "
               "with: .venv/bin/python -m pip install -e '.[dev]'")




def test_schemas_are_valid_draft_2020_12(jsonschema):
    for name in ("schema-core.json", "schema-infrastructure.json"):
        schema = _artefact(name)
        jsonschema.Draft202012Validator.check_schema(schema)


def test_builder_goldens_validate_against_their_profile(jsonschema):
    goldens = _artefact("examples.json")["entries"]
    for slug, meta in sorted(goldens.items()):
        if meta["origin"] != "builder-output":
            continue
        schema = _artefact(f"schema-{meta['profile']}.json")
        errors = list(jsonschema.Draft202012Validator(
            schema).iter_errors(_artefact(slug)))
        assert not errors, f"{slug} rejected: " + "; ".join(
            f"{e.json_path}: {e.message}" for e in errors)


def test_every_negative_is_rejected_by_the_schemas(jsonschema):
    """A schema that accepts everything is worthless, so this is the load-bearing
    Layer-2 test - for the six rules JSON Schema CAN encode. The other six are
    structurally out of reach (see schemas.json 'not_encodable_in_any_profile'),
    which is why the linter is Layer 1 and not a convenience."""
    schemas = {p: _artefact(f"schema-{p}.json") for p in ("core", "infrastructure")}
    encodable = _artefact("schemas.json")["encodable"]
    for rule_id, crate in sorted(
            (f.stem, json.loads(f.read_text()))
            for f in (SPEC / "negatives").glob("*.json")):
        judged = [p for p in schemas if rule_id in encodable[p]]
        if not judged:
            continue
        rejected = any(
            list(jsonschema.Draft202012Validator(
                schemas[p]).iter_errors(crate)) for p in judged)
        assert rejected, (
            f"negatives/{rule_id}.json passes the {judged} schema(s) even though "
            f"{rule_id} is declared encodable there")


def test_schema_and_linter_agree_exactly(jsonschema):
    """Two independent implementations, one verdict, on every shipped crate.

    The point of shipping both is that a consumer can validate with whichever
    they have; that only works if they cannot disagree. The precise claim is
    stronger than "they point the same way": the schema rejects a crate IF AND
    ONLY IF the linter sees a rule the schema is able to encode. So a crate that
    only breaks cross-entity rules (W002, W004, W006, W008, W009, W011) is
    schema-valid and lint-dirty BY DESIGN, and a crate the schema rejects cannot
    be lint-clean. schemas.json records this computed during generation; this
    recomputes it from the shipped files, so the claim is checked at test time
    and not merely asserted at build time.
    """
    goldens = _artefact("examples.json")["entries"]
    encodable = _artefact("schemas.json")["encodable"]
    rejected_count = 0
    for slug, meta in sorted(goldens.items()):
        crate = _artefact(slug)
        schema = _artefact(f"schema-{meta['profile']}.json")
        rejected = bool(list(jsonschema.Draft202012Validator(
            schema).iter_errors(crate)))
        judgable = encodable[meta["profile"]]
        seen = [v for v in lint(crate) if v in judgable]
        assert rejected == bool(seen), (
            f"{slug}: schema rejected={rejected}, linter saw {seen} of the "
            f"rules that profile can encode ({judgable})")
        rejected_count += rejected
    # Non-vacuity: if no golden were ever rejected the equivalence above would
    # be "false == false" fourteen times, which proves nothing. Every fixture
    # predates the profile URI, so W012 makes these rejections real.
    assert rejected_count, "no golden is schema-rejected - the check is vacuous"
    assert rejected_count == sum(
        1 for m in goldens.values() if m["origin"] == "fixture-input")


def test_committed_prose_matches_the_generator():
    """The prose half of `--check`, which nothing else in the suite covered.

    `test_committed_artefacts_match_the_generator` diffs the JSON and stops
    there, so a rule could change, the JSON regenerate, and every generated TABLE
    in docs/spec/*.md go stale unnoticed by `pytest` - caught only by someone
    remembering to run `--check` by hand. docs/spec/README.md claims otherwise
    ("fail if stale (used by tests/test_spec)"), and until this test existed that
    claim was false for the prose, which is the part people actually read.
    """
    artefacts = gen_wire_spec.build_artefacts()
    stale = gen_wire_spec.sync_prose(
        gen_wire_spec.prose_regions(artefacts), write=False,
        tokens=gen_wire_spec.inline_tokens(artefacts))
    assert not stale, (
        "generated regions in docs/spec are stale; regenerate with:\n"
        "    .venv/bin/python tools/gen_wire_spec.py\n"
        f"offending: {', '.join(stale)}")


def test_inline_token_markers_round_trip(tmp_path, monkeypatch):
    """A `<!-- GEN:name -->14` marker must survive a write and read back stable.

    This is the mechanism's one non-obvious failure mode. Generation keeps the
    marker and rewrites only the value after it; if the value contained a
    character the scanner excludes (a space, a comma), the scanner would read back
    a shorter value, call the file stale, rewrite the longer one, and the spec
    would be permanently un-passable - loud, but in a way that reads like a
    generator bug rather than a bad token. Tested on the REAL token set, not a
    synthetic one, because that is what would have to break.
    """
    tokens = gen_wire_spec.inline_tokens(gen_wire_spec.build_artefacts())
    assert tokens, "no inline tokens defined - this test would pass vacuously"
    for name, value in tokens.items():
        assert gen_wire_spec.INLINE_VALUE_RE.match(value), (
            f"token {name}={value!r} cannot round-trip through the prose scanner")
        marker = gen_wire_spec.INLINE_MARK.format(name) + value
        match = gen_wire_spec.INLINE_RE.fullmatch(marker)
        assert match and match.group(1) == name and match.group(2) == value, (
            f"token {name} does not read back from its own committed form")
    # And the stale-detection path itself: a marker holding a wrong value must be
    # reported, or a drifted number would silently become the new truth.
    name, value = next(iter(tokens.items()))
    marker = gen_wire_spec.INLINE_MARK.format(name)
    wrong = "99"  # cannot equal any of these counts, and cannot prefix-match one
    doc = tmp_path / "t.md"
    doc.write_text(f"there are {marker}{wrong} rules\n", encoding="utf-8")
    monkeypatch.setattr(gen_wire_spec, "PROSE_DIR", tmp_path)

    assert gen_wire_spec.sync_prose({}, write=False, tokens=tokens) == ["t.md"], (
        "a marker holding the wrong value was not reported stale - the drift this "
        "mechanism exists to prevent would pass silently")
    gen_wire_spec.sync_prose({}, write=True, tokens=tokens)
    assert gen_wire_spec.sync_prose({}, write=False, tokens=tokens) == []
    text = doc.read_text(encoding="utf-8")
    assert f"{marker}{value}" in text, (
        "filling a token removed the marker, which would make the number correct "
        "once and uncheckable forever - exactly how the stale 13s got written")
    assert wrong not in text


def test_github_anchor_algorithm_matches_the_one_ground_truth():
    """The slug function below is also used by the link test, so pin it here.

    Without this, a systematically wrong slug function would regenerate both the
    links and their expectations and the link test would pass while every anchor
    404s on GitHub. These five are independent of this repo: they follow from
    GitHub's slug being lowercase, then DELETE punctuation/symbols (not
    hyphenate), then space -> '-'.

    The second and third are the ones actually got wrong on first writing:
    github-slugger's strip class runs `!-,` (U+0021..U+002C) and then jumps over
    U+002D to `\\.`, so HYPHEN-MINUS AND UNDERSCORE SURVIVE. Dropping them turns
    `root-dataset` into `rootdataset`, which matches nothing. The `#` and em-dash
    cases go the other way - deleted outright, so the spaces either side collapse
    into a DOUBLE hyphen that looks like a typo and is not one.
    """
    cases = {
        "List-valued properties": "list-valued-properties",   # '-' kept
        "`@id` allocation": "id-allocation",                   # backticks deleted
        "The `#` prefix": "the--prefix",                       # '#' deleted -> '--'
        "W013 — `RuntimePlatform.input` entries are not references": (
            "w013--runtimeplatforminput-entries-are-not-references"),
        "tool.types → vre_type": "tooltypes--vre_type",        # '→' deleted -> '--'
    }
    for heading, expected in cases.items():
        assert _heading_anchor(heading) == expected, (
            f"slug for {heading!r} changed - every anchor in docs/spec is now "
            f"computed wrong")


def _heading_anchor(text):
    """GitHub's heading slug, as computed by the link test below.

    Equivalent to github-slugger's regex on this corpus because every heading
    character here is ASCII alnum, '-', '_', a Unicode letter or a Unicode mark;
    the `else: assert` fails if that ever stops being true rather than guessing.
    """
    out = []
    for ch in text.lower():
        category = unicodedata.category(ch)
        if ch == " ":
            out.append("-")
        elif ch.isascii() and (ch.isalnum() or ch in "-_"):
            out.append(ch)
        elif category[0] in ("L", "M"):
            out.append(ch)
        else:
            assert category[0] in ("P", "S", "Z"), f"unclassified char {ch!r}"
    return "".join(out)


def _heading_anchors(doc):
    """Slug -> raw title for every heading outside a fenced block.

    A heading inside a fence is not a heading, and GitHub appends `-1`, `-2` to
    repeated slugs, which the numbering here reproduces.
    """
    anchors, seen, in_fence = {}, {}, False
    for line in doc.read_text(encoding="utf-8").splitlines():
        if re.match(r"^\s*(```|~~~)", line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = re.match(r"^(#{1,6})\s+(.*?)\s*$", line)
        if not m:
            continue
        title = m.group(2)
        # GitHub slugs the rendered text: link text, no markup.
        title = re.sub(r"\[([^\]]*)\]\((?:[^()]|\([^()]*\))*\)", r"\1", title)
        base = _heading_anchor(re.sub(r"\*\*([^*]*)\*\*", r"\1",
                                     re.sub(r"`([^`]*)`", r"\1", title)))
        n = seen.get(base, 0)
        seen[base] = n + 1
        anchors[base if n == 0 else f"{base}-{n}"] = m.group(2)
    return anchors


def test_spec_cross_references_resolve_as_links():
    """Every mutual reference between docs/spec pages is a clickable link, and
    every link lands.

    This prose is handed to teams implementing the format in another language,
    who navigate it on GitHub. A `§version negotiation` is only useful if you can
    jump to it, and a link whose anchor drifted from a renamed heading is worse
    than the plain text it replaced: it looks authoritative and goes nowhere. A
    heading rename is an entirely reasonable edit to make and nothing else in the
    suite would notice.
    """
    prose = sorted((ROOT / "docs" / "spec").glob("*.md"))
    assert len(prose) >= 8, f"expected the full spec set, found {len(prose)}"
    index = {doc.name: _heading_anchors(doc) for doc in prose}

    # Links must be found in the joined text, not line by line: a markdown link
    # may wrap and GitHub resolves it anyway, so a line-based scan would skip it
    # and then report the § inside its text as an unconverted reference.
    link = re.compile(r"(?<!!)\[(?P<text>[^\]\[]*)\]\((?P<target>[^()\s]+)\)")
    problems = []
    checked = 0
    for doc in prose:
        text, in_fence = [], False
        for line in doc.read_text(encoding="utf-8").splitlines(keepends=True):
            if re.match(r"^\s*(```|~~~)", line):
                in_fence = not in_fence
            # Blank a fenced line, never drop it, so an offset in the joined text
            # still maps back to the same line number in the file.
            text.append("\n" * line.count("\n") if in_fence else line)
        text = "".join(text)

        spans = [(m.start(), m.end()) for m in link.finditer(text)]
        lines = text.splitlines()

        def line_no(offset):
            return text.count("\n", 0, offset) + 1

        for m in link.finditer(text):
            checked += 1
            target, where = m.group("target"), f"{doc.name}:{line_no(m.start())}"
            if target.startswith(("http://", "https://", "mailto:")):
                continue  # external, not this document's graph
            file_part, _, frag = target.partition("#")
            if not file_part:
                if frag not in index[doc.name]:
                    problems.append(f"{where} dead in-page anchor #{frag}")
                continue
            resolved = (doc.parent / file_part).resolve()
            if not resolved.exists():
                problems.append(f"{where} links to missing file {file_part}")
                continue
            if frag:
                if resolved.suffix != ".md":
                    problems.append(f"{where} puts an anchor on {file_part}")
                    continue
                if frag not in _heading_anchors(resolved):
                    near = sorted(a for a in _heading_anchors(resolved)
                                  if a.startswith(frag[:14]))
                    problems.append(
                        f"{where} dead anchor in {file_part}: #{frag} "
                        f"(closest {near[:3]})")

        # An unconverted section reference. A § inside link text is fine; one in a
        # fence renders literally, so fences are already blanked above.
        outside = text
        for start, end in spans:
            outside = outside[:start] + " " * (end - start) + outside[end:]
        # Any surviving § at all: in this corpus the character has exactly one
        # use, as a section reference, so matching it plainly is both stricter
        # and simpler than a pattern that could miss an odd-shaped one.
        for m in re.finditer("§", outside):
            lineno = line_no(m.start())
            problems.append(
                f"{doc.name}:{lineno} section reference is not a link: "
                f"{lines[lineno - 1].strip()[:76]}")

        # A markdown link inside a fenced block renders as literal text, which is
        # how the Layout tree in README.md must stay. Blanking fences above makes
        # such a link invisible to both scans, so check the raw file separately -
        # otherwise "the link is there" would be true of text nobody can click.
        in_fence, opened_at = False, 0
        for lineno, line in enumerate(doc.read_text(encoding="utf-8").splitlines(), 1):
            if re.match(r"^\s*(```|~~~)", line):
                in_fence = not in_fence
                opened_at = lineno
                continue
            if in_fence and link.search(line):
                problems.append(
                    f"{doc.name}:{opened_at} link inside a fenced block renders "
                    f"literally: {line.strip()[:70]}")

    assert not problems, ("docs/spec cross-references are broken:\n  "
                          + "\n  ".join(problems))
    # Non-vacuity: the spec's whole premise is that these pages cross-reference
    # each other heavily. Zero links would mean the scanner found nothing.
    assert checked > 40, f"only {checked} links found - the scanner matched nothing"


def test_spec_mentions_no_stale_test_counts_or_paths():
    """Prose rots by citing numbers and paths, which is exactly how README and
    AGENTS.md drifted. Anything shaped like a repo path inside docs/spec/*.md
    must exist.
    """
    prose = sorted((ROOT / "docs" / "spec").glob("*.md"))
    if not prose:
        pytest.skip("prose spec not written yet")
    pathlike = re.compile(r"(?<![\w./-])((?:src|tests|tools|docs|examples)/[\w/.-]+\.(?:py|json|md))")
    for doc in prose:
        text = doc.read_text(encoding="utf-8")
        for rel in set(pathlike.findall(text)):
            assert (ROOT / rel).exists(), f"{doc.name} cites missing {rel}"
        for lineno, line in enumerate(text.splitlines(), 1):
            for m in re.finditer(r"((?:src|tools)/[\w/.-]+\.py):(\d+)", line):
                target, num = ROOT / m.group(1), int(m.group(2))
                assert target.is_file(), f"{doc.name}:{lineno} cites missing {target}"
                n = len(target.read_text(encoding="utf-8").splitlines())
                assert num <= n, (
                    f"{doc.name}:{lineno} cites {m.group(1)}:{num}, past its "
                    f"{n} lines - the citation was not re-checked")
