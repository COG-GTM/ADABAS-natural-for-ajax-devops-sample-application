#!/usr/bin/env python3
"""Validation generator for the business-rule and requirements artifacts.

This is a documentation generator and consistency checker, not a conversion
of any Natural program.  It reads the shipped Natural sources through
``tests/harness/source_parser.py`` and ``tools/analyze_disposition.py`` and
rewrites the marked ``<!-- generated:NAME --> ... <!-- /generated:NAME -->``
blocks inside the Markdown files of

    fpps-hcm-modernization-deliverable/02-business-rule-extraction/
    fpps-hcm-modernization-deliverable/05-requirements-baseline/

so that every count, code set, and line-number list in those documents is
derived from source rather than typed by hand.

``--check`` additionally verifies, without writing anything, that

* every generated block on disk equals what the sources produce today;
* every backticked citation ``path:start-end`` points at an existing file
  and a line range inside it;
* the BR-nnn identifiers defined in business-rules.md are exactly the ones
  used in rule-traceability-matrix.md (bidirectional), the REQ identifiers
  defined in requirements-baseline.md are exactly the ones used in
  acceptance-criteria.md, and every REQ/BR reference across both
  directories resolves to a definition;
* every confidence score in business-rules.md equals the score the rubric
  in confidence-model.md yields for the evidence classes listed next to it.

Usage (from the repository root):
    python3 fpps-hcm-modernization-deliverable/02-business-rule-extraction/generate_rule_evidence.py
    python3 fpps-hcm-modernization-deliverable/02-business-rule-extraction/generate_rule_evidence.py --check
"""

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from tests.harness import source_parser as sp  # noqa: E402
from tools import analyze_disposition as ad  # noqa: E402

DELIVERABLE = REPO_ROOT / "fpps-hcm-modernization-deliverable"
DIR_02 = DELIVERABLE / "02-business-rule-extraction"
DIR_05 = DELIVERABLE / "05-requirements-baseline"
TESTS_DIR = REPO_ROOT / "tests"
SERVICES = ("CONEW-N", "CRLIST-N", "CRGET-N", "CUGET-N", "CUNEW-N",
            "CUMOD-N", "CAMSG-N")

# Confidence rubric (mirrors confidence-model.md).  Letters are the evidence
# classes cited next to each score in business-rules.md.
RUBRIC = {
    "S": 0.50,   # static citation of an executable source line
    "C": 0.20,   # source-conformance test asserts the construct
    "H": 0.20,   # harness execution reproduces the behaviour
    "D": 0.10,   # repository documentation describes the same semantics
    "N": -0.20,  # depends on Natural runtime semantics inferred, not observed
    "R": -0.10,  # depends on data content not present in the synthetic set
}
CONFIDENCE_CAP = 0.95
CONFIDENCE_FLOOR = 0.20

BLOCK_RE = re.compile(
    r"(<!-- generated:(?P<name>[a-z0-9-]+) -->)(?P<body>.*?)(<!-- /generated:(?P=name) -->)",
    re.DOTALL,
)
CITATION_RE = re.compile(
    r"`(?P<path>(?:SunnyIslands|tests|tools|docs|fpps-hcm-modernization-deliverable)/"
    r"[^`:]+?):(?P<start>\d+)(?:-(?P<end>\d+))?`"
)
BR_DEF_RE = re.compile(r"^### (BR-(?:D|C|M)?\d{3})\b", re.MULTILINE)
BR_REF_RE = re.compile(r"\bBR-(?:D|C|M)?\d{3}\b")
REQ_DEF_RE = re.compile(r"^### (REQ-[FDIXN]-\d{3})\b", re.MULTILINE)
REQ_REF_RE = re.compile(r"\bREQ-[FDIXN]-\d{3}\b")
CONFIDENCE_RE = re.compile(
    r"^\| Confidence \| (?P<score>\d\.\d{2}) \((?P<classes>[SCHDNR](?:\+[SCHDNR])*)\)",
    re.MULTILINE,
)
EMIT_RE = re.compile(r"MOVE\s+(\d{4})\s+TO\s+MSG-GROUP-PARA\.MSG-NR")
STUDENT_RE = re.compile(r"^\s*IF\s+#STUDENT\b")


