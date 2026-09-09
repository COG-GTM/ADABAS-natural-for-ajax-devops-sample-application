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

Three further variants make the retry re-architecture options of
``docs/retry-rearchitecture.md`` executable. They are target-state models
and leave ``conew_refactored`` (the current-state reference) untouched:

* ``conew_with_retry`` — option 3: bounded BT + re-drive around
  ``conew_refactored`` with a defined outcome when the budget is spent, an
  ON ERROR path for abends, and an optional idempotency key.
* ``conew_optimistic`` — option 2: compare-and-swap on CRUISE-STATUS
  guarded by the unheld read value, bounded retry, 9902 after the cap.
* ``conew_target_state`` — options 4 + 5: atomic conditional decrement and
  a platform-generated CONTRACT-ID (no MAX+1 hotspot).

Message codes mirror CAMSG-N: 9800 booking OK (mapped to response code 0),
9902 no longer available, 9904 customer number missing, 9905 cruise number
missing, 9918 customer number not found.
"""

from contextlib import contextmanager
from dataclasses import dataclass, field

from .adabas_sim import (DuplicateRequestError, RecordHeldError,
                         RetryBudgetExhausted, retry_on_hold)

MSG_OK = 9800
MSG_NOT_AVAILABLE = 9902
MSG_CUSTOMER_MISSING = 9904
MSG_CRUISE_MISSING = 9905
MSG_CUSTOMER_NOT_FOUND = 9918
MSG_CRUISE_LIST_SHOWN = 9807
MSG_NO_CRUISES_FOUND = 9857

#: Proposed target-state code for "booking could not be serialized within
#: the retry/wait budget" (docs/retry-rearchitecture.md). Not part of the
#: production CAMSG-N catalog; CAMSG passes unknown numbers through
#: unchanged, so the retry variants default to 9902 and only emit this code
#: when a caller opts in.
MSG_BOOKING_BUSY = 9936

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
    #: number of transaction attempts the retry-aware variants needed
    attempts: int = 0
    #: True when an idempotent re-drive replayed a committed outcome
    replayed: bool = False


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

    def __init__(self, after_status_read=None, after_maxid_read=None,
                 after_cruise_read=None):
        self.after_status_read = after_status_read or (lambda: None)
        self.after_maxid_read = after_maxid_read or (lambda: None)
        # target-state variants only: after the unheld FIND, before the write
        self.after_cruise_read = after_cruise_read or (lambda: None)


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
            # empty-file guard: back out (release the held cruise record,
            # discard the decrement) and report a defined failure code.
            session.backout()
            return _finish(result, MSG_NOT_AVAILABLE)
        top_isn, top_rec = top[0]
        session.update("NCCONTRACT", top_isn, {})  # fake update -> hold
        top_rec = session.get_held("NCCONTRACT", top_isn)
        new_id = top_rec["CONTRACT-ID"] + 1
        hooks.after_maxid_read()

        # HANDLE-INPUT-DATA: like the source, the customer check runs
        # inside the availability branch; a failure backs out everything.
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
    except RecordHeldError:
        session.backout()
        raise


# ---------------------------------------------------------------------------
# Retry re-architecture variants (target-state models)
# ---------------------------------------------------------------------------


class RequestMismatchError(Exception):
    """An idempotency key was re-used for a request with different inputs;
    replaying the stored outcome would silently answer the wrong booking."""

    def __init__(self, request_id, stored, presented):
        super().__init__(
            f"request {request_id!r} was committed for {stored}, "
            f"re-driven with {presented}")
        self.request_id = request_id
        self.stored = stored
        self.presented = presented


def _request_fingerprint(customer_in, cruise_in, booking_date):
    return (customer_in.strip(), cruise_in.strip(), booking_date)


@contextmanager
def _on_error(session):
    """CONEW-N's ON ERROR block (lines 36-40): whatever escapes the
    transaction body — a hold conflict or an abend — BACKOUT TRANSACTION
    runs before the condition propagates, so no hold, buffered update or
    store outlives the failure."""
    try:
        yield
    except Exception:
        session.backout()
        raise


def _store_and_commit(session, result, cruise, cruise_id, customer_id,
                      booking_date, new_id):
    """HANDLE-INPUT-DATA + STORE + ET tail shared by the target-state
    variants (mirrors the same block in ``conew_refactored``)."""
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


def _max_plus_one_held(session):
    """BR-007 idiom: hold the highest NCCONTRACT record and return MAX+1,
    or None when the file is empty."""
    top = session.read_descending("NCCONTRACT", "CONTRACT-ID", limit=1)
    if not top:
        return None
    top_isn, _ = top[0]
    session.update("NCCONTRACT", top_isn, {})  # fake update -> hold
    return session.get_held("NCCONTRACT", top_isn)["CONTRACT-ID"] + 1


def conew_with_retry(session, customer_in, cruise_in, booking_date=20260820,
                     hooks=None, attempts=3, before_retry=None,
                     exhausted_msg=MSG_NOT_AVAILABLE, request_id=None):
    """Option 3: application-level retry (BT + re-drive) around
    ``conew_refactored``.

    Every attempt is a complete transaction: ``conew_refactored`` backs out
    before surfacing ``RecordHeldError``, and ``retry_on_hold`` backs out
    whatever a failed attempt might still hold, so nothing buffered or held
    survives into the next attempt. ``before_retry(attempt, error)`` is the
    backoff/jitter point (the simulation never sleeps). When ``attempts``
    is spent the caller receives ``exhausted_msg`` (9902 by default, or
    ``MSG_BOOKING_BUSY``) with ``attempts`` filled in — never an exception.

    Any other exception is the ON ERROR path: BACKOUT TRANSACTION, then the
    abend propagates (no retry of an abend).

    ``request_id`` is an idempotency key. Every attempt claims the id under
    a hold and reads the committed ledger under that same hold (one atomic
    step — a commit that lands between a separate lookup and the claim is
    still seen), replaying the stored outcome if present; a concurrent
    transaction for the same id is a hold conflict that retries — and finds
    the replay — rather than a second booking. Should a duplicate still
    reach ET (a claim path that bypassed the hold), the ET is refused and
    backed out and the committed outcome is replayed instead of surfacing
    ``DuplicateRequestError``. The ledger entry is bound to the request's inputs
    (``RequestMismatchError`` when the same id arrives with different
    inputs) and is written by the booking's own ET, describing the contract
    that ET stores.
    """
    fingerprint = _request_fingerprint(customer_in, cruise_in, booking_date)

    def replay(done, attempt):
        if done["fingerprint"] != fingerprint:
            raise RequestMismatchError(request_id, done["fingerprint"],
                                       fingerprint)
        result = _finish(BookingResult(), done["msg_nr"],
                         new_contract_id=done["new_contract_id"])
        result.replayed = True
        result.attempts = attempt
        return result

    def committed_outcome():
        # evaluated by the ET inside conew_refactored, i.e. only on 9800
        stored = session.pending_stores("NCCONTRACT")
        return {"msg_nr": MSG_OK,
                "new_contract_id": stored[-1]["CONTRACT-ID"],
                "fingerprint": fingerprint}

    def attempt_once(attempt):
        if request_id is not None:
            # may raise RecordHeldError: another transaction holds the claim
            done = session.record_request(request_id, committed_outcome)
            if done is not None:
                session.backout()  # release the claim; nothing was buffered
                return replay(done, attempt)
        try:
            res = conew_refactored(session, customer_in, cruise_in,
                                   booking_date, hooks)
        except RecordHeldError:
            raise  # conew_refactored has already backed out
        except DuplicateRequestError:
            # ET refused and backed out: the id was committed by someone
            # else after all, so the committed outcome is the answer
            return replay(session.completed_request(request_id), attempt)
        except Exception:
            session.backout()  # ON ERROR: the abend is not retried
            raise
        res.attempts = attempt
        if res.msg_nr != MSG_OK and request_id is not None:
            session.backout()  # discard the unused ledger claim
        return res

    try:
        return retry_on_hold(attempt_once, session, attempts, before_retry)
    except RetryBudgetExhausted as exc:
        result = _finish(BookingResult(), exhausted_msg)
        result.attempts = exc.attempts
        return result


def conew_hold_and_wait(session, customer_in, cruise_in,
                        booking_date=20260820, hooks=None):
    """Option 1: CONEW-N's statements as the nucleus runs them in
    hold-and-wait mode.

    Same statement order as ``conew_refactored``; the difference is what a
    hold conflict does. ``conew_refactored`` handles it as a response to
    the program (BACKOUT TRANSACTION, ``RecordHeldError`` to the caller —
    a complete transaction ends there, which is what a BT + re-drive loop
    wants). Here a conflict is not the program's business at all: it is
    left to the nucleus (``AdabasSim.submit``), which parks the session
    with its transaction *open* — the holds taken and the writes buffered
    before the blocked statement stay, exactly as a real session in the
    hold queue keeps them. That is what makes a wait cycle possible
    (``DeadlockError``) and why the wait has to be bounded
    (``HoldTimeoutError`` → BT). Anything other than a hold conflict is
    ON ERROR: BACKOUT TRANSACTION, then the abend propagates.
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
        cruise = session.get_held("NCCRUISE", isn)  # R1: may park here
        local_avail = int(cruise["CRUISE-STATUS"])
        hooks.after_status_read()
        if local_avail <= 0:
            session.backout()
            return _finish(result, MSG_NOT_AVAILABLE)
        session.update("NCCRUISE", isn,
                       {"CRUISE-STATUS": str(local_avail - 1)})
        new_id = _max_plus_one_held(session)  # R2: may park, R1 hold kept
        if new_id is None:
            session.backout()
            return _finish(result, MSG_NOT_AVAILABLE)
        hooks.after_maxid_read()
        return _store_and_commit(session, result, cruise, cruise_id,
                                 customer_id, booking_date, new_id)
    except RecordHeldError:
        raise  # the nucleus parks the session; its transaction stays open
    except Exception:
        session.backout()  # ON ERROR
        raise


