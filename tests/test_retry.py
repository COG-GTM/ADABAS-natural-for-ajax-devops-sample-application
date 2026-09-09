"""Retry / wait re-architecture tests for the CONEW-N booking transaction.

Companion to ``tests/test_concurrency.py``: that module proves the current
hold-and-wait refactor is safe; this module makes the target-state options
of ``docs/retry-rearchitecture.md`` executable and proves, for each, that
booking integrity survives contention:

* option 1 - hold-queue wait/resume with a bounded wait (``AdabasSim.submit``)
* option 2 - optimistic compare-and-swap with bounded retry (``conew_optimistic``)
* option 3 - application-level BT + re-drive (``conew_with_retry``)
* options 4+5 - atomic decrement + platform identifier (``conew_target_state``)

Interleavings are deterministic. A competitor "in the middle of its
transaction" is modelled with ``begin_booking`` (held GET + buffered
decrement, CONEW-N lines 79-92) and completed with ``commit_booking``
(STORE + ET, lines 114-118); the retrying session's ``before_retry`` hook is
the moment at which the competitor finishes.
"""

import unittest

from tests.harness import natural_model as nm
from tests.harness.adabas_sim import (
    REQUEST_LEDGER,
    DeadlockError,
    DuplicateRequestError,
    HoldTimeoutError,
    RecordHeldError,
    RetryBudgetExhausted,
    retry_on_hold,
)
from tests.harness.fixtures import make_db


class AbendError(RuntimeError):
    """Stands in for a Natural runtime error (NATnnnn) raised mid-program."""


def abend(text):
    """Hook callback that abends with ``text`` (fault injection)."""
    def _raise():
        raise AbendError(text)
    return _raise


def cruise_isn(db, cruise_id=196):
    return db.session("probe").find("NCCRUISE", "CRUISE-ID", cruise_id)[0][0]


def cruise_status(db, cruise_id=196):
    return db.session("probe").find(
        "NCCRUISE", "CRUISE-ID", cruise_id)[0][1]["CRUISE-STATUS"]


def contracts_for(db, cruise_id):
    return [rec for rec in db.files["NCCONTRACT"].records.values()
            if rec["ID-CRUISE"] == cruise_id]


def contract_ids(db):
    return [rec["CONTRACT-ID"] for rec in db.files["NCCONTRACT"].records.values()]


def begin_booking(session, cruise_id=196, hold_top_contract=False):
    """Competitor between its held GET and its ET (CONEW-N lines 79-102)."""
    isn, _ = session.find("NCCRUISE", "CRUISE-ID", cruise_id)[0]
    held = session.get_held("NCCRUISE", isn)
    session.update("NCCRUISE", isn,
                   {"CRUISE-STATUS": str(int(held["CRUISE-STATUS"]) - 1)})
    if hold_top_contract:
        top_isn, _ = session.read_descending(
            "NCCONTRACT", "CONTRACT-ID", limit=1)[0]
        session.update("NCCONTRACT", top_isn, {})  # fake update -> hold
    return isn


def commit_booking(session, cruise_id=196, customer_id=10000001):
    """Competitor's STORE NCCONTRACT + END TRANSACTION (lines 114-118)."""
    top_isn, top = session.read_descending(
        "NCCONTRACT", "CONTRACT-ID", limit=1)[0]
    session.update("NCCONTRACT", top_isn, {})
    session.store("NCCONTRACT", {
        "CONTRACT-ID": top["CONTRACT-ID"] + 1,
        "PRICE": 0.0,
        "DATE-BOOKING": 20260820,
        "ID-CRUISE": cruise_id,
        "ID-CUSTOMER": customer_id,
    })
    session.et()


