"""Generate the process-flow evidence tables for capability 04 from source.

This is a validation/generator harness, not a conversion of Natural into
Python.  It reads the Natural for AJAX adapter (RDCRUISP.NSP), the page
definition (rdcruisx.xml) and the CRUISE16 service subprograms through the
shared parsers in ``tests/harness/source_parser.py`` and
``tools/analyze_disposition.py`` and writes:

* ``evidence/process-evidence.json`` – machine-readable facts
* ``evidence/process-evidence.md``   – the tables referenced by
  ``process-flows.md``, ``process-to-hcm-mapping.md`` and the BPMN notes

Every count, event list, message-code set and transaction-boundary line
number quoted in this directory comes from these files, never from a
hand-typed snapshot.

Usage (from the repository root)::

    python3 fpps-hcm-modernization-deliverable/04-business-process-flow-bpmn/generate_process_evidence.py
    python3 fpps-hcm-modernization-deliverable/04-business-process-flow-bpmn/generate_process_evidence.py --check

``--check`` exits non-zero when the committed evidence differs from what the
sources produce today (drift guard for CI).  It also cross-checks the
hand-written documents in this directory against the generated facts in both
directions (counts quoted in ``process-flows.md``, message codes drawn in each
Mermaid diagram, error codes and references in ``bpmn/booking-process.bpmn``)
so that a hand-typed number cannot silently go stale.
"""

import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tests.harness import source_parser as sp  # noqa: E402
from tools import analyze_disposition as ad  # noqa: E402

OUT_DIR = HERE / "evidence"
ADAPTER = sp.RDCRUISE / "Programs" / "RDCRUISP.NSP"
UI_XML = ad.UI_XML

#: Business services whose flows are narrated in process-flows.md, in the
#: order the four processes are presented.
SERVICES = ("CRLIST-N", "CRGET-N", "CUGET-N", "CUNEW-N", "CUMOD-N", "CONEW-N")

PROCESSES = [
    ("P1", "List cruises", ("CRLIST-N",)),
    ("P2", "Cruise detail", ("CRGET-N",)),
    ("P3", "Customer lookup / create / modify", ("CUGET-N", "CUNEW-N", "CUMOD-N")),
    ("P4", "Book cruise", ("CONEW-N",)),
]

#: Statements that define the ADABAS access and transaction boundary of a
#: service.  Order matters only for presentation.
BOUNDARY_STATEMENTS = (
    ("ON ERROR", re.compile(r"^\s*ON\s+ERROR\b")),
    ("FIND", re.compile(r"^\s*(?:[A-Z0-9]+\.\s*)?FIND\b")),
    ("READ", re.compile(r"^\s*(?:[A-Z0-9]+\.\s*)?READ\s+(?!WORK)")),
    ("GET", re.compile(r"^\s*(?:[A-Z0-9]+\.\s*)?GET\b")),
    ("UPDATE", re.compile(r"^\s*UPDATE\b")),
    ("STORE", re.compile(r"^\s*STORE\b")),
    ("END TRANSACTION", re.compile(r"^\s*END\s+TRANSACTION\b")),
    ("BACKOUT TRANSACTION", re.compile(r"^\s*BACKOUT\s+TRANSACTION\b")),
    ("ESCAPE ROUTINE", re.compile(r"^\s*ESCAPE\s+ROUTINE\b")),
)

_VALUE_RE = re.compile(r"^\s*VALUE\s+U?'([^']+)'")
_NONE_RE = re.compile(r"^\s*NONE\s+VALUE\b")
_PERFORM_RE = re.compile(r"\bPERFORM\s+([A-Z0-9\-]+)")
_CALLNAT_RE = re.compile(r"\bCALLNAT\s+[\"']([A-Z0-9\-]+)[\"']")
_FETCH_RE = re.compile(r"\bFETCH\s+RETURN\s+'([A-Z0-9\-]+)'")
_SUBR_RE = re.compile(r"^\s*DEFINE\s+SUBROUTINE\s+([A-Z0-9\-]+)")
_MSG_RE = re.compile(r"MOVE\s+(\d{4})\s+TO\s+MSG-GROUP-PARA\.MSG-NR")
_CAMSG_RESET_RE = re.compile(r"MOVE\s+0\s+TO\s+MSG-GROUP-PARA\.MSG-NR")
_CAMSG_VALUE_RE = re.compile(r"VALUE\s+(\d{4})\s+COMPRESS\s+'([^']*)'")
_MENU_RE = re.compile(r"MOVE\s+'([A-Za-z]+)\s*'\s+TO\s+DLMENU\.METHOD")


