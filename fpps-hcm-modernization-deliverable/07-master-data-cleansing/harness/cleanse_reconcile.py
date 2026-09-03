#!/usr/bin/env python3
"""Profiling, cleansing and reconciliation harness for synthetic ADABAS master data.

Scope statement
---------------
This script is a *validation and cleansing harness*. It exists to prove, on
synthetic data, that a rule catalogue keyed to the DDM dictionary can be
executed, that the cleansed output reconciles to the input, and that the
result cannot drift from what is checked in. It is not, and must never be
read as, a rewrite target for any Natural program: the business behaviour it
checks is implemented in Oracle HCM (or an alternate HCM), not in Python.

What it does
------------
1. ``build_dirty_db``  - starts from ``tests/harness/fixtures.make_db()`` and
   adds deterministic synthetic rows, then injects known defects (orphans,
   invalid domains, bad formats, duplicates, missing audit fields, name-field
   lineage conflicts) on top of ``tests/harness/adabas_sim.AdabasSim``.
2. ``profile``         - per-file / per-field fill rates, distinct counts,
   min/max and multiple-value / periodic-group occurrence distributions.
3. ``apply_rules``     - evaluates the rule catalogue (``RULES``) against every
   record; each rule decides ``pass`` / ``correct`` / ``flag`` / ``reject``.
4. ``reconcile``       - in / loaded / held / rejected per file and per rule,
   control totals (record counts, contract price totals, bookings per cruise),
   a content hash of the loadable set, and the exception list.
5. Writes ``sample-output/`` (Markdown report, JSON report, exceptions CSV,
   profile). ``--check`` regenerates in memory and exits non-zero when the
   committed output differs or when the rule IDs in ``../cleansing-rules.md``
   do not match ``RULES`` exactly.

Run from the repository root::

    python3 fpps-hcm-modernization-deliverable/07-master-data-cleansing/harness/cleanse_reconcile.py
    python3 fpps-hcm-modernization-deliverable/07-master-data-cleansing/harness/cleanse_reconcile.py --check
"""

import argparse
import copy
import csv
import datetime as dt
import hashlib
import io
import json
import random
import re
import sys
from collections import Counter, OrderedDict, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
sys.path.insert(0, str(REPO_ROOT))

from tests.harness import fixtures  # noqa: E402
from tests.harness.adabas_sim import AdabasSim  # noqa: E402

OUT_DIR = HERE / "sample-output"
RULES_DOC = HERE.parent / "cleansing-rules.md"
SEED = 20260903
AS_OF = dt.date(2026, 9, 3)  # fixed "today" so the output is reproducible

FILES = ("NCYACHT", "NCCRUISE", "NCCUSTOMER", "NCCONTRACT")
BUSINESS_KEY = {
    "NCYACHT": "YACHT-ID",
    "NCCRUISE": "CRUISE-ID",
    "NCCUSTOMER": "PERSON-ID",
    "NCCONTRACT": "CONTRACT-ID",
}
MU_FIELDS = {"NCCUSTOMER": ("EMAIL",)}
PE_GROUPS = {"NCCUSTOMER": ("PHONE",)}

# Outcome severity order: a record's final disposition is its worst outcome.
PASS, CORRECT, FLAG, REJECT = "pass", "correct", "flag", "reject"
SEVERITY = {PASS: 0, CORRECT: 1, FLAG: 2, REJECT: 3}
DISPOSITION = {PASS: "loaded", CORRECT: "loaded", FLAG: "held", REJECT: "rejected"}


# --------------------------------------------------------------------------
# Rule catalogue
# --------------------------------------------------------------------------
class Rule:
    """One cleansing rule keyed to dictionary fields.

    ``fields`` is a tuple of ``(file, field)`` pairs the rule is keyed to; the
    dictionary generator in 03 reads this to populate its cleansing-flag
    column, so the two directories cannot disagree about which field a rule
    covers. ``evidence`` lists repo-relative ``path:start-end`` citations that
    were opened while authoring the rule.
    """

    def __init__(self, rule_id, name, file, fields, category, action,
                 payroll_analog, hcm_target, evidence, check):
        self.id = rule_id
        self.name = name
        self.file = file
        self.fields = tuple(fields)
        self.category = category
        self.action = action
        self.payroll_analog = payroll_analog
        self.hcm_target = hcm_target
        self.evidence = tuple(evidence)
        self.check = check

    def as_dict(self):
        return OrderedDict([
            ("id", self.id),
            ("name", self.name),
            ("file", self.file),
            ("fields", [f"{f}.{n}" for f, n in self.fields]),
            ("category", self.category),
            ("action", self.action),
            ("payroll_analog", self.payroll_analog),
            ("hcm_target", self.hcm_target),
            ("evidence", list(self.evidence)),
        ])


def _blank(v):
    return v is None or (isinstance(v, str) and v.strip() == "") or v == 0


def _valid_yyyymmdd(n):
    try:
        s = f"{int(n):08d}"
        return dt.date(int(s[:4]), int(s[4:6]), int(s[6:]))
    except (TypeError, ValueError):
        return None


def _emails(rec):
    v = rec.get("EMAIL")
    if v is None:
        return []
    if isinstance(v, str):
        return [v]
    return list(v)


def _phones(rec):
    v = rec.get("PHONE")
    return list(v) if isinstance(v, list) else []


# Each check returns (outcome, message, corrected_values_or_None).
def chk_orphan_customer(rec, ctx):
    v = rec.get("ID-CUSTOMER")
    if v in ctx["person_ids"]:
        return PASS, "", None
    return REJECT, f"ID-CUSTOMER {v!r} has no NCCUSTOMER.PERSON-ID", None


def chk_orphan_cruise(rec, ctx):
    v = rec.get("ID-CRUISE")
    if v in ctx["cruise_ids"]:
        return PASS, "", None
    return REJECT, f"ID-CRUISE {v!r} has no NCCRUISE.CRUISE-ID", None


def chk_orphan_yacht(rec, ctx):
    v = rec.get("ID-YACHT")
    if v in ctx["yacht_ids"]:
        return PASS, "", None
    return FLAG, f"ID-YACHT {v!r} has no NCYACHT.YACHT-ID", None