class BoundedRetryTests(unittest.TestCase):
    """Option 3: BT + re-drive around conew_refactored (conew_with_retry)."""

    def test_loser_retries_after_commit_and_gets_9902_for_last_place(self):
        """Two sessions contend for the last place. The loser's first
        attempt meets the hold, backs out, and its retry (after the winner's
        ET) sees CRUISE-STATUS=0 -> 9902. Exactly one booking exists."""
        db = make_db(cruise_status="1")
        user1, user2 = db.session("user1"), db.session("user2")
        begin_booking(user1)

        second = nm.conew_with_retry(
            user2, "10000002", "196", attempts=3,
            before_retry=lambda attempt, err: commit_booking(user1))

        self.assertEqual((second.msg_nr, second.rsp_code), (9902, 9902))
        self.assertEqual(second.attempts, 2)
        self.assertEqual(len(contracts_for(db, 196)), 1)
        self.assertEqual(cruise_status(db), "0")
        self.assertEqual(db.hold_table, {})

    def test_retry_succeeds_when_capacity_remains_after_commit(self):
        db = make_db(cruise_status="2")
        user1, user2 = db.session("user1"), db.session("user2")
        begin_booking(user1)

        second = nm.conew_with_retry(
            user2, "10000002", "196", attempts=3,
            before_retry=lambda attempt, err: commit_booking(user1))

        self.assertEqual((second.msg_nr, second.rsp_code), (9800, 0))
        self.assertEqual(second.attempts, 2)
        self.assertEqual(second.new_contract_id, 500102)
        self.assertEqual(cruise_status(db), "0")
        self.assertEqual(len(contracts_for(db, 196)), 2)
        self.assertEqual(len(contract_ids(db)), len(set(contract_ids(db))))

    def test_budget_exhausted_under_sustained_contention_is_defined(self):
        """The competitor never releases: every attempt hits the hold. The
        caller gets a defined code, not an exception, and nothing of the
        loser's work survives (no hold, no decrement, no contract)."""
        db = make_db(cruise_status="1")
        user1, user2 = db.session("user1"), db.session("user2")
        begin_booking(user1)
        seen = []

        second = nm.conew_with_retry(
            user2, "10000002", "196", attempts=3,
            before_retry=lambda attempt, err: seen.append(
                (attempt, type(err))))

        self.assertEqual((second.msg_nr, second.rsp_code), (9902, 9902))
        self.assertEqual(second.attempts, 3)
        self.assertEqual(seen, [(1, RecordHeldError), (2, RecordHeldError)])
        self.assertEqual(db.bt_count, 3)  # one BACKOUT per failed attempt
        self.assertEqual(user2.holds, set())
        self.assertEqual(list(db.hold_table.values()), [user1])
        self.assertEqual(cruise_status(db), "1")  # user1 has not committed
        self.assertEqual(contracts_for(db, 196), [])

    def test_exhaustion_can_opt_into_distinct_target_state_code(self):
        db = make_db(cruise_status="1")
        user1, user2 = db.session("user1"), db.session("user2")
        begin_booking(user1)

        second = nm.conew_with_retry(user2, "10000002", "196", attempts=2,
                                     exhausted_msg=nm.MSG_BOOKING_BUSY)

        self.assertEqual(second.msg_nr, 9936)
        self.assertEqual(second.rsp_code, 9936)  # passes through CAMSG-N
        self.assertEqual(second.attempts, 2)
        self.assertNotIn(9936, nm.CAMSG_TEXT_EN)  # not a production code

    def test_maxid_contention_never_duplicates_contract_ids(self):
        """user1 holds the highest NCCONTRACT record (BR-007 fake UPDATE)
        on a different cruise; user2's retry after user1's ET computes
        MAX+1 from the committed 500101 -> 500102."""
        db = make_db(cruise_status="5")
        user1, user2 = db.session("user1"), db.session("user2")
        begin_booking(user1, cruise_id=196, hold_top_contract=True)

        second = nm.conew_with_retry(
            user2, "10000002", "1484", attempts=3,
            before_retry=lambda attempt, err: commit_booking(user1))

        self.assertEqual(second.msg_nr, 9800)
        self.assertEqual(second.attempts, 2)
        self.assertEqual(second.new_contract_id, 500102)
        self.assertEqual(sorted(contract_ids(db)), [500100, 500101, 500102])
        self.assertEqual(cruise_status(db, 1484), "2")

    def test_backout_on_retry_leaves_no_dangling_state(self):
        """Between attempts the loser owns no hold and has nothing
        buffered; after it gives up the cruise record is untouched."""
        db = make_db(cruise_status="1")
        user1, user2 = db.session("user1"), db.session("user2")
        cruise_key = ("NCCRUISE", begin_booking(user1))
        snapshots = []

        def inspect(attempt, err):
            snapshots.append((
                err.key, err.holder.name,
                set(user2.holds), dict(db.hold_table),
                user2._pending_updates, user2._pending_stores,
            ))

        second = nm.conew_with_retry(user2, "10000002", "196", attempts=2,
                                     before_retry=inspect)

        self.assertEqual(second.msg_nr, 9902)
        self.assertEqual(snapshots, [
            (cruise_key, "user1", set(), {cruise_key: user1}, {}, []),
        ])
        self.assertEqual(cruise_status(db), "1")
        self.assertEqual(contracts_for(db, 196), [])
        user1.backout()  # abandoned competitor
        self.assertEqual(db.hold_table, {})
        self.assertEqual(cruise_status(db), "1")

    def test_abend_mid_retry_backs_out_cleanly(self):
        """Attempt 1 meets the hold; the competitor commits; attempt 2 gets
        past the status check and abends (ON ERROR). The abend propagates,
        BACKOUT TRANSACTION has released every hold and discarded the
        decrement and the store."""
        db = make_db(cruise_status="3")
        user1, user2 = db.session("user1"), db.session("user2")
        begin_booking(user1)
        calls = {"maxid": 0}

        def abend_on_second_pass():
            calls["maxid"] += 1
            if calls["maxid"] == 1:
                raise AbendError("NAT0954 abnormal termination")

        hooks = nm.Hooks(after_maxid_read=abend_on_second_pass)
        with self.assertRaises(AbendError):
            nm.conew_with_retry(
                user2, "10000002", "196", hooks=hooks, attempts=3,
                before_retry=lambda attempt, err: commit_booking(user1))

        self.assertEqual(db.hold_table, {})
        self.assertEqual(user2._pending_updates, {})
        self.assertEqual(user2._pending_stores, [])
        self.assertEqual(cruise_status(db), "2")  # only user1's decrement
        self.assertEqual(len(contracts_for(db, 196)), 1)
        self.assertEqual(db.bt_count, 2)  # attempt-1 conflict + ON ERROR

    def test_completed_attempt_is_never_redriven(self):
        """retry_on_hold treats any returned value as terminal."""
        db = make_db()
        calls = []

        def operation(attempt):
            calls.append(attempt)
            return "committed"

        self.assertEqual(retry_on_hold(operation, db.session("user"), attempts=5),
                         "committed")
        self.assertEqual(calls, [1])

    def test_ledger_payload_abend_at_et_backs_the_transaction_out(self):
        """The ledger payload is evaluated by ET. If it abends, ET must not
        leave the transaction half-open: holds are released, nothing is
        applied, the error propagates (ON ERROR sees a backed-out session)
        and a later session can take the same records."""
        db = make_db(cruise_status="2")
        isn = cruise_isn(db)
        user1 = db.session("user1")
        begin_booking(user1)
        user1.store("NCCONTRACT", {"CONTRACT-ID": 500101, "PRICE": 0.0,
                                    "DATE-BOOKING": 20260820,
                                    "ID-CRUISE": 196, "ID-CUSTOMER": 1})
        user1.record_request("req-1", abend("payload failed"))

        with self.assertRaises(AbendError):
            user1.et()

        self.assertFalse(user1.in_transaction())
        self.assertEqual((db.hold_table, db.et_count, db.bt_count), ({}, 0, 1))
        self.assertEqual(cruise_status(db), "2")
        self.assertEqual(contract_ids(db), [500100])
        self.assertIsNone(user1.completed_request("req-1"))
        user2 = db.session("user2")
        user2.get_held("NCCRUISE", isn)  # not blocked by a leaked hold
        self.assertEqual(user2.holds, {("NCCRUISE", isn)})
        user2.backout()

    def test_failed_attempt_is_backed_out_before_the_next_one(self):
        """retry_on_hold is BT + re-drive for *any* operation, not only one
        that cleans up after itself: a raw sequence that buffers a STORE and
        then meets a hold is backed out before ``before_retry`` runs, so the
        successful attempt commits its own STORE exactly once."""
        db = make_db(cruise_status="5")
        user1, user2 = db.session("user1"), db.session("user2")
        isn = begin_booking(user1)
        seen = []

        def raw_booking(attempt):
            user2.store("NCCONTRACT", {"CONTRACT-ID": 900001, "PRICE": 0.0,
                                       "DATE-BOOKING": 20260820,
                                       "ID-CRUISE": 196,
                                       "ID-CUSTOMER": 10000002})
            held = user2.get_held("NCCRUISE", isn)  # conflicts on attempt 1
            user2.update("NCCRUISE", isn,
                         {"CRUISE-STATUS": str(int(held["CRUISE-STATUS"]) - 1)})
            user2.et()
            return attempt

        def competitor_commits(attempt, err):
            seen.append((user2.pending_stores("NCCONTRACT"), set(user2.holds),
                         db.bt_count))
            commit_booking(user1)

        self.assertEqual(retry_on_hold(raw_booking, user2, attempts=2,
                                       before_retry=competitor_commits), 2)
        self.assertEqual(seen, [([], set(), 1)])  # backed out before the retry
        self.assertEqual(contract_ids(db).count(900001), 1)
        self.assertEqual(cruise_status(db), "3")  # one decrement each
        self.assertEqual((db.et_count, db.hold_table), (2, {}))

    def test_exhausted_retry_leaves_nothing_to_commit(self):
        """retry_on_hold backs out the last attempt's buffered work before
        raising RetryBudgetExhausted: a later ET on the same session commits
        nothing stale."""
        db = make_db(cruise_status="5")
        user1, user2 = db.session("user1"), db.session("user2")
        isn = begin_booking(user1)  # never releases
        baseline = contract_ids(db)

        def raw_booking(attempt):
            user2.store("NCCONTRACT", {"CONTRACT-ID": 900000 + attempt,
                                       "ID-CRUISE": 196, "ID-CUSTOMER": 1})
            user2.get_held("NCCRUISE", isn)

        with self.assertRaises(RetryBudgetExhausted):
            retry_on_hold(raw_booking, user2, attempts=3)
        self.assertEqual(db.bt_count, 3)  # one BT per failed attempt
        self.assertFalse(user2.in_transaction())
        user2.et()  # an unrelated later ET has nothing stale to apply
        self.assertEqual(contract_ids(db), baseline)
        self.assertEqual(db.hold_table, {("NCCRUISE", isn): user1})

    def test_redrive_with_same_request_id_replays_committed_outcome(self):
        """A caller that lost the response and re-drives the same request
        gets the committed contract back: one decrement, one contract."""
        db = make_db(cruise_status="2")
        user2 = db.session("user2")

        first = nm.conew_with_retry(user2, "10000002", "196",
                                    request_id="req-42")
        again = nm.conew_with_retry(user2, "10000002", "196",
                                    request_id="req-42")

        self.assertEqual((first.msg_nr, first.replayed), (9800, False))
        self.assertEqual((again.msg_nr, again.replayed), (9800, True))
        self.assertEqual(again.new_contract_id, first.new_contract_id)
        self.assertEqual(cruise_status(db), "1")
        self.assertEqual(len(contracts_for(db, 196)), 1)
        self.assertEqual(db.et_count, 1)

    def test_failed_request_is_not_recorded_and_can_be_redriven(self):
        db = make_db(cruise_status="1")
        user1, user2 = db.session("user1"), db.session("user2")
        begin_booking(user1)

        first = nm.conew_with_retry(user2, "10000002", "196", attempts=1,
                                    request_id="req-7")
        self.assertEqual(first.msg_nr, 9902)
        self.assertIsNone(user2.completed_request("req-7"))
        user1.backout()  # competitor abandons: capacity comes back

        second = nm.conew_with_retry(user2, "10000002", "196", attempts=1,
                                     request_id="req-7")
        self.assertEqual((second.msg_nr, second.replayed), (9800, False))
        self.assertEqual(cruise_status(db), "0")

    def test_concurrent_same_request_id_books_once_and_replays(self):
        """Two sessions carry the same request id at the same time (a
        client double-submit). user2 arrives while user1 is mid-transaction:
        the ledger claim is held, so user2 conflicts, waits for user1's ET
        and then finds the committed outcome to replay. One decrement, one
        contract, both callers see the same contract id."""
        db = make_db(cruise_status="5")
        user1, user2 = db.session("user1"), db.session("user2")
        second = {}

        def user2_double_submits():
            second["result"] = nm.conew_with_retry(
                user2, "10000001", "196", attempts=1, request_id="req-9")

        hooks = nm.Hooks(after_maxid_read=user2_double_submits)
        first = nm.conew_with_retry(user1, "10000001", "196", hooks=hooks,
                                    request_id="req-9")
        self.assertEqual((first.msg_nr, first.replayed), (9800, False))
        # user2's only attempt met the ledger claim: busy, nothing booked
        self.assertEqual((second["result"].msg_nr, second["result"].attempts),
                         (9902, 1))

        redrive = nm.conew_with_retry(user2, "10000001", "196", attempts=1,
                                      request_id="req-9")
        self.assertEqual((redrive.msg_nr, redrive.replayed), (9800, True))
        self.assertEqual(redrive.new_contract_id, first.new_contract_id)
        self.assertEqual(cruise_status(db), "4")
        self.assertEqual(len(contracts_for(db, 196)), 1)
        self.assertEqual((db.et_count, db.hold_table), (1, {}))

    def test_same_request_id_retry_finds_the_replay(self):
        """The retrying twin: user2 conflicts on the ledger claim, user1
        commits in user2's before_retry, and user2's second attempt replays
        instead of booking again."""
        db = make_db(cruise_status="5")
        user1, user2 = db.session("user1"), db.session("user2")
        user1.record_request("req-11", {})  # user1 has claimed the request

        def user1_commits(attempt, err):
            self.assertEqual(err.key, (REQUEST_LEDGER, "req-11"))
            user1.backout()  # drop the bare claim, then book for real
            nm.conew_with_retry(user1, "10000001", "196", request_id="req-11")

        second = nm.conew_with_retry(user2, "10000001", "196", attempts=2,
                                     before_retry=user1_commits,
                                     request_id="req-11")
        self.assertEqual((second.msg_nr, second.replayed, second.attempts),
                         (9800, True, 2))
        self.assertEqual(cruise_status(db), "4")
        self.assertEqual(len(contracts_for(db, 196)), 1)

    def test_commit_between_lookup_and_claim_is_replayed_not_rebooked(self):
        """Lookup and claim are one step: the ledger is read *under* the
        claim hold. A twin that claims, books and commits the same id in
        the instant before user2 acquires the hold is therefore seen by
        user2's claim, which replays instead of booking a second contract
        and tripping DuplicateRequestError at ET."""
        db = make_db(cruise_status="5")
        user1, user2 = db.session("user1"), db.session("user2")
        first = {}
        real_hold = user2.hold

        def hold_with_twin_committing_first(file_name, isn):
            if file_name == REQUEST_LEDGER and not first:
                first["result"] = nm.conew_with_retry(
                    user1, "10000001", "196", request_id="req-21")
            return real_hold(file_name, isn)

        user2.hold = hold_with_twin_committing_first
        second = nm.conew_with_retry(user2, "10000001", "196", attempts=1,
                                     request_id="req-21")

        self.assertEqual((first["result"].msg_nr, first["result"].replayed),
                         (9800, False))
        self.assertEqual((second.msg_nr, second.replayed, second.attempts),
                         (9800, True, 1))
        self.assertEqual(second.new_contract_id, first["result"].new_contract_id)
        self.assertEqual(cruise_status(db), "4")
        self.assertEqual(len(contracts_for(db, 196)), 1)
        self.assertEqual((db.et_count, db.hold_table, user2.holds), (1, {}, set()))

    def test_duplicate_at_et_is_backed_out_and_replayed(self):
        """Belt and braces for a claim path that bypassed the hold: when the
        id turns out to be committed at ET, the booking is refused and
        backed out (no decrement, no contract) and the caller receives the
        committed outcome as a replay, not DuplicateRequestError."""
        db = make_db(cruise_status="5")
        user2 = db.session("user2")
        foreign = {"msg_nr": 9800, "new_contract_id": 424242,
                   "fingerprint": ("10000001", "196", 20260820)}

        def foreign_writer_commits_same_id():
            db.request_ledger["req-23"] = dict(foreign)  # bypasses the claim

        hooks = nm.Hooks(after_maxid_read=foreign_writer_commits_same_id)
        res = nm.conew_with_retry(user2, "10000001", "196", hooks=hooks,
                                  attempts=1, request_id="req-23")

        self.assertEqual((res.msg_nr, res.replayed, res.new_contract_id),
                         (9800, True, 424242))
        self.assertEqual(cruise_status(db), "5")  # user2's decrement backed out
        self.assertNotIn(424242, contract_ids(db))
        self.assertEqual(len(contracts_for(db, 196)), 0)
        self.assertEqual((db.et_count, db.bt_count), (0, 1))
        self.assertEqual((db.hold_table, user2.holds), ({}, set()))

    def test_waiter_resumed_by_ledger_release_sees_complete_outcome(self):
        """The ledger entry is written by the same ET that stores the
        contract, fully formed: a session parked on the ledger claim is
        re-driven from inside that ET and must observe the complete
        committed outcome, never an empty or half-filled entry."""
        db = make_db(cruise_status="5")
        user1, user2 = db.session("user1"), db.session("user2")
        tickets = {}

        def observe_ledger_on_resume():
            user2.hold(REQUEST_LEDGER, "req-15")  # parks behind user1's claim
            seen = user2.completed_request("req-15")
            user2.backout()
            return seen

        def user2_double_submits():
            tickets["twin"] = db.submit(user2, observe_ledger_on_resume)
            self.assertEqual(tickets["twin"].key, (REQUEST_LEDGER, "req-15"))

        hooks = nm.Hooks(after_maxid_read=user2_double_submits)
        first = nm.conew_with_retry(user1, "10000001", "196", hooks=hooks,
                                    request_id="req-15")
        twin = tickets["twin"]
        self.assertEqual((first.msg_nr, twin.done, twin.error), (9800, True, None))
        self.assertEqual(twin.result, {
            "msg_nr": 9800, "new_contract_id": first.new_contract_id,
            "fingerprint": ("10000001", "196", 20260820)})
        # the ledger holds its own copy, not an alias the caller can mutate
        twin.result["new_contract_id"] = -1
        self.assertEqual(user2.completed_request("req-15"), {
            "msg_nr": 9800, "new_contract_id": first.new_contract_id,
            "fingerprint": ("10000001", "196", 20260820)})

        redrive = nm.conew_with_retry(user2, "10000001", "196", attempts=1,
                                      request_id="req-15")
        self.assertEqual((redrive.msg_nr, redrive.replayed, redrive.new_contract_id),
                         (9800, True, first.new_contract_id))
        self.assertEqual(cruise_status(db), "4")
        self.assertEqual(len(contracts_for(db, 196)), 1)
        self.assertEqual((db.et_count, db.hold_table, db.waiting()), (1, {}, []))

    def test_reused_request_id_with_different_inputs_is_rejected(self):
        """An idempotency key is bound to its inputs: re-driving req-17 for a
        different cruise (or customer) must not replay the 196 booking as if
        it were the 1484 booking, and must not book 1484 either. Covers the
        sequential re-drive and the double-submit-then-re-drive path."""
        db = make_db(cruise_status="5")
        user1, user2 = db.session("user1"), db.session("user2")
        first = nm.conew_with_retry(user1, "10000001", "196", request_id="req-17")
        self.assertEqual(first.msg_nr, 9800)
        before_1484 = (cruise_status(db, 1484), contracts_for(db, 1484))

        with self.assertRaises(nm.RequestMismatchError) as ctx:
            nm.conew_with_retry(user1, "10000001", "1484", request_id="req-17")
        self.assertEqual(ctx.exception.stored, ("10000001", "196", 20260820))
        self.assertEqual(ctx.exception.presented, ("10000001", "1484", 20260820))
        with self.assertRaises(nm.RequestMismatchError):
            nm.conew_with_retry(user1, "10000002", "196", request_id="req-17")
        # padded input is the same request, not a mismatch (CONEW-N trims)
        same = nm.conew_with_retry(user1, " 10000001 ", "196 ", request_id="req-17")
        self.assertEqual((same.replayed, same.new_contract_id),
                         (True, first.new_contract_id))

        # double submit of req-19 with different inputs while user1 is busy
        second = {}

        def user2_double_submits():
            second["result"] = nm.conew_with_retry(
                user2, "10000001", "1484", attempts=1, request_id="req-19")

        hooks = nm.Hooks(after_maxid_read=user2_double_submits)
        nm.conew_with_retry(user1, "10000001", "196", hooks=hooks,
                            request_id="req-19")
        self.assertEqual(second["result"].msg_nr, 9902)  # busy on the claim
        with self.assertRaises(nm.RequestMismatchError):
            nm.conew_with_retry(user2, "10000001", "1484", request_id="req-19")

        self.assertEqual(cruise_status(db), "3")
        self.assertEqual((cruise_status(db, 1484), contracts_for(db, 1484)),
                         before_1484)
        self.assertEqual((db.hold_table, user1.holds, user2.holds),
                         ({}, set(), set()))

    def test_ledger_uniqueness_is_enforced_at_et(self):
        """Belt and braces: if a caller bypasses the claim and two
        transactions both buffer the same request id, the second ET is
        refused and backed out, exactly like a unique-constraint violation."""
        db = make_db(cruise_status="5")
        user1, user2 = db.session("user1"), db.session("user2")
        user1.record_request("req-13", {"msg_nr": 9800})
        user1.et()
        user2._pending_requests.append(("req-13", {"msg_nr": 9800}))
        isn = begin_booking(user2)

        with self.assertRaises(DuplicateRequestError):
            user2.et()
        self.assertEqual(cruise_status(db), "5")
        self.assertEqual(db.hold_table, {})
        self.assertNotIn(("NCCRUISE", isn), user2.holds)

    def test_customer_not_found_during_retry_still_backs_out(self):
        """BR-010 is unchanged by the retry wrapper: 9918 after a retry
        still discards the buffered decrement."""
        db = make_db(cruise_status="2")
        user1, user2 = db.session("user1"), db.session("user2")
        begin_booking(user1)

        second = nm.conew_with_retry(
            user2, "99999999", "196", attempts=3,
            before_retry=lambda attempt, err: commit_booking(user1))

        self.assertEqual(second.msg_nr, 9918)
        self.assertEqual(second.attempts, 2)
        self.assertEqual(cruise_status(db), "1")  # only user1's decrement
        self.assertEqual(db.hold_table, {})


