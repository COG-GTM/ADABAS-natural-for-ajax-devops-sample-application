#!/usr/bin/env python3
"""Generate ``disposition-ledger.md`` and ``diagrams/reachability.mmd`` from the
static analyzer's evidence plus the authored disposition annotations below.

Scope statement
---------------
This script is a *generator*, not an application. It exists so the ledger a
payroll SI signs off against cannot drift from the evidence in
``tools/analyze_disposition.py``. Nothing here is a rewrite target; dispositions
are decisions about what does or does not become an Oracle HCM (or alternate
HCM) requirement.

Inputs (all read at run time, never hand-typed)
-----------------------------------------------
* ``tools.analyze_disposition.analyze()`` - inventory, references,
  reachability, message-catalogue reconciliation, DDM/PDA field usage,
  unused variables, commented-out statements, markers.
* ``FINDINGS`` below - one authored record per finding: taxonomy class,
  proposed disposition, confidence, evidence class, owner, SME flag, payroll
  analog, and the *claims* that bind the finding to generated evidence items
  (objects, message codes, PDA fields, DDM fields, level-1 variables).

Every claim must exist in the evidence and every evidence candidate must be
claimed by exactly one finding; the build fails otherwise. ``REST`` claims
whatever no other finding claims in that category, so a new analyzer result
lands in a ledger row instead of silently disappearing.

Run from the repository root::

    python3 fpps-hcm-modernization-deliverable/10-migration-disposition-dead-code/generate_ledger.py
    python3 fpps-hcm-modernization-deliverable/10-migration-disposition-dead-code/generate_ledger.py --check
"""

import argparse
import sys
from collections import OrderedDict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tools.analyze_disposition import analyze  # noqa: E402

LEDGER = HERE / "disposition-ledger.md"
DIAGRAM = HERE / "diagrams" / "reachability.mmd"
DIAGRAM_README = HERE / "diagrams" / "README.md"
LIB = "SunnyIslands/Natural-Libraries"

REST = "REST"

# Evidence classes (see taxonomy.md). Static classes are what the analyzer can
# prove from source; the last two need FPPS-scale inputs and are Roadmap.
EVIDENCE_CLASSES = OrderedDict([
    ("S1", "No static reference from any analyzed object (CALLNAT/FETCH/INCLUDE/USING)"),
    ("S2", "Interface field declared but never assigned by any analyzed caller"),
    ("S3", "Catalogued value never produced by executable code"),
    ("S4", "Statement present only as a comment"),
    ("S5", "Literal, marker, or path that identifies training, sample, or channel scaffolding"),
    ("S6", "Executable logic whose semantics contradict the surrounding contract"),
    ("R1", "Runtime trace / Natural profiler / ADABAS command log (Roadmap)"),
    ("R2", "SME confirmation and signed decision (Roadmap)"),
])

# Taxonomy class -> proposed HCM disposition vocabulary (taxonomy.md).
CLASSES = OrderedDict([
    ("dead interface contract", "do not map"),
    ("unreachable by integration gap", "decide (intent may be real)"),
    ("implemented but unreferenced", "retire candidate"),
    ("time-bombed rule", "never re-implement literally"),
    ("commented-out logic", "candidate rule only"),
    ("data-lineage defect", "correct, then map"),
    ("misapplied rule", "correct, then map"),
    ("unused data", "profile, then decide"),
    ("operational utility", "replace with platform"),
    ("inactive presentation utility", "retire"),
    ("presentation or content infrastructure", "out of scope for requirements"),
    ("training or exercise scaffolding", "exclude"),
    ("unimplemented interface field", "exclude"),
    ("unused data item or dead statement", "ignore"),
    ("unused data area", "retire"),
    ("dead copycode", "record the gap; platform concern"),
    ("UI scaffolding", "exclude"),
    ("keep: converter-fragile logic", "requirement; HCM native"),
])