def chk_cruise_status(rec, ctx):
    v = rec.get("CRUISE-STATUS")
    if isinstance(v, str) and len(v) == 1 and v.isdigit():
        return PASS, "", None
    return REJECT, f"CRUISE-STATUS {v!r} outside domain '0'..'9'", None


def chk_sex(rec, ctx):
    v = rec.get("SEX")
    if _blank(v):
        return FLAG, "SEX blank; HCM Sex/Gender attribute needs a steward value", None
    if v in ("M", "F"):
        return PASS, "", None
    return FLAG, f"SEX {v!r} outside DDM-documented domain M/F", None


def chk_email(rec, ctx):
    emails = _emails(rec)
    non_blank = [e.strip() for e in emails if not _blank(e)]
    if not non_blank:
        return FLAG, "no EMAIL occurrence populated (login-by-email path unusable)", None
    corrected = None
    msgs = []
    if _blank(emails[0]):
        msgs.append("EMAIL(1) blank but a later occurrence is populated; promoted")
    deduped = list(OrderedDict.fromkeys(e.lower() for e in non_blank))
    if len(deduped) < len(non_blank):
        msgs.append("duplicate EMAIL occurrences removed")
    bad = [e for e in deduped if "@" not in e or e.startswith("@") or e.endswith("@")]
    if bad:
        return FLAG, f"EMAIL occurrence(s) without a valid address shape: {bad}", None
    if len(deduped) > 1:
        msgs.append(f"{len(deduped)} distinct EMAIL occurrences; only EMAIL(1) is read by code")
        corrected = {"EMAIL": deduped}
        return FLAG, "; ".join(msgs), corrected
    if msgs:
        return CORRECT, "; ".join(msgs), {"EMAIL": deduped}
    return PASS, "", None


def chk_phone(rec, ctx):
    phones = _phones(rec)
    if len(phones) > 2:
        return FLAG, f"{len(phones)} PHONE occurrences; DDM documents 2 (private, company)", None
    for i, p in enumerate(phones, start=1):
        if _blank(p.get("PHONE-NUMBER")) and not _blank(p.get("AREA-CODE")):
            return FLAG, f"PHONE({i}) has AREA-CODE but no PHONE-NUMBER", None
        num = p.get("PHONE-NUMBER")
        if not _blank(num) and not re.fullmatch(r"[0-9 ]{3,15}", str(num)):
            return FLAG, f"PHONE({i}).PHONE-NUMBER {num!r} is not digits/spaces", None
    return PASS, "", None


def chk_zip(rec, ctx):
    v = rec.get("ZIP-CODE")
    if _blank(v):
        if _blank(rec.get("COUNTRY")) and _blank(rec.get("CITY")):
            return FLAG, "address group entirely blank", None
        return FLAG, "ZIP-CODE blank while other address fields are populated", None
    s = str(v)
    if s != s.strip():
        return CORRECT, f"ZIP-CODE {v!r} trimmed", {"ZIP-CODE": s.strip()}
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9 -]{1,9}", s.upper()):
        return FLAG, f"ZIP-CODE {v!r} outside expected alphanumeric shape", None
    return PASS, "", None


def chk_country(rec, ctx):
    v = rec.get("COUNTRY")
    if _blank(v):
        return FLAG, "COUNTRY blank; HCM address needs a country code", None
    s = str(v).strip()
    if re.fullmatch(r"[A-Z]{3}", s):
        return PASS, "", None
    if re.fullmatch(r"[A-Za-z]{3}", s):
        return CORRECT, f"COUNTRY {v!r} normalised to upper case", {"COUNTRY": s.upper()}
    return FLAG, f"COUNTRY {v!r} is not a 3-letter code", None


def chk_birth_date(rec, ctx):
    v = rec.get("BIRTH-DATE")
    if _blank(v):
        return FLAG, "BIRTH-DATE missing", None
    d = _valid_yyyymmdd(v)
    if d is None:
        return REJECT, f"BIRTH-DATE {v!r} is not a valid YYYYMMDD date", None
    if d > ctx["as_of"]:
        return REJECT, f"BIRTH-DATE {v} is in the future", None
    age = (ctx["as_of"] - d).days // 365
    if age > 110:
        return FLAG, f"BIRTH-DATE {v} implies age {age}", None
    return PASS, "", None


def chk_timestamp(rec, ctx):
    if _blank(rec.get("TIMESTAMP")):
        return FLAG, "TIMESTAMP absent; optimistic-lock token missing", None
    return PASS, "", None


def chk_duplicate_person(rec, ctx):
    pid = rec.get("PERSON-ID")
    first_isn = ctx["first_isn_person"].get(pid)
    if _blank(pid):
        return REJECT, "PERSON-ID blank", None
    if ctx["person_count"][pid] == 1:
        return PASS, "", None
    if first_isn == ctx["isn"]:
        return FLAG, f"PERSON-ID {pid} duplicated ({ctx['person_count'][pid]} records); survivor", None
    return REJECT, f"PERSON-ID {pid} duplicated; later occurrence (ISN {ctx['isn']})", None


def chk_name_lineage(rec, ctx):
    old = rec.get("FIRST-NAME-OLD")
    new = rec.get("FIRST-NAME-1")
    if _blank(rec.get("SURNAME")):
        return REJECT, "SURNAME blank; Person LastName is mandatory", None
    if _blank(old) and _blank(new):
        return FLAG, "no first name in FIRST-NAME-OLD or FIRST-NAME-1", None
    if _blank(old):
        return CORRECT, "FIRST-NAME-OLD blank; derived from FIRST-NAME-1 (adapter-written field)", \
            {"FIRST-NAME-OLD": str(new).strip()}
    if not _blank(new) and str(new).strip().lower() != str(old).strip().lower():
        return FLAG, f"FIRST-NAME-OLD {old!r} differs from FIRST-NAME-1 {new!r}", None
    return PASS, "", None


def chk_duplicate_contract(rec, ctx):
    cid = rec.get("CONTRACT-ID")
    if _blank(cid):
        return REJECT, "CONTRACT-ID blank", None
    if ctx["contract_count"][cid] == 1:
        return PASS, "", None
    if ctx["first_isn_contract"].get(cid) == ctx["isn"]:
        return FLAG, f"CONTRACT-ID {cid} duplicated; survivor", None
    return REJECT, f"CONTRACT-ID {cid} duplicated; later occurrence (ISN {ctx['isn']})", None