def _is_comment(raw):
    st = raw.strip()
    return not st or st.startswith("*") or st.startswith("/*")


def _code(raw):
    """Executable part of a source line (inline comment removed)."""
    return re.split(r"/\*", raw)[0].rstrip()


def _numbered(path):
    return list(enumerate(sp.read_source(path).splitlines(), 1))


# --------------------------------------------------------------------------
# Adapter: event dispatch and subroutines
# --------------------------------------------------------------------------

def _subroutines(lines):
    subs = {}
    current = None
    for lineno, raw in lines:
        if _is_comment(raw):
            continue
        code = _code(raw)
        m = _SUBR_RE.match(code)
        if m:
            current = {"name": m.group(1), "start": lineno, "end": None,
                       "performs": [], "callnats": []}
            subs[m.group(1)] = current
            continue
        if current is None:
            continue
        if re.match(r"^\s*END-SUBROUTINE\b", code):
            current["end"] = lineno
            current = None
            continue
        for pm in _PERFORM_RE.finditer(code):
            current["performs"].append(pm.group(1))
        for cm in _CALLNAT_RE.finditer(code):
            current["callnats"].append({"target": cm.group(1), "line": lineno})
    return subs


def _resolve_services(performs, callnats, subs, seen=None):
    """Transitive CALLNAT targets of a branch through PERFORMed subroutines."""
    seen = seen if seen is not None else set()
    out = list(callnats)
    for name in performs:
        if name in seen or name not in subs:
            continue
        seen.add(name)
        sub = subs[name]
        out.extend(sub["callnats"])
        out.extend(_resolve_services(sub["performs"], [], subs, seen))
    return out


def _event_branches(lines, subs):
    start = next(i for i, (_, raw) in enumerate(lines)
                 if "DECIDE ON FIRST *PAGE-EVENT" in raw)
    end = next(i for i, (_, raw) in enumerate(lines)
               if i > start and re.match(r"^\s*END-DECIDE\b", raw.strip()))
    branches = []
    current = None
    for lineno, raw in lines[start + 1:end]:
        if _is_comment(raw):
            continue
        code = _code(raw)
        m = _VALUE_RE.match(code)
        if m or _NONE_RE.match(code):
            current = {"event": m.group(1) if m else "NONE VALUE", "line": lineno,
                       "statements": [], "performs": [], "callnats": [],
                       "fetches": []}
            branches.append(current)
            continue
        if current is None:
            continue
        current["statements"].append(code.strip())
        current["performs"].extend(_PERFORM_RE.findall(code))
        current["callnats"].extend(
            {"target": c, "line": lineno} for c in _CALLNAT_RE.findall(code))
        current["fetches"].extend(_FETCH_RE.findall(code))
    for b in branches:
        calls = _resolve_services(b["performs"], b["callnats"], subs)
        b["services"] = sorted({c["target"] for c in calls if c["target"] in SERVICES})
        b["other_callnats"] = sorted({c["target"] for c in calls
                                      if c["target"] not in SERVICES})
        b["classification"] = _classify(b)
    return branches


def _classify(b):
    st = b["statements"]
    if st == ["IGNORE"]:
        return "ignored (IGNORE)"
    if "TERMINATE" in st:
        return "session end (TERMINATE)"
    if b["services"]:
        return "dispatches to business service"
    if b["fetches"]:
        return "language switch (FETCH RETURN RDCRINIP)"
    if all(s.startswith("PROCESS PAGE") for s in st):
        return "page refresh only"
    return "UI state only (visibility / GDA moves)"


def _ui_events():
    xml = sp.read_source(UI_XML)
    counts = {}
    for m in ad._UI_METHOD_RE.finditer(xml):
        counts[m.group(1)] = counts.get(m.group(1), 0) + 1
    return counts


def _menu_methods(lines):
    """Events the adapter raises through the DLMENU dynamic menu control."""
    rows = {}
    for lineno, raw in lines:
        if _is_comment(raw):
            continue
        m = _MENU_RE.search(_code(raw))
        if m:
            rows[m.group(1)] = lineno
    return rows


def _commented_callnats(lines):
    rows = []
    for lineno, raw in lines:
        if _is_comment(raw):
            m = _CALLNAT_RE.search(raw)
            if m:
                rows.append({"line": lineno, "target": m.group(1),
                             "text": raw.strip()})
    return rows