class HoldQueueWaitTests(unittest.TestCase):
    """Option 1: wait in the hold queue, resume at the holder's ET/BT.

    The booking body is ``conew_hold_and_wait``: a hold conflict is left
    to the nucleus, so a parked session keeps its open transaction (holds
    and buffered writes) while it waits. ``conew_refactored`` backs out
    before it surfaces a conflict; the tests that use it here say so."""

    def test_waiter_resumes_at_holders_et_and_gets_9902_for_last_place(self):
        db = make_db(cruise_status="1")
        user2 = db.session("user2")
        tickets = []

        def competitor_books_at_same_time():
            tickets.append(db.submit(
                user2, lambda: nm.conew_hold_and_wait(user2, "10000002", "196")))
            self.assertFalse(tickets[0].done)  # parked, not failed

        user1 = db.session("user1")
        hooks = nm.Hooks(after_status_read=competitor_books_at_same_time)
        first = nm.conew_refactored(user1, "10000001", "196", hooks=hooks)

        self.assertEqual(first.msg_nr, 9800)
        ticket = tickets[0]
        self.assertTrue(ticket.done)  # re-driven inside user1's ET
        self.assertEqual((ticket.waits, ticket.attempts), (1, 2))
        self.assertEqual(nm.booking_outcome(ticket).msg_nr, 9902)
        self.assertEqual(len(contracts_for(db, 196)), 1)
        self.assertEqual(db.hold_table, {})
        self.assertEqual(db.waiting(), [])

    def test_waiter_succeeds_when_capacity_remains(self):
        db = make_db(cruise_status="2")
        user2 = db.session("user2")
        tickets = []
        user1 = db.session("user1")
        hooks = nm.Hooks(after_status_read=lambda: tickets.append(db.submit(
            user2, lambda: nm.conew_hold_and_wait(user2, "10000002", "196"))))

        first = nm.conew_refactored(user1, "10000001", "196", hooks=hooks)
        second = nm.booking_outcome(tickets[0])

        self.assertEqual((first.msg_nr, second.msg_nr), (9800, 9800))
        self.assertEqual(sorted((first.new_contract_id,
                                 second.new_contract_id)), [500101, 500102])
        self.assertEqual(cruise_status(db), "0")

    def test_wait_limit_zero_translates_to_defined_code(self):
        """The ADABAS "return immediately" hold option / a hold-queue
        timeout: no waiting, a defined message code instead of an abend."""
        db = make_db(cruise_status="1", wait_limit=0)
        user1, user2 = db.session("user1"), db.session("user2")
        begin_booking(user1)

        ticket = db.submit(
            user2, lambda: nm.conew_hold_and_wait(user2, "10000002", "196"))

        self.assertIsInstance(ticket.error, HoldTimeoutError)
        self.assertEqual(ticket.error.holder, user1)
        self.assertEqual(nm.booking_outcome(ticket).msg_nr, 9902)
        self.assertEqual(
            nm.booking_outcome(ticket, nm.MSG_BOOKING_BUSY).msg_nr, 9936)
        self.assertEqual(user2.holds, set())
        self.assertEqual(db.waiting(), [])

    def test_bounded_wait_gives_up_after_repeated_reparking(self):
        """The waiter needs both hotspots and keeps meeting a holder: parked
        on the cruise (user1), then — holding the cruise and its buffered
        decrement — on the highest contract (user3). With wait_limit=2 the
        next unit of waiting (a clock tick behind user3) spends the budget:
        the booking is abandoned with a defined outcome and the BT releases
        the cruise it was holding while it waited."""
        db = make_db(cruise_status="1", wait_limit=2)
        user1, user2, user3 = (db.session("user1"), db.session("user2"),
                               db.session("user3"))
        isn = begin_booking(user1)
        top_isn, _ = user3.read_descending("NCCONTRACT", "CONTRACT-ID",
                                           limit=1)[0]
        user3.update("NCCONTRACT", top_isn, {})

        ticket = db.submit(
            user2, lambda: nm.conew_hold_and_wait(user2, "10000002", "196"))
        self.assertEqual((ticket.waits, ticket.key), (1, ("NCCRUISE", isn)))
        self.assertEqual(user2.holds, set())  # blocked at R1: nothing yet

        user1.backout()  # user2 resumes, takes the cruise, meets user3
        self.assertFalse(ticket.done)
        self.assertEqual((ticket.waits, ticket.key),
                         (2, ("NCCONTRACT", top_isn)))
        self.assertEqual(user2.holds, {("NCCRUISE", isn)})  # kept while parked
        self.assertEqual(user2._pending_updates,
                         {("NCCRUISE", isn): {"CRUISE-STATUS": "0"}})
        with self.assertRaises(RecordHeldError) as held:
            user1.get_held("NCCRUISE", isn)  # the waiter still owns it
        self.assertIs(held.exception.holder, user2)

        self.assertEqual(db.tick(), [ticket])  # budget spent behind user3

        self.assertIsInstance(ticket.error, HoldTimeoutError)
        self.assertEqual((ticket.error.key, ticket.error.holder),
                         (("NCCONTRACT", top_isn), user3))
        self.assertEqual((ticket.waits, ticket.attempts), (3, 2))
        self.assertEqual(nm.booking_outcome(ticket).msg_nr, 9902)
        self.assertEqual(user2.holds, set())  # the timeout's BT released it
        self.assertEqual(cruise_status(db), "1")
        self.assertEqual(contracts_for(db, 196), [])
        self.assertEqual(db.hold_table, {("NCCONTRACT", top_isn): user3})
        user3.backout()
        self.assertEqual(db.hold_table, {})
        self.assertEqual(db.waiting(), [])

    def test_parked_waiter_keeps_its_open_transaction_and_resumes_it(self):
        """Hold-and-wait, not BT + re-drive: user2 takes the cruise (R1),
        buffers the decrement and blocks on the highest contract (R2) held
        by user1. While parked its transaction is still the one it started
        — no BT, cruise hold kept, a third session cannot take the cruise.
        When user1 releases, the resumed run finishes *that* transaction:
        one ET, no BT, one decrement, one contract."""
        db = make_db(cruise_status="3")
        user1, user2, user3 = (db.session("user1"), db.session("user2"),
                               db.session("user3"))
        isn = cruise_isn(db)
        top_isn, _ = user1.read_descending("NCCONTRACT", "CONTRACT-ID",
                                           limit=1)[0]
        user1.update("NCCONTRACT", top_isn, {})  # holds R2 only
        transaction = user2._transaction

        ticket = db.submit(
            user2, lambda: nm.conew_hold_and_wait(user2, "10000002", "196"))

        self.assertEqual((ticket.done, ticket.key),
                         (False, ("NCCONTRACT", top_isn)))
        self.assertEqual(db.hold_table[("NCCRUISE", isn)], user2)
        self.assertEqual(user2._pending_updates,
                         {("NCCRUISE", isn): {"CRUISE-STATUS": "2"}})
        self.assertEqual((user2._transaction, db.bt_count), (transaction, 0))
        with self.assertRaises(RecordHeldError):
            user3.get_held("NCCRUISE", isn)

        user1.backout()  # releases R2: user2 resumes

        self.assertEqual((ticket.done, ticket.error, ticket.attempts),
                         (True, None, 2))
        self.assertEqual(nm.booking_outcome(ticket).msg_nr, 9800)
        self.assertEqual(ticket.result.new_contract_id, 500101)
        self.assertEqual((db.et_count, db.bt_count), (1, 1))  # user1's BT only
        self.assertEqual(cruise_status(db), "2")  # one decrement, not two
        self.assertEqual(contract_ids(db), [500100, 500101])
        self.assertEqual(db.hold_table, {})
        self.assertEqual(db.waiting(), [])

    def test_bounded_wait_expires_behind_a_holder_that_never_releases(self):
        """Option 1's max-wait must also fire when the holder simply never
        ends its transaction: the parked waiter's budget is consumed by the
        clock (``tick``), and at wait_limit it times out, is backed out and
        dequeued, while the holder's transaction is untouched."""
        db = make_db(cruise_status="1", wait_limit=3)
        user1, user2 = db.session("user1"), db.session("user2")
        isn = begin_booking(user1)  # user1 holds the cruise and walks away

        ticket = db.submit(
            user2, lambda: nm.conew_hold_and_wait(user2, "10000002", "196"))
        self.assertEqual((ticket.done, ticket.waits), (False, 1))  # 1 of 3

        self.assertEqual(db.tick(), [])  # 2 of 3: still waiting
        self.assertEqual((ticket.done, ticket.waits), (False, 2))
        self.assertEqual(db.waiting(), [ticket])

        self.assertEqual(db.tick(), [ticket])  # 3 of 3: budget spent
        self.assertEqual(ticket.waits, 3)
        self.assertIsInstance(ticket.error, HoldTimeoutError)
        self.assertEqual((ticket.error.key, ticket.error.holder), (("NCCRUISE", isn), user1))
        self.assertEqual((ticket.done, ticket.attempts), (True, 1))
        self.assertEqual(nm.booking_outcome(ticket).msg_nr, 9902)
        self.assertEqual((db.waiting(), db.hold_queue, db._parked), ([], {}, {}))
        self.assertEqual(user2.holds, set())
        self.assertEqual(cruise_status(db), "1")
        self.assertEqual(contracts_for(db, 196), [])

        # the holder was never disturbed and can still commit
        self.assertEqual(db.hold_table, {("NCCRUISE", isn): user1})
        commit_booking(user1)
        self.assertEqual((cruise_status(db), db.hold_table), ("0", {}))
        self.assertEqual(db.tick(), [])  # nothing left to expire

    def test_simultaneous_timeouts_do_not_resume_each_other(self):
        """Two waiters expire in the same tick and the first one's backout
        releases the record the second is parked on. Both must time out
        (the second is not re-driven by a release that only happened
        because its neighbour gave up), be dequeued and backed out, and the
        never-releasing holder is untouched."""
        db = make_db(cruise_status="5", wait_limit=2)
        holder, user2, user3 = (db.session(n) for n in ("holder", "user2", "user3"))
        isn = begin_booking(holder)  # holds the cruise and walks away
        top_isn, _ = db.session("probe").read_descending(
            "NCCONTRACT", "CONTRACT-ID", limit=1)[0]

        def user2_op():
            user2.update("NCCONTRACT", top_isn, {})  # holds the top contract
            user2.get_held("NCCRUISE", isn)            # parks behind holder
            user2.et()

        def user3_op():
            user3.update("NCCONTRACT", top_isn, {})  # parks behind user2
            user3.et()

        t2 = db.submit(user2, user2_op)
        t3 = db.submit(user3, user3_op)
        self.assertEqual(db.waiting(), [t2, t3])
        self.assertEqual((t2.key, t3.key),
                         (("NCCRUISE", isn), ("NCCONTRACT", top_isn)))

        self.assertEqual(db.tick(), [t2, t3])

        self.assertIsInstance(t2.error, HoldTimeoutError)
        self.assertIsInstance(t3.error, HoldTimeoutError)
        self.assertEqual((t2.error.key, t2.error.holder), (("NCCRUISE", isn), holder))
        self.assertEqual((t3.error.key, t3.error.holder), (("NCCONTRACT", top_isn), user2))
        self.assertEqual((t2.attempts, t3.attempts), (1, 1))  # user3 was not re-driven
        self.assertEqual((db.waiting(), db.hold_queue, db._parked), ([], {}, {}))
        self.assertEqual((user2.holds, user3.holds), (set(), set()))
        self.assertEqual(db.hold_table, {("NCCRUISE", isn): holder})
        self.assertEqual(db.et_count, 0)

        commit_booking(holder)
        self.assertEqual((cruise_status(db), db.hold_table), ("4", {}))

    def test_resumed_waiter_does_not_repeat_its_pre_conflict_work(self):
        """A re-drive equals a resume: work the operation buffered before it
        blocked (a STORE) is discarded and re-done once by the re-run, and
        work the session had buffered *before* ``submit`` is kept. One
        submission, one contract per STORE, one decrement."""
        db = make_db(cruise_status="5")
        user1, user2 = db.session("user1"), db.session("user2")
        isn = begin_booking(user1)
        row = {"PRICE": 0.0, "DATE-BOOKING": 20260820,
               "ID-CRUISE": 196, "ID-CUSTOMER": 10000002}
        user2.store("NCCONTRACT", dict(row, **{"CONTRACT-ID": 900000}))  # pre-submit
        runs = []

        def raw_booking():
            runs.append(len(user2.pending_stores("NCCONTRACT")))
            user2.store("NCCONTRACT", dict(row, **{"CONTRACT-ID": 900001}))
            held = user2.get_held("NCCRUISE", isn)  # blocks on the first run
            user2.update("NCCRUISE", isn,
                         {"CRUISE-STATUS": str(int(held["CRUISE-STATUS"]) - 1)})
            user2.et()

        ticket = db.submit(user2, raw_booking)
        self.assertFalse(ticket.done)
        self.assertEqual(len(user2.pending_stores("NCCONTRACT")), 2)  # parked as-is

        commit_booking(user1)  # resumes user2

        self.assertEqual((ticket.done, ticket.error, ticket.attempts), (True, None, 2))
        self.assertEqual(runs, [1, 1])  # the re-run started from the checkpoint
        self.assertEqual(contract_ids(db).count(900000), 1)
        self.assertEqual(contract_ids(db).count(900001), 1)
        self.assertEqual(cruise_status(db), "3")  # user1's and user2's decrement
        self.assertEqual((db.et_count, db.hold_table), (2, {}))

    def test_checkpoint_dies_with_the_transaction_that_backed_out(self):
        """user2 has an uncommitted re-pricing of cruise 1484 when it submits
        a booking for 196. The booking meets user1's hold and, as CONEW-N
        does, backs out: that BT ends user2's transaction, releasing 1484
        and discarding the re-pricing. A competitor then re-prices 1484 and
        commits. When user2 is resumed its checkpoint must not resurrect
        the discarded update (it no longer holds 1484), so the resumed
        booking's ET cannot overwrite the competitor's commit."""
        db = make_db(cruise_status="5")
        other = cruise_isn(db, 1484)
        user1, user2 = db.session("user1"), db.session("user2")
        begin_booking(user1)
        user2.update("NCCRUISE", other, {"PRICE-1W": 111.0})  # pre-submit

        ticket = db.submit(
            user2, lambda: nm.conew_refactored(user2, "10000002", "196"))
        self.assertFalse(ticket.done)
        self.assertEqual(user2.holds, set())  # the model's BT released 1484

        pricing = db.session("pricing")
        pricing.update("NCCRUISE", other, {"PRICE-1W": 222.0})
        pricing.et()
        commit_booking(user1)  # resumes user2

        self.assertEqual((ticket.done, ticket.error, ticket.result.msg_nr),
                         (True, None, 9800))
        self.assertEqual(
            db.files["NCCRUISE"].records[other]["PRICE-1W"], 222.0)
        self.assertEqual(cruise_status(db), "3")
        self.assertEqual(db.hold_table, {})

    def test_fifo_hold_queue_is_fair_and_starvation_free(self):
        """Three waiters on the last two places resume in arrival order:
        the first two book, the third gets 9902, nobody is left parked."""
        db = make_db(cruise_status="2")
        user1 = db.session("user1")
        begin_booking(user1)
        waiters = [db.session(f"user{i}") for i in (2, 3, 4)]
        order = []

        def booking(session):
            def run():
                order.append(session.name)
                return nm.conew_hold_and_wait(session, "10000002", "196")
            return run

        tickets = [db.submit(s, booking(s)) for s in waiters]
        self.assertEqual([t.done for t in tickets], [False] * 3)
        self.assertEqual(order, ["user2", "user3", "user4"])

        user1.backout()  # abandons its place: capacity 2 is back

        self.assertEqual([t.done for t in tickets], [True] * 3)
        self.assertEqual(order[3:], ["user2", "user3", "user4"])
        self.assertEqual([nm.booking_outcome(t).msg_nr for t in tickets],
                         [9800, 9800, 9902])
        self.assertEqual(cruise_status(db), "0")
        self.assertEqual(db.hold_table, {})
        self.assertEqual(db.waiting(), [])

    def test_interleaved_cruise_and_contract_holds_resolve(self):
        """user1 holds both hotspots (cruise 196 + highest contract). user2
        (cruise 1484) takes its own cruise and parks on the contract record
        still holding it; user3 (cruise 196) parks on the cruise record.
        Both bookings take R1 before R2, so the kept hold cannot close a
        cycle. user1's ET releases both; each waiter resumes, no hold is
        left, and every CONTRACT-ID is unique."""
        db = make_db(cruise_status="5")
        user2, user3 = db.session("user2"), db.session("user3")
        tickets = {}

        def others_arrive():
            tickets["u2"] = db.submit(
                user2, lambda: nm.conew_hold_and_wait(user2, "10000002", "1484"))
            tickets["u3"] = db.submit(
                user3, lambda: nm.conew_hold_and_wait(user3, "10000002", "196"))
            self.assertEqual([t.key[0] for t in db.waiting()],
                             ["NCCONTRACT", "NCCRUISE"])
            self.assertEqual(user2.holds, {("NCCRUISE", cruise_isn(db, 1484))})
            self.assertEqual(user3.holds, set())

        user1 = db.session("user1")
        hooks = nm.Hooks(after_maxid_read=others_arrive)
        first = nm.conew_refactored(user1, "10000001", "196", hooks=hooks)

        outcomes = [first] + [nm.booking_outcome(tickets[k])
                              for k in ("u2", "u3")]
        self.assertEqual([o.msg_nr for o in outcomes], [9800] * 3)
        self.assertEqual(sorted(o.new_contract_id for o in outcomes),
                         [500101, 500102, 500103])
        self.assertEqual(db.hold_table, {})
        self.assertEqual(db.waiting(), [])
        self.assertEqual(cruise_status(db, 196), "3")
        self.assertEqual(cruise_status(db, 1484), "2")

    def test_wait_for_cycle_is_detected_instead_of_blocking_forever(self):
        """Pure hold-and-wait failure mode: two raw sessions each hold one
        record and wait for the other's. The simulator refuses to close the
        cycle; the victim is backed out and the survivor resumes."""
        db = make_db()
        a, b = db.session("A"), db.session("B")
        cruise, contract = ("NCCRUISE", 1), ("NCCONTRACT", 1)
        a.hold(*cruise)
        b.hold(*contract)

        ta = db.submit(a, lambda: a.hold(*contract))  # A parks, keeps cruise
        self.assertFalse(ta.done)
        tb = db.submit(b, lambda: b.hold(*cruise))    # would close the cycle

        self.assertIsInstance(tb.error, DeadlockError)
        self.assertTrue(ta.done and ta.error is None)  # A got the contract
        self.assertEqual(set(db.hold_table), {cruise, contract})
        self.assertEqual(set(db.hold_table.values()), {a})
        a.backout()
        self.assertEqual(db.hold_table, {})

    def test_model_releases_before_waiting_so_no_cycle_forms(self):
        """conew_refactored backs out before it surfaces a hold conflict,
        so two bookings that need each other's records can never deadlock:
        the second one waits with empty hands and resumes after the first."""
        db = make_db(cruise_status="5")
        user2 = db.session("user2")
        tickets = []

        def competitor_holds_the_other_hotspot():
            tickets.append(db.submit(
                user2, lambda: nm.conew_refactored(user2, "10000002", "1484")))
            self.assertEqual(user2.holds, set())  # parked without holds

        user1 = db.session("user1")
        hooks = nm.Hooks(after_maxid_read=competitor_holds_the_other_hotspot)
        first = nm.conew_refactored(user1, "10000001", "196", hooks=hooks)

        self.assertEqual(first.msg_nr, 9800)
        self.assertIsNone(tickets[0].error)
        self.assertEqual(tickets[0].result.msg_nr, 9800)

    def test_resumed_waiter_abend_stays_with_the_waiter(self):
        """user2 is parked on the cruise; when user1's ET resumes it, user2
        re-acquires the hold and then abends. The abend must not surface
        through user1's ET (user1 is already committed), and user2's
        transaction is backed out: no hold, no decrement, no contract."""
        db = make_db(cruise_status="3")
        user1, user2 = db.session("user1"), db.session("user2")
        begin_booking(user1)
        hooks = nm.Hooks(after_maxid_read=abend("NAT0954 abnormal termination"))

        ticket = db.submit(user2, lambda: nm.conew_hold_and_wait(
            user2, "10000002", "196", hooks=hooks))
        self.assertFalse(ticket.done)

        commit_booking(user1)  # returns normally

        self.assertTrue(ticket.done)
        self.assertIsInstance(ticket.error, AbendError)
        self.assertEqual(user2.holds, set())
        self.assertEqual(user2._pending_updates, {})
        self.assertEqual(db.hold_table, {})
        self.assertEqual(cruise_status(db), "2")  # only user1's decrement
        self.assertEqual(len(contracts_for(db, 196)), 1)
        with self.assertRaises(AbendError):
            nm.booking_outcome(ticket)