def chk_booking_date(rec, ctx):
    v = rec.get("DATE-BOOKING")
    if _blank(v):
        return REJECT, "DATE-BOOKING missing", None
    d = _valid_yyyymmdd(v)
    if d is None:
        return REJECT, f"DATE-BOOKING {v!r} is not a valid YYYYMMDD date", None
    if d > ctx["as_of"]:
        return FLAG, f"DATE-BOOKING {v} is after the as-of date", None
    return PASS, "", None


RULES = [
    Rule("CR-01", "Orphaned ID-CUSTOMER", "NCCONTRACT",
         [("NCCONTRACT", "ID-CUSTOMER")], "referential integrity", REJECT,
         "Pay transaction whose employee ID does not exist in the person master",
         "Assignment / Element Entry keyed to a Person source key",
         ["SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:157-162",
          "SunnyIslands/Natural-Libraries/CRUISE16/DDMs/NCCONTRA.NSD:26-27"],
         chk_orphan_customer),
    Rule("CR-02", "Orphaned ID-CRUISE", "NCCONTRACT",
         [("NCCONTRACT", "ID-CRUISE")], "referential integrity", REJECT,
         "Pay transaction referencing a position or pay element that does not exist",
         "Element Entry referencing a Position / Element source key",
         ["SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:79-83",
          "SunnyIslands/Natural-Libraries/CRUISE16/DDMs/NCCONTRA.NSD:28-29"],
         chk_orphan_cruise),
    Rule("CR-03", "Orphaned ID-YACHT", "NCCRUISE",
         [("NCCRUISE", "ID-YACHT")], "referential integrity", FLAG,
         "Position whose organisation / department does not exist",
         "Position.OrganizationId / Department",
         ["SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CRLIST-N.NSN:80-83",
          "SunnyIslands/Natural-Libraries/CRUISE16/DDMs/NCCRUISE.NSD:23-24"],
         chk_orphan_yacht),
    Rule("CR-04", "CRUISE-STATUS domain", "NCCRUISE",
         [("NCCRUISE", "CRUISE-STATUS")], "domain", REJECT,
         "Open-headcount / vacancy counter outside its coded domain",
         "Position headcount (open FTE) or status lookup",
         ["SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:82-92",
          "SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CRLIST-N.NSN:53-57",
          "SunnyIslands/Natural-Libraries/CRUISE16/DDMs/NCCRUISE.NSD:13-14"],
         chk_cruise_status),
    Rule("CR-05", "SEX domain", "NCCUSTOMER",
         [("NCCUSTOMER", "SEX")], "domain", FLAG,
         "Legislative / biographical code outside its lookup",
         "Person Legislative Data: Sex (lookup)",
         ["SunnyIslands/Natural-Libraries/CRUISE16/DDMs/NCCUSTOM.NSD:14-16",
          "SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CUGET-N.NSN:94"],
         chk_sex),
    Rule("CR-06", "EMAIL occurrences", "NCCUSTOMER",
         [("NCCUSTOMER", "EMAIL")], "occurrence / format", CORRECT,
         "Multiple-value contact field where only the first occurrence is used by code",
         "Person Email: one row per occurrence, primary flag on occurrence 1",
         ["SunnyIslands/Natural-Libraries/CRUISE16/DDMs/NCCUSTOM.NSD:24",
          "SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CUNEW-N.NSN:50",
          "SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CUGET-N.NSN:68-77"],
         chk_email),
    Rule("CR-07", "PHONE occurrences", "NCCUSTOMER",
         [("NCCUSTOMER", "PHONE"), ("NCCUSTOMER", "AREA-CODE"),
          ("NCCUSTOMER", "PHONE-NUMBER")], "occurrence / format", FLAG,
         "Periodic group never referenced by executable code; occurrence semantics come from the DDM remark only",
         "Person Phone: PhoneType from occurrence position (1 = home, 2 = work)",
         ["SunnyIslands/Natural-Libraries/CRUISE16/DDMs/NCCUSTOM.NSD:29-33"],
         chk_phone),
    Rule("CR-08", "ZIP-CODE format", "NCCUSTOMER",
         [("NCCUSTOMER", "ZIP-CODE")], "format", CORRECT,
         "Postal code that fails the target country's address validation",
         "Person Address: PostalCode",
         ["SunnyIslands/Natural-Libraries/CRUISE16/DDMs/NCCUSTOM.NSD:27",
          "SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CUNEW-N.NSN:52"],
         chk_zip),
    Rule("CR-09", "COUNTRY format", "NCCUSTOMER",
         [("NCCUSTOMER", "COUNTRY")], "format", CORRECT,
         "Country code that fails the target lookup (3-letter code, upper case)",
         "Person Address: Country",
         ["SunnyIslands/Natural-Libraries/CRUISE16/DDMs/NCCUSTOM.NSD:26",
          "SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CUGET-N.NSN:99"],
         chk_country),
    Rule("CR-10", "BIRTH-DATE validity", "NCCUSTOMER",
         [("NCCUSTOMER", "BIRTH-DATE")], "validity", REJECT,
         "Date of birth that is not a calendar date, is in the future, or implies an implausible age",
         "Person: DateOfBirth",
         ["SunnyIslands/Natural-Libraries/CRUISE16/DDMs/NCCUSTOM.NSD:13",
          "SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CUMOD-N.NSN:59-61",
          "SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CUGET-N.NSN:93"],
         chk_birth_date),
    Rule("CR-11", "TIMESTAMP presence", "NCCUSTOMER",
         [("NCCUSTOMER", "TIMESTAMP")], "presence", FLAG,
         "Missing last-update audit token; the source's optimistic-lock check cannot run",
         "Source-side audit attribute; not loaded, but drives the extract cut-off reconciliation",
         ["SunnyIslands/Natural-Libraries/CRUISE16/DDMs/NCCUSTOM.NSD:34",
          "SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CUMOD-N.NSN:50-67",
          "SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CUNEW-N.NSN:55"],
         chk_timestamp),
    Rule("CR-12", "Duplicate PERSON-ID", "NCCUSTOMER",
         [("NCCUSTOMER", "PERSON-ID")], "uniqueness", REJECT,
         "Two person-master records carrying the same employee identifier",
         "Worker source key (SourceSystemId) must be unique",
         ["SunnyIslands/Natural-Libraries/CRUISE16/DDMs/NCCUSTOM.NSD:12",
          "SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CUNEW-N.NSN:41-46"],
         chk_duplicate_person),
    Rule("CR-13", "Name-field lineage", "NCCUSTOMER",
         [("NCCUSTOMER", "SURNAME"), ("NCCUSTOMER", "FIRST-NAME-OLD"),
          ("NCCUSTOMER", "FIRST-NAME-1")], "lineage", CORRECT,
         "Two candidate columns for one legal name attribute, populated by different code paths",
         "Person Name: FirstName = FIRST-NAME-OLD, fallback FIRST-NAME-1; LastName = SURNAME",
         ["SunnyIslands/Natural-Libraries/CRUISE16/Local Data Areas/NCDATA-L.NSL:44-45",
          "SunnyIslands/Natural-Libraries/CRUISE16/Local Data Areas/NCDATA-L.NSL:56",
          "SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CUNEW-N.NSN:48-49",
          "SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CUMOD-N.NSN:53-54",
          "SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CUGET-N.NSN:95-96",
          "SunnyIslands/Natural-Libraries/RDCRUISE/Programs/RDCRUISP.NSP:619",
          "SunnyIslands/Natural-Libraries/RDCRUISE/Programs/RDCRUISP.NSP:663"],
         chk_name_lineage),
    Rule("CR-14", "Duplicate CONTRACT-ID", "NCCONTRACT",
         [("NCCONTRACT", "CONTRACT-ID")], "uniqueness", REJECT,
         "Two pay transactions carrying the same transaction identifier",
         "Element Entry source key must be unique",
         ["SunnyIslands/Natural-Libraries/CRUISE16/DDMs/NCCONTRA.NSD:12",
          "SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:96-102"],
         chk_duplicate_contract),
    Rule("CR-15", "DATE-BOOKING validity", "NCCONTRACT",
         [("NCCONTRACT", "DATE-BOOKING")], "validity", REJECT,
         "Transaction effective date that is not a calendar date or lies after the extract cut-off",
         "Element Entry: EffectiveStartDate",
         ["SunnyIslands/Natural-Libraries/CRUISE16/DDMs/NCCONTRA.NSD:18",
          "SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:105-106"],
         chk_booking_date),
]
RULES_BY_FILE = defaultdict(list)
for _r in RULES:
    RULES_BY_FILE[_r.file].append(_r)


