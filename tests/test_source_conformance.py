"""Source-conformance tests: assert the real Natural sources and DDMs.

These tests parse the actual .NSN/.NSD files so the Python behavioral model,
the documentation, and the shipped Natural code cannot silently drift apart.
Checks are bidirectional wherever a set is compared.
"""

import re
import unittest

from tests.harness import natural_model as nm
from tests.harness import source_parser as sp

CONEW = sp.CRUISE16 / "Subprograms" / "CONEW-N.NSN"
CRLIST = sp.CRUISE16 / "Subprograms" / "CRLIST-N.NSN"
CUNEW = sp.CRUISE16 / "Subprograms" / "CUNEW-N.NSN"
CAMSG = sp.CRUISE16 / "Subprograms" / "CAMSG-N.NSN"


class ConewSourceTests(unittest.TestCase):
    def setUp(self):
        self.src = sp.read_source(CONEW)
        self.code = "\n".join(sp.strip_comments(self.src))

    def test_message_codes_match_model_exactly(self):
        """Bidirectional: codes in CONEW-N source == codes the model uses."""
        expected = {9800, 9902, 9904, 9905, 9918, 9999}
        self.assertEqual(sp.message_codes(self.src), expected)

    def test_all_conew_codes_translatable_by_camsg(self):
        camsg = sp.camsg_codes(sp.read_source(CAMSG))
        untranslatable = sp.message_codes(self.src) - camsg
        self.assertEqual(untranslatable, set())

    def test_cruise_record_reread_in_hold_before_test_and_set(self):
        """Fix 1: GET re-reads the found record; the UPDATE references the
        GET label, so the fresh CRUISE-STATUS is read in hold."""
        self.assertRegex(self.code, r"GET\s+NCCRUISE\s+\*ISN\(R1\.\)")
        get_pos = self.code.index("GET NCCRUISE")
        status_pos = self.code.index("VAL(NCCRUISE.CRUISE-STATUS)")
        update_pos = self.code.index("UPDATE (G1.)")
        self.assertLess(get_pos, status_pos)
        self.assertLess(status_pos, update_pos)

    def test_highest_contract_held_before_id_generation(self):
        """Fix 2: fake UPDATE on the READ(1) DESCENDING loop holds the
        highest contract record before MAX+1 is computed."""
        read_pos = self.code.index(
            "READ (1) NCCONTRACT DESCENDING BY NCCONTRACT.CONTRACT-ID")
        update_pos = self.code.index("UPDATE (R2.)")
        newid_pos = self.code.index("NCCONTRACT.CONTRACT-ID +1")
        self.assertLess(read_pos, update_pos)
        self.assertLess(update_pos, newid_pos)

    def test_transaction_boundaries_preserved(self):
        self.assertIn("STORE NCCONTRACT", self.code)
        self.assertIn("END TRANSACTION", self.code)
        self.assertIn("BACKOUT TRANSACTION", self.code)
        store_pos = self.code.index("STORE NCCONTRACT")
        et_pos = self.code.index("END TRANSACTION", store_pos)
        self.assertLess(store_pos, et_pos)

    def test_empty_contract_file_guard_backs_out(self):
        """Defensive path: if the READ (1) loop body never runs (empty
        NCCONTRACT file), a guard after END-READ backs out so the held
        cruise record and its buffered decrement are released."""
        end_read_pos = self.code.index("END-READ")
        guard = self.code.index("IF LOCAL-NEWCONTRACTID = 0", end_read_pos)
        backout = self.code.index("BACKOUT TRANSACTION", guard)
        end_if = self.code.index("END-IF", guard)
        self.assertLess(guard, backout)
        self.assertLess(backout, end_if)

    def test_validation_decide_block_unchanged(self):
        self.assertRegex(self.code, r"WHEN P-CONTRACT-DATA\.ID-CUSTOMER-IN")
        self.assertRegex(self.code, r"WHEN P-CONTRACT-DATA\.ID-CRUISE-IN")
        self.assertRegex(self.code, r"IS \(N8\)")

    def test_fake_update_idiom_matches_cunew(self):
        """The contract-ID hold uses the same idiom CUNEW-N established."""
        cunew = "\n".join(sp.strip_comments(sp.read_source(CUNEW)))
        self.assertRegex(cunew, r"READ \(1\) NCCUSTOMER DESCENDING BY PERSON-ID")
        self.assertRegex(cunew, r"\bUPDATE\b")