# --------------------------------------------------------------------------
# Services: message codes and transaction boundaries
# --------------------------------------------------------------------------

def _camsg_catalog():
    lines = _numbered(sp.CRUISE16 / "Subprograms" / "CAMSG-N.NSN")
    texts = {}
    resets = set()
    branch = None
    pending = None
    for lineno, raw in lines:
        if _is_comment(raw):
            continue
        code = _code(raw)
        if "MSG-LANG = '2'" in code:
            branch = "DE"
        elif "MSG-LANG NE '2'" in code:
            branch = "EN"
        m = _CAMSG_VALUE_RE.search(code)
        if m:
            pending = int(m.group(1))
            texts.setdefault(pending, {})[branch] = m.group(2).strip()
            continue
        if pending is not None and _CAMSG_RESET_RE.search(code):
            resets.add(pending)
        if re.match(r"^\s*VALUE\b", code) or re.match(r"^\s*NONE\b", code):
            pending = None
    return texts, resets


def _service_facts(name, texts, resets):
    path = sp.CRUISE16 / "Subprograms" / f"{name}.NSN"
    lines = _numbered(path)
    emitted = []
    commented = []
    boundaries = []
    for lineno, raw in lines:
        m = _MSG_RE.search(raw)
        if m:
            code = int(m.group(1))
            row = {"code": code, "line": lineno,
                   "text_en": texts.get(code, {}).get("EN", ""),
                   "success_remap": code in resets}
            (commented if _is_comment(raw) else emitted).append(row)
        if _is_comment(raw):
            continue
        code_line = _code(raw)
        for label, rx in BOUNDARY_STATEMENTS:
            if rx.search(code_line):
                boundaries.append({"statement": label, "line": lineno,
                                   "text": code_line.strip()})
    assert set(sp.message_codes(sp.read_source(path))) == {r["code"] for r in emitted}
    return {
        "object": name,
        "path": str(path.relative_to(REPO_ROOT)),
        "lines": len(lines),
        "emitted": emitted,
        "commented_out_emits": commented,
        "boundaries": boundaries,
        "has_end_transaction": any(b["statement"] == "END TRANSACTION" for b in boundaries),
        "has_backout_transaction": any(b["statement"] == "BACKOUT TRANSACTION" for b in boundaries),
        "student_gate": any("#STUDENT" in _code(raw) for _, raw in lines if not _is_comment(raw)),
    }


# --------------------------------------------------------------------------
# Assemble
# --------------------------------------------------------------------------

def analyze():
    adapter_lines = _numbered(ADAPTER)
    subs = _subroutines(adapter_lines)
    branches = _event_branches(adapter_lines, subs)
    ui_counts = _ui_events()
    menu = _menu_methods(adapter_lines)
    handled = {b["event"].split(".")[-1] for b in branches}
    texts, resets = _camsg_catalog()
    services = {name: _service_facts(name, texts, resets) for name in SERVICES}

    events = []
    for b in branches:
        short = b["event"].split(".")[-1]
        events.append({
            "event": b["event"],
            "adapter_line": b["line"],
            "declared_in_ui": ui_counts.get(short, 0),
            "raised_via_menu_line": menu.get(short),
            "performs": b["performs"],
            "services": b["services"],
            "other_callnats": b["other_callnats"],
            "classification": b["classification"],
        })
    declared_not_handled = sorted(e for e in ui_counts if e not in handled)
    handled_not_declared = sorted(
        b["event"] for b in branches
        if b["event"] != "NONE VALUE" and b["event"].split(".")[-1] not in ui_counts
        and b["event"].split(".")[-1] not in menu)
    menu_only = sorted(
        b["event"] for b in branches
        if b["event"].split(".")[-1] in menu and b["event"].split(".")[-1] not in ui_counts)

    processes = []
    for pid, title, svc in PROCESSES:
        proc_events = [e["event"] for e in events
                       if any(s in svc for s in e["services"])]
        codes = sorted({r["code"] for s in svc for r in services[s]["emitted"]})
        processes.append({"id": pid, "title": title, "services": list(svc),
                          "events": proc_events, "message_codes": codes})

    result = {
        "scope": ("SunnyIslands/Natural-Libraries + rdcruisx.xml (static analysis of "
                  "executable lines; findings are candidates)"),
        "adapter": {
            "path": str(ADAPTER.relative_to(REPO_ROOT)),
            "lines": len(adapter_lines),
            "subroutines": {
                k: {"start": v["start"], "end": v["end"],
                    "callnats": v["callnats"], "performs": sorted(set(v["performs"]))}
                for k, v in subs.items()
            },
            "commented_out_callnats": _commented_callnats(adapter_lines),
        },
        "ui_events": events,
        "ui_events_declared_not_handled": declared_not_handled,
        "adapter_handlers_not_declared_in_ui": handled_not_declared,
        "adapter_handlers_raised_only_via_menu": menu_only,
        "menu_methods": menu,
        "services": services,
        "processes": processes,
        "camsg": {
            "path": str((sp.CRUISE16 / "Subprograms" / "CAMSG-N.NSN").relative_to(REPO_ROOT)),
            "success_remap_codes": sorted(resets),
            "catalog_size": len(texts),
        },
        "camsg_catalog_codes": sorted(texts),
    }
    result["control_totals"] = control_totals(result)
    return result


