"""Drift tests for tools/analyze_disposition.py.

The migration-disposition evidence under
fpps-hcm-modernization-deliverable/10-migration-disposition-dead-code/evidence/
is generated from the Natural sources.  These tests (a) pin the control
totals so a change in the sources or the analyzer is a deliberate, reviewed
event, (b) assert set equality in both directions for the key findings, and
(c) assert the committed evidence files match the generator byte-for-byte.
"""

import json
import unittest

from tools import analyze_disposition as ad


class DispositionControlTotals(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = ad.analyze()
        cls.ct = cls.result["control_totals"]

    def test_object_inventory(self):
        self.assertEqual(self.ct["objects"], 31)
        self.assertEqual(self.ct["code_objects"], 15)
        by_type = {}
        for o in self.result["inventory"]:
            by_type[o["type"]] = by_type.get(o["type"], 0) + 1
        self.assertEqual(by_type, {
            "subprogram": 11, "program": 3, "copycode": 1,
            "local data area": 2, "global data area": 1,
            "parameter data area": 9, "DDM": 4,
        })

    def test_no_dynamic_invocations_in_sample(self):
        self.assertEqual(self.ct["dynamic_invocations"], 0)

    def test_unreferenced_objects_exact(self):
        self.assertEqual(set(self.ct["unreferenced_objects"]), {
            "CA3900-N", "IMG-LOAD",
            "CONTPDA", "MYPDA", "SYPDA", "YACHTPDA", "NCCUSL-P",
        })
        self.assertEqual(self.ct["standalone_programs_no_ui_path"], ["DELETECU"])

    def test_every_service_reachable_from_adapter(self):
        reachable = {r["object"] for r in self.result["reachability"]
                     if r["status"] == "reachable from UI root"}
        for svc in ("CRLIST-N", "CRGET-N", "CONEW-N", "CUGET-N", "CUNEW-N",
                    "CUMOD-N", "CAMSG-N", "RDCRINIP", "RDREADWN", "MAKEURL",
                    "ERRLOG-I", "NCDATA-L", "NCCOMM-P", "NCCONW-P"):
            self.assertIn(svc, reachable)

    def test_message_catalog_reconciliation(self):
        mc = self.result["message_codes"]
        self.assertEqual(self.ct["message_codes_cataloged"], 31)
        self.assertEqual(self.ct["message_codes_emitted"], 11)
        self.assertEqual(self.ct["message_codes_emitted_not_cataloged"], 0)
        self.assertEqual(set(mc["cataloged_never_emitted"]), {
            9801, 9803, 9804, 9805, 9806, 9855, 9856, 9901, 9903,
            9911, 9912, 9913, 9914, 9915, 9916, 9917, 9919, 9921, 9922, 9935,
        })
        # bidirectional: catalog == emitted ∪ never-emitted
        self.assertEqual(
            set(mc["catalog"]),
            {int(c) for c in mc["emitted"]} | set(mc["cataloged_never_emitted"]),
        )
        self.assertEqual(self.ct["commented_out_message_emits"], 10)

    def test_pda_fields_never_assigned_exact(self):
        self.assertEqual(set(self.ct["pda_fields_never_assigned"]), {
            "NCCOMM-P.P-LANG", "NCCOMM-P.P-USER", "NCCOMM-P.P-PASSWORD",
            "NCCONW-P.WEEK-COUNT-IN", "NCCONW-P.DATE-RESERVATION-IN",
            "NCCONW-P.DATE-BOOKING-IN", "NCCRUL-P.P-DESTHARBOR",
        })

    def test_ddm_field_usage_totals(self):
        self.assertEqual(self.ct["ddm_fields_never_referenced"], 21)
        self.assertEqual(self.ct["ddm_fields_ambiguous_name"], 4)
        never = {(r["file"], r["field"]) for r in self.result["ddm_field_usage"]
                 if r["kind"] == "field" and not r["referenced_by"]
                 and not r["ambiguous"]}
        self.assertIn(("NCCUSTOMER", "FIRST-NAME-2"), never)
        self.assertIn(("NCCONTRACT", "DATE-CANCELLATION"), never)
        self.assertNotIn(("NCCRUISE", "CRUISE-STATUS"), never)

    def test_unused_variables_and_comments(self):
        self.assertEqual(self.ct["unused_level1_variables"], 15)
        self.assertEqual(self.ct["commented_out_statements"], 81)
        unused = {(r["object"], r["variable"])
                  for r in self.result["unused_level1_variables"]}
        self.assertIn(("CONEW-N", "UP-INPUT-OK"), unused)

    def test_ui_events_all_handled(self):
        self.assertEqual(self.ct["ui_events_declared"], 27)
        self.assertEqual(self.ct["ui_events_unhandled"], [])


class DispositionEvidenceFilesInSync(unittest.TestCase):
    def test_committed_json_matches_generator(self):
        committed = json.loads(
            (ad.OUT_DIR / "disposition-evidence.json").read_text(encoding="utf-8"))
        self.assertEqual(committed, ad.analyze())

    def test_committed_markdown_matches_generator(self):
        committed = (ad.OUT_DIR / "disposition-evidence.md").read_text(encoding="utf-8")
        self.assertEqual(committed, ad.render_markdown(ad.analyze()))


if __name__ == "__main__":
    unittest.main()
