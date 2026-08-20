"""Executable behavioral model of the CRUISE16 booking logic.

The GitHub-hosted CI runners have no Natural runtime or ADABAS nucleus, so
the regression suite validates the business rules through a faithful Python
port of the Natural subprograms (a "driver harness" / executable
specification), plus source-conformance tests that parse the real ``.NSN``
sources (see ``source_parser.py``).

Two variants of the CONEW-N booking transaction are modeled:

* ``conew_original`` — the pre-refactor logic: availability decision made on
  a copy of CRUISE-STATUS taken from an unheld read, and contract-ID
  generation from an unheld ``READ (1) DESCENDING`` of NCCONTRACT.
* ``conew_refactored`` — the refactored logic: validation first, the
  availability test-and-set performed on the held record's current value,
  and the highest NCCONTRACT record placed in hold (CUNEW-N's fake-UPDATE
  idiom) so ID generation is serialized.

Message codes mirror CAMSG-N: 9800 booking OK (mapped to response code 0),
9902 no longer available, 9904 customer number missing, 9905 cruise number
missing, 9918 customer number not found.
"""

from dataclasses import dataclass, field

from .adabas_sim import RecordHeldError

MSG_OK = 9800
MSG_NOT_AVAILABLE = 9902
MSG_CUSTOMER_MISSING = 9904
MSG_CRUISE_MISSING = 9905
MSG_CUSTOMER_NOT_FOUND = 9918
MSG_CRUISE_LIST_SHOWN = 9807
MSG_NO_CRUISES_FOUND = 9857

#: CAMSG-N message numbers that are remapped to response code 0 ("success").
SUCCESS_CODES = {9800, 9801, 9803, 9804, 9805, 9806, 9807}

CAMSG_TEXT_EN = {
    9800: "Travel Booking successful",
    9807: "Cruise List shown",
    9857: "no Cruise Data found",
    9902: "Cruise no longer available",
    9904: "Customer Number input missing",
    9905: "Cruise Number input missing",
    9918: "Customer Number not found",
}


def camsg(msg_nr):
    """Model of CAMSG-N: returns (response_code, text)."""
    text = CAMSG_TEXT_EN.get(msg_nr, "")
    if msg_nr in SUCCESS_CODES:
        return 0, text
    return msg_nr, text


@dataclass
class BookingResult:
    msg_nr: int = 0
    rsp_code: int = 0
    rsp_text: str = ""
    new_contract_id: int = 0


def _is_n8(value):
    """Natural ``IS (N8)`` check on an alphanumeric input field."""
    v = value.strip()
    return v.isdigit() and len(v) <= 8


def _finish(result, msg_nr, new_contract_id=0):
    result.msg_nr = msg_nr
    result.rsp_code, result.rsp_text = camsg(msg_nr)
    result.new_contract_id = new_contract_id
    return result


def _validate_inputs(customer_in, cruise_in, result):
    """The DECIDE FOR FIRST CONDITION block shared by both variants.

    Returns (cruise_id, customer_id, pending_msg) or a finished result.
    ``pending_msg`` reproduces the original quirk: a format error sets the
    message number but execution still falls through to the cruise FIND.
    """
    if customer_in.strip() in ("", "0"):
        return None, None, _finish(result, MSG_CUSTOMER_MISSING)
    if cruise_in.strip() in ("", "0"):
        return None, None, _finish(result, MSG_CRUISE_MISSING)

    pending_msg = 0
    cruise_id = 0
    customer_id = 0
    if _is_n8(cruise_in):
        cruise_id = int(cruise_in)
    else:
        pending_msg = MSG_CRUISE_MISSING
    if _is_n8(customer_in):
        customer_id = int(customer_in)
    else:
        pending_msg = MSG_CUSTOMER_MISSING
    return cruise_id, customer_id, pending_msg


def _customer_exists(session, customer_id):
    return bool(session.find("NCCUSTOMER", "PERSON-ID", customer_id))