def booking_outcome(ticket, timeout_msg=MSG_NOT_AVAILABLE):
    """Option 1: translate a hold-queue ``WaitTicket`` into a booking result.

    A completed ticket yields the booking's own result; a ticket abandoned
    by the nucleus (``HoldTimeoutError``/``DeadlockError``) becomes the
    defined ``timeout_msg`` (9902 by default, or ``MSG_BOOKING_BUSY``). A
    ticket abandoned by its own abend re-raises it: that is the waiter's ON
    ERROR outcome (already backed out), not a booking message.
    """
    if ticket.error is None:
        result = ticket.result
    elif isinstance(ticket.error, RecordHeldError):
        result = _finish(BookingResult(), timeout_msg)
    else:
        raise ticket.error
    result.attempts = ticket.attempts
    return result


def conew_optimistic(session, customer_in, cruise_in, booking_date=20260820,
                     hooks=None, attempts=3):
    """Option 2: optimistic compare-and-swap on CRUISE-STATUS.

    The availability decision is taken on an unheld read (as the original
    code did) but the decrement is applied with ``update_if`` guarded by
    that value, so a lost update is impossible: a stale guard — or a hold
    conflict while acquiring the row — backs out, re-reads and retries.
    The guard covers CRUISE-STATUS only, so once the swap holds the row the
    record is re-read under that hold and the contract is priced from the
    held copy, never from the unheld snapshot. After ``attempts`` failed
    swaps the caller gets 9902. Every 9902 is preceded by BACKOUT
    TRANSACTION, as in CONEW-N (lines 133-138): whatever the session had
    open when the sold-out read was taken ends with it. An abend anywhere
    in the loop takes the ON ERROR path (``_on_error``). ``attempts`` must
    be at least 1 (as for ``retry_on_hold``): a cap of 0 is a caller error,
    not a sold-out answer.
    """
    if attempts < 1:
        raise ValueError("attempts must be at least 1")
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
    hooks.after_cruise_read()

    with _on_error(session):
        for attempt in range(1, attempts + 1):
            result.attempts = attempt
            guard = cruise["CRUISE-STATUS"]
            hooks.after_status_read()
            if int(guard) <= 0:
                session.backout()
                return _finish(result, MSG_NOT_AVAILABLE)
            try:
                swapped = session.update_if(
                    "NCCRUISE", isn, "CRUISE-STATUS", guard,
                    {"CRUISE-STATUS": str(int(guard) - 1)})
                if swapped:
                    cruise = session.get_held("NCCRUISE", isn)
                    new_id = _max_plus_one_held(session)
                    if new_id is None:
                        session.backout()
                        return _finish(result, MSG_NOT_AVAILABLE)
                    hooks.after_maxid_read()
                    return _store_and_commit(session, result, cruise,
                                             cruise_id, customer_id,
                                             booking_date, new_id)
            except RecordHeldError:
                pass
            session.backout()
            cruise = session.find("NCCRUISE", "CRUISE-ID", cruise_id)[0][1]
        return _finish(result, MSG_NOT_AVAILABLE)


