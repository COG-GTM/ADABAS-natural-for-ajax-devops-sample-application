#!/usr/bin/env python3
"""Generate regression-suite-map.md by parsing tests/ (validation tooling only).

This script is a GENERATOR for the deliverable, not application code and not
a rewrite target: it walks the repository's unittest suite with the ``ast``
module, extracts every test class and method with its docstring, the message
codes and model/parser functions it exercises, and the Natural source strings
it asserts, and maps each test to the extracted rule it protects.  The
inventory is cross-checked against ``unittest`` discovery so the count in the
document is the count CI runs.  Message-code coverage is computed against the
codes actually emitted by the Natural sources (``tools.analyze_disposition``),
so coverage gaps are reported from source, not typed by hand.

Usage (from the repository root)::

    python3 <dir>/generator/build_suite_map.py            # write the map
    python3 <dir>/generator/build_suite_map.py --stdout   # print it
    python3 <dir>/generator/build_suite_map.py --check    # exit 1 on drift
"""

import argparse
import ast
import io
import os
import re
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
DELIVERABLE_DIR = HERE.parent
REPO_ROOT = DELIVERABLE_DIR.parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests.harness import source_parser as sp  # noqa: E402
from tools import analyze_disposition as ad  # noqa: E402

TESTS_DIR = REPO_ROOT / "tests"
OUT_PATH = DELIVERABLE_DIR / "regression-suite-map.md"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "regression-tests.yml"

CODE_RE = re.compile(r"(?<!\d)(9[89]\d\d)(?!\d)")
NATURAL_KEYWORD_RE = re.compile(
    r"\b(GET|READ|FIND|UPDATE|STORE|END TRANSACTION|BACKOUT TRANSACTION|"
    r"DECIDE|WHEN|MOVE|IF|END-IF|END-READ|VAL\(|DESCENDING|NCCRUISE|"
    r"NCCONTRACT|NCCUSTOMER|MSG-GROUP-PARA|P-CONTRACT-DATA|START-HARBOR|"
    r"DESTINATION-HARBOR|LOCAL-AVAIL|LOCAL-NEWCONTRACTID|PERSON-ID)\b")

# ---------------------------------------------------------------------------
# Rule catalogue: the extracted behaviours a test can protect.  Keys are stable
# identifiers used in this directory; ``source`` cites opened line ranges.
# ``match`` predicates are evaluated against the parsed evidence of each test.
# ---------------------------------------------------------------------------

CONEW = "SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN"
CRLIST = "SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CRLIST-N.NSN"
CRGET = "SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CRGET-N.NSN"
CAMSG = "SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CAMSG-N.NSN"
CUNEW = "SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CUNEW-N.NSN"
DDMS = "SunnyIslands/Natural-Libraries/CRUISE16/DDMs/"


def _has(ev, *needles):
    text = ev["haystack"]
    return any(n.lower() in text for n in needles)


def _code(ev, *codes):
    """Behavioural tests only: conformance tests compare whole code sets."""
    if ev["file"] == "test_source_conformance.py":
        return False
    return any(c in ev["codes"] for c in codes)


def _file(ev, name):
    return ev["file"] == name