FINDINGS = [
    dict(
        id="D-01",
        title="Credentials passed to every service but never set or read",
        klass="dead interface contract",
        evidence="S2",
        confidence="High",
        sme=False,
        owner="Security / identity lead",
        status="Proposed",
        analog="Legacy userid/password parameters on batch calls",
        note="HCM identity (SSO) replaces the contract; no field mapping.",
        xref="05 E-04",
        pda_fields=["NCCOMM-P.P-USER", "NCCOMM-P.P-PASSWORD"],
        cite=[f"{LIB}/CRUISE16/Parameter Data Areas/NCCOMM-P.NSA:11-12"],
    ),
    dict(
        id="D-02",
        title="German message catalogue unreachable because the language flag is never populated",
        klass="unreachable by integration gap",
        evidence="S2",
        confidence="High",
        sme=True,
        owner="Business owner (payroll operations)",
        status="SME required",
        analog="Duplicate or legacy edit-message tables",
        note="Do not carry the German texts as requirements; record multilingual intent as an HCM configuration question.",
        xref="05 E-04, E-05",
        pda_fields=["NCCOMM-P.P-LANG"],
        cite=[f"{LIB}/CRUISE16/Parameter Data Areas/NCCOMM-P.NSA:10",
              f"{LIB}/CRUISE16/Subprograms/CAMSG-N.NSN:17-99"],
    ),
    dict(
        id="D-03",
        title="Catalogued message codes that no executable statement emits",
        klass="implemented but unreferenced",
        evidence="S3",
        confidence="High (sample) / Medium (FPPS)",
        sme=True,
        owner="Payroll SME + Cognition analyst",
        status="SME required",
        analog="Orphaned pay-edit codes",
        note="Retire unless XRef or runtime evidence shows an emitter elsewhere in the estate.",
        xref="05 E-05",
        codes=REST,
        cite=[f"{LIB}/CRUISE16/Subprograms/CAMSG-N.NSN"],
    ),
    dict(
        id="D-04",
        title="Year-range edits hard-coded to 2015-2020",
        klass="time-bombed rule",
        evidence="S4",
        confidence="High",
        sme=False,
        owner="Cognition analyst",
        status="Proposed",
        analog="Hard-coded pay-year tables",
        note="Never re-implement as a literal; if the intent survives, parameterise it.",
        xref="02 BR-D, 05 E-05",
        codes=[9911, 9913],
        cite=[f"{LIB}/CRUISE16/Subprograms/CONEW-N.NSN:198-199",
              f"{LIB}/CRUISE16/Subprograms/CONEW-N.NSN:210-211"],
    ),
    dict(
        id="D-05",
        title="Commented-out validations in the booking service",
        klass="commented-out logic",
        evidence="S4",
        confidence="High",
        sme=True,
        owner="Business owner (payroll operations)",
        status="SME required",
        analog="Edits disabled 'temporarily' years ago",
        note="Recorded in the requirements baseline as candidate rules needing a business decision, never as active rules.",
        xref="02 BR-D series, 05 E-05",
        commented_emits=True,
        cite=[f"{LIB}/CRUISE16/Subprograms/CONEW-N.NSN:164-211"],
    ),
    dict(
        id="D-06",
        title="First-name lineage break between the page and the services",
        klass="data-lineage defect",
        evidence="S6",
        confidence="High",
        sme=False,
        owner="Data-migration lead",
        status="Proposed",
        analog="Half-migrated name or SSN field renames",
        note="Map one HCM first name; flag both legacy columns for cleansing and merge.",
        xref="03 data dictionary, 07 cleansing rules",
        ddm_fields=["NCCUSTOMER.FIRST-NAME-1", "NCCUSTOMER.FIRST-NAME-2"],
        cite=[f"{LIB}/RDCRUISE/Programs/RDCRUISP.NSP:619",
              f"{LIB}/CRUISE16/Subprograms/CUNEW-N.NSN:48",
              f"{LIB}/CRUISE16/Subprograms/CUMOD-N.NSN:53"],
    ),
    dict(
        id="D-07",
        title="Cruise lookup reports 'not found' with the concurrency message",
        klass="misapplied rule",
        evidence="S6",
        confidence="High",
        sme=False,
        owner="Cognition analyst",
        status="Proposed",
        analog="Wrong edit message on a pay transaction",
        note="Correct the semantics in the requirement; do not clone the message.",
        xref="02 BR-M series",
        cite=[f"{LIB}/CRUISE16/Subprograms/CRGET-N.NSN:116"],
    ),
    dict(
        id="D-08",
        title="DDM fields never referenced by executable code",
        klass="unused data",
        evidence="S1",
        confidence="Medium",
        sme=True,
        owner="Data-migration lead + payroll SME",
        status="SME required",
        analog="Dormant master-record fields",
        note="Profile in cleansing: empty in data means drop; populated means the SME decides (another estate program may feed it).",
        xref="03 data dictionary, 07 cleansing profile",
        ddm_fields=REST,
        cite=[f"{LIB}/CRUISE16/DDMs"],
    ),
    dict(
        id="D-09",
        title="Interactive physical-ISN delete utility with no caller and no audit",
        klass="operational utility",
        evidence="S1",
        confidence="High",
        sme=False,
        owner="Platform / DBA lead",
        status="Proposed",
        analog="DBA fix-it utilities",
        note="Not an HCM function; replace with a governed purge and audit log.",
        xref="05 E-03",
        objects=["DELETECU"],
        cite=[f"{LIB}/RDCRUISE/Programs/DELETECU.NSP:18-26"],
    ),
    dict(
        id="D-10",
        title="Subprogram with no caller in the analyzed scope",
        klass="implemented but unreferenced",
        evidence="S1",
        confidence="Medium",
        sme=True,
        owner="Payroll SME",
        status="SME required",
        analog="Thousands of FPPS orphans",
        note="Retire candidate; needs XRef or production-trace confirmation.",
        xref="05 E-01",
        objects=["CA3900-N"],
        cite=[f"{LIB}/CRUISE16/Subprograms/CA3900-N.NSN"],
    ),
    dict(
        id="D-11",
        title="Image loader whose only call sites are commented out",
        klass="inactive presentation utility",
        evidence="S1",
        confidence="High",
        sme=False,
        owner="Cognition analyst",
        status="Proposed",
        analog="Dead report or print routines",
        note="Retire.",
        xref="05 E-02",
        objects=["IMG-LOAD"],
        cite=[f"{LIB}/RDCRUISE/Programs/RDCRUISP.NSP:85-91"],
    ),
    dict(
        id="D-12",
        title="Content and URL infrastructure for the page channel",
        klass="presentation or content infrastructure",
        evidence="S5",
        confidence="High",
        sme=False,
        owner="Cognition analyst",
        status="Proposed",
        analog="Work-file-driven screen text",
        note="Channel concern, not a requirement; MAKEURL and RDREADWN stay reachable but map to nothing in an HCM.",
        xref="05 E-02, E-06",
        cite=[f"{LIB}/RDCRUISE/Subprograms/RDREADWN.NSN:35",
              f"{LIB}/RDCRUISE/Subprograms/MAKEURL.NSN"],
    ),
    dict(
        id="D-13",
        title="Training gate that short-circuits five services to 'not yet supported'",
        klass="training or exercise scaffolding",
        evidence="S5",
        confidence="High",
        sme=False,
        owner="Cognition analyst",
        status="Proposed",
        analog="Training-region toggles",
        note="Exclude. Code 9999 counts as *emitted* only because of this gate; the constant is initialised FALSE, so the branch never runs.",
        xref="05 E-07",
        cite=[f"{LIB}/CRUISE16/Local Data Areas/NCDATA-L.NSL:86",
              f"{LIB}/CRUISE16/Subprograms/CONEW-N.NSN:48"],
    ),
    dict(
        id="D-14",
        title="Interface fields declared 'not yet used' or for an exercise",
        klass="unimplemented interface field",
        evidence="S2",
        confidence="High",
        sme=False,
        owner="Cognition analyst",
        status="Proposed",
        analog="Reserved or unused fields in copybooks",
        note="Do not infer requirements from parameter names.",
        xref="05 E-04, E-07",
        pda_fields=["NCCONW-P.WEEK-COUNT-IN", "NCCONW-P.DATE-RESERVATION-IN",
                    "NCCONW-P.DATE-BOOKING-IN"],
        cite=[f"{LIB}/CRUISE16/Parameter Data Areas/NCCONW-P.NSA:11-13",
              f"{LIB}/CRUISE16/Parameter Data Areas/NCCRUL-P.NSA:28-30"],
    ),
    dict(
        id="D-15",
        title="Unused level-1 variables and an always-false date block",
        klass="unused data item or dead statement",
        evidence="S1",
        confidence="High",
        sme=False,
        owner="Cognition analyst",
        status="Proposed",
        analog="Working-storage clutter",
        note="Ignore in requirements.",
        xref="—",
        variables=REST,
        cite=[f"{LIB}/CRUISE16/Subprograms/CUGET-N.NSN:32-34"],
    ),
    dict(
        id="D-16",
        title="Parameter data areas with no USING reference",
        klass="unused data area",
        evidence="S1",
        confidence="High",
        sme=False,
        owner="Cognition analyst",
        status="Proposed",
        analog="Unused PDAs and LDAs",
        note="Retire.",
        xref="05 E-08",
        objects=REST,
        cite=[f"{LIB}/CRUISE16/Parameter Data Areas"],
    ),
    dict(
        id="D-17",
        title="Error-logging copycode whose every statement is commented out",
        klass="dead copycode",
        evidence="S4",
        confidence="High",
        sme=False,
        owner="Platform lead",
        status="Proposed",
        analog="Commented-out audit hooks",
        note="Error handling is an HCM platform concern; record the absence of logging as a gap, not a requirement.",
        xref="05 behaviours not reproduced",
        cite=[f"{LIB}/CRUISE16/Copycodes/ERRLOG-I.NSC"],
    ),
    dict(
        id="D-18",
        title="Hard-coded favourites, image names, placeholder text, and ignored handlers in the page adapter",
        klass="UI scaffolding",
        evidence="S5",
        confidence="High",
        sme=False,
        owner="Cognition analyst",
        status="Proposed",
        analog="Screen-level hard codes",
        note="Exclude.",
        xref="—",
        variables=["RDCRUISP.#FILEIMG1", "RDCRUISP.#FILEIMG2", "RDCRUISP.#FILEIMG3",
                   "RDCRUISP.#FILEIMG4", "RDCRUISP.#FILEIMGHOME", "RDCRUISP.#FILEIMGALL"],
        cite=[f"{LIB}/RDCRUISE/Programs/RDCRUISP.NSP:39-42",
              f"{LIB}/RDCRUISE/Programs/RDCRUISP.NSP:976"],
    ),
    dict(
        id="D-19",
        title="Booking availability race and MAX+1 duplicate key",
        klass="keep: converter-fragile logic",
        evidence="S6",
        confidence="High",
        sme=False,
        owner="Payroll SI (HCM configuration)",
        status="Proposed",
        analog="Pay-run integrity",
        note="Requirement: atomic inventory decrement and generated identifiers; an HCM provides both natively. A naive converter copies the defect.",
        xref="02 BR-C series, 08 harness",
        cite=[f"{LIB}/CRUISE16/Subprograms/CONEW-N.NSN:74-135"],
    ),
    dict(
        id="D-20",
        title="Destination-harbour filter never driven from the page",
        klass="unreachable by integration gap",
        evidence="S2",
        confidence="High",
        sme=True,
        owner="Business owner (payroll operations)",
        status="SME required",
        analog="Selection criteria that the front end never sends",
        note="The filter branch is a candidate requirement only; decide whether the intent survives before configuring an HCM filter.",
        xref="02 BR-L series",
        pda_fields=["NCCRUL-P.P-DESTHARBOR"],
        cite=[f"{LIB}/CRUISE16/Subprograms/CRLIST-N.NSN:62",
              f"{LIB}/CRUISE16/Parameter Data Areas/NCCRUL-P.NSA:12"],
    ),
]