def control_totals(result):
    events = result["ui_events"]
    by_class = {}
    for e in events:
        by_class[e["classification"]] = by_class.get(e["classification"], 0) + 1
    return {
        "ui_events_declared_distinct": len({e["event"].split(".")[-1]
                                            for e in events if e["declared_in_ui"]}),
        "ui_method_declarations_total": sum(e["declared_in_ui"] for e in events),
        "adapter_event_branches": len([e for e in events if e["event"] != "NONE VALUE"]),
        "ui_events_declared_not_handled": len(result["ui_events_declared_not_handled"]),
        "adapter_handlers_not_declared_in_ui": len(result["adapter_handlers_not_declared_in_ui"]),
        "adapter_handlers_raised_only_via_menu": len(result["adapter_handlers_raised_only_via_menu"]),
        "events_by_classification": dict(sorted(by_class.items())),
        "commented_out_callnats_in_adapter": len(result["adapter"]["commented_out_callnats"]),
        "services_with_end_transaction": sorted(
            n for n, s in result["services"].items() if s["has_end_transaction"]),
        "services_with_backout_transaction": sorted(
            n for n, s in result["services"].items() if s["has_backout_transaction"]),
        "emitted_codes_by_service": {
            n: sorted({r["code"] for r in s["emitted"]}) for n, s in result["services"].items()},
        "commented_out_emits_by_service": {
            n: len(s["commented_out_emits"]) for n, s in result["services"].items()},
    }


# --------------------------------------------------------------------------
# Markdown rendering
# --------------------------------------------------------------------------

def _table(headers, rows):
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join("---" for _ in headers) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(c) for c in r) + " |")
    return out