class CrlistSourceTests(unittest.TestCase):
    def setUp(self):
        self.src = sp.read_source(CRLIST)
        self.code = "\n".join(sp.strip_comments(self.src))

    def test_message_codes_match_model_exactly(self):
        self.assertEqual(sp.message_codes(self.src), {9807, 9857, 9999})

    def test_reads_descending_by_start_date(self):
        self.assertRegex(self.code, r"READ NCCRUISE DESCENDING BY START-DATE")

    def test_skips_fully_booked_and_filters_harbors(self):
        self.assertRegex(self.code, r"IF LOCAL-AVAIL EQ 0")
        self.assertRegex(self.code, r"START-HARBOR NE P-STARTHARBOR")
        self.assertRegex(self.code, r"DESTINATION-HARBOR NE P-DESTHARBOR")


class CamsgModelSyncTests(unittest.TestCase):
    def test_model_texts_are_subset_of_camsg_codes(self):
        camsg = sp.camsg_codes(sp.read_source(CAMSG))
        self.assertLessEqual(set(nm.CAMSG_TEXT_EN), camsg)

    def test_success_code_remap_in_source(self):
        """CAMSG-N remaps 98xx success numbers to response code 0."""
        code = "\n".join(sp.strip_comments(sp.read_source(CAMSG)))
        self.assertRegex(code, r"MOVE 0 TO MSG-GROUP-PARA\.MSG-NR")


class DdmDictionaryTests(unittest.TestCase):
    """Bidirectional sync between the DDM files and expected control totals."""

    def setUp(self):
        self.ddms = sp.all_ddms()

    def test_all_four_logical_files_present(self):
        self.assertEqual(
            set(self.ddms),
            {"NCCRUISE", "NCCONTRACT", "NCCUSTOMER", "NCYACHT"},
        )

    def test_nccruise_key_fields(self):
        fields = {f.name: f for f in self.ddms["NCCRUISE"].fields}
        self.assertEqual(fields["CRUISE-ID"].fmt, "N")
        self.assertEqual(fields["CRUISE-ID"].descriptor, "D")
        self.assertEqual(fields["CRUISE-STATUS"].fmt, "A")
        self.assertEqual(fields["CRUISE-STATUS"].length, "1")
        for price in ("PRICE-1W", "PRICE-2W", "PRICE-3W"):
            self.assertEqual(fields[price].fmt, "P")

    def test_nccontract_contract_id_is_descriptor(self):
        fields = {f.name: f for f in self.ddms["NCCONTRACT"].fields}
        self.assertEqual(fields["CONTRACT-ID"].fmt, "P")
        self.assertEqual(fields["CONTRACT-ID"].descriptor, "D")
        self.assertEqual(fields["ID-CUSTOMER"].descriptor, "D")
        self.assertEqual(fields["ID-CRUISE"].descriptor, "D")

    def test_nccustomer_person_id_is_descriptor(self):
        fields = {f.name: f for f in self.ddms["NCCUSTOMER"].fields}
        self.assertEqual(fields["PERSON-ID"].fmt, "N")
        self.assertEqual(fields["PERSON-ID"].descriptor, "D")

    def test_ncyacht_key_fields(self):
        fields = {f.name: f for f in self.ddms["NCYACHT"].fields}
        self.assertEqual(fields["YACHT-ID"].descriptor, "D")
        self.assertEqual(fields["YACHT-NAME"].fmt, "A")

    def test_field_control_totals(self):
        """Explicit control totals so DDM changes are deliberate."""
        counts = {name: len(ddm.fields) for name, ddm in self.ddms.items()}
        self.assertEqual(counts, {
            "NCCRUISE": 15,
            "NCCONTRACT": 14,
            "NCCUSTOMER": 20,
            "NCYACHT": 12,
        })


class DocsSyncTests(unittest.TestCase):
    """The generated data dictionary in /docs must match the DDMs."""

    def test_data_dictionary_regenerates_identically(self):
        import subprocess
        import sys
        doc = sp.REPO_ROOT / "docs" / "data-dictionary.md"
        self.assertTrue(doc.exists(), "docs/data-dictionary.md missing")
        generated = subprocess.run(
            [sys.executable,
             str(sp.REPO_ROOT / "tools" / "generate_data_dictionary.py"),
             "--stdout"],
            capture_output=True, text=True, check=True,
        ).stdout
        self.assertEqual(doc.read_text(encoding="utf-8"), generated)

    def test_every_ddm_field_appears_in_doc(self):
        doc = (sp.REPO_ROOT / "docs" / "data-dictionary.md").read_text(
            encoding="utf-8")
        for ddm in sp.all_ddms().values():
            for f in ddm.fields:
                self.assertIn(f.name, doc)


if __name__ == "__main__":
    unittest.main()