# --------------------------------------------------------------------------
# Synthetic dirty dataset
# --------------------------------------------------------------------------
SURNAMES = ["Miller", "Schmidt", "Okafor", "Nguyen", "Garcia", "Kowalski",
            "Haddad", "Petrov", "Larsen", "Tanaka", "Mensah", "Rossi"]
FIRST_NAMES = ["Anna", "Jens", "Chidi", "Linh", "Maria", "Piotr", "Layla",
               "Ivan", "Sofie", "Hiro", "Ama", "Luca"]
HARBORS = ["Agios Nikolaos", "Santorini", "Paros", "Lefkas", "Corfu",
           "Rhodes", "Kos", "Mykonos"]
COUNTRIES = ["DEU", "GRC", "USA", "GBR", "FRA", "ITA"]


def _clean_customer(rng, pid):
    fn = rng.choice(FIRST_NAMES)
    return {
        "PERSON-ID": pid,
        "BIRTH-DATE": int(f"{rng.randint(1950, 2004)}{rng.randint(1, 12):02d}{rng.randint(1, 28):02d}"),
        "SEX": rng.choice(["M", "F"]),
        "SURNAME": rng.choice(SURNAMES),
        "FIRST-NAME-OLD": fn,
        "FIRST-NAME-1": fn,
        "EMAIL": [f"user{pid}@example.test"],
        "STREET-NUMBER": f"Harbour Road {rng.randint(1, 200)}",
        "COUNTRY": rng.choice(COUNTRIES),
        "ZIP-CODE": f"{rng.randint(10000, 99999)}",
        "CITY": rng.choice(HARBORS),
        "PHONE": [{"AREA-CODE": f"0{rng.randint(30, 89)}",
                   "PHONE-NUMBER": f"{rng.randint(100000, 999999)}"}],
        "TIMESTAMP": f"TS{pid:08d}",
    }


def _clean_cruise(rng, cid, yacht_ids):
    start = dt.date(2026, 9, 1) + dt.timedelta(days=7 * rng.randint(0, 40))
    end = start + dt.timedelta(days=7)
    p1 = rng.choice([990.0, 1290.0, 1490.0, 1790.0])
    return {
        "CRUISE-ID": cid,
        "CRUISE-STATUS": str(rng.randint(0, 9)),
        "START-DATE": int(start.strftime("%Y%m%d")),
        "END-DATE": int(end.strftime("%Y%m%d")),
        "START-HARBOR": rng.choice(HARBORS),
        "DESTINATION-HARBOR": rng.choice(HARBORS),
        "ID-YACHT": rng.choice(yacht_ids),
        "PRICE-1W": p1,
        "PRICE-2W": round(p1 * 1.85, 2),
        "PRICE-3W": round(p1 * 2.6, 2),
    }


def _clean_contract(rng, cid, customer_ids, cruises):
    cruise = rng.choice(cruises)
    booked = dt.date(2026, 1, 5) + dt.timedelta(days=rng.randint(0, 200))
    return {
        "CONTRACT-ID": cid,
        "PRICE": cruise["PRICE-1W"],
        "DATE-BOOKING": int(booked.strftime("%Y%m%d")),
        "ID-CUSTOMER": rng.choice(customer_ids),
        "ID-CRUISE": cruise["CRUISE-ID"],
    }