def render_markdown(result):
    ct = result["control_totals"]
    ad_ = result["adapter"]
    L = [
        "# Process-flow evidence (generated)",
        "",
        "Generated by `generate_process_evidence.py` from the Natural sources and the",
        "NJX page definition; do not edit by hand. Re-run the generator (or",
        "`--check`) after any source change. All findings are static-analysis",
        "candidates over executable lines; comment lines are excluded unless a",
        "table says otherwise.",
        "",
        f"Scope: {result['scope']}",
        "",
        "## Control totals",
        "",
    ]
    L += _table(["Measure", "Value"], [
        ("Distinct UI events declared in `rdcruisx.xml`", ct["ui_events_declared_distinct"]),
        ("`method=` declarations in `rdcruisx.xml` (incl. repeats)", ct["ui_method_declarations_total"]),
        ("Event branches in the adapter `DECIDE ON FIRST *PAGE-EVENT`", ct["adapter_event_branches"]),
        ("Declared in UI but not handled in adapter", ct["ui_events_declared_not_handled"]),
        ("Handled in adapter, raised only through the `DLMENU` menu control", ct["adapter_handlers_raised_only_via_menu"]),
        ("Handled in adapter but neither declared in UI nor in the menu", ct["adapter_handlers_not_declared_in_ui"]),
        ("Commented-out `CALLNAT` lines in adapter", ct["commented_out_callnats_in_adapter"]),
        ("Services issuing `END TRANSACTION`", ", ".join(f"`{s}`" for s in ct["services_with_end_transaction"])),
        ("Services issuing `BACKOUT TRANSACTION`", ", ".join(f"`{s}`" for s in ct["services_with_backout_transaction"]) or "none"),
    ])
    L += ["", "### Event branches by classification", ""]
    L += _table(["Classification", "Branches"],
                sorted(ct["events_by_classification"].items()))

    L += ["", f"## UI events → adapter branches → services (`{ad_['path']}`, {ad_['lines']} lines)", "",
          "`Declared` is the number of `method=` attributes for the event in",
          "`rdcruisx.xml`; `Menu` is the adapter line that registers the event in",
          "the `DLMENU` dynamic menu control (events with 0 declarations and no",
          "menu line exist in the adapter but the page never raises them).",
          "`Services` are the CRUISE16 subprograms reached through the branch's",
          "`PERFORM`ed subroutines.", ""]
    L += _table(["Event", "Adapter line", "Declared", "Menu", "PERFORMs", "Services", "Classification"], [
        (f"`{e['event']}`", e["adapter_line"], e["declared_in_ui"],
         e["raised_via_menu_line"] or "—",
         ", ".join(f"`{p}`" for p in e["performs"]) or "—",
         ", ".join(f"`{s}`" for s in e["services"]) or "—",
         e["classification"]) for e in result["ui_events"]
    ])
    L += ["", "### Declared in UI but not handled in adapter", ""]
    L += [f"- `{e}`" for e in result["ui_events_declared_not_handled"]] or ["- none"]
    L += ["", "### Handled in adapter, raised only through the menu control", ""]
    L += [f"- `{e}` (`{ad_['path']}:{result['menu_methods'][e]}`)"
          for e in result["adapter_handlers_raised_only_via_menu"]] or ["- none"]
    L += ["", "### Handled in adapter but neither declared in UI nor in the menu (unreachable from the page in analyzed scope)", ""]
    L += [f"- `{e}`" for e in result["adapter_handlers_not_declared_in_ui"]] or ["- none"]

    L += ["", "### Adapter subroutines that call CRUISE16 services", ""]
    L += _table(["Subroutine", "Lines", "CALLNAT target", "CALLNAT line"], [
        (f"`{name}`", f"{s['start']}-{s['end']}", f"`{c['target']}`", c["line"])
        for name, s in result["adapter"]["subroutines"].items()
        for c in s["callnats"]
    ])
    L += ["", "### Commented-out CALLNAT lines in the adapter (presentation-only, inactive)", ""]
    L += _table(["Line", "Target", "Text"], [
        (r["line"], f"`{r['target']}`", "`" + r["text"].replace("|", "\\|") + "`")
        for r in ad_["commented_out_callnats"]
    ])

    L += ["", "## Processes → services → events → message codes", ""]
    L += _table(["Process", "Services", "Triggering events", "Emitted codes"], [
        (f"{p['id']} {p['title']}", ", ".join(f"`{s}`" for s in p["services"]),
         ", ".join(f"`{e}`" for e in p["events"]) or "—",
         ", ".join(str(c) for c in p["message_codes"]))
        for p in result["processes"]
    ])

    L += ["", "## Message codes emitted per service (executable lines)", "",
          "`Success remap` = `CAMSG-N` resets the code to 0, so the adapter's",
          "`P-RSPCODE = '0'` test treats it as success.", ""]
    rows = []
    for name in SERVICES:
        s = result["services"][name]
        for r in s["emitted"]:
            rows.append((f"`{name}`", f"`{s['path']}:{r['line']}`", r["code"],
                         r["text_en"] or "(not in catalog)",
                         "yes" if r["success_remap"] else "no"))
    L += _table(["Service", "Source line", "Code", "Text (EN, CAMSG-N)", "Success remap"], rows)

    L += ["", "### Commented-out message emits per service (inactive validation candidates)", ""]
    rows = []
    for name in SERVICES:
        s = result["services"][name]
        for r in s["commented_out_emits"]:
            rows.append((f"`{name}`", f"`{s['path']}:{r['line']}`", r["code"],
                         r["text_en"] or "(not in catalog)"))
    L += _table(["Service", "Source line", "Code", "Text (EN, CAMSG-N)"], rows)

    L += ["", "## ADABAS access and transaction-boundary statements per service", ""]
    rows = []
    for name in SERVICES:
        s = result["services"][name]
        for b in s["boundaries"]:
            rows.append((f"`{name}`", f"`{s['path']}:{b['line']}`", b["statement"],
                         "`" + b["text"].replace("|", "\\|") + "`"))
    L += _table(["Service", "Source line", "Statement", "Text"], rows)

    L += ["", "### Service summary", ""]
    L += _table(["Service", "Lines", "`END TRANSACTION`", "`BACKOUT TRANSACTION`", "`#STUDENT` gate (9999)", "Emitted codes"], [
        (f"`{name}`", s["lines"], "yes" if s["has_end_transaction"] else "no",
         "yes" if s["has_backout_transaction"] else "no",
         "yes" if s["student_gate"] else "no",
         ", ".join(str(c) for c in ct["emitted_codes_by_service"][name]))
        for name, s in result["services"].items()
    ])
    L += ["", f"`CAMSG-N` (`{result['camsg']['path']}`): {result['camsg']['catalog_size']} cataloged codes; "
          f"codes remapped to 0 on success: {', '.join(str(c) for c in result['camsg']['success_remap_codes'])}.", ""]
    return "\n".join(L) + "\n"


