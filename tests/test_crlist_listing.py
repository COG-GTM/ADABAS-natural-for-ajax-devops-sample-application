"""Regression tests for the CRLIST-N cruise list service."""

import unittest

from tests.harness import natural_model as nm
from tests.harness.fixtures import make_db


class CruiseListTests(unittest.TestCase):
    def test_lists_only_available_cruises(self):
        db = make_db()
        result = nm.crlist(db.session())
        ids = [row.cruise_id for row in result.rows]
        self.assertEqual(sorted(ids), [196, 1484])
        self.assertNotIn(696, ids)  # fully booked cruise is skipped

    def test_sorted_by_start_date_descending(self):
        db = make_db()
        result = nm.crlist(db.session())
        dates = [row.start_date for row in result.rows]
        self.assertEqual(dates, sorted(dates, reverse=True))

    def test_returns_9807_when_rows_found(self):
        db = make_db()
        result = nm.crlist(db.session())
        self.assertEqual(result.msg_nr, 9807)
        self.assertEqual(result.rsp_code, 0)  # success codes map to 0

    def test_returns_9857_when_no_rows_found(self):
        db = make_db()
        result = nm.crlist(db.session(), start_harbor="Atlantis")
        self.assertEqual(result.rows, [])
        self.assertEqual(result.msg_nr, 9857)
        self.assertEqual(result.rsp_code, 9857)

    def test_start_harbor_filter(self):
        db = make_db()
        result = nm.crlist(db.session(), start_harbor="Paros")
        self.assertEqual([r.cruise_id for r in result.rows], [1484])

    def test_destination_harbor_filter(self):
        db = make_db()
        result = nm.crlist(db.session(), dest_harbor="Santorini")
        self.assertEqual([r.cruise_id for r in result.rows], [196])

    def test_both_filters_must_match(self):
        db = make_db()
        result = nm.crlist(db.session(), start_harbor="Paros",
                           dest_harbor="Santorini")
        self.assertEqual(result.rows, [])

    def test_dates_edited_to_iso_format(self):
        db = make_db()
        row = [r for r in nm.crlist(db.session()).rows if r.cruise_id == 196][0]
        self.assertEqual(row.start_date, "2026-09-01")
        self.assertEqual(row.end_date, "2026-09-08")

    def test_prices_edited_with_two_decimals(self):
        db = make_db()
        row = [r for r in nm.crlist(db.session()).rows if r.cruise_id == 196][0]
        self.assertEqual(row.price_1w, "1290.00")
        self.assertEqual(row.price_2w, "2390.00")
        self.assertEqual(row.price_3w, "3290.00")

    def test_yacht_name_joined_from_ncyacht(self):
        db = make_db()
        rows = {r.cruise_id: r for r in nm.crlist(db.session()).rows}
        self.assertEqual(rows[196].yacht_name, "Sunny Dream")
        self.assertEqual(rows[1484].yacht_name, "Island Breeze")

    def test_cruise_becomes_invisible_after_last_slot_booked(self):
        """End-to-end: booking the last slot removes the cruise from the
        list on the next call (CRLIST-N reads CRUISE-STATUS live)."""
        db = make_db(cruise_status="1")
        self.assertIn(196, [r.cruise_id for r in nm.crlist(db.session()).rows])
        nm.conew_refactored(db.session(), "10000001", "196")
        self.assertNotIn(196, [r.cruise_id for r in nm.crlist(db.session()).rows])


class PriceSelectionTests(unittest.TestCase):
    """CRGET-N duration-based price selection (exercise 04 logic)."""

    PRICES = {"1W": 1290.0, "2W": 2390.0, "3W": 3290.0}

    def test_seven_day_cruise_selects_one_week_price(self):
        price = nm.crget_price_selection(20260901, 20260908, self.PRICES)
        self.assertEqual(price, 1290.0)

    def test_fourteen_day_cruise_selects_two_week_price(self):
        price = nm.crget_price_selection(20260901, 20260915, self.PRICES)
        self.assertEqual(price, 2390.0)

    def test_twentyone_day_cruise_selects_three_week_price(self):
        price = nm.crget_price_selection(20260901, 20260922, self.PRICES)
        self.assertEqual(price, 3290.0)

    def test_other_durations_fall_back_to_two_week_price(self):
        for end in (20260905, 20260911, 20260930):
            with self.subTest(end=end):
                price = nm.crget_price_selection(20260901, end, self.PRICES)
                self.assertEqual(price, 2390.0)


if __name__ == "__main__":
    unittest.main()