class Hooks:
    """Interleaving points used by the concurrency tests.

    Each hook is invoked at the statement boundary named after it; tests
    inject callbacks that run the competing session at exactly that point,
    reproducing a multi-user interleaving deterministically.
    """

    def __init__(self, after_status_read=None, after_maxid_read=None):
        self.after_status_read = after_status_read or (lambda: None)
        self.after_maxid_read = after_maxid_read or (lambda: None)


def conew_original(session, customer_in, cruise_in, booking_date=20260820,
                   hooks=None):
    """Pre-refactor CONEW-N behavior (defective under concurrency)."""
    hooks = hooks or Hooks()
    result = BookingResult()

    cruise_id, customer_id, pending = _validate_inputs(
        customer_in, cruise_in, result)
    if isinstance(pending, BookingResult):
        return pending
    msg_nr = pending

    found = session.find("NCCRUISE", "CRUISE-ID", cruise_id)
    if not found:
        return _finish(result, msg_nr)
    isn, cruise = found[0]

    # Defect 1: decision made on a copy of CRUISE-STATUS from an unheld
    # read; the record is only updated (and held) afterwards.
    local_avail = int(cruise["CRUISE-STATUS"])
    hooks.after_status_read()
    if local_avail <= 0:
        return _finish(result, MSG_NOT_AVAILABLE)

    session.update("NCCRUISE", isn, {"CRUISE-STATUS": str(local_avail - 1)})

    # Defect 2: highest CONTRACT-ID read without hold -> two sessions can
    # compute the same MAX+1 and store duplicate contract IDs.
    top = session.read_descending("NCCONTRACT", "CONTRACT-ID", limit=1)
    if not top:
        return _finish(result, msg_nr)  # empty-file quirk: no store, no ET
    new_id = top[0][1]["CONTRACT-ID"] + 1
    hooks.after_maxid_read()

    # HANDLE-INPUT-DATA runs only now, after the decrement was buffered.
    if not _customer_exists(session, customer_id):
        session.backout()
        return _finish(result, MSG_CUSTOMER_NOT_FOUND)

    session.store("NCCONTRACT", {
        "CONTRACT-ID": new_id,
        "PRICE": cruise["PRICE-1W"],
        "DATE-BOOKING": booking_date,
        "ID-CRUISE": cruise_id,
        "ID-CUSTOMER": customer_id,
    })
    session.et()
    return _finish(result, MSG_OK, new_contract_id=new_id)


def conew_refactored(session, customer_in, cruise_in, booking_date=20260820,
                     hooks=None):
    """Refactored CONEW-N behavior (concurrency-safe).

    Raises RecordHeldError if a required record is held by another session;
    on a real ADABAS nucleus the session would simply wait in the hold
    queue and proceed once the competitor issues ET/BT.
    """
    hooks = hooks or Hooks()
    result = BookingResult()

    cruise_id, customer_id, pending = _validate_inputs(
        customer_in, cruise_in, result)
    if isinstance(pending, BookingResult):
        return pending
    msg_nr = pending

    found = session.find("NCCRUISE", "CRUISE-ID", cruise_id)
    if not found:
        return _finish(result, msg_nr)
    isn, _ = found[0]

    try:
        # Validate before touching any record.
        if not _customer_exists(session, customer_id):
            session.backout()
            return _finish(result, MSG_CUSTOMER_NOT_FOUND)

        # Fix 1: test-and-set on the held record's current value.
        cruise = session.get_held("NCCRUISE", isn)
        local_avail = int(cruise["CRUISE-STATUS"])
        hooks.after_status_read()
        if local_avail <= 0:
            session.backout()
            return _finish(result, MSG_NOT_AVAILABLE)
        session.update("NCCRUISE", isn,
                       {"CRUISE-STATUS": str(local_avail - 1)})

        # Fix 2: hold the highest contract record (CUNEW-N fake-UPDATE
        # idiom) so MAX+1 generation is serialized until ET/BT.
        top = session.read_descending("NCCONTRACT", "CONTRACT-ID", limit=1)
        if not top:
            session.backout()
            return _finish(result, msg_nr)
        top_isn, top_rec = top[0]
        session.update("NCCONTRACT", top_isn, {})  # fake update -> hold
        top_rec = session.get_held("NCCONTRACT", top_isn)
        new_id = top_rec["CONTRACT-ID"] + 1
        hooks.after_maxid_read()

        session.store("NCCONTRACT", {
            "CONTRACT-ID": new_id,
            "PRICE": cruise["PRICE-1W"],
            "DATE-BOOKING": booking_date,
            "ID-CRUISE": cruise_id,
            "ID-CUSTOMER": customer_id,
        })
        session.et()
        return _finish(result, MSG_OK, new_contract_id=new_id)
    except RecordHeldError:
        session.backout()
        raise