def build_dirty_db(seed=SEED):
    """Baseline fixture + deterministic synthetic bulk + injected defects.

    Returns ``(db, injected, baseline)``. ``injected`` records how many
    records each planted defect touches (a duplicate group counts the survivor
    as well as the extra copies), so the report can show that every planted
    defect was detected and nothing else was. ``baseline`` is the set of ISNs
    per file that came from the fixture untouched; those rows carry only the
    fields the behavioural tests need and surface as presence exceptions.
    """
    rng = random.Random(seed)
    db = fixtures.make_db()
    baseline = {f: frozenset(fl.records) for f, fl in db.files.items()}
    injected = Counter()

    yacht = db.files["NCYACHT"]
    for i in range(3, 13):
        yacht.insert({"YACHT-ID": 4710 + i,
                      "YACHT-NAME": f"Yacht {i:02d}",
                      "YACHT-TYPE": rng.choice(["Ketch", "Sloop", "Catamaran"])})
    yacht_ids = sorted(r["YACHT-ID"] for r in yacht.records.values())

    cruise = db.files["NCCRUISE"]
    for cid in range(2000, 2040):
        cruise.insert(_clean_cruise(rng, cid, yacht_ids))
    # Injected cruise defects
    bad = _clean_cruise(rng, 2900, yacht_ids)
    bad["CRUISE-STATUS"] = "X"
    cruise.insert(bad)
    injected["CR-04 CRUISE-STATUS non-digit"] += 1
    bad = _clean_cruise(rng, 2901, yacht_ids)
    bad["CRUISE-STATUS"] = " "
    cruise.insert(bad)
    injected["CR-04 CRUISE-STATUS blank"] += 1
    bad = _clean_cruise(rng, 2902, yacht_ids)
    bad["ID-YACHT"] = 9999
    cruise.insert(bad)
    injected["CR-03 orphan ID-YACHT"] += 1
    cruises = [r for r in cruise.records.values()
               if isinstance(r["CRUISE-STATUS"], str) and r["CRUISE-STATUS"].isdigit()
               and r["ID-YACHT"] in yacht_ids]

    cust = db.files["NCCUSTOMER"]
    for pid in range(10000003, 10000203):
        cust.insert(_clean_customer(rng, pid))
    customer_ids = sorted(r["PERSON-ID"] for r in cust.records.values())

    def dirty_customer(pid, **overrides):
        rec = _clean_customer(rng, pid)
        rec.update(overrides)
        cust.insert(rec)
        return rec

    # CR-12 duplicate PERSON-ID (two extra copies of one id; survivor + 2 copies touched)
    dirty_customer(10000050)
    dirty_customer(10000050)
    injected["CR-12 duplicate PERSON-ID (survivor + 2 extra copies)"] += 3
    # CR-13 name lineage
    dirty_customer(10000301, **{"FIRST-NAME-OLD": "", "FIRST-NAME-1": "Nadia"})
    injected["CR-13 FIRST-NAME-OLD blank, FIRST-NAME-1 set"] += 1
    dirty_customer(10000302, **{"FIRST-NAME-OLD": "Tom", "FIRST-NAME-1": "Thomas"})
    injected["CR-13 FIRST-NAME-OLD differs from FIRST-NAME-1"] += 1
    dirty_customer(10000303, **{"FIRST-NAME-OLD": "", "FIRST-NAME-1": ""})
    injected["CR-13 no first name"] += 1
    dirty_customer(10000304, SURNAME="")
    injected["CR-13 SURNAME blank"] += 1
    # CR-10 birth date
    dirty_customer(10000311, **{"BIRTH-DATE": 19991340})
    injected["CR-10 BIRTH-DATE invalid month/day"] += 1
    dirty_customer(10000312, **{"BIRTH-DATE": 20301231})
    injected["CR-10 BIRTH-DATE in future"] += 1
    dirty_customer(10000313, **{"BIRTH-DATE": 19000101})
    injected["CR-10 BIRTH-DATE implausible age"] += 1
    dirty_customer(10000314, **{"BIRTH-DATE": 0})
    injected["CR-10 BIRTH-DATE missing"] += 1
    # CR-11 timestamp
    dirty_customer(10000321, TIMESTAMP=None)
    dirty_customer(10000322, TIMESTAMP="")
    injected["CR-11 TIMESTAMP absent"] += 2
    # CR-06 email occurrences
    dirty_customer(10000331, EMAIL=["", "second@example.test"])
    injected["CR-06 EMAIL(1) blank, EMAIL(2) set"] += 1
    dirty_customer(10000332, EMAIL=["dup@example.test", "DUP@example.test"])
    injected["CR-06 duplicate EMAIL occurrences"] += 1
    dirty_customer(10000333, EMAIL=["a@example.test", "b@example.test", "c@example.test"])
    injected["CR-06 >1 distinct EMAIL occurrence"] += 1
    dirty_customer(10000334, EMAIL=["not-an-address"])
    injected["CR-06 EMAIL without address shape"] += 1
    dirty_customer(10000335, EMAIL=[])
    injected["CR-06 no EMAIL occurrence"] += 1
    # CR-07 phone occurrences
    dirty_customer(10000341, PHONE=[{"AREA-CODE": "030", "PHONE-NUMBER": "111111"},
                                    {"AREA-CODE": "040", "PHONE-NUMBER": "222222"},
                                    {"AREA-CODE": "050", "PHONE-NUMBER": "333333"}])
    injected["CR-07 >2 PHONE occurrences"] += 1
    dirty_customer(10000342, PHONE=[{"AREA-CODE": "030", "PHONE-NUMBER": ""}])
    injected["CR-07 AREA-CODE without PHONE-NUMBER"] += 1
    dirty_customer(10000343, PHONE=[{"AREA-CODE": "030", "PHONE-NUMBER": "12-34-AB"}])
    injected["CR-07 PHONE-NUMBER non-numeric"] += 1
    # CR-08 / CR-09 address formats
    dirty_customer(10000351, **{"ZIP-CODE": " 12345 "})
    injected["CR-08 ZIP-CODE untrimmed"] += 1
    dirty_customer(10000352, **{"ZIP-CODE": ""})
    injected["CR-08 ZIP-CODE blank"] += 1
    dirty_customer(10000353, **{"ZIP-CODE": "??/12"})
    injected["CR-08 ZIP-CODE bad shape"] += 1
    dirty_customer(10000354, COUNTRY="deu")
    injected["CR-09 COUNTRY lower case"] += 1
    dirty_customer(10000355, COUNTRY="Germany")
    injected["CR-09 COUNTRY not 3 letters"] += 1
    dirty_customer(10000356, COUNTRY="")
    injected["CR-09 COUNTRY blank"] += 1
    # CR-05 sex domain
    dirty_customer(10000361, SEX="X")
    injected["CR-05 SEX outside M/F"] += 1

    contract = db.files["NCCONTRACT"]
    for cid in range(500101, 500401):
        contract.insert(_clean_contract(rng, cid, customer_ids, cruises))
    # CR-01 / CR-02 orphans
    for i in range(4):
        rec = _clean_contract(rng, 500901 + i, customer_ids, cruises)
        rec["ID-CUSTOMER"] = 99999900 + i
        contract.insert(rec)
    injected["CR-01 orphan ID-CUSTOMER"] += 4
    for i in range(3):
        rec = _clean_contract(rng, 500911 + i, customer_ids, cruises)
        rec["ID-CRUISE"] = 8800 + i
        contract.insert(rec)
    injected["CR-02 orphan ID-CRUISE"] += 3
    rec = _clean_contract(rng, 500921, customer_ids, cruises)
    rec["ID-CUSTOMER"] = 99999999
    rec["ID-CRUISE"] = 8899
    contract.insert(rec)
    injected["CR-01+CR-02 both keys orphaned"] += 1
    # CR-14 duplicate CONTRACT-ID
    contract.insert(_clean_contract(rng, 500150, customer_ids, cruises))
    injected["CR-14 duplicate CONTRACT-ID (survivor + 1 extra copy)"] += 2
    # CR-15 booking date
    rec = _clean_contract(rng, 500931, customer_ids, cruises)
    rec["DATE-BOOKING"] = 20260231
    contract.insert(rec)
    injected["CR-15 DATE-BOOKING invalid"] += 1
    rec = _clean_contract(rng, 500932, customer_ids, cruises)
    rec["DATE-BOOKING"] = 20271001
    contract.insert(rec)
    injected["CR-15 DATE-BOOKING after as-of"] += 1

    return db, injected, baseline