RULES = [
    # --- validation edits (CONEW-N) ------------------------------------
    ("EDIT-9904", "validation edit",
     "Blank, '0' or non-N8 customer identifier is rejected with 9904",
     f"{CONEW}:54-71",
     lambda ev: _code(ev, "9904") and not _code(ev, "9918")
     or _has(ev, "blank_customer", "customer_checked_before")),
    ("EDIT-9905", "validation edit",
     "Blank, '0' or non-N8 cruise identifier is rejected with 9905",
     f"{CONEW}:54-71",
     lambda ev: _code(ev, "9905")),
    ("EDIT-PRECEDENCE", "validation edit",
     "DECIDE FOR FIRST CONDITION: the customer edit wins when both inputs "
     "are blank",
     f"{CONEW}:54-59",
     lambda ev: _has(ev, "customer_checked_before", "decide for first")),
    ("EDIT-9918", "validation edit",
     "Customer not found in NCCUSTOMER is rejected with 9918 after the "
     "availability check, inside the transaction",
     f"{CONEW}:157-162",
     lambda ev: _code(ev, "9918") and not _has(ev, "9902")),
    ("EDIT-9902", "integrity",
     "Sold-out cruise (CRUISE-STATUS 0) is rejected with 9902 after "
     "BACKOUT releases the held record",
     f"{CONEW}:86-136",
     lambda ev: _code(ev, "9902") or _has(ev, "oversell", "sold_out",
                                          "sold-out", "9902")),
    ("EDIT-NOCHANGE", "integrity",
     "A rejected transaction leaves availability and contracts unchanged",
     f"{CONEW}:114-136",
     lambda ev: _has(ev, "does_not_change_availability",
                     "does_not_create_a_contract", "creates_nothing")),
    # --- integrity (concurrency refactor) ------------------------------
    ("INT-HOLD-REREAD", "integrity",
     "Cruise record is re-read in hold (GET *ISN) and availability is "
     "tested and decremented on the held record",
     f"{CONEW}:80-92",
     lambda ev: _has(ev, "reread_in_hold", "get nccruise",
                     "race_on_cruise_status", "competitor_blocks",
                     "after_status_read")),
    ("INT-MAXID-HOLD", "integrity",
     "Highest NCCONTRACT record is held (fake UPDATE) before MAX+1 "
     "CONTRACT-ID generation",
     f"{CONEW}:95-102",
     lambda ev: _has(ev, "maxid", "update (r2.)", "fake_update",
                     "duplicate_contract_ids", "previous_maximum_plus_one",
                     "after_maxid_read")),
    ("INT-TXN-BOUNDARY", "integrity",
     "STORE then END TRANSACTION on success; BACKOUT TRANSACTION on every "
     "error path, including the empty-file guard",
     f"{CONEW}:114-136",
     lambda ev: _has(ev, "transaction_boundaries", "backs_out",
                     "empty_contract_file", "no_holds_left",
                     "end transaction", "backout transaction")),
    ("INT-DECREMENT", "integrity",
     "One accepted booking decrements CRUISE-STATUS by exactly one",
     f"{CONEW}:88-92",
     lambda ev: _has(ev, "decrements_by_one", "last_available_slot",
                     "invisible_after_last_slot")),
    # --- derivations -----------------------------------------------------
    ("DER-PRICE-1W", "derivation",
     "Contract PRICE is the one-week price (PRICE-1W)",
     f"{CONEW}:103",
     lambda ev: _has(ev, "price_selected_is_one_week")),
    ("DER-CONTRACT-FIELDS", "derivation",
     "Contract carries ID-CUSTOMER, ID-CRUISE and DATE-BOOKING from input",
     f"{CONEW}:104-110",
     lambda ev: _has(ev, "records_customer_cruise_and_booking_date")),
    ("DER-PRICE-DURATION", "derivation",
     "CRGET-N selects PRICE-1W/2W/3W from cruise duration (display path)",
     f"{CRGET}:81-95",
     lambda ev: _has(ev, "crget_price_selection")),
    # --- messages --------------------------------------------------------
    ("MSG-9800-REMAP", "message",
     "Success code 9800 is remapped to response code 0 by CAMSG-N",
     f"{CAMSG}:101-106",
     lambda ev: _has(ev, "9800_mapped_to_zero", "success_code_remap",
                     "returns_9807_when_rows_found")),
    ("MSG-CATALOGUE", "message",
     "Every code a subprogram emits has a CAMSG-N text; model texts are a "
     "subset of the catalogue",
     f"{CAMSG}:101-181",
     lambda ev: _has(ev, "translatable_by_camsg", "camsg_codes",
                     "message_codes_match_model", "model_texts_are_subset",
                     "message_catalog_reconciliation")),
    # --- listing (CRLIST-N) ---------------------------------------------
    ("LIST-AVAILABLE", "workflow",
     "CRLIST-N lists only cruises with availability > 0, read DESCENDING BY "
     "START-DATE",
     f"{CRLIST}:51-57",
     lambda ev: _has(ev, "lists_only_available", "sorted_by_start_date",
                     "reads_descending_by_start_date",
                     "skips_fully_booked", "invisible_after_last_slot")),
    ("LIST-FILTERS", "workflow",
     "Start- and destination-harbour filters must both match",
     f"{CRLIST}:59-64",
     lambda ev: _has(ev, "harbor_filter", "both_filters", "filters_harbors")),
    ("LIST-9807-9857", "message",
     "CRLIST-N returns 9807 when rows are found and 9857 when none",
     f"{CRLIST}:88-93",
     lambda ev: _code(ev, "9807", "9857")),
    ("LIST-EDITING", "derivation",
     "Dates are edited to ISO format, prices to two decimals, yacht name "
     "joined from NCYACHT",
     f"{CRLIST}:72-83",
     lambda ev: _has(ev, "iso_format", "two_decimals", "yacht_name_joined")),
    # --- data model ------------------------------------------------------
    ("DDM-STRUCTURE", "data model",
     "DDM logical files, key descriptors, formats and field counts",
     f"{DDMS}NCCRUISE.NSD, NCCONTRA.NSD, NCCUSTOM.NSD, NCYACHT.NSD",
     lambda ev: _file(ev, "test_source_conformance.py")
     and _has(ev, "ddm", "logical_files", "key_fields", "descriptor",
              "field_control_totals")),
    ("DDM-DOC-SYNC", "data model",
     "docs/data-dictionary.md regenerates identically from the DDMs",
     "tools/generate_data_dictionary.py",
     lambda ev: _has(ev, "data_dictionary", "ddm_field_appears_in_doc")),
    # --- source conformance idioms -------------------------------------
    ("SRC-CUNEW-IDIOM", "integrity",
     "The fake-UPDATE hold idiom matches the one CUNEW-N established",
     f"{CUNEW}:41-42",
     lambda ev: _has(ev, "matches_cunew")),
    ("SRC-DECIDE-BLOCK", "validation edit",
     "The validation DECIDE block and IS (N8) format checks are unchanged",
     f"{CONEW}:54-71",
     lambda ev: _has(ev, "validation_decide_block")),
    # --- disposition evidence ------------------------------------------
    ("DISP-CONTROL-TOTALS", "disposition evidence",
     "Object inventory, reachability, message-catalogue, DDM-usage, "
     "unused-variable and UI-event control totals are pinned",
     "tools/analyze_disposition.py",
     lambda ev: _file(ev, "test_disposition_analysis.py")
     and not _has(ev, "committed_")),
    ("DISP-EVIDENCE-SYNC", "disposition evidence",
     "Committed disposition evidence (JSON and Markdown) matches the "
     "generator byte-for-byte",
     "fpps-hcm-modernization-deliverable/10-migration-disposition-dead-code/"
     "evidence/",
     lambda ev: _has(ev, "committed_json", "committed_markdown")),
    # --- deliverable package integrity ------------------------------------
    ("PKG-LINKS", "package integrity",
     "Every relative link, image and back-ticked repository path in the "
     "deliverable resolves to a file in the checkout",
     "fpps-hcm-modernization-deliverable/",
     lambda ev: _file(ev, "test_deliverable_links.py")
     and _has(ev, "relative_reference_resolves")),
    ("PKG-STRUCTURE", "package integrity",
     "The package has the hub README and capability directories 00-10, "
     "each with a README",
     "fpps-hcm-modernization-deliverable/README.md",
     lambda ev: _file(ev, "test_deliverable_links.py")
     and _has(ev, "hub_and_all_capability_directories")),
    ("PKG-GENERATORS", "package integrity",
     "Every capability generator is inventoried (bidirectionally) and its "
     "committed artifacts match a fresh --check run",
     "fpps-hcm-modernization-deliverable/*/generate_*.py",
     lambda ev: _file(ev, "test_deliverable_generators.py")),
]