class OptimisticRetryTests(unittest.TestCase):
    """Option 2: compare-and-swap on CRUISE-STATUS with a retry cap."""

    def test_stale_guard_retries_and_gets_9902_for_last_place(self):
        """Both sessions read CRUISE-STATUS=1 without hold. The competitor
        commits first; the swap guarded by '1' fails, the re-read sees '0'
        -> 9902 on attempt 2. No overbooking."""
        db = make_db(cruise_status="1")
        user2 = db.session("user2")
        results = []

        def competitor_commits_between_read_and_swap():
            if not results:
                results.append(nm.conew_refactored(user2, "10000002", "196"))

        user1 = db.session("user1")
        hooks = nm.Hooks(
            after_status_read=competitor_commits_between_read_and_swap)
        first = nm.conew_optimistic(user1, "10000001", "196", hooks=hooks)

        self.assertEqual(results[0].msg_nr, 9800)
        self.assertEqual((first.msg_nr, first.attempts), (9902, 2))
        self.assertEqual(len(contracts_for(db, 196)), 1)
        self.assertEqual(cruise_status(db), "0")
        self.assertEqual(db.hold_table, {})

    def test_price_change_between_read_and_swap_is_not_booked_stale(self):
        """The guard covers CRUISE-STATUS only. A competitor re-prices the
        cruise between the unheld read and the swap; the swap still succeeds
        (capacity unchanged) but the contract must carry the price as
        re-read under the hold, not the snapshot's."""
        db = make_db(cruise_status="3")
        isn = cruise_isn(db)
        pricing = db.session("pricing")

        def competitor_reprices():
            if not pricing.in_transaction() and db.et_count == 0:
                pricing.update("NCCRUISE", isn, {"PRICE-1W": 9999.0})
                pricing.et()

        user1 = db.session("user1")
        first = nm.conew_optimistic(
            user1, "10000001", "196",
            hooks=nm.Hooks(after_status_read=competitor_reprices))

        self.assertEqual((first.msg_nr, first.attempts), (9800, 1))
        self.assertEqual(contracts_for(db, 196)[-1]["PRICE"], 9999.0)
        self.assertEqual(cruise_status(db), "2")

    def test_stale_guard_retries_and_succeeds_when_capacity_remains(self):
        db = make_db(cruise_status="2")
        user2 = db.session("user2")
        results = []

        def competitor_commits_once():
            if not results:
                results.append(nm.conew_refactored(user2, "10000002", "196"))

        user1 = db.session("user1")
        hooks = nm.Hooks(after_status_read=competitor_commits_once)
        first = nm.conew_optimistic(user1, "10000001", "196", hooks=hooks)

        self.assertEqual((first.msg_nr, first.attempts), (9800, 2))
        self.assertEqual(sorted((first.new_contract_id,
                                 results[0].new_contract_id)),
                         [500101, 500102])
        self.assertEqual(cruise_status(db), "0")

    def test_retry_cap_under_sustained_contention_returns_9902(self):
        """A competitor commits between every read and swap: after the cap
        the caller gets 9902, capacity reflects only the competitor's
        bookings and no hold or buffered decrement remains."""
        db = make_db(cruise_status="5")
        user2 = db.session("user2")
        user1 = db.session("user1")
        hooks = nm.Hooks(after_status_read=lambda: nm.conew_refactored(
            user2, "10000002", "196"))

        first = nm.conew_optimistic(user1, "10000001", "196", hooks=hooks,
                                    attempts=3)

        self.assertEqual((first.msg_nr, first.rsp_code), (9902, 9902))
        self.assertEqual(first.attempts, 3)
        self.assertEqual(cruise_status(db), "2")  # 3 competitor bookings
        self.assertEqual(len(contracts_for(db, 196)), 3)
        self.assertEqual(db.hold_table, {})
        self.assertEqual(user1._pending_updates, {})

    def test_hold_conflict_during_swap_counts_as_a_retry(self):
        """Attempt 1: the swap meets user1's hold. Attempt 2: user1 commits
        after the unheld read, so the guard is stale. Attempt 3 swaps."""
        db = make_db(cruise_status="3")
        user1, user2 = db.session("user1"), db.session("user2")
        begin_booking(user1)
        passes = []

        def competitor_finishes_after_first_conflict():
            passes.append(len(passes) + 1)
            if len(passes) == 2:
                commit_booking(user1)

        hooks = nm.Hooks(
            after_status_read=competitor_finishes_after_first_conflict)
        first = nm.conew_optimistic(user2, "10000002", "196", hooks=hooks,
                                    attempts=3)

        self.assertEqual((first.msg_nr, first.attempts), (9800, 3))
        self.assertEqual(cruise_status(db), "1")
        self.assertEqual(sorted(contract_ids(db)), [500100, 500101, 500102])
        self.assertEqual(db.hold_table, {})

    def test_abend_after_swap_backs_out(self):
        """ON ERROR after the swap took the row and the MAX+1 hold: both
        holds and the buffered decrement are discarded."""
        db = make_db(cruise_status="3")
        user2 = db.session("user2")
        hooks = nm.Hooks(after_maxid_read=abend("NAT3009 transaction lost"))

        with self.assertRaises(AbendError):
            nm.conew_optimistic(user2, "10000002", "196", hooks=hooks)

        self.assertEqual(db.hold_table, {})
        self.assertEqual(user2._pending_updates, {})
        self.assertEqual(cruise_status(db), "3")
        self.assertEqual(contract_ids(db), [500100])
        self.assertEqual(db.bt_count, 1)