def planted_vs_detected(injected, exceptions, baseline):
    """Per rule: records touched by planted defects + baseline-fixture presence
    exceptions must equal the exceptions the rule raised."""
    detected = Counter(e["rule"] for e in exceptions)
    from_baseline = Counter(e["rule"] for e in exceptions
                            if e["isn"] in baseline[e["file"]])
    rows = []
    for rule in RULES:
        planted = sum(v for k, v in injected.items()
                      if rule.id in k.split(" ")[0].split("+"))
        rows.append(OrderedDict([
            ("rule", rule.id), ("planted", planted),
            ("baseline_fixture", from_baseline[rule.id]),
            ("detected", detected[rule.id]),
            ("balanced", planted + from_baseline[rule.id] == detected[rule.id]),
        ]))
    return rows


# --------------------------------------------------------------------------
# Profiling
# --------------------------------------------------------------------------
def profile(db):
    out = OrderedDict()
    for fname in FILES:
        recs = list(db.files[fname].records.values())
        fields = sorted({k for r in recs for k in r})
        rows = []
        for field in fields:
            values = [r.get(field) for r in recs]
            if isinstance(next((v for v in values if isinstance(v, list)), None), list):
                occ = Counter(len(v) if isinstance(v, list) else 0 for v in values)
                rows.append(OrderedDict([
                    ("field", field), ("kind", "MU/PE"),
                    ("populated", sum(1 for v in values if isinstance(v, list) and len(v) > 0)),
                    ("distinct", ""), ("min", ""), ("max", ""),
                    ("occurrences", {str(k): occ[k] for k in sorted(occ)}),
                ]))
                continue
            populated = [v for v in values if not _blank(v)]
            scalars = [v for v in populated if isinstance(v, (int, float, str))]
            rows.append(OrderedDict([
                ("field", field), ("kind", "scalar"),
                ("populated", len(populated)),
                ("distinct", len({str(v) for v in populated})),
                ("min", str(min(scalars)) if scalars and len({type(s) for s in scalars}) == 1 else ""),
                ("max", str(max(scalars)) if scalars and len({type(s) for s in scalars}) == 1 else ""),
                ("occurrences", {}),
            ]))
        out[fname] = OrderedDict([("records", len(recs)), ("fields", rows)])
    return out


# --------------------------------------------------------------------------
# Rule application
# --------------------------------------------------------------------------
def _context(db):
    persons = db.files["NCCUSTOMER"].records
    contracts = db.files["NCCONTRACT"].records
    person_count = Counter(r.get("PERSON-ID") for r in persons.values())
    contract_count = Counter(r.get("CONTRACT-ID") for r in contracts.values())
    first_isn_person, first_isn_contract = {}, {}
    for isn in sorted(persons):
        first_isn_person.setdefault(persons[isn].get("PERSON-ID"), isn)
    for isn in sorted(contracts):
        first_isn_contract.setdefault(contracts[isn].get("CONTRACT-ID"), isn)
    return {
        "as_of": AS_OF,
        "person_ids": {r.get("PERSON-ID") for r in persons.values()},
        "cruise_ids": {r.get("CRUISE-ID") for r in db.files["NCCRUISE"].records.values()},
        "yacht_ids": {r.get("YACHT-ID") for r in db.files["NCYACHT"].records.values()},
        "person_count": person_count,
        "contract_count": contract_count,
        "first_isn_person": first_isn_person,
        "first_isn_contract": first_isn_contract,
    }


def apply_rules(db):
    """Evaluate every rule against every record of its file.

    Returns ``(records, exceptions)``. ``records[file]`` is a list of
    ``{isn, key, disposition, outcome, cleansed}`` in ISN order; ``exceptions``
    is the flat list of non-pass outcomes.
    """
    ctx = _context(db)
    records = OrderedDict()
    exceptions = []
    for fname in FILES:
        rows = []
        for isn in sorted(db.files[fname].records):
            rec = copy.deepcopy(db.files[fname].records[isn])
            ctx["isn"] = isn
            worst = PASS
            for rule in RULES_BY_FILE.get(fname, []):
                outcome, msg, corrections = rule.check(rec, ctx)
                if outcome == PASS:
                    continue
                if corrections:
                    rec.update(corrections)
                if SEVERITY[outcome] > SEVERITY[worst]:
                    worst = outcome
                exceptions.append(OrderedDict([
                    ("file", fname), ("isn", isn),
                    ("business_key", rec.get(BUSINESS_KEY[fname])),
                    ("rule", rule.id), ("fields", ";".join(n for _, n in rule.fields)),
                    ("outcome", outcome), ("message", msg),
                ]))
            rows.append(OrderedDict([
                ("isn", isn), ("key", rec.get(BUSINESS_KEY[fname])),
                ("outcome", worst), ("disposition", DISPOSITION[worst]),
                ("cleansed", rec),
            ]))
        records[fname] = rows
    return records, exceptions