RULE_INDEX = {r[0]: r for r in RULES}

REQUIREMENTS = {
    "validation edit": "HCM validation (element-entry or fast-formula edit) "
                       "returns the mapped code",
    "integrity": "Pay-run integrity: no double consumption, unique "
                 "identifiers, atomic commit/rollback",
    "derivation": "Calculated value equals legacy to the cent / exact field",
    "message": "Message catalogue mapped 1:1 to HCM messages",
    "workflow": "Inquiry/listing behaviour reproduced",
    "data model": "Personnel-payroll data model mapped field-by-field",
    "disposition evidence": "Extraction evidence reproducible and reviewed",
    "package integrity": "Every deliverable cross-reference the SI follows "
                         "resolves; the package structure is complete",
}

FILE_CLASS = {
    "test_conew_booking.py": ("Behavioural (single session)",
                              "tests/harness/natural_model.py"),
    "test_concurrency.py": ("Behavioural (interleaved sessions)",
                            "tests/harness/natural_model.py + adabas_sim.py"),
    "test_crlist_listing.py": ("Behavioural (listing and pricing)",
                               "tests/harness/natural_model.py"),
    "test_source_conformance.py": ("Source conformance",
                                   "tests/harness/source_parser.py over .NSN/.NSD"),
    "test_disposition_analysis.py": ("Evidence drift",
                                     "tools/analyze_disposition.py"),
    "test_deliverable_links.py": ("Package integrity",
                                  "fpps-hcm-modernization-deliverable/**/*.md"),
    "test_deliverable_generators.py": ("Package integrity",
                                       "fpps-hcm-modernization-deliverable/**/*.py --check"),
}


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _string_constants(node):
    for sub in ast.walk(node):
        if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
            yield sub.value


