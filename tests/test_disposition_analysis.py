"""Drift tests for tools/analyze_disposition.py.

The migration-disposition evidence under
fpps-hcm-modernization-deliverable/10-migration-disposition-dead-code/evidence/
is generated from the Natural sources.  These tests (a) pin the control
totals so a change in the sources or the analyzer is a deliberate, reviewed
event, (b) assert set equality in both directions for the key findings,
(c) assert the committed evidence files match the generator byte-for-byte,
and (d) exercise the analyzer's symbol resolution, dynamic-call detection and
marker classification on small synthetic Natural fixtures so the snapshot
numbers are backed by behavioural checks.
"""

import json
import textwrap
import unittest

from tools import analyze_disposition as ad


def _obj(name, otype, src):
    return {"object": name, "type": otype, "library": "FIX",
            "path": f"FIX/{name}", "lines": 0, "executable_lines": 0,
            "_src": textwrap.dedent(src)}


PDA_SRC = """\
    DEFINE DATA PARAMETER
    1 P-CUSTOMER-DATA
      2 PERSON-ID (N8)
      2 NAME
        3 SURNAME (A20)
        3 FIRST-NAME-1 (U40)
      2 P-NOTE (A10)
    END-DEFINE
"""

LDA_SRC = """\
    DEFINE DATA LOCAL
    1 NCCUSTOMER VIEW OF NCCUSTOMER
      2 PERSON-ID (N8)
      2 NAME
        3 SURNAME (A20)
        3 FIRST-NAME-OLD (A20)
    * 2 FIRST-NAME-1 (U40)
    1 #WORK (A10)
    END-DEFINE
"""

SVC_SRC = """\
    DEFINE DATA
    PARAMETER USING FIX-PDA
    LOCAL USING FIX-LDA
    END-DEFINE
    FIND (1) NCCUSTOMER WITH PERSON-ID = P-CUSTOMER-DATA.PERSON-ID
      MOVE NCCUSTOMER.SURNAME TO P-CUSTOMER-DATA.SURNAME
      MOVE FIRST-NAME-OLD TO NAME.FIRST-NAME-1
      IF P-NOTE = 'X' THEN IGNORE END-IF
    END-FIND
    END
"""


class SymbolResolutionFixtures(unittest.TestCase):
    """Same-named fields in a DDM view and a PDA must be attributed to the
    structure that actually owns the reference."""

    def setUp(self):
        self.objs = {
            "FIX-PDA": _obj("FIX-PDA", "parameter data area", PDA_SRC),
            "FIX-LDA": _obj("FIX-LDA", "local data area", LDA_SRC),
            "FIX-SVC": _obj("FIX-SVC", "subprogram", SVC_SRC),
        }
        self.refs, self.dynamic = ad._references(self.objs)
        self.scope = ad._scopes(self.objs, self.refs)["FIX-SVC"]

    def test_structures_carry_view_and_qualifiers(self):
        lda = ad._structures(self.objs["FIX-LDA"]["_src"], "FIX-LDA")
        self.assertEqual([s["name"] for s in lda], ["NCCUSTOMER", "#WORK"])
        self.assertEqual(lda[0]["view_of"], "NCCUSTOMER")
        self.assertIsNone(lda[1]["view_of"])
        fields = {f[0]: f[3] for f in lda[0]["fields"]}
        self.assertEqual(fields["FIRST-NAME-OLD"], {"NCCUSTOMER", "NAME"})
        self.assertNotIn("FIRST-NAME-1", fields)  # commented-out declaration

    def test_scope_includes_using_data_areas(self):
        self.assertEqual(
            {(s["owner"], s["name"]) for s in self.scope},
            {("FIX-PDA", "P-CUSTOMER-DATA"), ("FIX-LDA", "NCCUSTOMER"),
             ("FIX-LDA", "#WORK")})

    def test_qualified_reference_resolves_to_owner(self):
        pda_hit = ad._resolve("P-CUSTOMER-DATA", "SURNAME", self.scope)
        self.assertEqual([(s["owner"], s["name"]) for s in pda_hit],
                         [("FIX-PDA", "P-CUSTOMER-DATA")])
        view_hit = ad._resolve("NCCUSTOMER", "SURNAME", self.scope)
        self.assertEqual([s["view_of"] for s in view_hit], ["NCCUSTOMER"])
        # a group qualifier that exists in both structures is ambiguous
        self.assertEqual(len(ad._resolve("NAME", "SURNAME", self.scope)), 2)

    def test_unqualified_reference_unique_owner_or_ambiguous(self):
        self.assertEqual(
            [s["owner"] for s in ad._resolve(None, "FIRST-NAME-OLD", self.scope)],
            ["FIX-LDA"])
        self.assertEqual(len(ad._resolve(None, "PERSON-ID", self.scope)), 2)
        # ...unless the line is a database access on the view
        line = "FIND (1) NCCUSTOMER WITH PERSON-ID = P-CUSTOMER-DATA.PERSON-ID"
        self.assertEqual(
            [s["view_of"] for s in ad._resolve(None, "PERSON-ID", self.scope, line)],
            ["NCCUSTOMER"])

    def test_occurrences_skip_system_variables_and_keyword_phrases(self):
        self.assertEqual(list(ad._occurrences("MOVE *LENGTH(#A) TO #B", "LENGTH")), [])
        self.assertEqual(list(ad._occurrences("MOVE BY NAME A TO B", "NAME")), [])
        occ = list(ad._occurrences("MOVE X.NAME TO NAME", "NAME"))
        self.assertEqual([q for q, _, _ in occ], ["X", None])

    def test_ddm_usage_not_credited_via_pda_field(self):
        ddm_fields = {
            "NCCUSTOMER": type("D", (), {"fields": [
                type("F", (), {"name": n, "field_type": "", "fmt": "A",
                               "length": 20})()
                for n in ("PERSON-ID", "SURNAME", "FIRST-NAME-OLD", "FIRST-NAME-1")
            ]})(),
        }
        real_all_ddms = ad.sp.all_ddms
        ad.sp.all_ddms = lambda: ddm_fields
        try:
            rows = {r["field"]: r for r in ad._ddm_field_usage(self.objs, self.refs)}
        finally:
            ad.sp.all_ddms = real_all_ddms
        self.assertEqual(rows["SURNAME"]["referenced_by"], ["FIX-SVC"])
        self.assertEqual(rows["FIRST-NAME-OLD"]["referenced_by"], ["FIX-SVC"])
        self.assertEqual(rows["PERSON-ID"]["referenced_by"], ["FIX-SVC"])
        self.assertEqual(rows["PERSON-ID"]["ambiguous_in"], [])
        # FIRST-NAME-1 is written in the PDA, but the view does not expose it
        self.assertEqual(rows["FIRST-NAME-1"]["referenced_by"], [])
        self.assertEqual(rows["FIRST-NAME-1"]["exposed_in_views"], [])
        self.assertEqual(rows["SURNAME"]["exposed_in_views"], ["FIX-LDA.NCCUSTOMER"])

    def test_pda_population_attributes_assignments_to_pda_only(self):
        rows = {r["field"]: r for r in ad._pda_field_population(self.objs, self.refs)}
        self.assertEqual(rows["SURNAME"]["assignments"], 1)
        self.assertEqual(rows["SURNAME"]["reads"], 0)
        self.assertEqual(rows["FIRST-NAME-1"]["assignments"], 1)
        self.assertEqual(rows["PERSON-ID"]["reads"], 1)
        self.assertEqual(rows["PERSON-ID"]["assignments"], 0)
        self.assertEqual(rows["P-NOTE"]["reads"], 1)
        self.assertEqual(rows["SURNAME"]["referenced_by"], ["FIX-SVC"])


