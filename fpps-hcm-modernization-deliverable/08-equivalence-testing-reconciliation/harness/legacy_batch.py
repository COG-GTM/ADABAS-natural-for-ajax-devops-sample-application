"""Synthetic legacy expected-results batch for the equivalence harness.

This module is a VALIDATION HARNESS, not a rewrite target. It drives the
existing behavioural model of CONEW-N (`tests/harness/natural_model.py`,
which mirrors SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN)
against the shared synthetic ADABAS fixture (`tests/harness/fixtures.py`) to
produce the "legacy expected" side of a reconciliation. Nothing here is
intended to run in production or to replace any Natural module.

Analogy: one booking transaction stands for one pay/personnel transaction;
the batch below stands for one pay-period input file; the expected outcomes
(message code, contract ID, price to the cent, availability after) stand for
the pay-calculate results an HCM must reproduce.
"""

import json
import os
import sys
from decimal import Decimal, ROUND_HALF_UP

REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from tests.harness import natural_model as nm  # noqa: E402
from tests.harness.fixtures import make_db  # noqa: E402

BATCH_ID = "SYN-2026-09-BATCH-01"
BOOKING_DATE = 20260903

# Extra synthetic master data layered on top of tests/harness/fixtures.make_db
# so that the batch exercises cent-bearing prices and more than two customers.
# Shapes follow the DDMs: NCCRUISE.PRICE-1W is P 10.3, CRUISE-STATUS is A1,
# NCCUSTOMER.PERSON-ID and NCCRUISE.CRUISE-ID are N 8.0.
EXTRA_CRUISES = [
    {
        "CRUISE-ID": 2201, "CRUISE-STATUS": "2",
        "START-DATE": 20261101, "END-DATE": 20261108,
        "START-HARBOR": "Lefkas", "DESTINATION-HARBOR": "Agios Nikolaos",
        "ID-YACHT": 4712,
        "PRICE-1W": 1349.99, "PRICE-2W": 2499.49, "PRICE-3W": 3599.95,
    },
    {
        "CRUISE-ID": 2202, "CRUISE-STATUS": "1",
        "START-DATE": 20261205, "END-DATE": 20261212,
        "START-HARBOR": "Santorini", "DESTINATION-HARBOR": "Lefkas",
        "ID-YACHT": 4711,
        "PRICE-1W": 2075.50, "PRICE-2W": 3890.00, "PRICE-3W": 5410.25,
    },
]
EXTRA_CUSTOMERS = [
    {"PERSON-ID": 10000003, "SURNAME": "Okafor", "FIRST-NAME-OLD": "Chidi"},
    {"PERSON-ID": 10000004, "SURNAME": "Nakamura", "FIRST-NAME-OLD": "Yui"},
    {"PERSON-ID": 10000005, "SURNAME": "Alvarez", "FIRST-NAME-OLD": "Lucia"},
]

# The synthetic transaction batch. Each tuple is (txn_id, customer_in,
# cruise_in). Inputs are the A8 character parameters CONEW-N receives
# (NCCONW-P ID-CUSTOMER-IN / ID-CRUISE-IN), so blanks and non-numeric values
# are legitimate members of the batch: they exercise the 9904/9905/9918 edits.
TRANSACTIONS = [
    ("T-0001", "10000001", "196"),        # accept, cruise 196 5->4
    ("T-0002", "10000002", "196"),        # accept, 4->3
    ("T-0003", "10000003", "1484"),       # accept, 1484 3->2
    ("T-0004", "10000004", "2201"),       # accept, 2201 2->1  (1349.99)
    ("T-0005", "10000005", "2202"),       # accept, 2202 1->0  (2075.50)
    ("T-0006", "10000001", "2202"),       # reject 9902, 2202 sold out
    ("T-0007", "10000001", "696"),        # reject 9902, 696 fully booked
    ("T-0008", "", "196"),                # reject 9904 customer id missing
    ("T-0009", "10000001", ""),           # reject 9905 cruise id missing
    ("T-0010", "", ""),                   # reject 9904 (customer edit first)
    ("T-0011", "99999999", "196"),        # reject 9918 customer not found
    ("T-0012", "ABCDEFGH", "196"),        # reject 9918 non-numeric customer
    ("T-0013", "10000001", "12AB"),       # reject 9905 non-numeric cruise
    ("T-0014", "10000002", "777777"),     # unknown cruise: msg 0, no store
    ("T-0015", "10000003", "2201"),       # accept, 2201 1->0  (1349.99)
    ("T-0016", "10000004", "2201"),       # reject 9902, 2201 sold out
    ("T-0017", "10000005", "196"),        # accept, 196 3->2
    ("T-0018", "10000002", "1484"),       # accept, 1484 2->1
    ("T-0019", "10000003", "1484"),       # accept, 1484 1->0
    ("T-0020", "10000004", "1484"),       # reject 9902, 1484 sold out
    ("T-0021", "10000001", "196"),        # accept, 196 2->1
    ("T-0022", "10000005", "196"),        # accept, 196 1->0
    ("T-0023", "10000002", "196"),        # reject 9902, 196 sold out
    ("T-0024", "99999999", "2202"),       # reject 9902 (availability edit
                                          # precedes customer lookup)
]

