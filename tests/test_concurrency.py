"""Concurrency regression tests for the CONEW-N refactor.

These tests interleave two simulated user sessions at the exact statement
boundaries where the original CONEW-N is unsafe, and prove:

1. the original logic loses updates on NCCRUISE.CRUISE-STATUS (overbooking)
   and generates duplicate NCCONTRACT.CONTRACT-ID values, and
2. the refactored logic serializes both through ADABAS record holds, so the
   defects cannot occur.

See docs/concurrency-refactor.md for the full analysis.
"""

import unittest

from tests.harness import natural_model as nm
from tests.harness.adabas_sim import RecordHeldError
from tests.harness.fixtures import make_db


class OriginalLogicDefectTests(unittest.TestCase):
    """Characterize the defects so the failure mode stays documented."""

    def test_race_on_cruise_status_overbooks_last_slot(self):
        """Two users book the last slot; both read CRUISE-STATUS=1 before
        either update lands, so both bookings succeed for one place."""
        db = make_db(cruise_status="1")
        user2 = db.session("user2")
        results = []

        def competitor_books_at_same_time():
            results.append(nm.conew_original(user2, "10000002", "196"))

        user1 = db.session("user1")
        hooks = nm.Hooks(after_status_read=competitor_books_at_same_time)
        first = nm.conew_original(user1, "10000001", "196", hooks=hooks)

        self.assertEqual(first.msg_nr, 9800)
        self.assertEqual(results[0].msg_nr, 9800)  # overbooked!
        contracts = [
            rec for rec in db.files["NCCONTRACT"].records.values()
            if rec["ID-CRUISE"] == 196
        ]
        self.assertEqual(len(contracts), 2)  # two contracts, one place

    def test_unheld_maxid_read_generates_duplicate_contract_ids(self):
        db = make_db(cruise_status="5")
        user2 = db.session("user2")
        results = []

        def competitor_books_at_same_time():
            results.append(nm.conew_original(user2, "10000002", "1484"))

        user1 = db.session("user1")
        hooks = nm.Hooks(after_maxid_read=competitor_books_at_same_time)
        first = nm.conew_original(user1, "10000001", "196", hooks=hooks)

        self.assertEqual(first.msg_nr, 9800)
        self.assertEqual(results[0].msg_nr, 9800)
        # both sessions computed MAX(CONTRACT-ID)+1 = 500101
        self.assertEqual(first.new_contract_id, results[0].new_contract_id)
        ids = [rec["CONTRACT-ID"]
               for rec in db.files["NCCONTRACT"].records.values()]
        self.assertEqual(len(ids), len(set(ids)) + 1)  # one duplicate key


class RefactoredLogicSafetyTests(unittest.TestCase):
    def test_competitor_blocks_until_first_booking_commits(self):
        """With the held test-and-set, the second session cannot read the
        cruise record between the first session's check and its ET: it
        lands in the hold queue (RecordHeldError in the simulation)."""
        db = make_db(cruise_status="1")
        user2 = db.session("user2")
        outcome = {}

        def competitor_books_at_same_time():
            try:
                nm.conew_refactored(user2, "10000002", "196")
                outcome["result"] = "ran"
            except RecordHeldError:
                outcome["result"] = "queued"

        user1 = db.session("user1")
        hooks = nm.Hooks(after_status_read=competitor_books_at_same_time)
        first = nm.conew_refactored(user1, "10000001", "196", hooks=hooks)

        self.assertEqual(first.msg_nr, 9800)
        self.assertEqual(outcome["result"], "queued")

        # once user1 committed, user2 retries and correctly gets 9902
        second = nm.conew_refactored(user2, "10000002", "196")
        self.assertEqual(second.msg_nr, 9902)
        contracts = [
            rec for rec in db.files["NCCONTRACT"].records.values()
            if rec["ID-CRUISE"] == 196
        ]
        self.assertEqual(len(contracts), 1)  # exactly one booking

    def test_no_duplicate_contract_ids_under_contention(self):
        """The fake-UPDATE hold on the highest contract record serializes
        MAX+1 generation across sessions."""
        db = make_db(cruise_status="5")
        user2 = db.session("user2")
        outcome = {}

        def competitor_books_at_same_time():
            try:
                nm.conew_refactored(user2, "10000002", "1484")
                outcome["result"] = "ran"
            except RecordHeldError:
                outcome["result"] = "queued"

        user1 = db.session("user1")
        hooks = nm.Hooks(after_maxid_read=competitor_books_at_same_time)
        first = nm.conew_refactored(user1, "10000001", "196", hooks=hooks)

        self.assertEqual(first.msg_nr, 9800)
        self.assertEqual(outcome["result"], "queued")

        second = nm.conew_refactored(user2, "10000002", "1484")
        self.assertEqual(second.msg_nr, 9800)
        ids = [rec["CONTRACT-ID"]
               for rec in db.files["NCCONTRACT"].records.values()]
        self.assertEqual(len(ids), len(set(ids)))  # all unique
        self.assertEqual(sorted((first.new_contract_id,
                                 second.new_contract_id)),
                         [500101, 500102])

    def test_sequential_bookings_never_oversell(self):
        """N+1 sequential booking attempts against N slots: exactly N
        succeed and the rest get 9902."""
        slots = 3
        db = make_db(cruise_status=str(slots))
        outcomes = [
            nm.conew_refactored(db.session(f"user{i}"), "10000001", "196").msg_nr
            for i in range(slots + 2)
        ]
        self.assertEqual(outcomes.count(9800), slots)
        self.assertEqual(outcomes.count(9902), 2)
        status = db.session().find(
            "NCCRUISE", "CRUISE-ID", 196)[0][1]["CRUISE-STATUS"]
        self.assertEqual(status, "0")


if __name__ == "__main__":
    unittest.main()