# --------------------------------------------------------------------------
# Consistency checks between the hand-written documents and the generated facts
# --------------------------------------------------------------------------

BPMN_NS = "http://www.omg.org/spec/BPMN/20100524/MODEL"
_CODE_IN_TEXT_RE = re.compile(r"\b(9[89]\d\d)\b")
_MERMAID_RE = re.compile(r"```mermaid\n(.*?)```", re.S)


def _check_process_flows(result, problems):
    path = HERE / "process-flows.md"
    text = path.read_text(encoding="utf-8")
    ct = result["control_totals"]
    catalog = set(result["camsg_catalog_codes"])
    for phrase in (f"{ct['ui_events_declared_distinct']} distinct UI events",
                   f"({ct['ui_method_declarations_total']} `method=`",
                   f"has {ct['adapter_event_branches']} branches"):
        if phrase not in text:
            problems.append(f"process-flows.md: expected phrase {phrase!r} (from control totals)")
    # event-inventory table: Branches column must equal the generator's per-class counts
    section = text.split("## Event inventory", 1)[1].split("\n## ", 1)[0]
    rows = [l for l in section.splitlines() if l.startswith("| ") and "|---" not in l]
    counts = []
    for row in rows[1:]:
        cells = [c.strip() for c in row.strip("|").split("|")]
        if len(cells) >= 2 and cells[1].isdigit():
            counts.append(int(cells[1]))
    expected = sorted(ct["events_by_classification"].values())
    if sorted(counts) != expected:
        problems.append(f"process-flows.md event inventory Branches column {sorted(counts)} != generator {expected}")
    # each Mermaid diagram must draw every code its services emit, and no unknown code
    blocks = _MERMAID_RE.findall(text)
    if len(blocks) != len(result["processes"]):
        problems.append(f"process-flows.md has {len(blocks)} mermaid blocks, expected {len(result['processes'])}")
        return
    for proc, block in zip(result["processes"], blocks):
        drawn = {int(c) for c in _CODE_IN_TEXT_RE.findall(block)}
        emitted = set(proc["message_codes"])
        missing = emitted - drawn
        unknown = drawn - catalog
        if missing:
            problems.append(f"process-flows.md {proc['id']}: emitted codes not drawn: {sorted(missing)}")
        if unknown:
            problems.append(f"process-flows.md {proc['id']}: codes not in CAMSG-N catalog: {sorted(unknown)}")