# --------------------------------------------------------------------------
# Reconciliation
# --------------------------------------------------------------------------
def _hash_rows(rows):
    payload = json.dumps(rows, sort_keys=True, default=str).encode()
    return hashlib.sha256(payload).hexdigest()


def reconcile(db, records, exceptions):
    per_file = OrderedDict()
    for fname in FILES:
        rows = records[fname]
        c = Counter(r["disposition"] for r in rows)
        per_file[fname] = OrderedDict([
            ("in", len(rows)),
            ("loaded", c["loaded"]),
            ("held", c["held"]),
            ("rejected", c["rejected"]),
            ("corrected", sum(1 for r in rows if r["outcome"] == CORRECT)),
            ("balances", len(rows) == c["loaded"] + c["held"] + c["rejected"]),
        ])

    per_rule = OrderedDict()
    for rule in RULES:
        evaluated = len(records[rule.file])
        c = Counter(e["outcome"] for e in exceptions if e["rule"] == rule.id)
        per_rule[rule.id] = OrderedDict([
            ("name", rule.name), ("file", rule.file), ("evaluated", evaluated),
            ("passed", evaluated - sum(c.values())),
            ("corrected", c[CORRECT]), ("flagged", c[FLAG]), ("rejected", c[REJECT]),
        ])

    # Control totals on the transaction file (booking ≈ pay transaction).
    contracts = records["NCCONTRACT"]
    def _sum(disp):
        return round(sum(float(r["cleansed"].get("PRICE") or 0) for r in contracts
                         if r["disposition"] == disp), 3)
    price_in = round(sum(float(r["cleansed"].get("PRICE") or 0) for r in contracts), 3)
    control = OrderedDict([
        ("contract_price_in", price_in),
        ("contract_price_loaded", _sum("loaded")),
        ("contract_price_held", _sum("held")),
        ("contract_price_rejected", _sum("rejected")),
        ("contract_price_balances",
         abs(price_in - (_sum("loaded") + _sum("held") + _sum("rejected"))) < 0.0005),
        ("distinct_customers_in", len({r["cleansed"].get("PERSON-ID")
                                       for r in records["NCCUSTOMER"]})),
        ("distinct_customers_loaded", len({r["cleansed"].get("PERSON-ID")
                                           for r in records["NCCUSTOMER"]
                                           if r["disposition"] == "loaded"})),
        ("bookings_per_cruise_loaded", OrderedDict(
            sorted(Counter(r["cleansed"].get("ID-CRUISE") for r in contracts
                           if r["disposition"] == "loaded").items(),
                   key=lambda kv: str(kv[0])))),
        ("loadable_set_sha256", OrderedDict(
            (f, _hash_rows([r["cleansed"] for r in records[f] if r["disposition"] == "loaded"]))
            for f in FILES)),
    ])

    crosswalk = OrderedDict()
    for fname in FILES:
        key = BUSINESS_KEY[fname]
        crosswalk[fname] = OrderedDict([
            ("source_key", key),
            ("isn_is_not_a_business_key", True),
            ("loaded_keys", sorted({str(r["key"]) for r in records[fname]
                                    if r["disposition"] == "loaded"})[:5] + ["..."]),
            ("loaded_key_count", len({str(r["key"]) for r in records[fname]
                                      if r["disposition"] == "loaded"})),
        ])

    return OrderedDict([
        ("as_of", AS_OF.isoformat()), ("seed", SEED),
        ("per_file", per_file), ("per_rule", per_rule),
        ("control_totals", control), ("crosswalk", crosswalk),
        ("exception_count", len(exceptions)),
    ])


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------
def _md_table(headers, rows):
    lines = ["| " + " | ".join(headers) + " |",
             "|" + "|".join("---" for _ in headers) + "|"]
    for r in rows:
        lines.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(lines)


def render_report_md(recon, injected, exceptions, pvd):
    lines = [
        "# Reconciliation report (synthetic data)",
        "",
        "Generated by `harness/cleanse_reconcile.py`; do not edit by hand. "
        "Run `python3 fpps-hcm-modernization-deliverable/07-master-data-cleansing/harness/cleanse_reconcile.py --check` "
        "from the repository root to verify it has not drifted.",
        "",
        f"As-of date `{recon['as_of']}`, seed `{recon['seed']}`. The dataset is the baseline fixture "
        "from `tests/harness/fixtures.py` plus deterministic synthetic rows and injected defects on top of "
        "`tests/harness/adabas_sim.py`. This Python is a validation/cleansing harness, never a rewrite target.",
        "",
        "## Record counts per file",
        "",
        _md_table(["File", "In", "Loaded", "Held for steward", "Rejected", "Of which corrected", "In = loaded + held + rejected"],
                  [[f, v["in"], v["loaded"], v["held"], v["rejected"], v["corrected"],
                    "yes" if v["balances"] else "NO"] for f, v in recon["per_file"].items()]),
        "",
        "## Outcome per rule",
        "",
        _md_table(["Rule", "Name", "File", "Evaluated", "Passed", "Corrected", "Flagged", "Rejected"],
                  [[rid, v["name"], v["file"], v["evaluated"], v["passed"], v["corrected"],
                    v["flagged"], v["rejected"]] for rid, v in recon["per_rule"].items()]),
        "",
        "## Control totals",
        "",
    ]
    ct = recon["control_totals"]
    lines.append(_md_table(["Control", "Value"], [
        ["NCCONTRACT.PRICE total in", f"{ct['contract_price_in']:.3f}"],
        ["NCCONTRACT.PRICE total loaded", f"{ct['contract_price_loaded']:.3f}"],
        ["NCCONTRACT.PRICE total held", f"{ct['contract_price_held']:.3f}"],
        ["NCCONTRACT.PRICE total rejected", f"{ct['contract_price_rejected']:.3f}"],
        ["Price in = loaded + held + rejected", "yes" if ct["contract_price_balances"] else "NO"],
        ["Distinct PERSON-ID in", ct["distinct_customers_in"]],
        ["Distinct PERSON-ID loaded", ct["distinct_customers_loaded"]],
        ["Cruises with loaded bookings", len(ct["bookings_per_cruise_loaded"])],
    ]))
    lines += ["", "### Loadable-set content hashes (SHA-256)", "",
              _md_table(["File", "SHA-256 of loaded records"],
                        [[f, h] for f, h in ct["loadable_set_sha256"].items()]),
              "", "## Injected defects versus detections", "",
              "Every defect planted by `build_dirty_db` is listed with the number of records it touches; "
              "the second table proves, per rule, that planted + baseline-fixture presence exceptions = detected. "
              "Baseline rows are the fixture records from `tests/harness/fixtures.py`, which carry only the fields "
              "the behavioural tests need.", "",
              _md_table(["Injected defect", "Records touched"], [[k, v] for k, v in sorted(injected.items())]),
              "",
              _md_table(["Rule", "Planted", "Baseline fixture", "Detected", "Planted + baseline = detected"],
                        [[r["rule"], r["planted"], r["baseline_fixture"], r["detected"],
                          "yes" if r["balanced"] else "NO"] for r in pvd]),
              "", "## Exception list", "",
              f"{len(exceptions)} exceptions (also in `exceptions.csv`). Baseline fixture rows from "
              "`tests/harness/fixtures.py` carry only the fields the behavioural tests need, so they "
              "surface as presence exceptions; that is the profiling step doing its job.", "",
              _md_table(["File", "ISN", "Business key", "Rule", "Field(s)", "Outcome", "Message"],
                        [[e["file"], e["isn"], e["business_key"], e["rule"], e["fields"],
                          e["outcome"], e["message"].replace("|", "\\|")] for e in exceptions]),
              ""]
    return "\n".join(lines)


