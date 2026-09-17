# 05 · VRE vocabulary

Which VRE a crate asks for, and how that decision was made on the far side.

Everything here is generated from `src/vre_rocrate/constants.py` at build time,
so a new VRE type appears in these tables the moment it appears in the code —
which matters more than it sounds, because this file's whole subject is a set of
five dictionaries that a human must keep in step by hand and one of which already
isn't (§gaps).

## `vre_type` never appears in the crate

The short name — `galaxy`, `oscar`, `sciencemesh` — exists only on the producer
side, as `ToolMeta.types` / `raw_definition["vre_type"]`. What travels is a
`ComputerLanguage` entity, and of its three identifying properties exactly one
routes the launch:

<!-- BEGIN GENERATED vocab-identity -->
| `vre_type` | `programmingLanguage.identifier` (the token that routes) | `name` | `url` | default `runtimePlatform` |
|---|---|---|---|---|
| `binder` | `https://jupyter.org/binder/` | `Binder` | `https://jupyter.org/binder/` | `https://mybinder.org/` |
| `galaxy` | `https://galaxyproject.org/` | `Galaxy` | `https://galaxyproject.org/` | `https://usegalaxy.eu/` |
| `jupyter` | `https://jupyter.org` | `Jupyter Notebook` | `https://jupyter.org` | `https://jupyterhub.egi.eu/` |
| `mddash` | `https://github.com/CERIT-SC/mddash` | `MDDash` | `https://github.com/CERIT-SC/mddash` | `https://mddash.cerit-sc.cz/` |
| `oscar` | `https://oscar.grycap.net/` | `OSCAR` | `https://oscar.grycap.net/` | `https://oscar.grycap.net/` |
| `sciencemesh` | `https://eosc.cernbox.cern.ch` | `Jupyter Notebook` | `https://jupyter.org/` | `https://eosc.cernbox.cern.ch` |
| `scipion` | `http://scipion.i2pc.es/` | `Scipion` | `http://scipion.i2pc.es/` | `http://scipion.i2pc.es/` |
| `vip` | `https://vip.creatis.insa-lyon.fr/` | `VIP` | `https://vip.creatis.insa-lyon.fr/` | `https://vip.creatis.insa-lyon.fr/` |
<!-- END GENERATED -->

- **`identifier` is the routing token.** A consumer **MUST** dispatch on this and
  nothing else.
- `name` and `url` are display text and **lie, usefully**: sciencemesh's
  `identifier` is an OpenCloudMesh domain while `name` on the same entity says
  "Jupyter Notebook" and its `url` says `https://jupyter.org/`, because the
  workload really is a notebook *inside* sciencemesh. Keying on `name` sends
  sciencemesh jobs to the Jupyter handler with no error anywhere. Compare those
  two rows in the table above; this is the most expensive single mistake available
  in this format.
- The identifier is a **URI-shaped string, not a dereferenceable resource**. Do
  not resolve it. `https://github.com/CERIT-SC/mddash` is mddash's identity, not
  a link to follow.
- Producers **MUST** emit `identifier`; consumers **MUST** tolerate the empty
  string, which arrives as `vre_type == "unknown"` (§gaps) rather than as an
  error.

Note the trailing-slash inconsistency in the table — `https://galaxyproject.org/`
has one, `https://jupyter.org` does not. That is verbatim from the source, it is
reproduced in every generated crate, and a consumer **MUST** therefore compare
identifiers by exact string match against this table, never by normalised or
scheme-stripped comparison. Normalising "fixes" the inconsistency and breaks the
match.

## `tool.types` → `vre_type`

On the producer side, req-packager tool-type strings alias onto `vre_type`. Many
aliases, few targets — `binder`, `mybinder`, `binder-launcher` and `egi-replay`
are all `binder`:

<!-- BEGIN GENERATED vocab-tool-types -->
| `tool.types[]` value | resolves to |
|---|---|
| `binder-launcher` | `binder` |
| `binder` | `binder` |
| `boutique` | `vip` |
| `cernbox` | `sciencemesh` |
| `egi-replay` | `binder` |
| `galaxy_workflow` | `galaxy` |
| `galaxy` | `galaxy` |
| `jupyter` | `jupyter` |
| `mddash` | `mddash` |
| `mybinder` | `binder` |
| `oscar` | `oscar` |
| `rrp` | `rrp` |
| `sciencemesh` | `sciencemesh` |
| `scipion` | `scipion` |
| `vip` | `vip` |
<!-- END GENERATED -->

A consumer never sees these strings. They are listed because a producer wiring
req-packager to this library will be holding them, and because `boutique → vip`
and `cernbox → sciencemesh` are the two that no reader would guess.

## Resolution order

