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
from unittest import mock

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
      2 TIMESTAMP (T)
      2 WEEK-COUNT-IN (N2)
    END-DEFINE
"""

LDA_SRC = """\
    DEFINE DATA LOCAL
    1 NCCUSTOMER VIEW OF NCCUSTOMER
      2 PERSON-ID (N8)
      2 NAME
        3 SURNAME (A20)
        3 FIRST-NAME-OLD (A20)
      2 TIMESTAMP (T)
    * 2 FIRST-NAME-1 (U40)
    1 #WORK (A10)
    END-DEFINE
"""

SVC_SRC = """\
    DEFINE DATA
    PARAMETER USING FIX-PDA
    LOCAL USING FIX-LDA
    END-DEFINE
    RESET P-CUSTOMER-DATA
    FIND (1) NCCUSTOMER WITH PERSON-ID = P-CUSTOMER-DATA.PERSON-ID
      MOVE NCCUSTOMER.SURNAME TO P-CUSTOMER-DATA.SURNAME
      MOVE FIRST-NAME-OLD TO NAME.FIRST-NAME-1
      MOVE *TIMESTMP TO NCCUSTOMER.TIMESTAMP P-CUSTOMER-DATA.TIMESTAMP
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

    def test_multi_target_move_assigns_every_target(self):
        line = "  MOVE *TIMESTMP TO NCCUSTOMER.TIMESTAMP P-CUSTOMER-DATA.TIMESTAMP"
        spans = [(q, s, e) for q, s, e in ad._occurrences(line, "TIMESTAMP")]
        self.assertEqual([q for q, _, _ in spans], ["NCCUSTOMER", "P-CUSTOMER-DATA"])
        self.assertTrue(all(ad._is_assignment(line, s, e) for _, s, e in spans))
        # the source operand of a MOVE is a read, not an assignment
        src = "MOVE P-CUSTOMER-DATA.TIMESTAMP TO #WORK"
        _, s, e = next(ad._occurrences(src, "TIMESTAMP"))
        self.assertFalse(ad._is_assignment(src, s, e))
        rows = {r["field"]: r for r in ad._pda_field_population(self.objs, self.refs)}
        self.assertEqual(rows["TIMESTAMP"]["assignments"], 1)
        self.assertEqual(rows["TIMESTAMP"]["reads"], 0)

    def test_group_reset_is_not_a_value_assignment(self):
        self.assertEqual(list(ad._group_reset_targets("RESET P-CUSTOMER-DATA")),
                         [(None, "P-CUSTOMER-DATA")])
        self.assertEqual(list(ad._group_reset_targets("  RESET A.X #B")),
                         [("A", "X"), (None, "#B")])
        self.assertEqual(list(ad._group_reset_targets("MOVE A TO B")), [])
        rows = {r["field"]: r for r in ad._pda_field_population(self.objs, self.refs)}
        # WEEK-COUNT-IN is only touched by the whole-structure RESET
        self.assertEqual(rows["WEEK-COUNT-IN"]["assignments"], 0)
        self.assertEqual(rows["WEEK-COUNT-IN"]["group_resets"], 1)
        self.assertEqual(rows["WEEK-COUNT-IN"]["referenced_by"], ["FIX-SVC"])
        self.assertEqual(rows["SURNAME"]["group_resets"], 1)
        self.assertEqual(rows["SURNAME"]["assignments"], 1)
        # a RESET of a scalar is an assignment of that scalar
        line = "RESET P-CUSTOMER-DATA.P-NOTE"
        _, s, e = next(ad._occurrences(line, "P-NOTE"))
        self.assertTrue(ad._is_assignment(line, s, e))


BY_NAME_SVC_SRC = """\
    DEFINE DATA
    PARAMETER USING FIX-PDA
    LOCAL USING FIX-LDA
    END-DEFINE
    READ (1) NCCUSTOMER BY PERSON-ID
      RESET NCCUSTOMER
      MOVE BY NAME NCCUSTOMER TO P-CUSTOMER-DATA(1)
      MOVE BY NAME P-CUSTOMER-DATA.NAME TO #WORK
    END-READ
    END
"""