class TargetStateTests(unittest.TestCase):
    """Options 4 + 5: atomic conditional decrement + platform identifier."""

    def test_atomic_decrement_never_goes_negative(self):
        db = make_db(cruise_status="1")
        outcomes = [
            nm.conew_target_state(db.session(f"user{i}"), "10000001", "196")
            for i in range(3)
        ]
        self.assertEqual([o.msg_nr for o in outcomes], [9800, 9902, 9902])
        self.assertEqual(cruise_status(db), "0")
        self.assertEqual(db.hold_table, {})

    def test_repeated_conditional_decrements_each_consume_one_unit(self):
        """Within one transaction decrement_if_positive reads through its own
        pending write: two decrements take two places, the third finds zero,
        and ET commits the count the transaction saw."""
        db = make_db(cruise_status="2")
        isn = cruise_isn(db)
        user = db.session("user")

        taken = [user.decrement_if_positive("NCCRUISE", isn, "CRUISE-STATUS")
                 for _ in range(3)]

        self.assertEqual(taken, [1, 0, None])
        self.assertEqual(user.holds, {("NCCRUISE", isn)})  # a refusal keeps
        self.assertFalse(user.update_if(  # the hold the earlier calls took
            "NCCRUISE", isn, "CRUISE-STATUS", "2", {"CRUISE-STATUS": "1"}))
        user.et()
        self.assertEqual(cruise_status(db), "0")
        self.assertEqual(db.hold_table, {})

    def test_contract_is_priced_from_the_row_held_by_the_decrement(self):
        """A competitor re-prices the cruise after the unheld FIND and before
        the decrement; the contract carries the committed price at the time
        the row was held, not the FIND snapshot's."""
        db = make_db(cruise_status="3")
        isn = cruise_isn(db)
        pricing = db.session("pricing")

        def competitor_reprices():
            pricing.update("NCCRUISE", isn, {"PRICE-1W": 9999.0})
            pricing.et()

        first = nm.conew_target_state(
            db.session("user1"), "10000001", "196",
            hooks=nm.Hooks(after_cruise_read=competitor_reprices))

        self.assertEqual(first.msg_nr, 9800)
        self.assertEqual(contracts_for(db, 196)[-1]["PRICE"], 9999.0)
        self.assertEqual(cruise_status(db), "2")

    def test_sequence_ids_remove_the_contract_hotspot(self):
        """user2 books a different cruise while user1 is between its id
        allocation and its ET: no NCCONTRACT hold exists to wait for, so
        user2 completes immediately and both ids are distinct."""
        db = make_db(cruise_status="5")
        user2 = db.session("user2")
        results = []
        user1 = db.session("user1")
        hooks = nm.Hooks(after_maxid_read=lambda: results.append(
            nm.conew_target_state(user2, "10000002", "1484")))

        first = nm.conew_target_state(user1, "10000001", "196", hooks=hooks)

        self.assertEqual((first.msg_nr, results[0].msg_nr), (9800, 9800))
        self.assertEqual((first.new_contract_id, results[0].new_contract_id),
                         (500101, 500102))
        self.assertEqual(len(contract_ids(db)), len(set(contract_ids(db))))

    def test_capacity_contention_resolves_via_lock_wait(self):
        """The one remaining hotspot (the cruise row) is resolved by the
        platform's lock wait: the waiter resumes at ET and sees 0 -> 9902."""
        db = make_db(cruise_status="1")
        user2 = db.session("user2")
        tickets = []
        user1 = db.session("user1")
        hooks = nm.Hooks(after_status_read=lambda: tickets.append(db.submit(
            user2, lambda: nm.conew_target_state(user2, "10000002", "196"))))

        first = nm.conew_target_state(user1, "10000001", "196", hooks=hooks)

        self.assertEqual(first.msg_nr, 9800)
        self.assertEqual(nm.booking_outcome(tickets[0]).msg_nr, 9902)
        self.assertEqual(len(contracts_for(db, 196)), 1)
        self.assertEqual(db.hold_table, {})

    def test_bounded_redrive_of_target_state_is_defined_on_exhaustion(self):
        db = make_db(cruise_status="1")
        user1, user2 = db.session("user1"), db.session("user2")
        begin_booking(user1)

        with self.assertRaises(RetryBudgetExhausted) as ctx:
            retry_on_hold(lambda attempt: nm.conew_target_state(
                user2, "10000002", "196"), user2, attempts=2)

        self.assertEqual(ctx.exception.attempts, 2)
        self.assertEqual(user2.holds, set())
        self.assertEqual(cruise_status(db), "1")

    def test_abend_after_decrement_backs_out(self):
        """ON ERROR between the conditional decrement and the STORE: the
        decrement is discarded, the row is released; the consumed sequence
        value is the only trace (a gap, as with any database sequence)."""
        db = make_db(cruise_status="3")
        user2 = db.session("user2")
        for hook_name in ("after_status_read", "after_maxid_read"):
            hooks = nm.Hooks(**{hook_name: abend("NAT0954 abnormal termination")})
            with self.assertRaises(AbendError):
                nm.conew_target_state(user2, "10000002", "196", hooks=hooks)
            self.assertEqual(db.hold_table, {})
            self.assertEqual(user2._pending_updates, {})
            self.assertEqual(user2._pending_stores, [])
            self.assertEqual(cruise_status(db), "3")
            self.assertEqual(contract_ids(db), [500100])
        self.assertEqual(db.bt_count, 2)

    def test_customer_not_found_and_sold_out_codes_are_preserved(self):
        db = make_db(cruise_status="1")
        s = db.session()
        self.assertEqual(nm.conew_target_state(s, "99999999", "196").msg_nr,
                         9918)
        self.assertEqual(nm.conew_target_state(s, "", "196").msg_nr, 9904)
        self.assertEqual(nm.conew_target_state(s, "10000001", "").msg_nr,
                         9905)
        self.assertEqual(nm.conew_target_state(s, "10000001", "696").msg_nr,
                         9902)
        self.assertEqual(cruise_status(db), "1")
        self.assertEqual(db.hold_table, {})

    def test_outcome_precedence_matches_the_current_state(self):
        """An unknown customer asking for a sold-out cruise gets 9902 from
        every variant, as CONEW-N answers (capacity is checked before the
        customer); with capacity left the same request gets 9918 and the
        buffered decrement is backed out. No variant re-orders the codes."""
        variants = {
            "refactored": nm.conew_refactored,
            "with_retry": nm.conew_with_retry,
            "optimistic": nm.conew_optimistic,
            "target_state": nm.conew_target_state,
        }
        for status, expected in (("0", 9902), ("1", 9918)):
            for name, variant in variants.items():
                db = make_db(cruise_status=status)
                res = variant(db.session("user"), "99999999", "196")
                self.assertEqual((name, status, res.msg_nr),
                                 (name, status, expected))
                self.assertEqual(cruise_status(db), status)
                self.assertEqual(contract_ids(db), [500100])
                self.assertEqual(db.hold_table, {})


if __name__ == "__main__":
    unittest.main()