`resolve_vre_type(tool)` (`src/vre_rocrate/constants.py`) tries three things and
then raises:

<!-- BEGIN GENERATED uri-resolution -->
1. raw_definition['vre_type'] if it names a known vre_type
2. first entry of tool.types present in tool_type_aliases
3. first uri substring match in uri_fallback_patterns
4. otherwise the producer raises - no crate is emitted
<!-- END GENERATED -->

The last URI fallback patterns, in order — first substring match in `tool.uri`
wins:

<!-- BEGIN GENERATED uri-fallbacks -->
| # | substring in the tool uri | `vre_type` |
|---|---|---|
| 1 | `galaxyproject.org` | `galaxy` |
| 2 | `usegalaxy.eu` | `galaxy` |
| 3 | `usegalaxy.org` | `galaxy` |
| 4 | `jupyter.org` | `jupyter` |
| 5 | `oscar.grycap` | `oscar` |
| 6 | `vip.creatis` | `vip` |
| 7 | `cernbox.cern.ch` | `sciencemesh` |
| 8 | `rrp-eosc` | `rrp` |
<!-- END GENERATED -->

Layer 1 is gated on the value naming a *known* type: `raw_definition =
{"vre_type": "galaxy"}` forces galaxy, but `{"vre_type": "nonsense"}` falls
through to layer 2 rather than raising. A producer that sets `vre_type` and
misspells it gets resolution by `tool.types`, which is silent. An unresolvable
tool raises `ValueError` from the `RocrateBuilder` **constructor**, before
`build()` is ever called — construction can throw, which surprises callers who
expect builders not to.

Note what layer 3 implies: `resolve_vre_type` is the *only* place a URI is
interpreted. Everywhere else in the format, URIs are opaque.

## Gaps

<!-- BEGIN GENERATED vocab-gaps -->
- **`rrp`** has no entry in `VRE_TYPE_TO_PROGRAMMING_LANGUAGE`, `VRE_TYPE_TO_DISPLAY_NAME`, `VRE_TYPE_TO_LANGUAGE_URL`. the builder emits an empty identifier, validation still passes (an empty string is not missing), and consumers receive vre_type 'unknown'.
<!-- END GENERATED -->

The `rrp` hole, in full, because it is the one live trap here:

1. `rrp` is in `TOOL_TYPE_TO_VRE_TYPE` and in
   `VRE_TYPE_TO_DEFAULT_RUNTIME_PLATFORM`, but **not** in
   `VRE_TYPE_TO_PROGRAMMING_LANGUAGE` — and `VRE_TYPES`, the tuple that decides
   what "known" means, is derived from that last table.
2. `resolve_vre_type` therefore returns `"rrp"` happily.
3. The builder looks up the language tables, finds nothing, and emits
   `{"@id": "#rrp-lang", "@type": "ComputerLanguage", "identifier": "", "name":
   "", "url": ""}`.
4. `ValidationPipeline.validate_basic` **passes** it — an empty string is not a
   missing string.
5. `VREPayload.vre_type` comes back as the literal string `"unknown"`.

Nothing errors at any step. `runtimePlatform` is still `https://rrp-eosc.ethz.ch/`
and the rest of the crate is well-formed, so the crate looks fine. Rule **W006**
is the only automated thing that notices.

Deliberately **not** fixed as part of this specification: closing the gap means
choosing an identity URI for RRP, and inventing an identity token for a live
protocol is worse than documenting the hole. This is a decision for the owners of
the vocabulary, not a mechanical fix; until it is made, treat `rrp` as a valid
`vre_type` with no wire identity.

## Consequences for each side

**A producer** adding a VRE type edits the tables in `constants.py` — there is no
registry, no subclass, no plugin point. Check **all four** tables plus, if the
type is reachable by URI, the fallback list: `VRE_TYPE_TO_PROGRAMMING_LANGUAGE`,
`VRE_TYPE_TO_DISPLAY_NAME`, `VRE_TYPE_TO_LANGUAGE_URL`,
`VRE_TYPE_TO_DEFAULT_RUNTIME_PLATFORM`, `TOOL_TYPE_TO_VRE_TYPE`,
`URI_FALLBACK_PATTERNS`. Adding to one and not the others is precisely how §gaps
acquired its entry. `tests/test_spec/test_wire_spec.py` cross-checks the tables
against each other, and this document re-generates from them, so a new VRE type
should show up here without anyone editing prose.

**A consumer** should treat the identifier table as the list of supported VREs,
match it exactly, and have an explicit policy for `"unknown"` — reject it loudly.
The string `"unknown"` also appears when `identifier` is absent *and* when it is
present but empty, so a consumer cannot distinguish "producer forgot" from
"producer declared the gap" — which is another argument for rejecting rather than
guessing.