class WholeStructureOperationFixtures(unittest.TestCase):
    """``MOVE BY NAME`` and a ``RESET`` of a whole view touch every matching
    field without naming it; the analysis must expand them."""

    def setUp(self):
        self.objs = {
            "FIX-PDA": _obj("FIX-PDA", "parameter data area", PDA_SRC),
            "FIX-LDA": _obj("FIX-LDA", "local data area", LDA_SRC),
            "FIX-SVC": _obj("FIX-SVC", "subprogram", BY_NAME_SVC_SRC),
        }
        self.refs, _ = ad._references(self.objs)
        self.scope = ad._scopes(self.objs, self.refs)["FIX-SVC"]

    def test_resolve_group_returns_scalars_below_structure_or_group(self):
        [(s, fields)] = ad._resolve_group(None, "NCCUSTOMER", self.scope)
        self.assertEqual(s["owner"], "FIX-LDA")
        self.assertEqual(fields, ["PERSON-ID", "SURNAME", "FIRST-NAME-OLD", "TIMESTAMP"])
        [(s, fields)] = ad._resolve_group("P-CUSTOMER-DATA", "NAME", self.scope)
        self.assertEqual(s["owner"], "FIX-PDA")
        self.assertEqual(fields, ["SURNAME", "FIRST-NAME-1"])
        # NAME is a group in both structures: ambiguous without a qualifier
        self.assertEqual(len(ad._resolve_group(None, "NAME", self.scope)), 2)
        # a scalar is not a group
        self.assertEqual(ad._resolve_group(None, "#WORK", self.scope), [])
        self.assertEqual(ad._resolve_group(None, "SURNAME", self.scope), [])

    def test_move_by_name_reads_source_and_assigns_matching_targets(self):
        ops = ad._implicit_ops(self.scope, ad._statement_lines(
            self.objs["FIX-SVC"]["_src"]))
        matched = {"PERSON-ID", "SURNAME", "TIMESTAMP"}  # FIRST-NAME-* differ
        for f in matched:
            self.assertEqual(ops[("FIX-LDA", "NCCUSTOMER", f, "read")], 1, f)
            self.assertEqual(ops[("FIX-PDA", "P-CUSTOMER-DATA", f, "assign")], 1, f)
        self.assertEqual(ops[("FIX-PDA", "P-CUSTOMER-DATA", "FIRST-NAME-1", "assign")], 0)
        self.assertEqual(ops[("FIX-LDA", "NCCUSTOMER", "FIRST-NAME-OLD", "read")], 0)
        # #WORK is a scalar, so the second MOVE BY NAME expands to nothing
        self.assertEqual(sum(v for k, v in ops.items() if k[3] == "assign"), 3)

    def test_view_reset_is_tracked_apart_from_references(self):
        ops = ad._implicit_ops(self.scope, ad._statement_lines(
            self.objs["FIX-SVC"]["_src"]))
        for f in ("PERSON-ID", "SURNAME", "FIRST-NAME-OLD", "TIMESTAMP"):
            self.assertEqual(ops[("FIX-LDA", "NCCUSTOMER", f, "reset")], 1, f)
        self.assertEqual(ops[("FIX-PDA", "P-CUSTOMER-DATA", "SURNAME", "reset")], 0)

    def test_ddm_usage_credits_by_name_but_not_reset_only(self):
        ddm_fields = {
            "NCCUSTOMER": type("D", (), {"fields": [
                type("F", (), {"name": n, "field_type": "", "fmt": "A",
                               "length": 20})()
                for n in ("PERSON-ID", "SURNAME", "FIRST-NAME-OLD", "TIMESTAMP")
            ]})(),
        }
        real_all_ddms = ad.sp.all_ddms
        ad.sp.all_ddms = lambda: ddm_fields
        try:
            rows = {r["field"]: r for r in ad._ddm_field_usage(self.objs, self.refs)}
        finally:
            ad.sp.all_ddms = real_all_ddms
        self.assertEqual(rows["SURNAME"]["referenced_by"], ["FIX-SVC"])
        self.assertEqual(rows["TIMESTAMP"]["referenced_by"], ["FIX-SVC"])
        self.assertEqual(rows["PERSON-ID"]["referenced_by"], ["FIX-SVC"])
        # only cleared by RESET NCCUSTOMER, never read or valued
        self.assertEqual(rows["FIRST-NAME-OLD"]["referenced_by"], [])
        for f in rows.values():
            self.assertEqual(f["cleared_by_view_reset_in"], ["FIX-SVC"])

    def test_pda_population_counts_by_name_assignments(self):
        rows = {r["field"]: r for r in ad._pda_field_population(self.objs, self.refs)}
        for f in ("PERSON-ID", "SURNAME", "TIMESTAMP"):
            self.assertEqual(rows[f]["assignments"], 1, f)
            self.assertEqual(rows[f]["referenced_by"], ["FIX-SVC"], f)
        self.assertEqual(rows["FIRST-NAME-1"]["assignments"], 0)
        self.assertEqual(rows["FIRST-NAME-1"]["referenced_by"], [])
        self.assertEqual(rows["WEEK-COUNT-IN"]["assignments"], 0)
        self.assertEqual(rows["SURNAME"]["group_resets"], 0)


