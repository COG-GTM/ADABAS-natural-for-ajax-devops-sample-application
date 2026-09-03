#!/usr/bin/env python3
"""Generate ``data-dictionary-hcm.md`` - the source side of an HCM Data Loader mapping workbook.

Scope statement
---------------
This script is a *generator*, not an application: it exists so the dictionary
cannot drift from the DDMs and the static analyzer. Nothing here is a rewrite
target; the business behaviour is implemented in Oracle HCM (or an alternate
HCM), and this Python only produces the mapping-workbook input.

Inputs (all read at run time, never hand-typed)
-----------------------------------------------
* ``tests.harness.source_parser.all_ddms()``           - fields, formats, lengths,
  descriptors, suppression, remarks from ``CRUISE16/DDMs/*.NSD``.
* ``tools.analyze_disposition.analyze()["ddm_field_usage"]`` - which Natural
  objects reference each field by name (static, name-based, heuristic).
* ``RULES`` from ``../07-master-data-cleansing/harness/cleanse_reconcile.py`` -
  the cleansing-flag column is derived from the rule catalogue's ``fields``.
* ``ANNOTATIONS`` below - the authored candidate Oracle HCM analog, mapping
  note and lineage note per field. Every annotation key must exist in the DDMs
  (the script fails otherwise), and every DDM field must have an annotation.

Run from the repository root::

    python3 fpps-hcm-modernization-deliverable/03-data-model-data-dictionary/generate_dictionary_hcm.py
    python3 fpps-hcm-modernization-deliverable/03-data-model-data-dictionary/generate_dictionary_hcm.py --check
"""

import argparse
import importlib.util
import sys
from collections import OrderedDict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tests.harness import source_parser as sp  # noqa: E402
from tools.analyze_disposition import analyze  # noqa: E402

OUT = HERE / "data-dictionary-hcm.md"
HARNESS = (REPO_ROOT / "fpps-hcm-modernization-deliverable"
           / "07-master-data-cleansing" / "harness" / "cleanse_reconcile.py")
FILE_ORDER = ("NCCUSTOMER", "NCCONTRACT", "NCCRUISE", "NCYACHT")

# Sample file -> payroll / HCM analog (designed). The hub README fixes the
# vocabulary: booking ≈ pay/personnel transaction, DDM ≈ personnel-payroll
# data model.
FILE_ROLE = OrderedDict([
    ("NCCUSTOMER", ("Customer master (person)", "Person / Worker",
                    "Worker.dat: Worker, PersonName, PersonEmail, PersonAddress, PersonPhone, PersonLegislativeData")),
    ("NCCONTRACT", ("Booking transaction (customer x cruise)", "Pay / personnel transaction",
                    "ElementEntry.dat: ElementEntry, ElementEntryValue (alternatively Assignment)")),
    ("NCCRUISE", ("Cruise catalogue with open-places counter", "Position with open headcount / pay element definition",
                  "Position.dat: Position (alternatively Element)")),
    ("NCYACHT", ("Yacht (resource) master", "Organisation / department / location",
                 "Organization.dat: Organization (alternatively Location)")),
])