@dataclass
class CruiseRow:
    cruise_id: int
    start_date: str
    end_date: str
    start_harbor: str
    destination_harbor: str
    yacht_name: str
    price_1w: str
    price_2w: str
    price_3w: str


@dataclass
class CruiseListResult:
    msg_nr: int = 0
    rsp_code: int = 0
    rsp_text: str = ""
    rows: list = field(default_factory=list)


def _edit_date(n8):
    s = f"{n8:08d}"
    return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"


def _edit_price(value):
    """MOVE EDITED (EM=ZZZZZZZZZ9.99): zero-suppressed, two decimals."""
    return f"{value:.2f}"


def crlist(session, start_harbor="", dest_harbor=""):
    """Model of CRLIST-N: list available cruises, newest start date first."""
    result = CruiseListResult()
    cruises = session.read_descending("NCCRUISE", "START-DATE")
    for _, cruise in cruises:
        if int(cruise["CRUISE-STATUS"]) == 0:
            continue  # fully booked -> skipped
        if start_harbor and cruise["START-HARBOR"] != start_harbor:
            continue
        if dest_harbor and cruise["DESTINATION-HARBOR"] != dest_harbor:
            continue
        yachts = session.find("NCYACHT", "YACHT-ID", cruise["ID-YACHT"])
        yacht_name = yachts[0][1]["YACHT-NAME"] if yachts else ""
        result.rows.append(CruiseRow(
            cruise_id=cruise["CRUISE-ID"],
            start_date=_edit_date(cruise["START-DATE"]),
            end_date=_edit_date(cruise["END-DATE"]),
            start_harbor=cruise["START-HARBOR"],
            destination_harbor=cruise["DESTINATION-HARBOR"],
            yacht_name=yacht_name,
            price_1w=_edit_price(cruise["PRICE-1W"]),
            price_2w=_edit_price(cruise["PRICE-2W"]),
            price_3w=_edit_price(cruise["PRICE-3W"]),
        ))
    result.msg_nr = MSG_NO_CRUISES_FOUND if not result.rows else MSG_CRUISE_LIST_SHOWN
    result.rsp_code, result.rsp_text = camsg(result.msg_nr)
    return result


def crget_price_selection(start_date, end_date, prices):
    """Model of CRGET-N's duration-based price selection (exercise 04).

    ``prices`` is a mapping with keys '1W', '2W', '3W'. Cruises lasting 7,
    14, or 21 days select the matching price; any other duration falls back
    to the two-week price.
    """
    from datetime import date

    def to_date(n8):
        s = f"{n8:08d}"
        return date(int(s[0:4]), int(s[4:6]), int(s[6:8]))

    days = (to_date(end_date) - to_date(start_date)).days
    if days == 7:
        return prices["1W"]
    if days == 14:
        return prices["2W"]
    if days == 21:
        return prices["3W"]
    return prices["2W"]