def conew_target_state(session, customer_in, cruise_in,
                       booking_date=20260820, hooks=None):
    """Options 4 + 5 (recommended target state).

    Capacity is taken with one atomic conditional decrement (REQ-I-001) and
    the contract identifier comes from a platform sequence (REQ-I-002), so
    the MAX+1 hold on NCCONTRACT disappears. Outcome precedence is CONEW-N's
    (9904/9905, then 9902, then 9918 after BT): a sold-out cruise answers
    9902 even for an unknown customer, exactly as ``conew_refactored`` does,
    so run-compare against the current state holds. Row contention still
    surfaces as ``RecordHeldError``
    and is resolved by the platform's lock wait (``AdabasSim.submit``) or a
    bounded re-drive (``retry_on_hold``); it and any abend leave through
    ``_on_error`` (BACKOUT TRANSACTION first). The contract is priced from
    the row as re-read under the decrement's hold, not from the unheld
    FIND.
    """
    hooks = hooks or Hooks()
    result = BookingResult(attempts=1)

    cruise_id, customer_id, pending = _validate_inputs(
        customer_in, cruise_in, result)
    if isinstance(pending, BookingResult):
        return pending
    msg_nr = pending

    found = session.find("NCCRUISE", "CRUISE-ID", cruise_id)
    if not found:
        return _finish(result, msg_nr)
    isn, _ = found[0]
    hooks.after_cruise_read()

    with _on_error(session):
        remaining = session.decrement_if_positive(
            "NCCRUISE", isn, "CRUISE-STATUS")
        hooks.after_status_read()
        if remaining is None:
            session.backout()
            return _finish(result, MSG_NOT_AVAILABLE)
        cruise = session.get_held("NCCRUISE", isn)
        new_id = session.next_id("NCCONTRACT", "CONTRACT-ID")
        hooks.after_maxid_read()
        return _store_and_commit(session, result, cruise, cruise_id,
                                 customer_id, booking_date, new_id)


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