# (file, field) -> (hcm_object, hcm_attribute, mapping_note, lineage_note)
# HCM object/attribute names are *candidates* to be confirmed against the
# target release's Business Object Details page; they are labelled (designed).
_C = "CRUISE16/Subprograms/"
_D = "CRUISE16/DDMs/"
ANNOTATIONS = {
    # ---------------------------------------------------------- NCCUSTOMER
    ("NCCUSTOMER", "PERSON-ID"): (
        "Worker", "SourceSystemId (source key); PersonNumber candidate",
        "Load as the HDL source key, not as the target PersonNumber unless the client keeps legacy numbers. Never load the ISN.",
        f"Generated MAX+1 under record hold in `{_C}CUNEW-N.NSN:41-46`; matched by FIND in `{_C}CUGET-N.NSN:58` and `{_C}CUMOD-N.NSN:44`; referenced by `NCCONTRACT.ID-CUSTOMER`."),
    ("NCCUSTOMER", "BIRTH-DATE"): (
        "Worker", "DateOfBirth",
        "N8 YYYYMMDD to ISO date. Zero or non-calendar values cannot be converted; see CR-10.",
        f"Written from an alpha date after `EXAMINE ... FOR '-' DELETE` and `VAL` in `{_C}CUMOD-N.NSN:59-61`; `{_C}CUNEW-N.NSN:54` applies `VAL` without the dash strip; read back with `EM=9999'-'99'-'99` in `{_C}CUGET-N.NSN:93`."),
    ("NCCUSTOMER", "SEX"): (
        "PersonLegislativeData", "Sex (lookup)",
        "Crosswalk 'M'/'F' to the target lookup; blank needs a steward value. See CR-05.",
        f"Domain documented only in the DDM remark (`{_D}NCCUSTOM.NSD:14-16`). Read in `{_C}CUGET-N.NSN:94`; not written by `CUNEW-N` or `CUMOD-N`, so the maintained UI path cannot populate it."),
    ("NCCUSTOMER", "NAME"): (
        "PersonName", "(group header)",
        "Group header only; map the children.", "Structural DDM group; no data."),
    ("NCCUSTOMER", "SURNAME"): (
        "PersonName", "LastName",
        "Mandatory in the target; blank SURNAME rejects the person row. See CR-13.",
        f"Persisted by `{_C}CUNEW-N.NSN:49` and `{_C}CUMOD-N.NSN:54`; read by `{_C}CUGET-N.NSN:95`."),
    ("NCCUSTOMER", "FIRST-NAME-OLD"): (
        "PersonName", "FirstName (primary source)",
        "Primary source of the target FirstName. Fallback to FIRST-NAME-1 when blank; conflict when both differ. See CR-13.",
        f"The field the code actually persists: `{_C}CUNEW-N.NSN:48`, `{_C}CUMOD-N.NSN:53`; read by `{_C}CUGET-N.NSN:96`. Active in the local view `CRUISE16/Local Data Areas/NCDATA-L.NSL:45`."),
    ("NCCUSTOMER", "FIRST-NAME-2"): (
        "PersonName", "MiddleNames (candidate)",
        "Do not map until 10 (disposition) confirms the field carries data; unreferenced in analyzed scope.",
        "Declared in the DDM only; no Natural object in the analyzed libraries names it."),
    ("NCCUSTOMER", "TITLE"): (
        "PersonName", "Title (lookup, candidate)",
        "Profile before mapping; unreferenced in analyzed scope.",
        "Declared in the DDM only."),
    ("NCCUSTOMER", "FORM-OF-ADDRESS"): (
        "PersonName", "Salutation / Title (candidate)",
        "Profile before mapping; unreferenced in analyzed scope.",
        "Declared in the DDM only."),
    ("NCCUSTOMER", "ADDRESS"): (
        "PersonAddress", "(group header)",
        "Group header only; map the children.", "Structural DDM group; no data."),
    ("NCCUSTOMER", "EMAIL"): (
        "PersonEmail", "EmailAddress (one row per occurrence); occurrence 1 = primary",
        "Multiple-value field (MU): explode to one PersonEmail row per populated occurrence, occurrence 1 primary. Only occurrence 1 has code meaning. See CR-06.",
        f"Only `EMAIL(1)` is written (`{_C}CUNEW-N.NSN:50`, `{_C}CUMOD-N.NSN:55`) and read (`{_C}CUGET-N.NSN:70`, `:97`); the login-by-email path scans `EMAIL(1)` with a full-file READ (`{_C}CUGET-N.NSN:69-74`)."),
    ("NCCUSTOMER", "STREET-NUMBER"): (
        "PersonAddress", "AddressLine1",
        "Direct move; A20 fits the target length.",
        f"Persisted by `{_C}CUNEW-N.NSN:51`, `{_C}CUMOD-N.NSN:56`; read by `{_C}CUGET-N.NSN:98`."),
    ("NCCUSTOMER", "COUNTRY"): (
        "PersonAddress", "Country",
        "A3 code needs a crosswalk to the target country code list; blank or non-3-letter values go to the steward queue. See CR-09.",
        f"Read in `{_C}CUGET-N.NSN:99` only; not written by `CUNEW-N` or `CUMOD-N`, so the maintained UI path never populates it."),
    ("NCCUSTOMER", "ZIP-CODE"): (
        "PersonAddress", "PostalCode",
        "Trim; validate against the country's postal format after the COUNTRY crosswalk. See CR-08.",
        f"Persisted by `{_C}CUNEW-N.NSN:52`, `{_C}CUMOD-N.NSN:57`; read by `{_C}CUGET-N.NSN:100`."),
    ("NCCUSTOMER", "CITY"): (
        "PersonAddress", "TownOrCity",
        "Direct move.",
        f"Persisted by `{_C}CUNEW-N.NSN:53`, `{_C}CUMOD-N.NSN:58`; read by `{_C}CUGET-N.NSN:101`."),
    ("NCCUSTOMER", "PHONE"): (
        "PersonPhone", "(periodic group header): one row per occurrence, PhoneType by position",
        "Periodic group (PE): occurrence 1 = home, occurrence 2 = work per the DDM remark. Unreferenced in analyzed scope, so occurrence semantics rest on the remark alone. See CR-07.",
        f"Occurrence meaning documented only in `{_D}NCCUSTOM.NSD:29-33`; no Natural object in the analyzed libraries names the group."),
    ("NCCUSTOMER", "AREA-CODE"): (
        "PersonPhone", "AreaCode",
        "Per occurrence; see PHONE.", "Declared in the DDM only."),
    ("NCCUSTOMER", "PHONE-NUMBER"): (
        "PersonPhone", "PhoneNumber",
        "Per occurrence; digits and spaces only. See CR-07.", "Declared in the DDM only."),
    ("NCCUSTOMER", "TIMESTAMP"): (
        "(not loaded)", "Source audit / optimistic-lock token",
        "Do not load. Use as the extract cut-off marker and for extract-to-load reconciliation. See CR-11.",
        f"Set from `*TIMESTMP` on store/update (`{_C}CUNEW-N.NSN:55`, `{_C}CUMOD-N.NSN:62`); compared before update to detect a concurrent change (`{_C}CUMOD-N.NSN:50-67`, message 9934)."),
    ("NCCUSTOMER", "FIRST-NAME-1"): (
        "PersonName", "FirstName (fallback only)",
        "Fallback source for FirstName when FIRST-NAME-OLD is blank. Do not map as a second name attribute. See CR-13.",
        "Adapter-written, never persisted by the analyzed code: `RDCRUISE/Programs/RDCRUISP.NSP:619` and `:663` move the page value into the PDA field `P-CUSTOMER-DATA.FIRST-NAME-1` (`CRUISE16/Parameter Data Areas/NCCUGE-P.NSA:29`), but `CUNEW-N`/`CUMOD-N` move only `FIRST-NAME-OLD` to the DB view and the DB-view field is commented out in `CRUISE16/Local Data Areas/NCDATA-L.NSL:56`. The analyzer's `RDCRUISP` reference is a name match on the PDA field, not on the DDM field."),
    # ---------------------------------------------------------- NCCONTRACT
    ("NCCONTRACT", "CONTRACT-ID"): (
        "ElementEntry", "SourceSystemId (source key)",
        "Source key for the transaction row; never load the ISN. See CR-14.",
        f"Generated MAX+1 under record hold in `{_C}CONEW-N.NSN:96-102`."),
    ("NCCONTRACT", "PRICE"): (
        "ElementEntryValue", "ScreenEntryValue (amount)",
        "P10.3 to decimal amount. Derived at booking from `NCCRUISE.PRICE-1W`; reconcile the sum in versus out as a control total.",
        f"Copied from `NCCRUISE.PRICE-1W` in `{_C}CONEW-N.NSN:103`."),
    ("NCCONTRACT", "DID-CONDITIONS"): (
        "(none)", "Document reference (candidate DocumentsOfRecord)",
        "Unreferenced in analyzed scope; send to 10 for disposition before mapping.",
        "Declared in the DDM and `NCDATA-L` only."),
    ("NCCONTRACT", "DATE-RESERVATION"): (
        "(none)", "Reservation date (no target analog)",
        "Unreferenced in analyzed scope; the PDA comment marks it 'not yet used'.",
        "PDA `CRUISE16/Parameter Data Areas/NCCONW-P.NSA:12` documents the input as not yet used; no Natural object moves it to the DB view."),
    ("NCCONTRACT", "DATE-BOOKING"): (
        "ElementEntry", "EffectiveStartDate",
        "N8 YYYYMMDD to ISO date; the transaction's effective date. See CR-15.",
        f"Set from `*DATN` in `{_C}CONEW-N.NSN:105-106`; the PDA input `DATE-BOOKING-IN` is documented as not yet used (`CRUISE16/Parameter Data Areas/NCCONW-P.NSA:13`)."),
    ("NCCONTRACT", "DATE-CANCELLATION"): (
        "ElementEntry", "EffectiveEndDate (candidate)",
        "Unreferenced in analyzed scope; no cancellation path exists in the analyzed code. Disposition first.",
        "Declared in the DDM and `NCDATA-L` only."),
    ("NCCONTRACT", "DEPOSIT"): (
        "ElementEntryValue", "(group header) deposit schedule",
        "Group header; children unreferenced.", "Structural DDM group; no data."),
    ("NCCONTRACT", "DATE-D"): (
        "ElementEntryValue", "Deposit date (candidate input value)",
        "Unreferenced in analyzed scope; disposition first.", "Declared in the DDM only."),
    ("NCCONTRACT", "AMOUNT-D"): (
        "ElementEntryValue", "Deposit amount (candidate input value)",
        "Unreferenced in analyzed scope; disposition first.", "Declared in the DDM only."),
    ("NCCONTRACT", "PAYMENT-OF-BALANCE"): (
        "ElementEntryValue", "(group header) balance payment",
        "Group header; children unreferenced.", "Structural DDM group; no data."),
    ("NCCONTRACT", "DATE-P"): (
        "ElementEntryValue", "Balance payment date (candidate input value)",
        "Unreferenced in analyzed scope; disposition first.", "Declared in the DDM only."),
    ("NCCONTRACT", "AMOUNT-P"): (
        "ElementEntryValue", "Balance payment amount (candidate input value)",
        "Unreferenced in analyzed scope; disposition first.", "Declared in the DDM only."),
    ("NCCONTRACT", "ID-CUSTOMER"): (
        "ElementEntry", "PersonId via Worker source key (foreign key)",
        "Resolve to the Person source key; rows whose customer does not exist are rejected. See CR-01.",
        f"Validated at booking by `FIND NCCUSTOMER PERSON-ID = ...` (`{_C}CONEW-N.NSN:157-162`, message 9918) and stored in `{_C}CONEW-N.NSN:110`."),
    ("NCCONTRACT", "ID-CRUISE"): (
        "ElementEntry", "Position / Element source key (foreign key)",
        "Resolve to the NCCRUISE source key; rows whose cruise does not exist are rejected. See CR-02.",
        f"Resolved by `FIND NCCRUISE WITH CRUISE-ID` (`{_C}CONEW-N.NSN:80`) and stored in `{_C}CONEW-N.NSN:109`."),
    # ---------------------------------------------------------- NCCRUISE
    ("NCCRUISE", "CRUISE-ID"): (
        "Position", "SourceSystemId / PositionCode (source key)",
        "Source key; referenced by `NCCONTRACT.ID-CRUISE`.",
        f"Looked up by `FIND` in `{_C}CONEW-N.NSN:80` and `READ (1) ... BY CRUISE-ID` in `{_C}CRGET-N.NSN:49`."),
    ("NCCRUISE", "CRUISE-STATUS"): (
        "Position", "Open headcount / FTE available (numeric in an A1)",
        "A1 holding a digit: convert with VAL; anything outside '0'..'9' is rejected. See CR-04.",
        f"Decremented under hold at booking (`{_C}CONEW-N.NSN:82-92`); cruises with `VAL(...) = 0` are skipped from the listing (`{_C}CRLIST-N.NSN:53-57`)."),
    ("NCCRUISE", "CRUISE-START"): (
        "Position", "(group header) start",
        "Group header only.", "Structural DDM group; no data."),
    ("NCCRUISE", "START-DATE"): (
        "Position", "EffectiveStartDate (candidate)",
        "N8 YYYYMMDD to ISO date; the listing's descriptor sort order.",
        f"Descriptor used by `READ NCCRUISE DESCENDING BY START-DATE` in `{_C}CRLIST-N.NSN:51`."),
    ("NCCRUISE", "START-TIME"): (
        "(none)", "Start time",
        "Unreferenced in analyzed scope; disposition first.", "Declared in the DDM only."),
    ("NCCRUISE", "CRUISE-END"): (
        "Position", "(group header) end",
        "Group header only.", "Structural DDM group; no data."),
    ("NCCRUISE", "END-DATE"): (
        "Position", "EffectiveEndDate (candidate)",
        "N8 YYYYMMDD to ISO date.",
        f"Edited for display in `{_C}CRLIST-N.NSN:73` and `{_C}CRGET-N.NSN:60`."),
    ("NCCRUISE", "END-TIME"): (
        "(none)", "End time",
        "Unreferenced in analyzed scope; disposition first.", "Declared in the DDM only."),
    ("NCCRUISE", "START-HARBOR"): (
        "Location", "LocationName (candidate)",
        "Text descriptor used as a listing filter; crosswalk to a Location if positions are location-bound.",
        f"Filter in `{_C}CRLIST-N.NSN:59`; output in `{_C}CRGET-N.NSN:56`."),
    ("NCCRUISE", "DESTINATION-HARBOR"): (
        "Location", "LocationName (candidate)",
        "Text descriptor; same treatment as START-HARBOR.", "Output by `CRLIST-N` and `CRGET-N`."),
    ("NCCRUISE", "ID-YACHT"): (
        "Position", "OrganizationId / Department (foreign key)",
        "Resolve to the NCYACHT source key; unresolved rows are held for the steward. See CR-03.",
        f"Joined by `FIND NCYACHT ... YACHT-ID = NCCRUISE.ID-YACHT` (`{_C}CRLIST-N.NSN:80`) and via the `YACHT-PICTURE` view (`{_C}CRGET-N.NSN:101`)."),
    ("NCCRUISE", "PRICES"): (
        "Element", "(group header) rates",
        "Group header only; name collides with a Natural keyword-like token so the analyzer marks it ambiguous.",
        "Structural DDM group; no data."),
    ("NCCRUISE", "PRICE-1W"): (
        "Element / rate definition", "Rate amount (one period)",
        "P10.3 to decimal; the only rate the booking path uses.",
        f"Copied to `NCCONTRACT.PRICE` at booking (`{_C}CONEW-N.NSN:103`)."),
    ("NCCRUISE", "PRICE-2W"): (
        "Element / rate definition", "Rate amount (two periods, candidate)",
        "Displayed but never booked; the PDA states all bookings are one week (`CRUISE16/Parameter Data Areas/NCCONW-P.NSA:11`).",
        f"Edited for display in `{_C}CRLIST-N.NSN:75` and `{_C}CRGET-N.NSN:64`."),
    ("NCCRUISE", "PRICE-3W"): (
        "Element / rate definition", "Rate amount (three periods, candidate)",
        "Displayed but never booked.", "Edited for display by `CRLIST-N` and `CRGET-N`."),
    # ---------------------------------------------------------- NCYACHT
    ("NCYACHT", "YACHT-ID"): (
        "Organization", "SourceSystemId (source key)",
        "Source key; referenced by `NCCRUISE.ID-YACHT`.",
        f"Join target in `{_C}CRLIST-N.NSN:80` and `{_C}CRGET-N.NSN:101`."),
    ("NCYACHT", "YACHT-NAME"): (
        "Organization", "Name",
        "Direct move.", f"Output in `{_C}CRLIST-N.NSN:81` and `{_C}CRGET-N.NSN:102`."),
    ("NCYACHT", "YACHT-TYPE"): (
        "Organization", "Classification (candidate)",
        "Unreferenced in analyzed scope; disposition first.", "Declared in the DDM and PDAs only."),
    ("NCYACHT", "LENGTH"): (
        "(none)", "Physical attribute",
        "No HCM analog. The analyzer's `MAKEURL` hit is a keyword collision (`LENGTH`), not a field reference.",
        "Declared in the DDM and PDAs; name is on the analyzer stoplist."),
    ("NCYACHT", "WIDTH"): ("(none)", "Physical attribute", "No HCM analog; unreferenced in analyzed scope.", "Declared in the DDM and PDAs only."),
    ("NCYACHT", "DRAFT"): ("(none)", "Physical attribute", "No HCM analog; unreferenced in analyzed scope.", "Declared in the DDM and PDAs only."),
    ("NCYACHT", "SAIL-SURFACE"): ("(none)", "Physical attribute", "No HCM analog; unreferenced in analyzed scope.", "Declared in the DDM and PDAs only."),
    ("NCYACHT", "MOTOR"): ("(none)", "Physical attribute", "No HCM analog; unreferenced in analyzed scope.", "Declared in the DDM and PDAs only."),
    ("NCYACHT", "HEAD-ROOM"): ("(none)", "Physical attribute", "No HCM analog; unreferenced in analyzed scope.", "Declared in the DDM and PDAs only."),
    ("NCYACHT", "BUNKS"): (
        "Organization", "Capacity (candidate headcount ceiling)",
        "Unreferenced in analyzed scope; candidate analog for a position headcount ceiling only if 10 confirms data.",
        "Declared in the DDM and PDAs only."),
    ("NCYACHT", "L@PICTURE"): (
        "(not loaded)", "LOB length",
        "Out of HCM scope; retained with the picture only if a DocumentsOfRecord attachment is wanted.",
        f"Moved to the response in `{_C}CRGET-N.NSN:105`."),
    ("NCYACHT", "PICTURE"): (
        "(not loaded)", "LOB (image)",
        "Out of HCM scope; candidate DocumentsOfRecord attachment at most.",
        f"Moved to the response in `{_C}CRGET-N.NSN:104`."),
}


