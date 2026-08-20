"""Parsers for Natural sources (.NSN) and ADABAS DDMs (.NSD).

Used by the source-conformance tests to assert business rules against the
real Natural sources, and by ``tools/generate_data_dictionary.py`` to derive
the data dictionary programmatically instead of hand-copying it.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CRUISE16 = REPO_ROOT / "SunnyIslands" / "Natural-Libraries" / "CRUISE16"
RDCRUISE = REPO_ROOT / "SunnyIslands" / "Natural-Libraries" / "RDCRUISE"
DDM_DIR = CRUISE16 / "DDMs"


def read_source(path):
    return Path(path).read_text(encoding="utf-8", errors="replace")


def strip_comments(source):
    """Return only executable lines (drop '*'-comment and '/*'-only lines)."""
    lines = []
    for line in source.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("*") or stripped.startswith("/*"):
            continue
        # drop trailing inline comments
        line = re.split(r"/\*", line)[0].rstrip()
        if line.strip():
            lines.append(line)
    return lines


def message_codes(source):
    """All 4-digit message codes moved to MSG-GROUP-PARA.MSG-NR in code."""
    codes = set()
    for line in strip_comments(source):
        m = re.search(r"MOVE\s+(\d{4})\s+TO\s+MSG-GROUP-PARA\.MSG-NR", line)
        if m:
            codes.add(int(m.group(1)))
    return codes


def camsg_codes(source):
    """All message codes CAMSG-N can translate (VALUE nnnn branches)."""
    codes = set()
    for line in strip_comments(source):
        for m in re.finditer(r"VALUE\s+(\d{4})\b", line):
            codes.add(int(m.group(1)))
    return codes


# --------------------------------------------------------------------------
# DDM parsing
# --------------------------------------------------------------------------

class DdmField:
    def __init__(self, field_type, level, shortname, name, fmt, length,
                 suppression, descriptor, remark):
        self.field_type = field_type      # ' ' scalar, G group, M multiple, P periodic
        self.level = level
        self.shortname = shortname
        self.name = name
        self.fmt = fmt
        self.length = length
        self.suppression = suppression
        self.descriptor = descriptor      # D descriptor, S sub/super, blank
        self.remark = remark

    def __repr__(self):
        return f"DdmField({self.name!r}, level={self.level}, fmt={self.fmt!r})"


class Ddm:
    def __init__(self, file_name, db, fnr, fields):
        self.file_name = file_name
        self.db = db
        self.fnr = fnr
        self.fields = fields


_FIELD_RE = re.compile(
    r"^(?P<t>[GMP ])\s(?P<lvl>\d)\s(?P<db>\S{2})\s(?P<name>[A-Z0-9@#$&\-]+)"
)
_HEADER_RE = re.compile(
    r"^DB:\s*(?P<db>\d+)\s+FILE:\s*(?P<fnr>\d+)\s+-\s+(?P<name>\S+)"
)


def parse_ddm(path):
    """Parse a .NSD DDM listing into a Ddm object.

    NSD listings are fixed-width: T(col 0), L(2), DB shortname(4-5),
    name(7-39), F(41), Leng(43-47), S(49), D(51), remark(53+).
    """
    text = read_source(path)
    db = fnr = None
    file_name = Path(path).stem
    fields = []
    remark_target = None
    for raw in text.splitlines():
        line = raw.rstrip("\n")
        h = _HEADER_RE.match(line)
        if h:
            db, fnr = int(h.group("db")), int(h.group("fnr"))
            file_name = h.group("name")
            continue
        if line.startswith("*"):
            comment = line.lstrip("*").strip()
            if remark_target is not None and comment and not comment.startswith(
                (">", "<", ":")
            ):
                remark_target.remark = (
                    (remark_target.remark + " " + comment).strip()
                )
            continue
        if line.startswith(("TYPE:", "T L", "- -", "***")) or not line.strip():
            continue
        if not _FIELD_RE.match(line):
            continue  # continuation lines such as sub-descriptor options
        field = DdmField(
            field_type=line[0],
            level=int(line[2]),
            shortname=line[4:6],
            name=line[7:40].strip(),
            fmt=line[41:42].strip(),
            length=line[43:48].strip(),
            suppression=line[49:50].strip(),
            descriptor=line[51:52].strip(),
            remark=line[53:].strip(),
        )
        fields.append(field)
        remark_target = field
    return Ddm(file_name, db, fnr, fields)


def all_ddms():
    """Parse the four CRUISE16 DDMs, keyed by logical file name."""
    return {
        ddm.file_name: ddm
        for ddm in (parse_ddm(p) for p in sorted(DDM_DIR.glob("*.NSD")))
    }