def _service_path(name):
    return sp.CRUISE16 / "Subprograms" / f"{name}.NSN"


def _rel(path):
    return str(Path(path).resolve().relative_to(REPO_ROOT))


def _executable_lines(source):
    """(lineno, code) pairs for executable lines, mirroring strip_comments."""
    out = []
    for lineno, line in enumerate(source.splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("*") or stripped.startswith("/*"):
            continue
        code = re.split(r"/\*", line)[0].rstrip()
        if code.strip():
            out.append((lineno, code))
    return out


def _camsg_texts():
    """{code: {'de': text, 'en': text}} parsed from the two DECIDE blocks."""
    src = sp.read_source(_service_path("CAMSG-N"))
    lines = src.splitlines()
    en_start = next(i for i, l in enumerate(lines)
                    if re.search(r"MSG-LANG\s+NE\s+'2'", l))
    texts = {}
    for i, raw in enumerate(lines):
        m = re.search(r"VALUE\s+(\d{4})\s+COMPRESS\s+'([^']*)'", raw)
        if m:
            lang = "en" if i >= en_start else "de"
            texts.setdefault(int(m.group(1)), {})[lang] = m.group(2).strip()
    return texts


def _success_remap_codes():
    """Codes whose English VALUE branch moves 0 to MSG-NR (response code 0)."""
    src = sp.read_source(_service_path("CAMSG-N"))
    codes, current = set(), None
    seen_en = False
    for _, code in _executable_lines(src):
        if re.search(r"MSG-LANG\s+NE\s+'2'", code):
            seen_en = True
        if not seen_en:
            continue
        m = re.search(r"VALUE\s+(\d{4})\b", code)
        if m:
            current = int(m.group(1))
        elif current is not None and re.search(
                r"MOVE\s+0\s+TO\s+MSG-GROUP-PARA\.MSG-NR", code):
            codes.add(current)
    return codes


def _emits_by_service():
    rows = []
    for name in SERVICES:
        src = sp.read_source(_service_path(name))
        by_code = {}
        for lineno, code in _executable_lines(src):
            m = EMIT_RE.search(code)
            if m:
                by_code.setdefault(int(m.group(1)), []).append(lineno)
        for code_nr, linenos in sorted(by_code.items()):
            rows.append((name, code_nr, linenos))
    return rows


def _student_gates():
    rows = []
    for name in SERVICES:
        src = sp.read_source(_service_path(name))
        gate = [ln for ln, code in _executable_lines(src) if STUDENT_RE.match(code)]
        if gate:
            rows.append((name, gate))
    return rows


def _tests_referencing(code_nr):
    pattern = re.compile(r"(?<!\d)%d(?!\d)" % code_nr)
    hits = {}
    for path in sorted(TESTS_DIR.rglob("*.py")):
        if path.name == "__init__.py":
            continue
        n = sum(1 for line in path.read_text(encoding="utf-8").splitlines()
                if pattern.search(line))
        if n:
            hits[_rel(path)] = n
    return hits


def _md_table(headers, rows):
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join("---" for _ in headers) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(out)


def _lines(linenos):
    return ", ".join(str(n) for n in linenos)


# --------------------------------------------------------------------------
# block renderers
# --------------------------------------------------------------------------

def block_emitted_codes_by_service(ctx):
    rows = []
    for name, code_nr, linenos in ctx["emits"]:
        rows.append((
            f"`{name}`", code_nr,
            f"`{_rel(_service_path(name))}:{_lines(linenos)}`" if len(linenos) == 1
            else f"`{_rel(_service_path(name))}` lines {_lines(linenos)}",
            ctx["texts"].get(code_nr, {}).get("en", "(not in catalog)"),
            0 if code_nr in ctx["success"] else code_nr,
        ))
    return _md_table(
        ["Service", "Code", "Executable source line(s)", "English catalog text",
         "Response code returned to caller"], rows)


def block_commented_out_emits(ctx):
    emitted = set(ctx["mc"]["emitted"])
    rows = []
    for r in ctx["mc"]["commented_out_emits"]:
        code_nr = r["code"]
        status = ("also emitted by executable code" if str(code_nr) in emitted
                  else "cataloged, never emitted")
        rows.append((
            f"`{r['object']}`",
            f"`{_rel(_service_path(r['object']))}:{r['line']}`",
            code_nr,
            ctx["texts"].get(code_nr, {}).get("en", "(not in catalog)"),
            status,
        ))
    return _md_table(
        ["Object", "Commented line", "Code", "English catalog text",
         "Catalog status"], rows)


def block_catalog_reconciliation(ctx):
    mc = ctx["mc"]
    never = mc["cataloged_never_emitted"]
    rows = [
        ("Codes translated by `CAMSG-N` (catalog)", len(mc["catalog"])),
        ("Codes emitted by executable statements", len(mc["emitted"])),
        ("Cataloged but never emitted in analyzed scope", len(never)),
        ("Emitted but missing from the catalog", len(mc["emitted_not_cataloged"])),
        ("Success codes remapped to response code 0",
         f"{len(ctx['success'])} ({', '.join(str(c) for c in sorted(ctx['success']))})"),
        ("Commented-out `MOVE nnnn TO MSG-NR` statements",
         len(mc["commented_out_emits"])),
    ]
    return _md_table(["Measure", "Value"], rows)


def block_catalog_never_emitted(ctx):
    mc = ctx["mc"]
    rows = []
    for code_nr in mc["cataloged_never_emitted"]:
        t = ctx["texts"].get(code_nr, {})
        commented_in = sorted({
            f"`{r['object']}:{r['line']}`" for r in mc["commented_out_emits"]
            if r["code"] == code_nr})
        kind = "success (would remap to 0)" if code_nr in ctx["success"] else "edit / information"
        rows.append((code_nr, t.get("en", ""), t.get("de", ""), kind,
                     ", ".join(commented_in) if commented_in else "none"))
    return _md_table(
        ["Code", "English text", "German text", "Kind",
         "Appears only in commented-out code at"], rows)


def block_code_test_coverage(ctx):
    mc = ctx["mc"]
    rows = []
    for code_str, services in mc["emitted"].items():
        code_nr = int(code_str)
        hits = _tests_referencing(code_nr)
        test_files = [f"`{p}` ({n})" for p, n in hits.items()
                      if not p.startswith("tests/harness/")]
        model_files = [f"`{p}` ({n})" for p, n in hits.items()
                       if p.startswith("tests/harness/")]
        rows.append((
            code_nr,
            ", ".join(f"`{s}`" for s in services),
            ", ".join(test_files) if test_files else "none (harness needed)",
            ", ".join(model_files) if model_files else "none",
        ))
    return _md_table(
        ["Code", "Emitting service(s)", "Test modules referencing the code (line hits)",
         "Behavioural model referencing the code"], rows)


def block_student_gates(ctx):
    rows = []
    for name, linenos in ctx["student"]:
        rows.append((f"`{name}`", f"`{_rel(_service_path(name))}:{_lines(linenos)}`"))
    rows.append(("`NCDATA-L`", f"`{_rel(sp.CRUISE16 / 'Local Data Areas' / 'NCDATA-L.NSL')}:"
                 f"{ctx['student_init_line']}` (`#STUDENT (L) INIT <FALSE>`)"))
    return _md_table(["Object", "`IF #STUDENT` gate (executable line)"], rows)


def block_unreferenced_objects(ctx):
    inv = {o["object"]: o for o in ctx["analysis"]["inventory"]}
    rows = []
    for r in ctx["analysis"]["reachability"]:
        if r["status"] in ("unreferenced in analyzed scope",
                           "standalone program; no UI path"):
            o = inv[r["object"]]
            rows.append((f"`{r['object']}`", o["type"], f"`{o['path']}`", r["status"]))
    return _md_table(["Object", "Type", "Path", "Static status"], rows)


def block_never_assigned_pda_fields(ctx):
    rows = []
    for r in ctx["analysis"]["pda_field_population"]:
        if r["assignments"] == 0:
            rows.append((f"`{r['pda']}.{r['field']}`", r["statement_references"],
                         r["reads"], "declared but never assigned"))
    return _md_table(["Interface field", "Statement references", "Reads",
                      "Static status"], rows)


def block_control_totals(ctx):
    ct = ctx["analysis"]["control_totals"]
    rows = [
        ("Natural objects in analyzed scope", ct["objects"]),
        ("Objects unreferenced in analyzed scope",
         f"{len(ct['unreferenced_objects'])} ({', '.join(ct['unreferenced_objects'])})"),
        ("Standalone programs with no UI path",
         f"{len(ct['standalone_programs_no_ui_path'])} "
         f"({', '.join(ct['standalone_programs_no_ui_path'])})"),
        ("Message codes cataloged / emitted / never emitted",
         f"{ct['message_codes_cataloged']} / {ct['message_codes_emitted']} / "
         f"{ct['message_codes_cataloged_never_emitted']}"),
        ("Interface (PDA) fields declared but never assigned",
         f"{len(ct['pda_fields_never_assigned'])} "
         f"({', '.join(ct['pda_fields_never_assigned'])})"),
        ("DDM fields never referenced by executable code",
         ct["ddm_fields_never_referenced"]),
        ("Commented-out executable statements", ct["commented_out_statements"]),
    ]
    return _md_table(["Measure (static, candidates only)", "Value"], rows)


def block_coverage_summary(ctx):
    """Counts rows of the matrix tables in the file currently being rendered."""
    text = ctx["_current_text"]
    sections = re.split(r"^## ", text, flags=re.MULTILINE)[1:]
    rows = []
    for section in sections:
        title = section.splitlines()[0].strip()
        rule_rows = [l for l in section.splitlines()
                     if re.match(r"^\| BR-(?:D|C|M)?\d{3} ", l)]
        if not rule_rows:
            continue
        needed = [re.match(r"^\| (BR-(?:D|C|M)?\d{3}) ", l).group(1)
                  for l in rule_rows
                  if "harness needed" in l.split("|")[4] or l.split("|")[4].strip() == "none"]
        rows.append((title, len(rule_rows), len(rule_rows) - len(needed),
                     f"{len(needed)}" + (f" ({', '.join(needed)})" if needed else "")))
    return _md_table(["Section", "Rules", "Existing test cited",
                      "No executable check yet (harness needed or none)"], rows)


def block_confidence_distribution(ctx):
    """Score bands per section, parsed from the confidence rows of business-rules.md."""
    text = (DIR_02 / "business-rules.md").read_text(encoding="utf-8")
    sections = re.split(r"^## ", text, flags=re.MULTILINE)[1:]
    rows = []
    for section in sections:
        title = section.splitlines()[0].strip()
        scores = [float(s) for s, _ in CONFIDENCE_RE.findall(section)]
        if not scores:
            continue
        high = sum(1 for s in scores if s >= 0.85)
        medium = sum(1 for s in scores if 0.60 <= s < 0.85)
        low = len(scores) - high - medium
        rows.append((title, len(scores), f"{sum(scores) / len(scores):.2f}",
                     high, medium, low))
    return _md_table(["Section", "Rules", "Mean score", "High (≥0.85)",
                      "Medium (0.60–0.84)", "Low (<0.60)"], rows)


REQ_TYPE_NAMES = {"F": "Functional", "D": "Data", "I": "Integrity",
                  "X": "Interface", "N": "Non-functional"}


def _requirement_records():
    """Parse the requirement sections of 05/requirements-baseline.md."""
    text = (DIR_05 / "requirements-baseline.md").read_text(encoding="utf-8")
    records = []
    for section in re.split(r"^### ", text, flags=re.MULTILINE)[1:]:
        head = section.splitlines()[0]
        m = re.match(r"(REQ-([FDIXN])-\d{3})\s+\u2014\s+(.*)", head)
        if not m:
            continue

        def cell(label):
            r = re.search(r"^\| %s \| (.*?) \|$" % re.escape(label), section, re.MULTILINE)
            return r.group(1).strip() if r else ""
        records.append({
            "id": m.group(1), "type": REQ_TYPE_NAMES[m.group(2)], "title": m.group(3).strip(),
            "fit": cell("HCM fit"), "disposition": cell("Disposition"),
            "maturity": cell("Maturity"),
            "rules": sorted(set(BR_REF_RE.findall(cell("Linked rules")))),
        })
    return records


def block_requirements_index(ctx):
    rows = [(r["id"], r["title"], r["type"], r["fit"], r["disposition"],
             r["maturity"], ", ".join(r["rules"]) or "\u2014")
            for r in _requirement_records()]
    return _md_table(["Requirement", "Title", "Type", "HCM fit", "Disposition",
                      "Maturity", "Linked rules"], rows)


def block_requirements_summary(ctx):
    recs = _requirement_records()
    fits = ["standard", "configured", "extension", "integration", "out of scope"]
    rows = []
    for t in REQ_TYPE_NAMES.values():
        sub = [r for r in recs if r["type"] == t]
        if not sub:
            continue
        rows.append([t, len(sub)] + [sum(1 for r in sub if r["fit"].split(" (")[0] == f)
                                     for f in fits])
    rows.append(["All", len(recs)] + [sum(1 for r in recs if r["fit"].split(" (")[0] == f)
                                       for f in fits])
    return _md_table(["Type", "Requirements"] + fits, rows)


def block_rule_to_requirement(ctx):
    """Every rule id and the requirements that link to it (reverse index)."""
    recs = _requirement_records()
    rules_text = (DIR_02 / "business-rules.md").read_text(encoding="utf-8")
    exclusions = (DIR_05 / "what-we-will-not-build.md").read_text(encoding="utf-8")
    excluded = set(BR_REF_RE.findall(exclusions))
    rows = []
    for rule in BR_DEF_RE.findall(rules_text):
        reqs = [r["id"] for r in recs if rule in r["rules"]]
        where = ", ".join(reqs)
        if rule in excluded:
            where = (where + "; " if where else "") + "what-we-will-not-build.md"
        rows.append((rule, where or "\u2014"))
    return _md_table(["Rule", "Carried by"], rows)


AC_ROW_RE = re.compile(
    r"^\| (?P<id>AC-(?P<req>REQ-[FDIXN]-\d{3})-\d+) \| (?P<given>.*?) \| (?P<when>.*?) \| "
    r"(?P<then>.*?) \| (?P<evidence>.*?) \| (?P<target>.*?) \|$", re.MULTILINE)


def _acceptance_rows():
    text = (DIR_05 / "acceptance-criteria.md").read_text(encoding="utf-8")
    return [m.groupdict() for m in AC_ROW_RE.finditer(text)]


def _evidence_class(evidence):
    if "**harness needed**" in evidence:
        detail = evidence.split("\u2014", 1)[1] if "\u2014" in evidence else ""
        for key, label in (("interleaving harness", "Harness needed \u2014 interleaving harness"),
                           ("fault injection", "Harness needed \u2014 fault injection"),
                           ("target-side", "Harness needed \u2014 target-side test only"),
                           ("catalogue check", "Harness needed \u2014 catalogue check"),
                           ("load reconciliation", "Harness needed \u2014 load reconciliation"),
                           ("service harness", "Harness needed \u2014 service harness"),
                           ("SME decision", "Harness needed \u2014 SME decision first")):
            if key in detail:
                return label
        return "Harness needed \u2014 other"
    if CITATION_RE.search(evidence):
        return "Executable check in the repository today"
    return "Design review (not testable in the sample)"


def block_acceptance_coverage(ctx):
    rows = _acceptance_rows()
    by_class = {}
    for r in rows:
        by_class.setdefault(_evidence_class(r["evidence"]), []).append(r["req"])
    order = sorted(by_class, key=lambda k: (k.startswith("Harness"), k.startswith("Design"), k))
    table = [(k, len(by_class[k]), ", ".join(sorted(set(by_class[k])))) for k in order]
    table.append(("All criteria", len(rows), f"{len({r['req'] for r in rows})} requirements"))
    return _md_table(["Evidence class", "Criteria", "Requirements touched"], table)


RENDERERS = {
    "acceptance-coverage": block_acceptance_coverage,
    "requirements-index": block_requirements_index,
    "requirements-summary": block_requirements_summary,
    "rule-to-requirement": block_rule_to_requirement,
    "coverage-summary": block_coverage_summary,
    "confidence-distribution": block_confidence_distribution,
    "emitted-codes-by-service": block_emitted_codes_by_service,
    "commented-out-emits": block_commented_out_emits,
    "catalog-reconciliation": block_catalog_reconciliation,
    "catalog-never-emitted": block_catalog_never_emitted,
    "code-test-coverage": block_code_test_coverage,
    "student-gates": block_student_gates,
    "unreferenced-objects": block_unreferenced_objects,
    "never-assigned-pda-fields": block_never_assigned_pda_fields,
    "control-totals": block_control_totals,
}


def build_context():
    analysis = ad.analyze()
    ncdata = sp.read_source(sp.CRUISE16 / "Local Data Areas" / "NCDATA-L.NSL")
    init_line = next(ln for ln, code in _executable_lines(ncdata)
                     if "#STUDENT" in code)
    return {
        "analysis": analysis,
        "mc": analysis["message_codes"],
        "texts": _camsg_texts(),
        "success": _success_remap_codes(),
        "emits": _emits_by_service(),
        "student": _student_gates(),
        "student_init_line": init_line,
    }


def markdown_files():
    files = []
    for d in (DIR_02, DIR_05):
        files += sorted(p for p in d.rglob("*.md"))
    return files


def render_file(text, ctx, path):
    ctx["_current_text"] = text

    def repl(m):
        name = m.group("name")
        if name not in RENDERERS:
            raise SystemExit(f"{path}: unknown generated block '{name}'")
        return m.group(1) + "\n" + RENDERERS[name](ctx) + "\n" + m.group(4)
    return BLOCK_RE.sub(repl, text)


# --------------------------------------------------------------------------
# checks
# --------------------------------------------------------------------------

def check_citations(path, text, problems):
    for m in CITATION_RE.finditer(text):
        target = REPO_ROOT / m.group("path")
        start = int(m.group("start"))
        end = int(m.group("end") or start)
        if not target.is_file():
            problems.append(f"{path}: citation to missing file {m.group(0)}")
            continue
        n_lines = len(target.read_text(encoding="utf-8", errors="replace").splitlines())
        if start < 1 or end < start or end > n_lines:
            problems.append(
                f"{path}: citation {m.group(0)} outside 1-{n_lines}")


def check_identifiers(texts, problems):
    rules = texts[DIR_02 / "business-rules.md"]
    matrix = texts[DIR_02 / "rule-traceability-matrix.md"]
    baseline = texts[DIR_05 / "requirements-baseline.md"]
    criteria = texts[DIR_05 / "acceptance-criteria.md"]

    br_defined = set(BR_DEF_RE.findall(rules))
    br_in_matrix = set(BR_REF_RE.findall(matrix))
    if br_defined != br_in_matrix:
        problems.append(
            "BR identifiers differ between business-rules.md and "
            f"rule-traceability-matrix.md: only in rules {sorted(br_defined - br_in_matrix)}, "
            f"only in matrix {sorted(br_in_matrix - br_defined)}")

    req_defined = set(REQ_DEF_RE.findall(baseline))
    req_in_criteria = set(REQ_REF_RE.findall(criteria))
    if req_defined != req_in_criteria:
        problems.append(
            "REQ identifiers differ between requirements-baseline.md and "
            f"acceptance-criteria.md: only in baseline {sorted(req_defined - req_in_criteria)}, "
            f"only in criteria {sorted(req_in_criteria - req_defined)}")

    for path, text in texts.items():
        dangling_req = set(REQ_REF_RE.findall(text)) - req_defined
        dangling_br = set(BR_REF_RE.findall(text)) - br_defined
        if dangling_req:
            problems.append(f"{path}: undefined requirement ids {sorted(dangling_req)}")
        if dangling_br:
            problems.append(f"{path}: undefined rule ids {sorted(dangling_br)}")

    exclusions = texts[DIR_05 / "what-we-will-not-build.md"]
    br_carried = set()
    for r in _requirement_records():
        br_carried.update(r["rules"])
    br_carried |= set(BR_REF_RE.findall(exclusions))
    if br_defined - br_carried:
        problems.append(
            "rules with no requirement or exclusion carrying them: "
            f"{sorted(br_defined - br_carried)}")
    baseline_links = {}
    for r in _requirement_records():
        for rule in r["rules"]:
            baseline_links.setdefault(rule, set()).add(r["id"])
    for line in matrix.splitlines():
        m = re.match(r"^\| (BR-(?:D|C|M)?\d{3}) ", line)
        if not m:
            continue
        in_matrix = set(REQ_REF_RE.findall(line))
        in_baseline = baseline_links.get(m.group(1), set())
        if in_matrix != in_baseline:
            problems.append(
                f"{m.group(1)}: matrix requirement column {sorted(in_matrix)} differs from "
                f"baseline 'Linked rules' {sorted(in_baseline)}")

    for d in (DIR_02, DIR_05):
        readme = (d / "diagrams" / "README.md").read_text(encoding="utf-8")
        for mmd in sorted((d / "diagrams").glob("*.mmd")):
            if mmd.read_text(encoding="utf-8").strip() not in readme:
                problems.append(
                    f"{mmd.relative_to(REPO_ROOT)} differs from the copy embedded in "
                    f"{(d / 'diagrams' / 'README.md').relative_to(REPO_ROOT)}")

    ac_rows = _acceptance_rows()
    req_with_criteria = {r["req"] for r in ac_rows}
    if req_defined - req_with_criteria:
        problems.append(
            "requirements without an acceptance-criterion row: "
            f"{sorted(req_defined - req_with_criteria)}")
    ac_ids = [r["id"] for r in ac_rows]
    if len(ac_ids) != len(set(ac_ids)):
        problems.append("acceptance-criteria.md repeats a criterion identifier")
    req_in_matrix = set(REQ_REF_RE.findall(matrix))
    if req_defined - req_in_matrix:
        problems.append(
            "requirements not traced from rule-traceability-matrix.md: "
            f"{sorted(req_defined - req_in_matrix)}")

    if len(BR_DEF_RE.findall(rules)) != len(br_defined):
        problems.append("business-rules.md defines a BR identifier more than once")
    if len(REQ_DEF_RE.findall(baseline)) != len(req_defined):
        problems.append("requirements-baseline.md defines a REQ identifier more than once")


def rubric_score(classes):
    score = sum(RUBRIC[c] for c in classes.split("+"))
    return round(min(CONFIDENCE_CAP, max(CONFIDENCE_FLOOR, score)), 2)


def check_confidence(path, text, problems):
    sections = re.split(r"^### ", text, flags=re.MULTILINE)[1:]
    for section in sections:
        rule_id = section.split()[0]
        if not rule_id.startswith("BR-"):
            continue
        found = CONFIDENCE_RE.findall(section)
        if len(found) != 1:
            problems.append(f"{path}: {rule_id} needs exactly one "
                            f"'| Confidence | 0.nn (S+...) |' row, found {len(found)}")
            continue
        score, classes = found[0]
        if "S" not in classes.split("+"):
            problems.append(f"{path}: {rule_id} confidence lacks the static citation class S")
        expected = rubric_score(classes)
        if abs(float(score) - expected) > 1e-9:
            problems.append(
                f"{path}: {rule_id} confidence {score} does not match rubric "
                f"value {expected:.2f} for {classes}")


def main(argv):
    check = "--check" in argv
    ctx = build_context()
    problems = []
    texts = {}
    for path in markdown_files():
        current = path.read_text(encoding="utf-8")
        rendered = render_file(current, ctx, path)
        texts[path] = rendered
        if rendered != current:
            if check:
                problems.append(f"{_rel(path)}: generated blocks are stale")
            else:
                path.write_text(rendered, encoding="utf-8")
                print(f"updated {_rel(path)}")
    for path, text in texts.items():
        check_citations(_rel(path), text, problems)
    check_identifiers(texts, problems)
    check_confidence(_rel(DIR_02 / "business-rules.md"),
                     texts[DIR_02 / "business-rules.md"], problems)
    if problems:
        for p in problems:
            print(f"FAIL: {p}", file=sys.stderr)
        return 1
    print("ok: generated blocks, citations, identifiers and confidence scores are consistent")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