def _load_rules():
    spec = importlib.util.spec_from_file_location("cleanse_reconcile", HARNESS)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.RULES


def _usage_index():
    return {(r["file"], r["field"]): r for r in analyze()["ddm_field_usage"]}


def _kind(f):
    return {"G": "group", "M": "multiple-value (MU)", "P": "periodic group (PE)"}.get(f.field_type, "scalar")


def _fmt(f):
    return f"{f.fmt}{f.length}" if f.fmt else ""


def _referenced(u):
    if u is None:
        return "not analyzed"
    if u["ambiguous"]:
        hits = ", ".join(f"`{o}`" for o in u["referenced_by"]) or "none"
        return f"ambiguous (keyword collision); name hits: {hits}"
    if u["referenced_by"]:
        return "yes: " + ", ".join(f"`{o}`" for o in u["referenced_by"])
    return "no - unreferenced in analyzed scope"


def _rules_for(rules, file_name, field):
    return [r.id for r in rules if (file_name, field) in r.fields]


def build():
    ddms = sp.all_ddms()
    usage = _usage_index()
    rules = _load_rules()

    ddm_keys = {(name, f.name) for name, d in ddms.items() for f in d.fields}
    missing = sorted(ddm_keys - set(ANNOTATIONS))
    stale = sorted(set(ANNOTATIONS) - ddm_keys)
    if missing or stale:
        raise SystemExit(f"ANNOTATIONS out of step with DDMs. missing={missing} stale={stale}")
    rule_keys = {k for r in rules for k in r.fields}
    stale_rules = sorted(rule_keys - ddm_keys)
    if stale_rules:
        raise SystemExit(f"cleansing rules reference unknown DDM fields: {stale_rules}")

    lines = [
        "# Data dictionary for HCM mapping (generated)",
        "",
        "Generated by `generate_dictionary_hcm.py`; do not edit by hand. Run "
        "`python3 fpps-hcm-modernization-deliverable/03-data-model-data-dictionary/generate_dictionary_hcm.py --check` "
        "from the repository root to verify it has not drifted.",
        "",
        "This is the *source side* of an HCM Data Loader mapping workbook: one row per DDM field, "
        "with the format, descriptor role, whether executable Natural code references it, its lineage, "
        "the candidate Oracle HCM object and attribute, a mapping note, and the cleansing rules keyed to it "
        "(rule IDs resolve in `../07-master-data-cleansing/cleansing-rules.md`). Field lists, formats, "
        "descriptors and the referenced-by column come from `tests/harness/source_parser.all_ddms()` and "
        "`tools/analyze_disposition.analyze()['ddm_field_usage']`; the HCM analog, mapping and lineage "
        "columns are authored annotations that the generator refuses to emit unless every DDM field has one.",
        "",
        "## Column semantics",
        "",
        "| Column | Meaning | Maturity |",
        "|---|---|---|",
        "| Fmt/len | Natural format and length from the DDM (`A` alpha, `N` numeric, `P` packed, `B` binary, `U` Unicode, `I` integer) | Demonstrated |",
        "| Desc | `D` when the field is an ADABAS descriptor (searchable/orderable key) | Demonstrated |",
        "| Referenced by executable code | Natural objects in the analyzed libraries that name the field; static, name-based, heuristic; 'ambiguous' when the name collides with a Natural keyword | Demonstrated (evidence class: static reference) |",
        "| Lineage notes | Where the value is written and read, with `path:lines` opened while authoring | Demonstrated (source citations) |",
        "| Candidate HCM object / attribute | HCM Data Loader business object and attribute the field would feed; to be confirmed against the target release | Designed |",
        "| Mapping notes | Conversion, crosswalk or exclusion guidance | Designed |",
        "| Cleansing rules | Rule IDs from the 07 harness catalogue that are keyed to the field | Demonstrated (rules execute on synthetic data) |",
        "",
        "## File roles and candidate HCM objects",
        "",
        "| DDM file | DB/FNR | Fields | Descriptors | Referenced | Unreferenced (candidates) | Ambiguous | With cleansing rules | Sample role | Payroll analog (designed) | Candidate HDL objects (designed) |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for name in FILE_ORDER:
        d = ddms[name]
        fields = d.fields
        refd = sum(1 for f in fields if usage[(name, f.name)]["referenced_by"] and not usage[(name, f.name)]["ambiguous"])
        unref = sum(1 for f in fields if usage[(name, f.name)]["kind"] == "field"
                    and not usage[(name, f.name)]["referenced_by"] and not usage[(name, f.name)]["ambiguous"])
        amb = sum(1 for f in fields if usage[(name, f.name)]["ambiguous"])
        with_rules = sum(1 for f in fields if _rules_for(rules, name, f.name))
        role, analog, hdl = FILE_ROLE[name]
        lines.append(f"| `{name}` | {d.db}/{d.fnr} | {len(fields)} | "
                     f"{sum(1 for f in fields if f.descriptor == 'D')} | {refd} | {unref} | {amb} | {with_rules} | "
                     f"{role} | {analog} | {hdl} |")
    lines += ["",
              "Counts include group headers (which are never 'referenced' by data statements); 'Unreferenced' counts "
              "scalar/MU/PE fields only, matching the definition in "
              "`../10-migration-disposition-dead-code/evidence/disposition-evidence.md`.", ""]

    for name in FILE_ORDER:
        d = ddms[name]
        role, analog, hdl = FILE_ROLE[name]
        lines += [
            f"## {name} - {role}",
            "",
            f"Payroll analog (designed): {analog}. Candidate HDL objects (designed): {hdl}. "
            f"Source: `SunnyIslands/Natural-Libraries/CRUISE16/DDMs/{_nsd_name(name)}`.",
            "",
            "| Lvl | Short | Field | Kind | Fmt/len | Sup | Desc | DDM remark | Referenced by executable code | Lineage notes | Candidate HCM object | Candidate HCM attribute | Mapping notes | Cleansing rules |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
        ]
        for f in d.fields:
            u = usage.get((name, f.name))
            obj, attr, mapping, lineage = ANNOTATIONS[(name, f.name)]
            rule_ids = ", ".join(_rules_for(rules, name, f.name)) or "-"
            lines.append("| " + " | ".join([
                str(f.level), f.shortname, f"`{f.name}`", _kind(f), _fmt(f), f.suppression or "",
                f.descriptor or "", f.remark or "", _referenced(u), lineage,
                f"{obj} (designed)" if obj not in ("(none)", "(not loaded)") else obj,
                attr, mapping, rule_ids,
            ]) + " |")
        lines.append("")

    lines += [
        "## First-name lineage (the worked example)",
        "",
        "| Step | Object | Line(s) | What happens |",
        "|---|---|---|---|",
        "| 1 | `RDCRUISE/Programs/RDCRUISP.NSP` | 619, 663 | Page value `PVMYFIRSTNAME` is moved into the PDA field `P-CUSTOMER-DATA.FIRST-NAME-1` (modify and new-customer paths) |",
        "| 2 | `CRUISE16/Parameter Data Areas/NCCUGE-P.NSA` | 29 | The PDA carries `FIRST-NAME-1 (U) DYNAMIC` alongside `FIRST-NAME-OLD` (line 21) |",
        "| 3 | `CRUISE16/Subprograms/CUNEW-N.NSN` / `CUMOD-N.NSN` | 48 / 53 | Only `P-CUSTOMER-DATA.FIRST-NAME-OLD` is moved into `NCCUSTOMER.FIRST-NAME-OLD`; `FIRST-NAME-1` is not touched |",
        "| 4 | `CRUISE16/Local Data Areas/NCDATA-L.NSL` | 45, 56 | The DB view declares `FIRST-NAME-OLD (A20)`; `FIRST-NAME-1 (U40)` is commented out |",
        "| 5 | `CRUISE16/Subprograms/CUGET-N.NSN` | 96 | Reads return `FIRST-NAME-OLD` only |",
        "",
        "Consequence for the mapping workbook: the target `PersonName.FirstName` has one persisted source (`FIRST-NAME-OLD`) and one "
        "adapter-only source (`FIRST-NAME-1`) that the analyzed code never stores. The dictionary maps `FIRST-NAME-OLD` as primary and "
        "`FIRST-NAME-1` as fallback, and rule CR-13 in 07 surfaces blank, conflicting and derived cases as exceptions. "
        "On the FPPS analogy (designed), this is the pattern of a personnel attribute maintained through two screen generations where "
        "only one column is still written; the extraction must decide the survivor from code evidence, not from column names.",
        "",
    ]
    return "\n".join(lines)


def _nsd_name(file_name):
    for p in sorted(sp.DDM_DIR.glob("*.NSD")):
        if sp.parse_ddm(p).file_name == file_name:
            return p.name
    return "?"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true",
                    help="regenerate in memory and fail if data-dictionary-hcm.md differs")
    args = ap.parse_args(argv)
    content = build()
    if args.check:
        if not OUT.exists() or OUT.read_text() != content:
            print(f"DRIFT DETECTED: {OUT.relative_to(REPO_ROOT)} differs from generated content")
            return 1
        print(f"OK: {OUT.relative_to(REPO_ROOT)} matches generated content")
        return 0
    OUT.write_text(content)
    print(f"wrote {OUT.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