class ReferenceAndMarkerFixtures(unittest.TestCase):
    def test_dynamic_call_reported_separately(self):
        objs = {"DYN": _obj("DYN", "program", """\
            DEFINE DATA LOCAL
            1 #TARGET (A8)
            END-DEFINE
            MOVE 'CUGET-N' TO #TARGET
            CALLNAT #TARGET P-COM
            CALLNAT 'CAMSG-N' MSG
            FETCH RETURN "RDCRINIP"
            END
        """)}
        refs, dynamic = ad._references(objs)
        self.assertEqual([(r["statement"], r["callee"]) for r in refs],
                         [("CALLNAT", "CAMSG-N"), ("FETCH", "RDCRINIP")])
        self.assertEqual([(d["statement"], d["operand"]) for d in dynamic],
                         [("CALLNAT", "#TARGET")])

    def test_statement_lines_exclude_define_data_and_callnat_operands(self):
        src = textwrap.dedent("""\
            DEFINE DATA LOCAL
            1 P-A (A1)
            END-DEFINE
            CALLNAT 'X'
              P-A
              P-B
            MOVE P-A TO P-B
            END
        """)
        self.assertEqual([l.strip() for l in ad._statement_lines(src)],
                         ["MOVE P-A TO P-B", "END"])

    def test_markers_ignore_ordinary_german_text(self):
        objs = {"MSG": _obj("MSG", "subprogram", """\
            VALUE 9902 COMPRESS 'Reise nicht mehr verfügbar' INTO T
            VALUE 9999 COMPRESS 'Funktion noch nicht implementiert' INTO T
            * TODO remove the exercise stub
            MOVE 'not yet supported' TO T
        """)}
        lines = [m["line"] for m in ad._markers(objs)]
        self.assertEqual(lines, [2, 3, 4])


class ObjectInventory(unittest.TestCase):
    def test_same_name_in_two_libraries_is_reported_not_overwritten(self):
        objs, shadowed = ad._objects()
        self.assertEqual(shadowed, [])
        self.assertEqual(len(objs), 31)


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
        self.assertEqual(self.ct["ddm_fields_never_referenced"], 23)
        self.assertEqual(self.ct["ddm_fields_not_in_any_view"], 17)
        self.assertEqual(self.ct["ddm_fields_ambiguous_reference"], 0)
        self.assertEqual(self.ct["shadowed_objects"], [])
        rows = {(r["file"], r["field"]): r for r in self.result["ddm_field_usage"]}
        never = {k for k, r in rows.items()
                 if r["kind"] == "field" and not r["referenced_by"]}
        self.assertIn(("NCCUSTOMER", "FIRST-NAME-2"), never)
        self.assertIn(("NCCONTRACT", "DATE-CANCELLATION"), never)
        self.assertNotIn(("NCCRUISE", "CRUISE-STATUS"), never)
        # the adapter writes P-CUSTOMER-DATA.FIRST-NAME-1 (PDA) but no view
        # exposes NCCUSTOMER.FIRST-NAME-1 — it must not count as DB usage
        self.assertIn(("NCCUSTOMER", "FIRST-NAME-1"), never)
        self.assertEqual(rows[("NCCUSTOMER", "FIRST-NAME-1")]["exposed_in_views"], [])
        # *LENGTH system variable is not a reference to NCYACHT.LENGTH
        self.assertIn(("NCYACHT", "LENGTH"), never)
        self.assertEqual(rows[("NCCUSTOMER", "PERSON-ID")]["referenced_by"],
                         ["CONEW-N", "CUGET-N", "CUMOD-N", "CUNEW-N"])

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
