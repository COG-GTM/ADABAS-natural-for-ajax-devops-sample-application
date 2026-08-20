"""Regression tests for the CONEW-N booking transaction (single user).

Both the original and the refactored logic must produce identical
single-user behavior: the refactor only changes what happens under
concurrent access (covered in test_concurrency.py).
"""

import unittest

from tests.harness import natural_model as nm
from tests.harness.fixtures import make_db


BOTH_VARIANTS = (nm.conew_original, nm.conew_refactored)


class BookingSuccessTests(unittest.TestCase):
    def test_successful_booking_returns_9800_mapped_to_zero(self):
        for conew in BOTH_VARIANTS:
            with self.subTest(variant=conew.__name__):
                db = make_db()
                result = conew(db.session(), "10000001", "196")
                self.assertEqual(result.msg_nr, 9800)
                self.assertEqual(result.rsp_code, 0)
                self.assertIn("successful", result.rsp_text)

    def test_availability_decrements_by_one_on_booking(self):
        for conew in BOTH_VARIANTS:
            with self.subTest(variant=conew.__name__):
                db = make_db(cruise_status="5")
                conew(db.session(), "10000001", "196")
                cruise = db.session().find("NCCRUISE", "CRUISE-ID", 196)[0][1]
                self.assertEqual(cruise["CRUISE-STATUS"], "4")

    def test_contract_id_is_previous_maximum_plus_one(self):
        for conew in BOTH_VARIANTS:
            with self.subTest(variant=conew.__name__):
                db = make_db()
                result = conew(db.session(), "10000001", "196")
                self.assertEqual(result.new_contract_id, 500101)

    def test_price_selected_is_one_week_price(self):
        """CONEW-N books one week only: PRICE := NCCRUISE.PRICE-1W."""
        for conew in BOTH_VARIANTS:
            with self.subTest(variant=conew.__name__):
                db = make_db()
                result = conew(db.session(), "10000001", "196")
                contract = db.session().find(
                    "NCCONTRACT", "CONTRACT-ID", result.new_contract_id)[0][1]
                self.assertEqual(contract["PRICE"], 1290.0)

    def test_contract_records_customer_cruise_and_booking_date(self):
        for conew in BOTH_VARIANTS:
            with self.subTest(variant=conew.__name__):
                db = make_db()
                result = conew(db.session(), "10000001", "196",
                               booking_date=20260820)
                contract = db.session().find(
                    "NCCONTRACT", "CONTRACT-ID", result.new_contract_id)[0][1]
                self.assertEqual(contract["ID-CUSTOMER"], 10000001)
                self.assertEqual(contract["ID-CRUISE"], 196)
                self.assertEqual(contract["DATE-BOOKING"], 20260820)


class InputValidationTests(unittest.TestCase):
    def test_blank_customer_id_returns_9904(self):
        for conew in BOTH_VARIANTS:
            for bad in ("", " ", "0"):
                with self.subTest(variant=conew.__name__, value=bad):
                    db = make_db()
                    result = conew(db.session(), bad, "196")
                    self.assertEqual(result.msg_nr, 9904)
                    self.assertEqual(result.rsp_code, 9904)

    def test_blank_cruise_id_returns_9905(self):
        for conew in BOTH_VARIANTS:
            for bad in ("", " ", "0"):
                with self.subTest(variant=conew.__name__, value=bad):
                    db = make_db()
                    result = conew(db.session(), "10000001", bad)
                    self.assertEqual(result.msg_nr, 9905)
                    self.assertEqual(result.rsp_code, 9905)

    def test_customer_checked_before_cruise(self):
        """DECIDE FOR FIRST CONDITION: 9904 wins when both are blank."""
        for conew in BOTH_VARIANTS:
            with self.subTest(variant=conew.__name__):
                db = make_db()
                result = conew(db.session(), "", "")
                self.assertEqual(result.msg_nr, 9904)

    def test_non_numeric_cruise_id_returns_9905(self):
        for conew in BOTH_VARIANTS:
            for bad in ("ABC", "12X45", "123456789"):
                with self.subTest(variant=conew.__name__, value=bad):
                    db = make_db()
                    result = conew(db.session(), "10000001", bad)
                    self.assertEqual(result.msg_nr, 9905)

    def test_non_numeric_customer_id_with_valid_cruise_becomes_9918(self):
        """Format error 9904 is overwritten by HANDLE-INPUT-DATA: the
        customer lookup with the unconverted id (0) finds no record and
        reports 9918 - a documented quirk both variants preserve."""
        for conew in BOTH_VARIANTS:
            with self.subTest(variant=conew.__name__):
                db = make_db()
                result = conew(db.session(), "ABC", "196")
                self.assertEqual(result.msg_nr, 9918)

    def test_validation_failure_does_not_change_availability(self):
        for conew in BOTH_VARIANTS:
            for customer, cruise in (("", "196"), ("10000001", ""),
                                     ("ABC", "196")):
                with self.subTest(variant=conew.__name__,
                                  customer=customer, cruise=cruise):
                    db = make_db(cruise_status="5")
                    conew(db.session(), customer, cruise)
                    status = db.session().find(
                        "NCCRUISE", "CRUISE-ID", 196)[0][1]["CRUISE-STATUS"]
                    self.assertEqual(status, "5")