ARITH_SVC_SRC = """\
    DEFINE DATA
    PARAMETER USING FIX-PDA
    LOCAL USING FIX-LDA
    END-DEFINE
    COMPUTE P-CUSTOMER-DATA.PERSON-ID = VAL(#WORK)
    SUBTRACT 1 FROM P-CUSTOMER-DATA.WEEK-COUNT-IN
    ADD 1 TO P-CUSTOMER-DATA.WEEK-COUNT-IN GIVING P-CUSTOMER-DATA.TIMESTAMP
    EXAMINE P-CUSTOMER-DATA.SURNAME FOR '-' DELETE
    COMPRESS P-CUSTOMER-DATA.SURNAME INTO P-CUSTOMER-DATA.P_NOTE LEAVING NO
    FOR P-CUSTOMER-DATA.FIRST-NAME-1 1 TO P-CUSTOMER-DATA.P-NOTE
    END-FOR
    END
"""


class AssignmentTargetFixtures(unittest.TestCase):
    """Every Natural statement form that writes an operand must be seen as an
    assignment of that operand and nothing else on the line."""

    def _targets(self, line):
        return [line[a:b].split() for a, b in ad._target_spans(line)]

    def test_compute_and_assign(self):
        self.assertEqual(self._targets("COMPUTE NCCONTRACT.DATE-BOOKING = VAL(LOCAL-DATE)"),
                         [["NCCONTRACT.DATE-BOOKING"]])
        self.assertEqual(self._targets("  ASSIGN ROUNDED #A #B = #C * 2"), [["#A", "#B"]])
        line = "COMPUTE ID-CUSTOMER-IN-N = VAL(P-CONTRACT-DATA.ID-CUSTOMER-IN)"
        _, s, e = next(ad._occurrences(line, "ID-CUSTOMER-IN-N"))
        self.assertTrue(ad._is_assignment(line, s, e))
        _, s, e = next(ad._occurrences(line, "ID-CUSTOMER-IN"))
        self.assertFalse(ad._is_assignment(line, s, e))

    def test_arithmetic_forms(self):
        self.assertEqual(self._targets("SUBTRACT 1 FROM #A"), [["#A"]])
        self.assertEqual(self._targets("SUBTRACT #X FROM #A GIVING #B"), [["#B"]])
        self.assertEqual(self._targets("MULTIPLY ROUNDED #A BY 2"), [["#A"]])
        self.assertEqual(self._targets("DIVIDE 3 INTO #A GIVING #Q REMAINDER #R"),
                         [["#Q"], ["#R"]])
        self.assertEqual(self._targets("ADD 1 TO C-RECCNT"), [["C-RECCNT"]])
        self.assertEqual(self._targets("EXAMINE #T FOR 'x' GIVING NUMBER #N"), [["#N"]])

    def test_examine_input_workfile_and_for(self):
        self.assertEqual(self._targets("EXAMINE TEMP_BIRTHDAY FOR '-' DELETE"),
                         [["TEMP_BIRTHDAY"]])
        self.assertEqual(self._targets("EXAMINE #T FOR '-' GIVING POSITION #P"), [["#P"]])
        self.assertEqual(self._targets("IF #T = 'a' THEN EXAMINE #T FOR 'a' DELETE END-IF"), [])
        self.assertEqual(self._targets("INPUT 'isn to delete' DELNAME"),
                         [["'isn", "to", "delete'", "DELNAME"]])
        self.assertEqual(self._targets("READ WORK FILE 1 ONCE RECORD V-REC"), [["V-REC"]])
        self.assertEqual(self._targets("FOR V-CROCC 1 TO *OCCURRENCE(P-CRUISE-DATA.CRUISE-ID)"),
                         [["V-CROCC"]])
        self.assertEqual(self._targets("FOR #I = 1 TO #MAX"), [["#I"]])

    def test_trailing_clauses_and_underscored_names(self):
        self.assertEqual(self._targets("COMPRESS 'nat:' #BLOBID INTO MAKEURL LEAVING NO"),
                         [["MAKEURL"]])
        self.assertEqual(self._targets("IF P-LANGUAGE LT 10 COMPRESS '0' P-LANGUAGE TO V-LANGV LEAVING NO END-IF"),
                         [["V-LANGV"]])
        self.assertEqual(self._targets("SEPARATE #A INTO #B #C WITH DELIMITER ','"),
                         [["#B", "#C"]])
        self.assertEqual(self._targets("MOVE EDITED START-DATE-ALPHA  TO DATE_START (EM=YYYYMMDD)"),
                         [["DATE_START", "(EM=YYYYMMDD)"]])
        self.assertEqual(self._targets("READ NCCRUISE BY START-DATE FROM #FROM"), [])
        self.assertEqual(self._targets("CALLNAT 'CAMSG-N' MSG-GROUP-PARA"), [])
        self.assertEqual(list(ad._data_fields("DEFINE DATA LOCAL\n1 TEMP_BIRTHDAY (A10)\nEND-DEFINE")),
                         [(1, "TEMP_BIRTHDAY", False)])

    def test_pda_population_counts_arithmetic_targets(self):
        objs = {
            "FIX-PDA": _obj("FIX-PDA", "parameter data area", PDA_SRC),
            "FIX-LDA": _obj("FIX-LDA", "local data area", LDA_SRC),
            "FIX-SVC": _obj("FIX-SVC", "subprogram", ARITH_SVC_SRC),
        }
        refs, _ = ad._references(objs)
        rows = {r["field"]: r for r in ad._pda_field_population(objs, refs)}
        self.assertEqual((rows["PERSON-ID"]["assignments"], rows["PERSON-ID"]["reads"]), (1, 0))
        # SUBTRACT ... FROM writes; ADD ... GIVING leaves the operand unchanged
        self.assertEqual((rows["WEEK-COUNT-IN"]["assignments"], rows["WEEK-COUNT-IN"]["reads"]), (1, 1))
        self.assertEqual((rows["TIMESTAMP"]["assignments"], rows["TIMESTAMP"]["reads"]), (1, 0))
        # EXAMINE ... DELETE writes; the COMPRESS then reads it
        self.assertEqual((rows["SURNAME"]["assignments"], rows["SURNAME"]["reads"]), (1, 1))
        self.assertEqual((rows["FIRST-NAME-1"]["assignments"], rows["FIRST-NAME-1"]["reads"]), (1, 0))
        # P_NOTE (underscore) is a different field from P-NOTE
        self.assertEqual((rows["P-NOTE"]["assignments"], rows["P-NOTE"]["reads"]), (0, 1))


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

    def test_executable_lines_exclude_declarations_but_keep_statements(self):
        src = textwrap.dedent("""\
            * header comment
            DEFINE DATA
            PARAMETER USING FIX-PDA
            LOCAL
            1 #A (A1)      /* trailing comment
            1 #B (A1)
            END-DEFINE

            CALLNAT 'X' #A
            MOVE #A TO #B  /* keep
            * MOVE #B TO #A
            END
        """)
        self.assertEqual([l.strip() for l in ad._executable_lines(src)],
                         ["CALLNAT 'X' #A", "MOVE #A TO #B", "END"])
        no_data = "MOVE 1 TO #A\nEND\n"
        self.assertEqual(len(ad._executable_lines(no_data)), 2)

    def test_markers_ignore_ordinary_german_text(self):
        objs = {"MSG": _obj("MSG", "subprogram", """\
            VALUE 9902 COMPRESS 'Reise nicht mehr verfügbar' INTO T
            VALUE 9999 COMPRESS 'Funktion noch nicht implementiert' INTO T
            * TODO remove the exercise stub
            MOVE 'not yet supported' TO T
        """)}
        lines = [m["line"] for m in ad._markers(objs)]
        self.assertEqual(lines, [2, 3, 4])