def render_profile_md(prof):
    lines = ["# Data profile (synthetic data)", "",
             "Generated by `harness/cleanse_reconcile.py`; do not edit by hand. "
             "Fill counts, distinct counts, min/max and multiple-value / periodic-group occurrence "
             "distributions for the synthetic dirty dataset before cleansing.", ""]
    for fname, p in prof.items():
        lines += [f"## {fname} ({p['records']} records)", "",
                  _md_table(["Field", "Kind", "Populated", "Distinct", "Min", "Max", "Occurrence distribution"],
                            [[r["field"], r["kind"], r["populated"], r["distinct"], r["min"], r["max"],
                              ", ".join(f"{k} occ: {v}" for k, v in r["occurrences"].items()) or ""]
                             for r in p["fields"]]), ""]
    return "\n".join(lines)


def render_exceptions_csv(exceptions):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["file", "isn", "business_key", "rule", "fields", "outcome", "message"])
    for e in exceptions:
        w.writerow([e["file"], e["isn"], e["business_key"], e["rule"], e["fields"],
                    e["outcome"], e["message"]])
    return buf.getvalue()


def render_rule_catalogue_md():
    lines = ["# Rule catalogue (generated)", "",
             "Generated from `RULES` in `harness/cleanse_reconcile.py`; do not edit by hand. "
             "`../cleansing-rules.md` explains each rule; `--check` fails if the two disagree on rule IDs.", "",
             _md_table(["Rule", "Name", "File", "Dictionary field(s)", "Category", "Default action",
                        "Payroll analog (designed)", "Candidate HCM target (designed)", "Source evidence"],
                       [[r.id, r.name, r.file, ", ".join(f"`{n}`" for _, n in r.fields), r.category,
                         r.action, r.payroll_analog, r.hcm_target,
                         "<br>".join(f"`{e}`" for e in r.evidence)] for r in RULES]), ""]
    return "\n".join(lines)


def generate():
    db, injected, baseline = build_dirty_db()
    prof = profile(db)
    records, exceptions = apply_rules(db)
    recon = reconcile(db, records, exceptions)
    pvd = planted_vs_detected(injected, exceptions, baseline)
    report_json = OrderedDict([
        ("reconciliation", recon),
        ("injected_defects", OrderedDict(sorted(injected.items()))),
        ("planted_vs_detected", pvd),
        ("rules", [r.as_dict() for r in RULES]),
        ("profile", prof),
    ])
    return OrderedDict([
        ("reconciliation-report.md", render_report_md(recon, injected, exceptions, pvd)),
        ("reconciliation-report.json", json.dumps(report_json, indent=2, default=str) + "\n"),
        ("exceptions.csv", render_exceptions_csv(exceptions)),
        ("profile.md", render_profile_md(prof)),
        ("rule-catalogue.md", render_rule_catalogue_md()),
    ])


def check_rule_ids_in_doc():
    """Bidirectional: rule IDs in RULES == rule IDs mentioned in cleansing-rules.md."""
    if not RULES_DOC.exists():
        return [f"{RULES_DOC.name} missing"]
    doc_ids = set(re.findall(r"\bCR-\d{2}\b", RULES_DOC.read_text()))
    code_ids = {r.id for r in RULES}
    problems = []
    for rid in sorted(code_ids - doc_ids):
        problems.append(f"{rid} defined in RULES but not documented in {RULES_DOC.name}")
    for rid in sorted(doc_ids - code_ids):
        problems.append(f"{rid} documented in {RULES_DOC.name} but not defined in RULES")
    return problems


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true",
                    help="regenerate in memory and fail if sample-output/ differs")
    args = ap.parse_args(argv)
    outputs = generate()
    if args.check:
        problems = []
        for name, content in outputs.items():
            path = OUT_DIR / name
            if not path.exists():
                problems.append(f"{path.relative_to(REPO_ROOT)} missing")
            elif path.read_text() != content:
                problems.append(f"{path.relative_to(REPO_ROOT)} differs from generated content")
        problems += check_rule_ids_in_doc()
        report = json.loads(outputs["reconciliation-report.json"])
        problems += [f"{r['rule']}: planted {r['planted']} + baseline {r['baseline_fixture']} != detected {r['detected']}"
                     for r in report["planted_vs_detected"] if not r["balanced"]]
        problems += [f"{f}: in != loaded + held + rejected"
                     for f, v in report["reconciliation"]["per_file"].items() if not v["balances"]]
        if problems:
            print("DRIFT DETECTED:\n  " + "\n  ".join(problems))
            return 1
        print(f"OK: {len(outputs)} sample-output files match; rule IDs consistent with {RULES_DOC.name}")
        return 0
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, content in outputs.items():
        (OUT_DIR / name).write_text(content)
        print(f"wrote {(OUT_DIR / name).relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