class AvailabilityTests(unittest.TestCase):
    def test_fully_booked_cruise_returns_9902(self):
        for conew in BOTH_VARIANTS:
            with self.subTest(variant=conew.__name__):
                db = make_db()
                result = conew(db.session(), "10000001", "696")
                self.assertEqual(result.msg_nr, 9902)
                self.assertEqual(result.rsp_code, 9902)

    def test_unknown_customer_on_sold_out_cruise_returns_9902(self):
        # Availability is checked before the customer FIND, as in the
        # source: a sold-out cruise yields 9902 even for an unknown
        # customer.
        for conew in BOTH_VARIANTS:
            with self.subTest(variant=conew.__name__):
                db = make_db()
                result = conew(db.session(), "99999999", "696")
                self.assertEqual(result.msg_nr, 9902)

    def test_9902_does_not_create_a_contract(self):
        for conew in BOTH_VARIANTS:
            with self.subTest(variant=conew.__name__):
                db = make_db()
                before = len(db.files["NCCONTRACT"].records)
                conew(db.session(), "10000001", "696")
                self.assertEqual(len(db.files["NCCONTRACT"].records), before)

    def test_booking_last_available_slot_succeeds_then_9902(self):
        """Edge case: last slot bookable; the very next attempt gets 9902."""
        for conew in BOTH_VARIANTS:
            with self.subTest(variant=conew.__name__):
                db = make_db(cruise_status="1")
                first = conew(db.session(), "10000001", "196")
                self.assertEqual(first.msg_nr, 9800)
                status = db.session().find(
                    "NCCRUISE", "CRUISE-ID", 196)[0][1]["CRUISE-STATUS"]
                self.assertEqual(status, "0")
                second = conew(db.session(), "10000002", "196")
                self.assertEqual(second.msg_nr, 9902)


class EdgeCaseTests(unittest.TestCase):
    def test_unknown_customer_id_returns_9918_and_backs_out(self):
        for conew in BOTH_VARIANTS:
            with self.subTest(variant=conew.__name__):
                db = make_db(cruise_status="5")
                result = conew(db.session(), "99999999", "196")
                self.assertEqual(result.msg_nr, 9918)
                # the availability decrement must be rolled back
                status = db.session().find(
                    "NCCRUISE", "CRUISE-ID", 196)[0][1]["CRUISE-STATUS"]
                self.assertEqual(status, "5")
                self.assertEqual(len(db.files["NCCONTRACT"].records), 1)

    def test_unknown_cruise_id_creates_nothing(self):
        for conew in BOTH_VARIANTS:
            with self.subTest(variant=conew.__name__):
                db = make_db()
                result = conew(db.session(), "10000001", "55555555")
                self.assertEqual(result.new_contract_id, 0)
                self.assertEqual(len(db.files["NCCONTRACT"].records), 1)

    def test_empty_contract_file_backs_out_and_releases_holds(self):
        # Defensive path: with no NCCONTRACT records the READ (1) loop
        # body never runs; the refactored logic must back out so the
        # held cruise record is released and the decrement discarded.
        db = make_db(cruise_status="5")
        db.add_file("NCCONTRACT", [])
        result = nm.conew_refactored(db.session(), "10000001", "196")
        self.assertEqual(result.new_contract_id, 0)
        self.assertEqual(db.hold_table, {})
        status = db.session().find(
            "NCCRUISE", "CRUISE-ID", 196)[0][1]["CRUISE-STATUS"]
        self.assertEqual(status, "5")
        self.assertEqual(len(db.files["NCCONTRACT"].records), 0)

    def test_no_holds_left_after_any_outcome(self):
        for conew in BOTH_VARIANTS:
            for customer, cruise in (("10000001", "196"),
                                     ("99999999", "196"),
                                     ("10000001", "696"),
                                     ("", "196")):
                with self.subTest(variant=conew.__name__,
                                  customer=customer, cruise=cruise):
                    db = make_db()
                    conew(db.session(), customer, cruise)
                    self.assertEqual(db.hold_table, {})


if __name__ == "__main__":
    unittest.main()