def _check_bpmn(result, problems):
    path = HERE / "bpmn" / "booking-process.bpmn"
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:  # not well-formed
        problems.append(f"booking-process.bpmn: not well-formed XML: {exc}")
        return
    ns = {"bpmn": BPMN_NS}
    ids = {el.get("id") for el in root.iter() if el.get("id")}
    if len(ids) != len([el for el in root.iter() if el.get("id")]):
        problems.append("booking-process.bpmn: duplicate ids")
    # every reference attribute must resolve to a declared id
    for el in root.iter():
        for attr in ("sourceRef", "targetRef", "attachedToRef", "errorRef", "messageRef",
                     "dataStoreRef", "processRef", "default"):
            ref = el.get(attr)
            if ref and ref not in ids:
                problems.append(f"booking-process.bpmn: {el.tag.split('}')[1]}#{el.get('id')} {attr}={ref} unresolved")
    for tag in ("flowNodeRef", "sourceRef", "targetRef", "incoming", "outgoing"):
        for el in root.iter(f"{{{BPMN_NS}}}{tag}"):
            if (el.text or "").strip() not in ids:
                problems.append(f"booking-process.bpmn: <{tag}>{el.text}</{tag}> unresolved")
    # incoming/outgoing lists must mirror the sequence flows in both directions
    flows = {f.get("id"): (f.get("sourceRef"), f.get("targetRef"))
             for f in root.iter(f"{{{BPMN_NS}}}sequenceFlow")}
    declared_out, declared_in = {}, {}
    for el in root.iter():
        nid = el.get("id")
        for o in el.findall("bpmn:outgoing", ns):
            declared_out[o.text.strip()] = nid
        for i in el.findall("bpmn:incoming", ns):
            declared_in[i.text.strip()] = nid
    for fid, (src, tgt) in flows.items():
        if declared_out.get(fid) != src:
            problems.append(f"booking-process.bpmn: {fid} sourceRef {src} lacks matching <outgoing>")
        if declared_in.get(fid) != tgt:
            problems.append(f"booking-process.bpmn: {fid} targetRef {tgt} lacks matching <incoming>")
    for fid in set(declared_out) | set(declared_in):
        if fid not in flows:
            problems.append(f"booking-process.bpmn: <incoming>/<outgoing> {fid} has no sequenceFlow")
    # error codes modelled == codes CONEW-N emits, minus the codes CAMSG-N remaps to success
    modelled = {int(e.get("errorCode")) for e in root.iter(f"{{{BPMN_NS}}}error")
                if (e.get("errorCode") or "").isdigit()}
    conew = set(result["control_totals"]["emitted_codes_by_service"]["CONEW-N"])
    expected = conew - set(result["camsg"]["success_remap_codes"])
    if modelled != expected:
        problems.append(f"booking-process.bpmn error codes {sorted(modelled)} != CONEW-N non-success emits {sorted(expected)}")
    # transaction semantics that process-flows.md promises
    if not root.findall(".//bpmn:transaction", ns):
        problems.append("booking-process.bpmn: no <transaction> element")
    if not root.findall(".//bpmn:compensateEventDefinition", ns):
        problems.append("booking-process.bpmn: no compensation event")
    if not any(t.get("isForCompensation") == "true" for t in root.iter(f"{{{BPMN_NS}}}task")):
        problems.append("booking-process.bpmn: no compensation handler task")
    # element counts quoted in import-notes.md must match the file
    tx = root.find(".//bpmn:transaction", ns)
    inside = set(tx.iter()) if tx is not None else set()

    def count(tag, inside_tx=None):
        els = list(root.iter(f"{{{BPMN_NS}}}{tag}"))
        if inside_tx is None:
            return len(els)
        return len([e for e in els if (e in inside) == inside_tx])

    notes = (HERE / "bpmn" / "import-notes.md").read_text(encoding="utf-8")
    expected_rows = {
        "`bpmn:lane`": count("lane"),
        "`bpmn:exclusiveGateway` outside the transaction": count("exclusiveGateway", False),
        "`bpmn:exclusiveGateway` inside the transaction": count("exclusiveGateway", True),
        "`bpmn:transaction`": count("transaction"),
        "Cancel end-events inside the transaction": len(
            [e for e in inside if e.tag == f"{{{BPMN_NS}}}endEvent"
             and e.find("bpmn:cancelEventDefinition", ns) is not None]),
        "Compensation handler (`isForCompensation=\"true\"`)": len(
            [t for t in root.iter(f"{{{BPMN_NS}}}task") if t.get("isForCompensation") == "true"]),
        "Boundary events on the transaction": len(
            [b for b in root.iter(f"{{{BPMN_NS}}}boundaryEvent")
             if tx is not None and b.get("attachedToRef") == tx.get("id")]),
        "`bpmn:error`": count("error"),
        "Plain end-events": len(
            [e for e in root.iter(f"{{{BPMN_NS}}}endEvent") if e not in inside
             and e.find("bpmn:errorEventDefinition", ns) is None]),
        "`bpmn:dataStoreReference`": count("dataStoreReference"),
    }
    for label, n in expected_rows.items():
        if f"| {label} | {n} |" not in notes:
            problems.append(f"import-notes.md: expected row '| {label} | {n} |'")
    total_gateways = count("exclusiveGateway")
    if f"gateway count {total_gateways};" not in notes:
        problems.append(f"import-notes.md: expected 'gateway count {total_gateways};'")


