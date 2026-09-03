#!/usr/bin/env python3
"""Static migration-disposition evidence for the Natural/ADABAS sources.

Scans every Natural object under ``SunnyIslands/Natural-Libraries`` and emits
the evidence an SI needs to decide what must *not* be carried into an HCM:
unreferenced objects, unreachable code, orphaned message-catalog entries,
never-referenced DDM fields, declared-but-unused variables, commented-out
statements, and interface fields that are declared but never populated.

All findings are *static candidates*. Nothing here proves a module is dead
at runtime; the outputs carry the evidence class so a Natural SME can
confirm or reject each row (see Predict XRef "Verify Application Integrity":
consistency / completeness / correctness).

Usage:
    python3 tools/analyze_disposition.py            # rewrite evidence files
    python3 tools/analyze_disposition.py --stdout   # print the JSON only

Outputs (under fpps-hcm-modernization-deliverable/10-migration-disposition-dead-code/evidence/):
    disposition-evidence.json   machine-readable evidence
    disposition-evidence.md     generated tables (do not edit by hand)
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.harness import source_parser as sp  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
LIB_ROOT = REPO_ROOT / "SunnyIslands" / "Natural-Libraries"
UI_XML = (REPO_ROOT / "SunnyIslands" / "User-Interface-Components"
          / "CruisePages" / "xml" / "rdcruisx.xml")
OUT_DIR = (REPO_ROOT / "fpps-hcm-modernization-deliverable"
           / "10-migration-disposition-dead-code" / "evidence")

OBJECT_TYPES = {
    ".NSN": "subprogram",
    ".NSP": "program",
    ".NSC": "copycode",
    ".NSL": "local data area",
    ".NSG": "global data area",
    ".NSA": "parameter data area",
    ".NSD": "DDM",
}
CODE_TYPES = {"subprogram", "program", "copycode"}
DATA_AREA_TYPES = {"local data area", "global data area", "parameter data area"}

# The NJX page adapter is the only externally driven entry point; programs
# (.NSP) can also be started directly from a Natural session.
UI_ROOT = "RDCRUISP"

# Natural system variables / keywords that collide with DDM field names.
FIELD_NAME_STOPLIST = {"LENGTH", "DATE", "TIME", "NAME", "ADDRESS", "PRICES"}

_CALL_RE = re.compile(
    r"\b(CALLNAT|FETCH(?:\s+RETURN)?|INCLUDE|PERFORM)\s+(?:'([A-Z0-9#@$&\-]+)'"
    r"|\"([A-Z0-9#@$&\-]+)\"|([A-Z0-9#@$&\-]+))"
)
_USING_RE = re.compile(r"\bUSING\s+([A-Z0-9#@$&\-]+)")
_COMMENTED_STMT_RE = re.compile(
    r"^\s*\*+\s*(MOVE|CALLNAT|PERFORM|RESET|COMPRESS|IF|FETCH|INCLUDE|"
    r"ASSIGN|ADD|SUBTRACT|DECIDE|READ|FIND|UPDATE|STORE|DELETE|WRITE|"
    r"DISPLAY|ESCAPE|END-IF|END-READ|END-FIND|ELSE|DEFINE\s+SUBROUTINE|"
    r"[A-Z0-9#@.\-]+\s*:=)\b"
)
_MARKER_RE = re.compile(
    r"TODO|exercise|not yet|nicht|Lorem ipsum|IGNORE\b|copyright",
    re.IGNORECASE,
)
_DATA_FIELD_RE = re.compile(
    r"^\s*([1-9])\s+([A-Z#][A-Z0-9#@$&\-]*)\s*(?P<fmt>\()?")
_UI_METHOD_RE = re.compile(r'method="([A-Za-z0-9_]+)"')


def _objects():
    objs = {}
    for path in sorted(LIB_ROOT.rglob("*")):
        otype = OBJECT_TYPES.get(path.suffix.upper())
        if not otype or not path.is_file():
            continue
        src = sp.read_source(path)
        rel = path.relative_to(REPO_ROOT).as_posix()
        library = path.relative_to(LIB_ROOT).parts[0]
        objs[path.stem] = {
            "object": path.stem,
            "type": otype,
            "library": library,
            "path": rel,
            "lines": len(src.splitlines()),
            "executable_lines": (
                len(sp.strip_comments(src)) if otype in CODE_TYPES else None
            ),
            "_src": src,
        }
    return objs


def _references(objs):
    """Static literal call/include/using references per object."""
    refs = []
    dynamic = []
    for name, o in objs.items():
        if o["type"] not in CODE_TYPES | DATA_AREA_TYPES:
            continue
        for lineno, raw in enumerate(o["_src"].splitlines(), 1):
            stripped = raw.strip()
            if not stripped or stripped.startswith(("*", "/*")):
                continue
            code = re.split(r"/\*", raw)[0]
            for m in _CALL_RE.finditer(code):
                stmt = m.group(1).split()[0]
                target = m.group(2) or m.group(3)
                bare = m.group(4)
                if stmt == "PERFORM":
                    continue  # inline subroutines, not objects
                if target:
                    refs.append({"caller": name, "statement": stmt,
                                 "callee": target, "line": lineno})
                elif bare and stmt == "INCLUDE":
                    refs.append({"caller": name, "statement": stmt,
                                 "callee": bare, "line": lineno})
                elif bare:
                    dynamic.append({"caller": name, "statement": stmt,
                                    "operand": bare, "line": lineno})
            for m in _USING_RE.finditer(code):
                refs.append({"caller": name, "statement": "USING",
                             "callee": m.group(1), "line": lineno})
    return refs, dynamic


def _reachability(objs, refs):
    edges = {}
    for r in refs:
        edges.setdefault(r["caller"], set()).add(r["callee"])
    reachable = set()
    stack = [UI_ROOT]
    while stack:
        n = stack.pop()
        if n in reachable:
            continue
        reachable.add(n)
        stack.extend(edges.get(n, ()))
    referenced = {r["callee"] for r in refs}
    rows = []
    for name, o in objs.items():
        if o["type"] == "DDM":
            continue
        callers = sorted({r["caller"] for r in refs if r["callee"] == name})
        if name == UI_ROOT:
            status = "entry point (NJX page adapter)"
        elif name in reachable:
            status = "reachable from UI root"
        elif o["type"] == "program":
            status = "standalone program; no UI path"
        elif name in referenced:
            status = "referenced only from unreachable code"
        else:
            status = "unreferenced in analyzed scope"
        rows.append({"object": name, "type": o["type"],
                     "library": o["library"], "callers": callers,
                     "status": status})
    return rows


def _message_codes(objs):
    camsg = sp.camsg_codes(objs["CAMSG-N"]["_src"])
    emitted = {}
    commented = []
    for name, o in objs.items():
        if o["type"] not in CODE_TYPES:
            continue
        for code in sp.message_codes(o["_src"]):
            emitted.setdefault(code, []).append(name)
        for lineno, raw in enumerate(o["_src"].splitlines(), 1):
            st = raw.strip()
            if st.startswith(("*", "/*")):
                m = re.search(r"MOVE\s+(\d{4})\s+TO\s+MSG-GROUP-PARA\.MSG-NR", st)
                if m:
                    commented.append({"object": name, "line": lineno,
                                      "code": int(m.group(1))})
    texts = {}
    for raw in objs["CAMSG-N"]["_src"].splitlines():
        m = re.search(r"VALUE\s+(\d{4})\s+COMPRESS\s+'([^']*)'", raw)
        if m:
            texts.setdefault(int(m.group(1)), []).append(m.group(2).strip())
    return {
        "catalog": sorted(camsg),
        "emitted": {str(c): sorted(v) for c, v in sorted(emitted.items())},
        "cataloged_never_emitted": sorted(camsg - set(emitted)),
        "emitted_not_cataloged": sorted(set(emitted) - camsg),
        "commented_out_emits": commented,
        "texts": {str(c): v for c, v in sorted(texts.items())},
    }


def _executable_body(objs, types):
    return "\n".join(
        "\n".join(sp.strip_comments(o["_src"]))
        for o in objs.values() if o["type"] in types
    )


def _ddm_field_usage(objs):
    body = _executable_body(objs, CODE_TYPES)
    per_obj = {n: "\n".join(sp.strip_comments(o["_src"]))
               for n, o in objs.items() if o["type"] in CODE_TYPES}
    data_areas = {n: "\n".join(sp.strip_comments(o["_src"]))
                  for n, o in objs.items() if o["type"] in DATA_AREA_TYPES}
    rows = []
    for file_name, ddm in sp.all_ddms().items():
        for f in ddm.fields:
            if f.field_type in ("G", "P", "M") and not f.fmt:
                kind = "group/periodic header"
            else:
                kind = "field"
            pat = re.compile(r"\b" + re.escape(f.name) + r"\b")
            users = sorted(n for n, b in per_obj.items() if pat.search(b))
            declared = sorted(n for n, b in data_areas.items() if pat.search(b))
            rows.append({
                "file": file_name, "field": f.name, "format": f.fmt,
                "length": f.length, "kind": kind,
                "referenced_by": users,
                "declared_in_data_areas": declared,
                "ambiguous": f.name in FIELD_NAME_STOPLIST,
            })
    return rows


def _data_fields(src):
    """Yield (level, name, is_group) for every field declared inline."""
    in_define = False
    for raw in src.splitlines():
        st = raw.strip()
        if st.startswith(("*", "/*")):
            continue
        if st.startswith("DEFINE DATA"):
            in_define = True
        elif st.startswith("END-DEFINE"):
            in_define = False
        if not in_define:
            continue
        m = _DATA_FIELD_RE.match(re.split(r"/\*", raw)[0])
        if m and m.group(2) not in ("USING", "REDEFINE"):
            yield int(m.group(1)), m.group(2), m.group("fmt") is None


def _count_refs(name, code):
    return len(re.findall(r"(?<![A-Z0-9#@$&\-.])" + re.escape(name)
                          + r"(?![A-Z0-9#@$&\-])", code))


def _unused_level1_vars(objs):
    """Level-1 locals whose only occurrence is their own declaration.  For a
    level-1 group the children are checked too, so a group whose members are
    used by qualified or unqualified name is not reported."""
    rows = []
    for name, o in objs.items():
        if o["type"] not in {"subprogram", "program"}:
            continue
        code = "\n".join(sp.strip_comments(o["_src"]))
        fields = list(_data_fields(o["_src"]))
        for i, (level, var, is_group) in enumerate(fields):
            if level != 1:
                continue
            names = [var]
            if is_group:
                for lvl, child, _ in fields[i + 1:]:
                    if lvl == 1:
                        break
                    names.append(child)
            n = sum(_count_refs(x, code) for x in names) - len(names)
            if n <= 0:
                rows.append({"object": name, "variable": var,
                             "kind": "group" if is_group else "scalar",
                             "references_in_code": n})
    return rows


def _pda_field_population(objs, refs):
    """For every PDA field: is it ever assigned / read outside DEFINE DATA and
    CALLNAT parameter lists?  Catches contracts that are passed but never
    populated (declared-only interface fields)."""
    code_lines = []
    for o in objs.values():
        if o["type"] in CODE_TYPES:
            code_lines += sp.strip_comments(o["_src"])
    stmt_lines = [l for l in code_lines
                  if not re.match(r"^\s*(\d\s|CALLNAT|LOCAL|PARAMETER|USING|"
                                  r"DEFINE DATA|END-DEFINE)", l)]
    used_pdas = {r["callee"] for r in refs if r["statement"] == "USING"}
    rows = []
    for name, o in objs.items():
        if o["type"] != "parameter data area" or name not in used_pdas:
            continue
        for level, field, is_group in _data_fields(o["_src"]):
            if level < 2 or is_group:
                continue
            pat = r"(?<![A-Z0-9#@$&\-])" + re.escape(field) + r"(?![A-Z0-9#@$&\-])"
            hits = [l for l in stmt_lines if re.search(pat, l)]
            assigned = [l for l in hits if re.search(
                r"(TO\s+[A-Z0-9#@$&\-.]*" + re.escape(field) + r"\b)|"
                r"(INTO\s+[A-Z0-9#@$&\-.]*" + re.escape(field) + r"\b)|"
                r"(\b[A-Z0-9#@$&\-.]*" + re.escape(field) + r"\s*:=)|"
                r"(RESET\s+[A-Z0-9#@$&\-.]*" + re.escape(field) + r"\b)", l)]
            rows.append({
                "pda": name, "field": field,
                "statement_references": len(hits),
                "assignments": len(assigned),
                "reads": len(hits) - len(assigned),
            })
    return rows


def _commented_statements(objs):
    rows = []
    for name, o in objs.items():
        if o["type"] not in CODE_TYPES | DATA_AREA_TYPES:
            continue
        for lineno, raw in enumerate(o["_src"].splitlines(), 1):
            if _COMMENTED_STMT_RE.match(raw) and not raw.strip().startswith(
                    ("* >", "* :", "* <", "/**")):
                rows.append({"object": name, "line": lineno,
                             "text": raw.strip()[:90]})
    return rows


def _markers(objs):
    rows = []
    for name, o in objs.items():
        for lineno, raw in enumerate(o["_src"].splitlines(), 1):
            if raw.strip().startswith(("* >", "* :", "* <")):
                continue
            if _MARKER_RE.search(raw):
                rows.append({"object": name, "line": lineno,
                             "text": raw.strip()[:90]})
    return rows


def _ui_events(objs):
    xml = sp.read_source(UI_XML)
    methods = _UI_METHOD_RE.findall(xml)
    adapter = "\n".join(sp.strip_comments(objs[UI_ROOT]["_src"]))
    rows = []
    for m in sorted(set(methods)):
        handled = bool(re.search(r"VALUE\s+U?'(?:[a-z]+\.)?" + re.escape(m) + r"'", adapter))
        rows.append({"event": m, "declared_in_ui": methods.count(m),
                     "handled_in_adapter": handled})
    return rows


def analyze():
    objs = _objects()
    refs, dynamic = _references(objs)
    result = {
        "scope": "SunnyIslands/Natural-Libraries (static analysis; candidates only)",
        "inventory": [
            {k: v for k, v in o.items() if not k.startswith("_")}
            for o in objs.values()
        ],
        "references": refs,
        "dynamic_invocations": dynamic,
        "reachability": _reachability(objs, refs),
        "message_codes": _message_codes(objs),
        "ddm_field_usage": _ddm_field_usage(objs),
        "unused_level1_variables": _unused_level1_vars(objs),
        "pda_field_population": _pda_field_population(objs, refs),
        "commented_out_statements": _commented_statements(objs),
        "markers": _markers(objs),
        "ui_events": _ui_events(objs),
    }
    result["control_totals"] = control_totals(result)
    return result


def control_totals(result):
    mc = result["message_codes"]
    never_used_fields = [
        r for r in result["ddm_field_usage"]
        if r["kind"] == "field" and not r["referenced_by"] and not r["ambiguous"]
    ]
    unref_objects = [r["object"] for r in result["reachability"]
                     if r["status"] == "unreferenced in analyzed scope"]
    standalone = [r["object"] for r in result["reachability"]
                  if r["status"] == "standalone program; no UI path"]
    never_populated = [
        f"{r['pda']}.{r['field']}" for r in result["pda_field_population"]
        if r["assignments"] == 0
    ]
    return {
        "objects": len(result["inventory"]),
        "code_objects": sum(1 for o in result["inventory"]
                            if o["type"] in CODE_TYPES),
        "static_references": len(result["references"]),
        "dynamic_invocations": len(result["dynamic_invocations"]),
        "unreferenced_objects": sorted(unref_objects),
        "standalone_programs_no_ui_path": sorted(standalone),
        "message_codes_cataloged": len(mc["catalog"]),
        "message_codes_emitted": len(mc["emitted"]),
        "message_codes_cataloged_never_emitted": len(mc["cataloged_never_emitted"]),
        "message_codes_emitted_not_cataloged": len(mc["emitted_not_cataloged"]),
        "commented_out_message_emits": len(mc["commented_out_emits"]),
        "ddm_fields_never_referenced": len(never_used_fields),
        "ddm_fields_ambiguous_name": sum(
            1 for r in result["ddm_field_usage"] if r["ambiguous"]),
        "unused_level1_variables": len(result["unused_level1_variables"]),
        "pda_fields_never_assigned": sorted(never_populated),
        "commented_out_statements": len(result["commented_out_statements"]),
        "ui_events_declared": len(result["ui_events"]),
        "ui_events_unhandled": sorted(
            r["event"] for r in result["ui_events"] if not r["handled_in_adapter"]),
    }


def _md_table(headers, rows):
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join("---" for _ in headers) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(c) for c in r) + " |")
    return out


def render_markdown(result):
    ct = result["control_totals"]
    mc = result["message_codes"]
    L = [
        "# Migration-disposition evidence (generated)",
        "",
        "Generated by `python3 tools/analyze_disposition.py` from the Natural",
        "sources under `SunnyIslands/Natural-Libraries/`. **Do not edit by hand.**",
        "",
        "> Every row is a *static* candidate derived from the shipped source.",
        "> None of it proves runtime behaviour; a Natural SME confirms or rejects",
        "> each item before it becomes a disposition decision. Dynamic",
        "> invocations (`CALLNAT #VAR`) are listed separately because static",
        "> analysis cannot resolve them.",
        "",
        "## Control totals",
        "",
    ]
    L += _md_table(["Measure", "Value"], [
        ("Natural objects analyzed", ct["objects"]),
        ("Code objects (subprogram / program / copycode)", ct["code_objects"]),
        ("Static literal references (CALLNAT/FETCH/INCLUDE/USING)", ct["static_references"]),
        ("Dynamic invocations (unresolvable statically)", ct["dynamic_invocations"]),
        ("Objects unreferenced in analyzed scope", ", ".join(ct["unreferenced_objects"]) or "none"),
        ("Standalone programs with no UI path", ", ".join(ct["standalone_programs_no_ui_path"]) or "none"),
        ("Message codes cataloged in CAMSG-N", ct["message_codes_cataloged"]),
        ("Message codes emitted by executable code", ct["message_codes_emitted"]),
        ("Cataloged but never emitted", ct["message_codes_cataloged_never_emitted"]),
        ("Emitted but not cataloged", ct["message_codes_emitted_not_cataloged"]),
        ("Commented-out message emits", ct["commented_out_message_emits"]),
        ("DDM fields never referenced by executable code", ct["ddm_fields_never_referenced"]),
        ("DDM fields with keyword-ambiguous names (excluded)", ct["ddm_fields_ambiguous_name"]),
        ("Level-1 variables declared but unused", ct["unused_level1_variables"]),
        ("PDA fields never assigned anywhere", ", ".join(ct["pda_fields_never_assigned"]) or "none"),
        ("Commented-out executable statements", ct["commented_out_statements"]),
        ("UI events declared / unhandled in adapter",
         f"{ct['ui_events_declared']} / {', '.join(ct['ui_events_unhandled']) or 'none'}"),
    ])
    L += ["", "## Object reachability from the NJX page adapter", ""]
    L += _md_table(["Object", "Type", "Library", "Callers", "Status"], [
        (f"`{r['object']}`", r["type"], r["library"],
         ", ".join(f"`{c}`" for c in r["callers"]) or "—", r["status"])
        for r in result["reachability"]
    ])
    L += ["", "## Static reference edges", ""]
    L += _md_table(["Caller", "Statement", "Callee", "Line"], [
        (f"`{r['caller']}`", r["statement"], f"`{r['callee']}`", r["line"])
        for r in result["references"]
    ])
    if result["dynamic_invocations"]:
        L += ["", "## Dynamic invocations (cannot be resolved statically)", ""]
        L += _md_table(["Caller", "Statement", "Operand", "Line"], [
            (f"`{r['caller']}`", r["statement"], f"`{r['operand']}`", r["line"])
            for r in result["dynamic_invocations"]
        ])
    L += ["", "## Message catalog reconciliation (CAMSG-N)", "",
          f"Cataloged: {len(mc['catalog'])} · Emitted: {len(mc['emitted'])} · "
          f"Cataloged-never-emitted: {len(mc['cataloged_never_emitted'])} · "
          f"Emitted-not-cataloged: {len(mc['emitted_not_cataloged'])}", ""]
    rows = []
    for code in mc["catalog"]:
        emitters = mc["emitted"].get(str(code), [])
        text = mc["texts"].get(str(code), [""])[-1]
        rows.append((code, text, ", ".join(f"`{e}`" for e in emitters) or "—",
                     "emitted" if emitters else "**never emitted**"))
    L += _md_table(["Code", "Text (EN)", "Emitted by", "Status"], rows)
    L += ["", "### Commented-out message emits", ""]
    L += _md_table(["Object", "Line", "Code"], [
        (f"`{r['object']}`", r["line"], r["code"]) for r in mc["commented_out_emits"]
    ])
    L += ["", "## DDM field usage (executable code only)", ""]
    L += _md_table(["File", "Field", "Fmt", "Len", "Referenced by (code)",
                    "Declared in data areas", "Note"], [
        (r["file"], f"`{r['field']}`", r["format"], r["length"],
         ", ".join(f"`{u}`" for u in r["referenced_by"]) or "**none**",
         ", ".join(f"`{u}`" for u in r["declared_in_data_areas"]) or "—",
         "keyword-ambiguous name; excluded from totals" if r["ambiguous"]
         else ("group header" if r["kind"] != "field" else ""))
        for r in result["ddm_field_usage"]
    ])
    L += ["", "## Level-1 variables declared but unused", ""]
    L += _md_table(["Object", "Variable", "Kind", "References beyond declaration"], [
        (f"`{r['object']}`", f"`{r['variable']}`", r["kind"],
         r["references_in_code"]) for r in result["unused_level1_variables"]
    ])
    L += ["", "## PDA interface fields: assignments vs reads", "",
          "Scalar fields of every PDA that is actually `USING`-referenced.",
          "Zero assignments means the field is declared in a service contract",
          "but never populated by any caller or service (heuristic: MOVE/",
          "COMPRESS INTO/:=/RESET targets count as assignments).", ""]
    L += _md_table(["PDA", "Field", "Statement refs", "Assignments", "Reads"], [
        (f"`{r['pda']}`", f"`{r['field']}`", r["statement_references"],
         r["assignments"], r["reads"]) for r in result["pda_field_population"]
    ])
    L += ["", "## Commented-out executable statements", ""]
    L += _md_table(["Object", "Line", "Text"], [
        (f"`{r['object']}`", r["line"], "`" + r["text"].replace("|", "\\|") + "`")
        for r in result["commented_out_statements"]
    ])
    L += ["", "## Source markers (TODO / exercise / not yet / placeholders)", ""]
    L += _md_table(["Object", "Line", "Text"], [
        (f"`{r['object']}`", r["line"], "`" + r["text"].replace("|", "\\|") + "`")
        for r in result["markers"]
    ])
    L += ["", "## UI events (rdcruisx.xml) vs adapter handlers", ""]
    L += _md_table(["Event", "Declared in UI", "Handled in RDCRUISP"], [
        (f"`{r['event']}`", r["declared_in_ui"],
         "yes" if r["handled_in_adapter"] else "**no**")
        for r in result["ui_events"]
    ])
    return "\n".join(L) + "\n"


def main(argv):
    result = analyze()
    if "--stdout" in argv:
        print(json.dumps(result, indent=2))
        return 0
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "disposition-evidence.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8")
    (OUT_DIR / "disposition-evidence.md").write_text(
        render_markdown(result), encoding="utf-8")
    print(json.dumps(result["control_totals"], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