def _int_constants(node):
    for sub in ast.walk(node):
        if isinstance(sub, ast.Constant) and isinstance(sub.value, int) \
                and not isinstance(sub.value, bool):
            yield sub.value


def _calls(node):
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            f = sub.func
            if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name):
                yield f"{f.value.id}.{f.attr}"
            elif isinstance(f, ast.Name):
                yield f.id


def parse_tests():
    """Return the ordered inventory of test methods parsed from tests/*.py."""
    inventory = []
    for path in sorted(TESTS_DIR.glob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        module_doc = (ast.get_docstring(tree) or "").strip()
        for cls in tree.body:
            if not isinstance(cls, ast.ClassDef):
                continue
            cls_doc = (ast.get_docstring(cls) or "").strip()
            for fn in cls.body:
                if not isinstance(fn, ast.FunctionDef) \
                        or not fn.name.startswith("test_"):
                    continue
                doc = (ast.get_docstring(fn) or "").strip()
                body = fn.body[1:] if doc and fn.body else fn.body
                body_mod = ast.Module(body=body, type_ignores=[])
                strings = list(_string_constants(body_mod))
                codes = set()
                for s in strings + [fn.name, doc]:
                    codes.update(CODE_RE.findall(s))
                for i in _int_constants(body_mod):
                    if 9800 <= i <= 9999:
                        codes.add(str(i))
                natural = sorted({
                    s for s in strings
                    if path.name == "test_source_conformance.py"
                    and NATURAL_KEYWORD_RE.search(s)})
                calls = sorted({c for c in _calls(body_mod)
                                if c.startswith(("nm.", "sp.", "ad.",
                                                 "make_db"))})
                ev = {
                    "file": path.name,
                    "class": cls.name,
                    "class_doc": cls_doc,
                    "module_doc": module_doc,
                    "name": fn.name,
                    "line": fn.lineno,
                    "doc": " ".join(doc.split()),
                    "codes": sorted(codes),
                    "natural": natural,
                    "calls": calls,
                }
                ev["haystack"] = " ".join(
                    [fn.name, doc, cls.name] + strings + calls).lower()
                ev["rules"] = [r[0] for r in RULES if r[4](ev)]
                inventory.append(ev)
    return inventory


def discovered_test_ids():
    loader = unittest.TestLoader()
    suite = loader.discover(str(TESTS_DIR), top_level_dir=str(REPO_ROOT))
    ids = []

    def walk(s):
        for t in s:
            if isinstance(t, unittest.TestSuite):
                walk(t)
            else:
                ids.append(t.id())
    walk(suite)
    return sorted(ids)


def source_message_codes():
    """Codes emitted per subprogram, from tools.analyze_disposition."""
    with io.StringIO() as sink:
        old = sys.stdout
        sys.stdout = sink
        try:
            result = ad.analyze()
        finally:
            sys.stdout = old
    mc = result["message_codes"]
    return mc["emitted"], mc["texts"], result["control_totals"]


def workflow_steps():
    """Extract every command from the run: entries of regression-tests.yml.

    Handles both ``run: cmd`` and block-scalar ``run: |`` forms."""
    steps = []
    lines = WORKFLOW.read_text(encoding="utf-8").splitlines()
    i = 0
    while i < len(lines):
        s = lines[i].strip()
        if s.startswith("run:"):
            rest = s[len("run:"):].strip()
            if rest in ("|", ">", "|-", ">-"):
                indent = len(lines[i]) - len(lines[i].lstrip())
                i += 1
                while i < len(lines) and lines[i].strip() and \
                        len(lines[i]) - len(lines[i].lstrip()) > indent:
                    steps.append(lines[i].strip())
                    i += 1
                continue
            steps.append(rest)
        i += 1
    return steps


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _md(headers, rows):
    out = ["| " + " | ".join(headers) + " |",
           "|" + "---|" * len(headers)]
    for r in rows:
        out.append("| " + " | ".join(str(c).replace("|", "\\|")
                                     for c in r) + " |")
    return "\n".join(out)


def render(inventory, discovered, emitted, texts, ct, steps):
    unmapped = [t for t in inventory if not t["rules"]]
    if unmapped:
        raise SystemExit("tests without a rule mapping: " + ", ".join(
            f"{t['file']}::{t['class']}::{t['name']}" for t in unmapped))
    parsed_ids = sorted(
        f"tests.{t['file'][:-3]}.{t['class']}.{t['name']}" for t in inventory)
    if parsed_ids != discovered:
        raise SystemExit(
            "parsed inventory differs from unittest discovery: "
            f"{len(parsed_ids)} parsed vs {len(discovered)} discovered")

    by_file = {}
    for t in inventory:
        by_file.setdefault(t["file"], []).append(t)
    name_counts = {}
    for t in inventory:
        name_counts[t["name"]] = name_counts.get(t["name"], 0) + 1

    def label(t):
        if name_counts[t["name"]] > 1:
            return f"`{t['class']}.{t['name']}`"
        return f"`{t['name']}`"

    lines = [
        "# Regression suite map",
        "",
        "Generated by `generator/build_suite_map.py` (a validation-tooling "
        "generator, not application code) by parsing `tests/*.py` with the "
        "Python `ast` module and cross-checking the inventory against "
        "`unittest` discovery. Do not edit by hand: run the generator, or "
        "`--check` fails in the same way the repository's other generated "
        "evidence does. Synthetic data only.",
        "",
        "## Inventory control totals",
        "",
        _md(["Total", "Value"], [
            ["Test methods parsed from `tests/`", len(inventory)],
            ["Test methods found by `unittest` discovery", len(discovered)],
            ["Test files", len(by_file)],
            ["Test classes", len({(t['file'], t['class'])
                                  for t in inventory})],
            ["Extracted rules in the catalogue", len(RULES)],
            ["Rules protected by at least one test",
             len({r for t in inventory for r in t['rules']})],
            ["Message codes emitted by the Natural sources "
             "(`tools.analyze_disposition`)", len(emitted)],
            ["Emitted codes referenced by at least one test",
             len({c for c in emitted
                  if any(c in t['codes'] for t in inventory)})],
        ]),
        "",
        "## What CI runs",
        "",
        "Steps extracted verbatim from `.github/workflows/regression-tests.yml`"
        " (`run:` lines, in order):",
        "",
        _md(["#", "Command", "Gate"], [
            [i + 1, f"`{s}`", _gate_for(s)] for i, s in enumerate(steps)]),
        "",
        "## Test files",
        "",
        _md(["File", "Class of test", "Harness", "Tests", "Purpose (module "
             "docstring, first sentence)"], [
            [f"`tests/{f}`", FILE_CLASS[f][0], f"`{FILE_CLASS[f][1]}`",
             len(ts), _first_sentence(ts[0]["module_doc"])]
            for f, ts in by_file.items()]),
        "",
        "## Rule catalogue and coverage",
        "",
        "Rule identifiers are local to this directory; the integrating "
        "session aligns them with the catalogue in "
        "`../02-business-rule-extraction/`. Source citations are line ranges "
        "opened while authoring; `tests/test_source_conformance.py` asserts "
        "the same idioms against the shipped files on every run.",
        "",
    ]
    cov_rows = []
    for rid, rclass, text, src, _ in RULES:
        tests = [t for t in inventory if rid in t["rules"]]
        cov_rows.append([
            f"`{rid}`", rclass, text, f"`{src}`",
            REQUIREMENTS[rclass], len(tests),
            "; ".join(label(t) for t in tests) or "**none**",
        ])
    lines += [_md(["Rule", "Class", "Behaviour protected", "Source",
                   "HCM requirement (analogy)", "Tests", "Test methods"],
                  cov_rows), ""]

    lines += [
        "## Message-code coverage (from source)",
        "",
        "Codes below are those the Natural sources emit today "
        "(`tools.analyze_disposition`, `message_codes.emitted`). A gap means "
        "no test references the code; each gap is a candidate for rule "
        "extraction and test generation, not a defect in the sources.",
        "",
    ]
    code_rows = []
    for code, emitters in emitted.items():
        tests = [t for t in inventory if code in t["codes"]]
        code_rows.append([
            code, texts.get(code, [""])[-1], ", ".join(emitters),
            len(tests),
            "; ".join(label(t) for t in tests)
            if tests else "**gap — no test references this code**",
        ])
    lines += [_md(["Code", "CAMSG-N text (EN)", "Emitted by", "Tests",
                   "Test methods"], code_rows), ""]

    lines += ["## Test inventory", "",
              "One row per test method, in file and source order. *Codes* "
              "are message numbers referenced in the test body, name or "
              "docstring; *Natural idioms asserted* are the literal source "
              "strings a conformance test searches for.", ""]
    for f, ts in by_file.items():
        lines += [f"### `tests/{f}`", ""]
        rows = []
        for t in ts:
            rows.append([
                f"`{t['class']}.{t['name']}`", t["line"],
                ", ".join(f"`{r}`" for r in t["rules"]),
                ", ".join(t["codes"]) or "—",
                "; ".join(f"`{s}`" for s in t["natural"]) or "—",
                t["doc"] or _humanize(t["name"]),
            ])
        lines += [_md(["Test", "Line", "Rules", "Codes",
                       "Natural idioms asserted", "Intent"], rows), ""]

    lines += [
        "## Disposition control totals the suite pins",
        "",
        "`tests/test_disposition_analysis.py` asserts these values from "
        "`tools.analyze_disposition`; they are reproduced here from the same "
        "generator so the map cannot disagree with the suite.",
        "",
        _md(["Control total", "Value"], [
            ["Objects in scope", ct["objects"]],
            ["Code objects", ct["code_objects"]],
            ["Message codes catalogued in CAMSG-N",
             ct["message_codes_cataloged"]],
            ["Message codes emitted", ct["message_codes_emitted"]],
            ["Emitted but not catalogued",
             ct["message_codes_emitted_not_cataloged"]],
            ["Commented-out message emits (candidate, disabled logic)",
             ct["commented_out_message_emits"]],
            ["Objects unreferenced in analyzed scope",
             len(ct["unreferenced_objects"])],
            ["PDA fields declared but never assigned",
             len(ct["pda_fields_never_assigned"])],
            ["UI events declared / unhandled",
             f"{ct['ui_events_declared']} / {len(ct['ui_events_unhandled'])}"],
        ]),
        "",
    ]
    return "\n".join(lines)


def _gate_for(cmd):
    if "compileall" in cmd:
        return "Every Python file under tests/ and tools/ byte-compiles"
    if "unittest" in cmd:
        return "All discovered tests pass (behavioural, conformance, drift)"
    if "generate_data_dictionary" in cmd:
        return "Regenerates docs/data-dictionary.md from the DDMs"
    if "git diff" in cmd:
        return "Committed docs/data-dictionary.md equals the regenerated " \
               "output (drift gate)"
    return ""


def _first_sentence(doc):
    doc = " ".join(doc.split())
    m = re.match(r"(.+?\.)(\s|$)", doc)
    return m.group(1) if m else doc


def _humanize(name):
    return name[len("test_"):].replace("_", " ").capitalize()


def build():
    inventory = parse_tests()
    emitted, texts, ct = source_message_codes()
    return render(inventory, discovered_test_ids(), emitted, texts, ct,
                  workflow_steps())


PROSE_DOCS = ("README.md", "test-generation-approach.md")
_COUNT_RE = re.compile(r"(?<![\w-])(?!0\d)(\d+) (tests|rules)\b")  # skips `02 rules`


def prose_count_errors(inventory):
    """Hand-written ``N tests`` / ``N rules`` figures in the authored 09
    documents must equal the suite total, one per-class subtotal, or the
    rule-catalogue size."""
    by_class = {}
    for t in inventory:
        by_class[t["file"]] = by_class.get(t["file"], 0) + 1
    class_totals = {}
    for f, n in by_class.items():
        cls = FILE_CLASS[f][0].split(" (")[0]
        class_totals[cls] = class_totals.get(cls, 0) + n
    ok_tests = {len(inventory), *class_totals.values()}
    errors = []
    for name in PROSE_DOCS:
        text = (OUT_PATH.parent / name).read_text(encoding="utf-8")
        for m in _COUNT_RE.finditer(text):
            n, what = int(m.group(1)), m.group(2)
            if (what == "tests" and n not in ok_tests) or \
                    (what == "rules" and n != len(RULES)):
                errors.append(f"{name}: '{m.group(0)}' does not match tests/ "
                              f"(total {len(inventory)}, by class "
                              f"{class_totals}, rules {len(RULES)})")
    return errors


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if regression-suite-map.md differs from a "
                         "fresh build")
    ap.add_argument("--stdout", action="store_true",
                    help="print the map instead of writing it")
    args = ap.parse_args(argv)
    text = build() + "\n"
    prose = prose_count_errors(parse_tests())
    if prose:
        sys.stderr.write("\n".join(prose) + "\n")
        return 1
    if args.stdout:
        sys.stdout.write(text)
        return 0
    if args.check:
        current = OUT_PATH.read_text(encoding="utf-8") \
            if OUT_PATH.exists() else ""
        if current != text:
            sys.stderr.write(
                "DRIFT: regression-suite-map.md differs from tests/ — run "
                f"{os.path.relpath(__file__, REPO_ROOT)}\n")
            return 1
        print("regression suite map: up to date with tests/")
        return 0
    OUT_PATH.write_text(text, encoding="utf-8")
    print(f"wrote {os.path.relpath(OUT_PATH, REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