CATEGORIES = ("objects", "codes", "pda_fields", "ddm_fields", "variables")


def _candidates(a):
    """Evidence items that every ledger row may claim, per category."""
    ct = a["control_totals"]
    ddm = sorted(
        f"{r['file']}.{r['field']}" for r in a["ddm_field_usage"]
        if r["kind"] == "field" and not r["referenced_by"] and not r["ambiguous_in"]
    )
    assert len(ddm) == ct["ddm_fields_never_referenced"], (len(ddm), ct)
    return {
        "objects": sorted(ct["unreferenced_objects"] + ct["standalone_programs_no_ui_path"]),
        "codes": sorted(a["message_codes"]["cataloged_never_emitted"]),
        "pda_fields": sorted(ct["pda_fields_never_assigned"]),
        "ddm_fields": ddm,
        "variables": sorted(f"{v['object']}.{v['variable']}" for v in a["unused_level1_variables"]),
    }


def _resolve_claims(a):
    """Bind every finding to concrete evidence items and verify the binding is
    total and exclusive (every candidate claimed exactly once)."""
    cands = _candidates(a)
    claimed = {c: OrderedDict() for c in CATEGORIES}
    rest_owner = {}
    for f in FINDINGS:
        for c in CATEGORIES:
            claim = f.get(c)
            if claim is None:
                continue
            if claim == REST:
                if c in rest_owner:
                    raise SystemExit(f"two findings claim REST of {c}: {rest_owner[c]} and {f['id']}")
                rest_owner[c] = f["id"]
                continue
            for item in claim:
                if item not in cands[c]:
                    raise SystemExit(f"{f['id']} claims {c} item {item!r} that the analyzer does not report")
                if item in claimed[c]:
                    raise SystemExit(f"{c} item {item!r} claimed by both {claimed[c][item]} and {f['id']}")
                claimed[c][item] = f["id"]
    resolved = {f["id"]: {c: [] for c in CATEGORIES} for f in FINDINGS}
    for c in CATEGORIES:
        for item in cands[c]:
            owner = claimed[c].get(item) or rest_owner.get(c)
            if owner is None:
                raise SystemExit(f"{c} item {item!r} reported by the analyzer is not claimed by any finding")
            resolved[owner][c].append(item)
    for f in FINDINGS:
        for c in CATEGORIES:
            if f.get(c) == REST and not resolved[f["id"]][c]:
                raise SystemExit(f"{f['id']} claims REST of {c} but nothing is left to claim")
    return cands, resolved


