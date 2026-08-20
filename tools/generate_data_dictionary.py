#!/usr/bin/env python3
"""Generate docs/data-dictionary.md from the ADABAS DDM (.NSD) files.

The dictionary is derived programmatically from the DDM sources so it cannot
drift from them; tests/test_source_conformance.py asserts that the committed
document matches this generator's output byte-for-byte.

Usage:
    python3 tools/generate_data_dictionary.py            # rewrite the doc
    python3 tools/generate_data_dictionary.py --stdout   # print to stdout
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.harness.source_parser import all_ddms  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT = REPO_ROOT / "docs" / "data-dictionary.md"

TYPE_LABEL = {"G": "group", "M": "multiple-value", "P": "periodic group"}
FMT_LABEL = {
    "A": "Alphanumeric",
    "B": "Binary",
    "N": "Numeric (unpacked)",
    "P": "Packed numeric",
    "I": "Integer",
    "U": "Unicode",
    "F": "Floating point",
    "L": "Logical",
    "D": "Date",
    "T": "Time",
}
FILE_ORDER = ["NCCRUISE", "NCCONTRACT", "NCCUSTOMER", "NCYACHT"]
FILE_ROLE = {
    "NCCRUISE": "Cruise catalogue: one record per scheduled cruise. "
                "`CRUISE-STATUS` (A1) holds the number of free places and is "
                "decremented by `CONEW-N` on every booking.",
    "NCCONTRACT": "Booking contracts: one record per booking created by "
                  "`CONEW-N`. `CONTRACT-ID` is generated as MAX+1 under a "
                  "record hold.",
    "NCCUSTOMER": "Customer master data, maintained by `CUNEW-N`/`CUMOD-N` "
                  "and read by `CUGET-N` and `CONEW-N`.",
    "NCYACHT": "Yacht master data, joined by `CRLIST-N`/`CRGET-N` via "
               "`ID-YACHT` to display yacht details.",
}


def render():
    ddms = all_ddms()
    lines = [
        "# Data Dictionary",
        "",
        "Derived automatically from the ADABAS DDM sources in",
        "`SunnyIslands/Natural-Libraries/CRUISE16/DDMs/` by",
        "`tools/generate_data_dictionary.py`. **Do not edit by hand** —",
        "regenerate with `python3 tools/generate_data_dictionary.py`.",
        "",
        "Column legend: **T** = field class (blank scalar, G group,",
        "M multiple-value, P periodic group), **Lv** = level, **F** = ADABAS",
        "format, **Len** = length, **D** = descriptor (D = descriptor /",
        "search key, S = sub-/superdescriptor).",
        "",
    ]
    for name in FILE_ORDER:
        ddm = ddms[name]
        lines += [
            f"## {name}",
            "",
            f"Source file: `{Path(ddm_path(name)).name}` — DB {ddm.db}, "
            f"file {ddm.fnr}. {FILE_ROLE[name]}",
            "",
            "| T | Lv | Field | F | Len | D | Remark |",
            "|---|----|-------|---|-----|---|--------|",
        ]
        for f in ddm.fields:
            fmt = FMT_LABEL.get(f.fmt, f.fmt)
            t = f.field_type if f.field_type.strip() else ""
            lines.append(
                f"| {t} | {f.level} | `{f.name}` | {fmt} | {f.length} "
                f"| {f.descriptor} | {f.remark} |"
            )
        descriptors = [f.name for f in ddm.fields if f.descriptor == "D"]
        lines += [
            "",
            f"Descriptors (search keys): {', '.join(f'`{d}`' for d in descriptors)}",
            "",
        ]
    return "\n".join(lines)


def ddm_path(logical_name):
    from tests.harness.source_parser import DDM_DIR, parse_ddm
    for p in sorted(DDM_DIR.glob("*.NSD")):
        if parse_ddm(p).file_name == logical_name:
            return p
    raise FileNotFoundError(logical_name)


def main():
    content = render() + "\n"
    if "--stdout" in sys.argv:
        sys.stdout.write(content)
    else:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(content, encoding="utf-8")
        print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