def _check_mapping(result, problems):
    path = HERE / "process-to-hcm-mapping.md"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    catalog = set(result["camsg_catalog_codes"])
    emitted = {r["code"] for s in result["services"].values() for r in s["emitted"]}
    mentioned = {int(c) for c in _CODE_IN_TEXT_RE.findall(text)}
    missing = emitted - mentioned
    unknown = mentioned - catalog
    if missing:
        problems.append(f"process-to-hcm-mapping.md: emitted codes without a mapping row: {sorted(missing)}")
    if unknown:
        problems.append(f"process-to-hcm-mapping.md: codes not in CAMSG-N catalog: {sorted(unknown)}")
    # message-code table: every `SERVICE.NSN:line` in the 'Emitted by' cell must be a real
    # emit of that code, and every real emit must be cited in the row of its code
    section = text.split("## Message codes to HCM validation rules", 1)[1].split("\n## ", 1)[0]
    cited = set()
    for row in section.splitlines():
        cells = [c.strip() for c in row.strip("|").split("|")]
        if len(cells) < 3 or not cells[0].isdigit():
            continue
        code = int(cells[0])
        service = None
        for m in re.finditer(r"`(?:([A-Z]+-N)\.NSN)?:(\d+)`", cells[2]):
            service = m.group(1) or service
            cited.add((service, int(m.group(2)), code))
    actual = {(name, r["line"], r["code"]) for name, s in result["services"].items()
              for r in s["emitted"]}
    for c in sorted(cited - actual, key=str):
        problems.append(f"process-to-hcm-mapping.md: cited emit {c} not found in source")
    for c in sorted(actual - cited, key=str):
        problems.append(f"process-to-hcm-mapping.md: source emit {c} not cited in the message-code table")


_EVENT_IN_TEXT_RE = re.compile(r"`((?:lines\.)?on[A-Za-z][A-Za-z0-9]*)`")
# `onFav1button`…`onFav4button` / `onShowdetails1`…`4` name every event in the range
_EVENT_RANGE_RE = re.compile(
    r"`(on[A-Za-z]+?)(\d)([A-Za-z]*)`…`(?:\1)?(\d)(?:\3)?`")
HAND_AUTHORED = ("README.md", "process-flows.md", "process-to-hcm-mapping.md",
                 "bpmn/import-notes.md")


def _check_event_names(result, problems):
    """Every back-ticked `onXxx` event named in the hand-authored documents must be
    an adapter branch; every adapter branch must be named at least once."""
    branches = {e["event"] for e in result["ui_events"]}
    named = {}
    for rel in HAND_AUTHORED:
        text = (HERE / rel).read_text(encoding="utf-8")
        for m in _EVENT_IN_TEXT_RE.finditer(text):
            named.setdefault(m.group(1), set()).add(rel)
        for m in _EVENT_RANGE_RE.finditer(text):
            stem, lo, tail, hi = m.groups()
            for n in range(int(lo), int(hi) + 1):
                named.setdefault(f"{stem}{n}{tail}", set()).add(rel)
    for ev in sorted(set(named) - branches):
        problems.append(f"event `{ev}` named in {sorted(named[ev])} is not a "
                        f"DECIDE branch of the adapter")
    for ev in sorted(branches - set(named)):
        if ev.startswith("on") or ev.startswith("lines."):
            problems.append(f"adapter branch `{ev}` is not named in any hand-authored document")


def _check_readme(result, problems):
    text = (HERE / "README.md").read_text(encoding="utf-8")
    ct = result["control_totals"]
    phrase = (f"has {ct['adapter_event_branches']} branches for "
              f"{ct['ui_events_declared_distinct']} distinct UI events")
    if phrase not in text:
        problems.append(f"README.md: expected phrase {phrase!r} (from control totals)")
    words = {6: "Six"}
    n = ct["commented_out_callnats_in_adapter"]
    phrase = f"{words.get(n, n)} `CALLNAT 'IMG-LOAD'` lines"
    if phrase not in text:
        problems.append(f"README.md: expected phrase {phrase!r} (from control totals)")


def consistency_problems(result):
    problems = []
    _check_process_flows(result, problems)
    _check_bpmn(result, problems)
    _check_mapping(result, problems)
    _check_event_names(result, problems)
    _check_readme(result, problems)
    return problems


def main(argv):
    result = analyze()
    md = render_markdown(result)
    js = json.dumps(result, indent=2) + "\n"
    if "--check" in argv:
        ok = True
        for fname, content in (("process-evidence.md", md), ("process-evidence.json", js)):
            path = OUT_DIR / fname
            if not path.exists() or path.read_text(encoding="utf-8") != content:
                print(f"DRIFT: {path.relative_to(REPO_ROOT)} differs from generator output")
                ok = False
        for p in consistency_problems(result):
            print(f"INCONSISTENT: {p}")
            ok = False
        if ok:
            print("process evidence up to date; documents consistent with source")
        return 0 if ok else 1
    if "--stdout" in argv:
        print(js)
        return 0
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "process-evidence.json").write_text(js, encoding="utf-8")
    (OUT_DIR / "process-evidence.md").write_text(md, encoding="utf-8")
    print(json.dumps(result["control_totals"], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