def _code_text(a, code):
    texts = a["message_codes"]["texts"].get(str(code), [])
    return texts[-1] if texts else ""


def _fmt_items(items, code=True):
    return ", ".join(f"`{i}`" for i in items) if code else ", ".join(items)


def _ledger(a, cands, resolved):
    ct = a["control_totals"]
    mc = a["message_codes"]
    L = [
        "# Disposition ledger",
        "",
        "One row per finding in the Sunny Islands sources that should **not** be carried into an HCM as-is. "
        "The evidence column is generated by `../../tools/analyze_disposition.py` through `generate_ledger.py`; "
        "the class, disposition, confidence, owner, and SME flag are authored decisions recorded next to that evidence. "
        "Every evidence candidate the analyzer reports is claimed by exactly one row (the generator fails otherwise), "
        "so a new analyzer result cannot disappear from scope sign-off.",
        "",
        "> Static evidence identifies *candidates*. Absence from a partial call graph is not runtime proof of dead code; "
        "rows marked *SME required* are discovery questions, not configuration items. "
        "[`fpps-scale-evidence-plan.md`](fpps-scale-evidence-plan.md) lists what raises confidence at FPPS scale.",
        "",
        "## Control totals (generated)",
        "",
        "| Measure | Value |",
        "|---|---|",
        f"| Natural objects analyzed | {ct['objects']} ({ct['code_objects']} with executable code) |",
        f"| Static references resolved | {ct['static_references']} (unresolved: {len(ct['unresolved_references'])}, ambiguous: {len(ct['ambiguous_references'])}) |",
        f"| Objects unreferenced in analyzed scope | {len(ct['unreferenced_objects'])} |",
        f"| Standalone programs with no UI path | {len(ct['standalone_programs_no_ui_path'])} |",
        f"| Message codes cataloged / emitted / never emitted / emitted-not-cataloged | {ct['message_codes_cataloged']} / {ct['message_codes_emitted']} / {ct['message_codes_cataloged_never_emitted']} / {ct['message_codes_emitted_not_cataloged']} |",
        f"| Commented-out message emissions | {ct['commented_out_message_emits']} |",
        f"| Interface (PDA) fields never assigned | {len(ct['pda_fields_never_assigned'])} |",
        f"| DDM fields never referenced by executable code | {ct['ddm_fields_never_referenced']} ({ct['ddm_fields_not_in_any_view']} not exposed in any view) |",
        f"| Unused level-1 variables | {ct['unused_level1_variables']} |",
        f"| Commented-out executable statements | {ct['commented_out_statements']} |",
        f"| UI events declared / unhandled by the adapter | {ct['ui_events_declared']} / {len(ct['ui_events_unhandled'])} |",
        "",
        "Ledger coverage (bidirectional): "
        + "; ".join(f"{c.replace('_', ' ')} {sum(len(resolved[f['id']][c]) for f in FINDINGS)}/{len(cands[c])}" for c in CATEGORIES)
        + ".",
        "",
        "## Ledger",
        "",
        "| ID | Finding | Class | Proposed disposition | Evidence class | Confidence | SME required | Decision owner | Status | Payroll analog |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for f in FINDINGS:
        L.append(
            f"| {f['id']} | {f['title']} | {f['klass']} | {CLASSES[f['klass']]} | {f['evidence']} | "
            f"{f['confidence']} | {'yes' if f['sme'] else 'no'} | {f['owner']} | {f['status']} | {f['analog']} |"
        )
    L += [
        "",
        "Evidence classes: " + "; ".join(f"**{k}** {v}" for k, v in EVIDENCE_CLASSES.items()) + ".",
        "",
        "## Findings with generated evidence",
        "",
    ]
    for f in FINDINGS:
        r = resolved[f["id"]]
        L += [f"### {f['id']} — {f['title']}", ""]
        L.append(f"**Disposition:** {CLASSES[f['klass']]}. {f['note']}")
        L.append("")
        L.append("**Source:** " + "; ".join(f"`{c}`" for c in f["cite"]) + f". **Cross-reference:** {f['xref']}.")
        L.append("")
        if r["objects"]:
            rows = []
            for o in r["objects"]:
                inv = next(i for i in a["inventory"] if i["object"] == o)
                reach = next(x for x in a["reachability"] if x["object"] == o)
                rows.append(f"| `{o}` | {inv['type']} | `{inv['path']}` | {reach['status']} |")
            L += ["| Object | Type | Path | Reachability |", "|---|---|---|---|"] + rows + [""]
        if r["codes"]:
            rows = [f"| {c} | {_code_text(a, c)} |" for c in r["codes"]]
            L += [f"{len(r['codes'])} catalogued code(s) with no executable emitter in `{mc['primary']}`:", "",
                  "| Code | Catalogue text |", "|---|---|"] + rows + [""]
        if r["pda_fields"]:
            rows = []
            for pf in r["pda_fields"]:
                pda, field = pf.split(".", 1)
                p = next(x for x in a["pda_field_population"] if x["pda"] == pda and x["field"] == field)
                readers = _fmt_items(p["referenced_by"]) or "none"
                rows.append(f"| `{pf}` | {p['assignments']} | {p['reads']} | {readers} |")
            L += ["| Interface field | Assignments | Reads | Referencing objects |", "|---|---|---|---|"] + rows + [""]
        if r["ddm_fields"]:
            by_file = OrderedDict()
            for df in r["ddm_fields"]:
                file_, field = df.split(".", 1)
                by_file.setdefault(file_, []).append(field)
            rows = []
            for file_, fields in by_file.items():
                views = sorted({v for x in a["ddm_field_usage"] if x["file"] == file_ and x["field"] in fields
                                for v in x["exposed_in_views"]})
                rows.append(f"| `{file_}` | {len(fields)} | {_fmt_items(fields)} | {_fmt_items(views) or 'none'} |")
            L += [f"{len(r['ddm_fields'])} field(s) never referenced through a view by executable code:", "",
                  "| DDM | Fields | Names | Exposed in views |", "|---|---|---|---|"] + rows + [""]
        if r["variables"]:
            rows = [f"| `{v}` |" for v in r["variables"]]
            L += ["| Level-1 variable (object.name) |", "|---|"] + rows + [""]
        if f.get("commented_emits"):
            emits = mc["commented_out_emits"]
            rows = [f"| `{e['object']}` | {e['line']} | {e['code']} | {_code_text(a, e['code'])} |" for e in emits]
            L += [f"{len(emits)} commented-out message emission(s):", "",
                  "| Object | Line | Code | Catalogue text |", "|---|---|---|---|"] + rows + [""]
    L += [
        "## How an SI consumes this",
        "",
        "Take the ledger into scope sign-off. Rows whose disposition is *retire*, *exclude*, *ignore*, *out of scope*, or *replace with platform* leave the requirements baseline; "
        "rows marked *SME required* become discovery questions with the evidence attached; rows marked *correct, then map* are configured to the corrected requirement in "
        "[`../05-requirements-baseline/`](../05-requirements-baseline/) rather than to the legacy behaviour. "
        "The one *keep* row (D-19) is the differentiator: the logic an HCM must preserve and a naive converter copies wrong.",
        "",
        "## Synthetic data and scope",
        "",
        f"Evidence scope: `{a['scope']}`; steplib chain {_fmt_items(a['steplib_chain'])}. "
        "All evidence is produced from the Sunny Islands Cruise sample sources; no production system, production data, or FPPS source is used or required. "
        "FPPS statements are analogies to a Software AG Natural 9.x / ADABAS 8.6 estate; nothing here proposes a language rewrite.",
        "",
        "← [Back to the capability README](README.md)",
        "",
    ]
    return "\n".join(L)


def _diagram(a, resolved):
    """Reachability graph: UI root, reached objects, unreferenced objects, and
    standalone programs, with ledger IDs on everything that has a row."""
    owner = {}
    for fid, r in resolved.items():
        for o in r["objects"]:
            owner[o] = fid
    inv = {i["object"]: i for i in a["inventory"]}
    reach = {r["object"]: r for r in a["reachability"]}
    edges = OrderedDict()
    for ref in a["references"]:
        if ref["statement"] == "USING" or not ref["resolved"]:
            continue
        for key in ref["resolved"]:
            callee = key.split("/", 1)[1]
            edges[(ref["caller"], callee)] = ref["statement"]
    code_objs = [o for o, i in inv.items() if i["type"] in ("program", "subprogram", "copycode")]
    L = ["%% Generated by generate_ledger.py from tools/analyze_disposition.py; do not edit by hand.",
         "%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#ffffff', "
         "'primaryTextColor': '#000000', 'primaryBorderColor': '#3969CA', 'lineColor': '#555555', "
         "'textColor': '#000000', 'edgeLabelBackground': '#ffffff', 'clusterBkg': '#fafafa', "
         "'clusterBorder': '#bbbbbb', 'titleColor': '#000000', 'fontFamily': 'Inter, Arial, sans-serif'}}}%%",
         "flowchart LR"]
    for lib in sorted({inv[o]["library"] for o in code_objs}):
        L.append(f"  subgraph {lib}")
        for o in code_objs:
            if inv[o]["library"] != lib:
                continue
            label = o if o not in owner else f"{o}<br/>{owner[o]}"
            L.append(f'    {o.replace("-", "_")}["{label}"]')
        L.append("  end")
    for (caller, callee), stmt in edges.items():
        if caller in inv and callee in inv:
            L.append(f'  {caller.replace("-", "_")} -->|{stmt}| {callee.replace("-", "_")}')
    L += [
        "  classDef root fill:#c9d9f5,stroke:#3969CA,stroke-width:3px;",
        "  classDef reached fill:#bdeedf,stroke:#21C19A;",
        "  classDef unref fill:#f4f4f4,stroke:#999999,stroke-dasharray: 4 3;",
        "  classDef standalone fill:#fbe3e0,stroke:#c0392b,stroke-width:2px;",
    ]
    groups = {"root": [], "reached": [], "unref": [], "standalone": []}
    for o in code_objs:
        s = reach[o]["status"] if o in reach else ""
        if s.startswith("entry point"):
            groups["root"].append(o)
        elif s.startswith("reachable"):
            groups["reached"].append(o)
        elif s.startswith("standalone"):
            groups["standalone"].append(o)
        else:
            groups["unref"].append(o)
    for cls, objs in groups.items():
        if objs:
            L.append(f"  class {','.join(o.replace('-', '_') for o in objs)} {cls};")
    return "\n".join(L) + "\n"


def _diagram_readme(diagram):
    return "\n".join([
        "# Diagrams (generated)",
        "",
        "Generated by `python3 fpps-hcm-modernization-deliverable/10-migration-disposition-dead-code/"
        "generate_ledger.py` from `tools/analyze_disposition.py`. **Do not edit by hand** — run the "
        "generator; `--check` fails if this file, the ledger, or the Mermaid source drifts. Images are "
        "exported with `npx -y @mermaid-js/mermaid-cli -i reachability.mmd -o reachability.svg -b white` "
        "(and `-o reachability.png -w 2200`).",
        "",
        "The reachability graph is **Demonstrated**: nodes and edges come from the analyzer's resolved "
        "static references, not from a drawing. Blue: the UI root. Green: reached from the root through "
        "literal `CALLNAT` / `FETCH` / `INCLUDE` statements. Grey dashed: unreferenced in the analyzed "
        "scope (a *candidate*, not a runtime finding). Red: a standalone program with no UI path. Ledger "
        "IDs mark every object with a disposition row.",
        "",
        "## Reachability (`reachability.mmd`)",
        "",
        "![Reachability from the UI adapter](reachability.svg)",
        "",
        "```mermaid",
        diagram.rstrip("\n"),
        "```",
        "",
    ])


def build():
    a = analyze()
    cands, resolved = _resolve_claims(a)
    diagram = _diagram(a, resolved)
    return _ledger(a, cands, resolved), diagram, _diagram_readme(diagram)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true",
                    help="regenerate in memory and fail if the ledger or diagram differs")
    args = ap.parse_args(argv)
    ledger, diagram, readme = build()
    outputs = [(LEDGER, ledger), (DIAGRAM, diagram), (DIAGRAM_README, readme)]
    if args.check:
        drift = [p for p, c in outputs if not p.exists() or p.read_text(encoding="utf-8") != c]
        for p in drift:
            print(f"DRIFT DETECTED: {p.relative_to(REPO_ROOT)} differs from generated content")
        if drift:
            return 1
        print("OK: ledger and reachability diagram match generated content")
        return 0
    for p, c in outputs:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(c, encoding="utf-8")
        print(f"wrote {p.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