def _lib_obj(library, name, otype, src):
    o = _obj(name, otype, src)
    o["library"] = library
    o["path"] = f"{library}/{name}"
    return o


# Same-named ``CAMSG-N`` in the presentation library and in a steplib; a
# third copy in a library the steplib chain never reaches.
SHADOW_OBJS = {
    "UI/RDCRUISP": _lib_obj("UI", "RDCRUISP", "program", """\
        DEFINE DATA LOCAL USING SHAREPDA
        END-DEFINE
        MOVE 9800 TO MSG-GROUP-PARA.MSG-NR
        CALLNAT 'CAMSG-N' #A
        CALLNAT 'SVC-N' #A
        END
    """),
    "UI/CAMSG-N": _lib_obj("UI", "CAMSG-N", "subprogram", """\
        DEFINE DATA PARAMETER USING SHAREPDA END-DEFINE
        DECIDE ON FIRST VALUE OF MSG-GROUP-PARA.MSG-NR
          VALUE 9800 COMPRESS 'UI ok' INTO T
          VALUE 9801 COMPRESS 'UI only, never emitted' INTO T
          NONE IGNORE
        END-DECIDE
        END
    """),
    "UI/SHAREPDA": _lib_obj("UI", "SHAREPDA", "parameter data area", """\
        DEFINE DATA PARAMETER
        1 UI-GROUP
          2 UI-FIELD (A10)
        END-DEFINE
    """),
    "STEP/CAMSG-N": _lib_obj("STEP", "CAMSG-N", "subprogram", """\
        DEFINE DATA PARAMETER USING SHAREPDA END-DEFINE
        DECIDE ON FIRST VALUE OF MSG-GROUP-PARA.MSG-NR
          VALUE 9800 COMPRESS 'STEP ok' INTO T
          VALUE 9904 COMPRESS 'STEP invalid customer' INTO T
          VALUE 9905 COMPRESS 'STEP only, never emitted' INTO T
          NONE IGNORE
        END-DECIDE
        END
    """),
    "STEP/SVC-N": _lib_obj("STEP", "SVC-N", "subprogram", """\
        DEFINE DATA PARAMETER USING SHAREPDA END-DEFINE
        MOVE 9904 TO MSG-GROUP-PARA.MSG-NR
        MOVE 9999 TO MSG-GROUP-PARA.MSG-NR
        * MOVE 9905 TO MSG-GROUP-PARA.MSG-NR
        CALLNAT 'CAMSG-N' #A
        CALLNAT 'ORPHAN-N' #A
        END
    """),
    "STEP/SHAREPDA": _lib_obj("STEP", "SHAREPDA", "parameter data area", """\
        DEFINE DATA PARAMETER
        1 STEP-GROUP
          2 STEP-FIELD (A10)
        END-DEFINE
    """),
    "FAR/CAMSG-N": _lib_obj("FAR", "CAMSG-N", "subprogram", """\
        DEFINE DATA LOCAL
        1 #X (A1)
        END-DEFINE
        END
    """),
    "FAR/ORPHAN-N": _lib_obj("FAR", "ORPHAN-N", "subprogram", """\
        END
    """),
}