ACCEPTED = "ACCEPTED"
REJECTED = "REJECTED"


def cents(value, decimals=2):
    """Quantize a numeric amount to `decimals` places, half-up, as Decimal."""
    q = Decimal(1).scaleb(-decimals)
    return Decimal(str(value)).quantize(q, rounding=ROUND_HALF_UP)


def build_db():
    """Shared synthetic fixture plus the extra masters declared above."""
    db = make_db(cruise_status="5")
    for row in EXTRA_CRUISES:
        db.files["NCCRUISE"].insert(row)
    for row in EXTRA_CUSTOMERS:
        db.files["NCCUSTOMER"].insert(row)
    return db


def _availability_snapshot(db):
    return {
        str(rec["CRUISE-ID"]): int(rec["CRUISE-STATUS"])
        for rec in db.files["NCCRUISE"].records.values()
    }


def _contract_by_id(db, contract_id):
    for rec in db.files["NCCONTRACT"].records.values():
        if rec["CONTRACT-ID"] == contract_id:
            return rec
    return None


def run_batch(model):
    """Run TRANSACTIONS through `model` (a conew_* function) sequentially.

    Returns (records, availability_before, availability_after, contract_ids
    that existed before the batch).
    """
    db = build_db()
    session = db.session("batch")
    before = _availability_snapshot(db)
    pre_existing = sorted(
        rec["CONTRACT-ID"] for rec in db.files["NCCONTRACT"].records.values())
    records = []
    for txn_id, customer_in, cruise_in in TRANSACTIONS:
        result = model(session, customer_in, cruise_in,
                       booking_date=BOOKING_DATE)
        accepted = result.new_contract_id != 0
        price = None
        availability_after = None
        cruise_key = cruise_in.strip()
        if cruise_key.isdigit():
            hit = session.find("NCCRUISE", "CRUISE-ID", int(cruise_key))
            if hit:
                availability_after = int(hit[0][1]["CRUISE-STATUS"])
        if accepted:
            contract = _contract_by_id(db, result.new_contract_id)
            price = str(cents(contract["PRICE"], 3))
        records.append({
            "txn_id": txn_id,
            "customer_in": customer_in,
            "cruise_in": cruise_in,
            "booking_date": BOOKING_DATE,
            "outcome": ACCEPTED if accepted else REJECTED,
            "msg_nr": result.msg_nr,
            "rsp_code": result.rsp_code,
            "rsp_text": result.rsp_text,
            "contract_id": result.new_contract_id if accepted else None,
            "price": price,
            "availability_after": availability_after,
        })
    after = _availability_snapshot(db)
    return records, before, after, pre_existing


def control_totals(records, before, after, decimals=2):
    """Batch-level totals an SI reconciles before looking at any record."""
    accepted = [r for r in records if r["outcome"] == ACCEPTED]
    by_msg = {}
    for r in records:
        key = str(r["msg_nr"])
        by_msg[key] = by_msg.get(key, 0) + 1
    price_sum = sum((cents(r["price"], decimals) for r in accepted),
                    Decimal(0))
    ids = [r["contract_id"] for r in accepted]
    return {
        "record_count": len(records),
        "accepted_count": len(accepted),
        "rejected_count": len(records) - len(accepted),
        "count_by_msg_nr": dict(sorted(by_msg.items())),
        "price_sum": str(cents(price_sum, decimals)),
        "contract_id_count": len(ids),
        "distinct_contract_id_count": len(set(ids)),
        "availability_delta": {
            k: after[k] - before[k] for k in sorted(before)
        },
    }


def generate_expected(decimals=2):
    """Produce the legacy expected batch as a JSON-serialisable dict.

    Runs the refactored (shipped-source) model as the oracle and the original
    model as a cross-check: for a single-session sequential batch both must
    agree, because their only difference is behaviour under concurrent
    sessions (see tests/test_concurrency.py).
    """
    ref_records, before, after, pre_existing = run_batch(nm.conew_refactored)
    orig_records, _, _, _ = run_batch(nm.conew_original)
    if ref_records != orig_records:
        raise RuntimeError(
            "original and refactored CONEW-N models disagree on a sequential "
            "batch; the legacy oracle is ambiguous")
    return {
        "batch_id": BATCH_ID,
        "oracle": "tests/harness/natural_model.conew_refactored",
        "cross_check": "tests/harness/natural_model.conew_original "
                       "(identical outcomes on this sequential batch)",
        "fixture": "tests/harness/fixtures.make_db(cruise_status='5') "
                   "+ harness/legacy_batch.EXTRA_CRUISES/EXTRA_CUSTOMERS",
        "booking_date": BOOKING_DATE,
        "decimals": decimals,
        "pre_existing_contract_ids": pre_existing,
        "availability_before": before,
        "availability_after": after,
        "control_totals": control_totals(ref_records, before, after, decimals),
        "records": ref_records,
    }


def dump_json(obj, path):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, sort_keys=False)
        fh.write("\n")


if __name__ == "__main__":
    print(json.dumps(generate_expected(), indent=2))