class ObjectInventory(unittest.TestCase):
    def test_every_library_qualified_definition_is_kept(self):
        objs = ad._objects()
        self.assertEqual(len(objs), 31)
        self.assertTrue(all(k == f"{o['library']}/{o['object']}"
                            for k, o in objs.items()))
        self.assertEqual(ad._shadowed_objects(objs), [])
        self.assertEqual(ad._steplibs(), ["CRUISE16"])

    def test_steplibs_absent_or_unparseable_is_unknown(self):
        self.assertIsNone(ad._steplibs(ad.REPO_ROOT / "does-not-exist"))
        self.assertIsNone(ad._steplibs(ad.REPO_ROOT / "README.md"))

    def test_shadowed_names_are_listed_with_every_definition(self):
        self.assertEqual(ad._shadowed_objects(SHADOW_OBJS), [
            {"object": "CAMSG-N",
             "definitions": ["FAR/CAMSG-N", "STEP/CAMSG-N", "UI/CAMSG-N"]},
            {"object": "SHAREPDA",
             "definitions": ["STEP/SHAREPDA", "UI/SHAREPDA"]},
        ])
        labels = ad._labels(SHADOW_OBJS)
        self.assertEqual(labels["UI/RDCRUISP"], "RDCRUISP")
        self.assertEqual(labels["STEP/CAMSG-N"], "STEP/CAMSG-N")

    def test_resolution_prefers_caller_library_then_steplib_order(self):
        objs = SHADOW_OBJS
        self.assertEqual(ad._find(objs, "CAMSG-N", "UI", ["STEP"]),
                         (["UI/CAMSG-N"], "current library"))
        self.assertEqual(ad._find(objs, "CAMSG-N", "STEP", ["STEP"]),
                         (["STEP/CAMSG-N"], "current library"))
        self.assertEqual(ad._find(objs, "SVC-N", "UI", ["STEP"]),
                         (["STEP/SVC-N"], "steplib STEP"))
        self.assertEqual(ad._find(objs, "CAMSG-N", "OTHER", ["FAR", "STEP"]),
                         (["FAR/CAMSG-N"], "steplib FAR"))
        # unknown steplib order: keep every other definition as a candidate
        self.assertEqual(ad._find(objs, "CAMSG-N", "OTHER", None),
                         (["FAR/CAMSG-N", "STEP/CAMSG-N", "UI/CAMSG-N"],
                          "ambiguous (steplib order unknown)"))
        self.assertEqual(ad._find(objs, "ORPHAN-N", "STEP", ["STEP"]),
                         ([], "outside steplib chain"))
        self.assertEqual(ad._find(objs, "NOPE", "UI", ["STEP"]),
                         ([], "not in analyzed scope"))

    def test_reference_edges_carry_resolution_and_candidates(self):
        refs, _ = ad._references(SHADOW_OBJS, ["STEP"])
        by = {(r["caller"], r["callee"]): r for r in refs}
        r = by[("UI/RDCRUISP", "CAMSG-N")]
        self.assertEqual(r["resolved"], ["UI/CAMSG-N"])
        self.assertEqual(r["candidates"],
                         ["FAR/CAMSG-N", "STEP/CAMSG-N", "UI/CAMSG-N"])
        self.assertEqual(by[("STEP/SVC-N", "CAMSG-N")]["resolved"],
                         ["STEP/CAMSG-N"])
        r = by[("STEP/SVC-N", "ORPHAN-N")]
        self.assertEqual((r["resolved"], r["resolution"], r["candidates"]),
                         ([], "outside steplib chain", ["FAR/ORPHAN-N"]))
        self.assertEqual(by[("UI/RDCRUISP", "SHAREPDA")]["resolved"],
                         ["UI/SHAREPDA"])
        self.assertEqual(by[("STEP/SVC-N", "SHAREPDA")]["resolved"],
                         ["STEP/SHAREPDA"])

    def test_reachability_distinguishes_reached_and_shadowed_definitions(self):
        objs = SHADOW_OBJS
        with mock.patch.object(ad, "UI_LIBRARY", "UI"):
            refs, _ = ad._references(objs, ["STEP"])
            status = {(r["library"], r["object"]): r["status"]
                      for r in ad._reachability(objs, refs, ["STEP"])}
            callers = {(r["library"], r["object"]): r["callers"]
                       for r in ad._reachability(objs, refs, ["STEP"])}
        self.assertEqual(status[("UI", "RDCRUISP")], "entry point (NJX page adapter)")
        self.assertEqual(status[("UI", "CAMSG-N")], "reachable from UI root")
        self.assertEqual(status[("STEP", "SVC-N")], "reachable from UI root")
        self.assertEqual(status[("STEP", "CAMSG-N")], "reachable from UI root")
        self.assertEqual(status[("STEP", "SHAREPDA")], "reachable from UI root")
        self.assertEqual(status[("UI", "SHAREPDA")], "reachable from UI root")
        self.assertEqual(
            status[("FAR", "CAMSG-N")],
            "shadowed: same-named object in another library is the one reached")
        self.assertEqual(
            status[("FAR", "ORPHAN-N")],
            "referenced by name but outside the caller's steplib chain")
        self.assertEqual(callers[("STEP", "CAMSG-N")], ["SVC-N"])
        self.assertEqual(callers[("UI", "CAMSG-N")], ["RDCRUISP"])
        self.assertEqual(callers[("FAR", "CAMSG-N")], [])

    def test_ambiguous_resolution_reaches_every_candidate(self):
        objs = {k: v for k, v in SHADOW_OBJS.items() if not k.startswith("FAR/")}
        objs["OTHER/CALLER"] = _lib_obj("OTHER", "CALLER", "program", """\
            CALLNAT 'CAMSG-N' #A
            END
        """)
        refs, _ = ad._references(objs, None)
        r = next(r for r in refs if r["caller"] == "OTHER/CALLER")
        self.assertEqual(r["resolved"], ["STEP/CAMSG-N", "UI/CAMSG-N"])
        self.assertEqual(r["resolution"], "ambiguous (steplib order unknown)")

    def test_message_reconciliation_groups_emitters_per_resolved_catalog(self):
        with mock.patch.object(ad, "UI_LIBRARY", "UI"):
            mc = ad._message_codes(SHADOW_OBJS, ["STEP"])
        self.assertEqual(mc["primary"], "UI/CAMSG-N")
        by = {c["key"]: c for c in mc["catalogs"]}
        self.assertEqual(set(by), {"FAR/CAMSG-N", "STEP/CAMSG-N", "UI/CAMSG-N"})
        # RDCRUISP (UI) reaches UI/CAMSG-N: 9800 emitted there, 9801 never
        ui = by["UI/CAMSG-N"]
        self.assertEqual(ui["catalog"], [9800, 9801])
        self.assertEqual(ui["emitted"], {"9800": ["RDCRUISP"]})
        self.assertEqual(ui["cataloged_never_emitted"], [9801])
        self.assertEqual(ui["emitted_not_cataloged"], [])
        self.assertEqual(ui["emitters"], {"RDCRUISP": "current library"})
        self.assertEqual(ui["commented_out_emits"], [])
        # SVC-N (STEP) reaches STEP/CAMSG-N, never the UI copy: 9904 is
        # cataloged there, 9999 is not, 9905 is only a commented-out emit
        step = by["STEP/CAMSG-N"]
        self.assertEqual(step["catalog"], [9800, 9904, 9905])
        self.assertEqual(step["emitted"], {"9904": ["SVC-N"], "9999": ["SVC-N"]})
        self.assertEqual(step["cataloged_never_emitted"], [9800, 9905])
        self.assertEqual(step["emitted_not_cataloged"], [9999])
        self.assertEqual(step["emitters"], {"SVC-N": "current library"})
        self.assertEqual(step["commented_out_emits"],
                         [{"object": "SVC-N", "line": 4, "code": 9905}])
        # the shadowed FAR copy is reached by nobody
        self.assertEqual(by["FAR/CAMSG-N"]["emitters"], {})
        self.assertEqual(by["FAR/CAMSG-N"]["emitted"], {})
        self.assertEqual(mc["emitters_without_catalog"], [])
        self.assertEqual(mc["ambiguous_emitters"], [])
        # top-level view == the primary (UI-resolved) catalog, not a pool
        for k in ("catalog", "emitted", "cataloged_never_emitted",
                  "emitted_not_cataloged", "commented_out_emits", "texts"):
            self.assertEqual(mc[k], ui[k], k)
        self.assertEqual(ui["texts"]["9800"], ["UI ok"])
        self.assertEqual(step["texts"]["9800"], ["STEP ok"])

    def test_message_reconciliation_with_unknown_steplib_order_is_ambiguous(self):
        objs = {k: v for k, v in SHADOW_OBJS.items()
                if not k.startswith(("FAR/", "LOST/"))}
        objs["OTHER/EMIT-N"] = _lib_obj("OTHER", "EMIT-N", "subprogram", """\
            MOVE 9904 TO MSG-GROUP-PARA.MSG-NR
            CALLNAT 'CAMSG-N' #A
            END
        """)
        with mock.patch.object(ad, "UI_LIBRARY", "UI"):
            mc = ad._message_codes(objs, None)
        self.assertEqual(mc["ambiguous_emitters"], [
            {"object": "EMIT-N", "codes": [9904],
             "catalogs": ["STEP/CAMSG-N", "UI/CAMSG-N"],
             "resolution": "ambiguous (steplib order unknown)"}])
        by = {c["key"]: c for c in mc["catalogs"]}
        # the ambiguous emission is visible under both candidate catalogs
        self.assertEqual(by["UI/CAMSG-N"]["emitted_not_cataloged"], [9904])
        self.assertEqual(by["STEP/CAMSG-N"]["emitted"]["9904"], ["EMIT-N", "SVC-N"])
        self.assertEqual(by["UI/CAMSG-N"]["emitters"]["EMIT-N"],
                         "ambiguous (steplib order unknown)")
        self.assertEqual(mc["primary"], "UI/CAMSG-N")

    def test_message_reconciliation_emitter_outside_every_catalog_chain(self):
        objs = dict(SHADOW_OBJS)
        objs["LOST/LOST-N"] = _lib_obj("LOST", "LOST-N", "subprogram", """\
            MOVE 9924 TO MSG-GROUP-PARA.MSG-NR
            * MOVE 9925 TO MSG-GROUP-PARA.MSG-NR
            CALLNAT 'CAMSG-N' #A
            END
        """)
        # steplib chain names a library with no CAMSG-N: UI and STEP still
        # reach their own copies, LOST-N reaches nothing
        with mock.patch.object(ad, "UI_LIBRARY", "UI"):
            mc = ad._message_codes(objs, ["NOCAT"])
        self.assertEqual(mc["emitters_without_catalog"], [
            {"object": "LOST-N", "codes": [9924], "commented_out_emits": 1,
             "resolution": "outside steplib chain"}])
        by = {c["key"]: c for c in mc["catalogs"]}
        self.assertEqual(by["UI/CAMSG-N"]["emitted"], {"9800": ["RDCRUISP"]})
        self.assertEqual(by["STEP/CAMSG-N"]["emitted"],
                         {"9904": ["SVC-N"], "9999": ["SVC-N"]})
        self.assertNotIn("9924", by["UI/CAMSG-N"]["emitted"])
        self.assertNotIn("9924", by["STEP/CAMSG-N"]["emitted"])

    def test_message_reconciliation_without_any_catalog_in_scope(self):
        objs = {"SOLO/SVC-N": _lib_obj("SOLO", "SVC-N", "subprogram", """\
            MOVE 9904 TO MSG-GROUP-PARA.MSG-NR
            END
        """)}
        mc = ad._message_codes(objs, [])
        self.assertIsNone(mc["primary"])
        self.assertEqual(mc["catalogs"], [])
        self.assertEqual(mc["catalog"], [])
        self.assertEqual(mc["emitted"], {})
        self.assertEqual(mc["emitters_without_catalog"], [
            {"object": "SVC-N", "codes": [9904], "commented_out_emits": 0,
             "resolution": "not in analyzed scope"}])

    def test_using_scope_takes_the_data_area_the_caller_actually_reaches(self):
        refs, _ = ad._references(SHADOW_OBJS, ["STEP"])
        scopes = ad._scopes(SHADOW_OBJS, refs)
        self.assertEqual([s["name"] for s in scopes["UI/RDCRUISP"]], ["UI-GROUP"])
        self.assertEqual([s["name"] for s in scopes["STEP/SVC-N"]], ["STEP-GROUP"])
        self.assertEqual([s["owner"] for s in scopes["STEP/SVC-N"]], ["STEP/SHAREPDA"])



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

    def test_every_reference_resolves_uniquely_in_sample(self):
        self.assertEqual(self.result["steplib_chain"], ["CRUISE16"])
        self.assertEqual(self.ct["shadowed_objects"], [])
        self.assertEqual(self.ct["unresolved_references"], [])
        self.assertEqual(self.ct["ambiguous_references"], [])
        self.assertEqual(self.ct["references_across_shadowed_names"], [])
        self.assertEqual(self.ct["definitions_not_reached_by_name_resolution"], [])
        how = {r["resolution"] for r in self.result["references"]}
        self.assertEqual(how, {"current library", "steplib CRUISE16"})
        cross = {r["caller"] for r in self.result["references"]
                 if r["resolution"] == "steplib CRUISE16"}
        self.assertEqual(cross, {"RDCRUISP", "DELETECU"})
        self.assertTrue(all(len(r["resolved"]) == 1 for r in self.result["references"]))

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
        # one catalog definition in the sample; every emitter resolves to it
        self.assertEqual(self.ct["message_catalogs"], ["CAMSG-N"])
        self.assertEqual(self.ct["message_emitters_without_catalog"], [])
        self.assertEqual(self.ct["message_emitters_ambiguous_catalog"], [])
        self.assertEqual(mc["primary"], "CRUISE16/CAMSG-N")
        self.assertEqual(len(mc["catalogs"]), 1)
        self.assertEqual(mc["catalogs"][0]["emitters"], {
            "CONEW-N": "current library", "CRGET-N": "current library",
            "CRLIST-N": "current library", "CUGET-N": "current library",
            "CUMOD-N": "current library", "CUNEW-N": "current library",
        })
        emitters = {e for v in mc["emitted"].values() for e in v}
        emitters |= {c["object"] for c in mc["commented_out_emits"]}
        self.assertEqual(emitters, set(mc["catalogs"][0]["emitters"]))

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
        # onpvLineClick is bound to both onclickmethod and ondblclickmethod
        self.assertEqual(self.ct["ui_event_declarations"], 28)
        self.assertEqual(sum(r["declared_in_ui"] for r in self.result["ui_events"]),
                         self.ct["ui_event_declarations"])
        by_event = {r["event"]: r["declared_in_ui"] for r in self.result["ui_events"]}
        self.assertEqual(by_event["onpvLineClick"], 2)
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
