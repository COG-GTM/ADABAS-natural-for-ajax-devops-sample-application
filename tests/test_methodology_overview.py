"""The customer-facing methodology page must quote the generated evidence,
not a snapshot of it.

Every count on ``00-executive-value-brief/methodology-overview.html`` that
comes from a generated artifact is wrapped in an element carrying
``data-metric="<key>"``.  This test derives each key's expected text from the
artifact that owns the number (rule catalogue, requirements baseline,
disposition evidence JSON, reconciliation summaries, the test suite itself)
and fails when the page and the artifact disagree in either direction:
a key the page uses but this test does not know, or a key this test knows
but the page no longer shows, is also a failure.

The page is also required to be genuinely self-contained: no stylesheet,
script, font, or image may be fetched from the network.
"""

import json
import re
import unittest
from html.parser import HTMLParser
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE = REPO_ROOT / "fpps-hcm-modernization-deliverable"
PAGE = PACKAGE / "00-executive-value-brief" / "methodology-overview.html"
RULES_MD = PACKAGE / "02-business-rule-extraction" / "business-rules.md"
REQS_MD = PACKAGE / "05-requirements-baseline" / "requirements-baseline.md"
ACS_MD = PACKAGE / "05-requirements-baseline" / "acceptance-criteria.md"
EVIDENCE_JSON = (PACKAGE / "10-migration-disposition-dead-code" / "evidence"
                 / "disposition-evidence.json")
LEDGER_MD = PACKAGE / "10-migration-disposition-dead-code" / "disposition-ledger.md"
RECON_OUT = PACKAGE / "08-equivalence-testing-reconciliation" / "sample-output"

RULE_DEF_RE = re.compile(r"^### (BR-(?:D|C|M)?\d{3})\b", re.MULTILINE)
REQ_DEF_RE = re.compile(r"^### (REQ-[FDIXN]-\d{3})\b", re.MULTILINE)
AC_DEF_RE = re.compile(r"^\| (AC-REQ-[FDIXN]-\d{3}-\d+) ", re.MULTILINE)
FINDING_DEF_RE = re.compile(r"^\| (D-\d{2}) ", re.MULTILINE)
REMOTE = r"""\s*["']?(?:https?:)?//"""
# Anything the browser fetches while rendering: <link href>, src= on any
# element, CSS @import and url().  Outbound <a href> navigation is allowed.
FETCH_RES = (
    re.compile(r"<link\b[^>]*\bhref=" + REMOTE, re.I),
    re.compile(r"\bsrc=" + REMOTE, re.I),
    re.compile(r"\bsrcset=" + REMOTE, re.I),
    re.compile(r"@import" + REMOTE, re.I),
    re.compile(r"\burl\(" + REMOTE, re.I),
)


class _MetricCollector(HTMLParser):
    """Collects the text content of every element carrying data-metric."""

    def __init__(self):
        super().__init__()
        self.metrics = []
        self._open = []

    def handle_starttag(self, tag, attrs):
        for depth in range(len(self._open)):
            self._open[depth][2] += 1
        key = dict(attrs).get("data-metric")
        if key is not None:
            self._open.append([key, [], 1])

    def handle_endtag(self, tag):
        for entry in self._open:
            entry[2] -= 1
        while self._open and self._open[-1][2] == 0:
            key, chunks, _ = self._open.pop()
            self.metrics.append((key, "".join(chunks).strip()))

    def handle_data(self, data):
        for entry in self._open:
            entry[1].append(data)


def _page_metrics(text):
    parser = _MetricCollector()
    parser.feed(text)
    parser.close()
    return parser.metrics


def _money(cents, signed=False):
    value = f"${abs(cents) / 100:,.2f}"
    if signed and cents > 0:
        return "+" + value
    if cents < 0:
        return "-" + value
    return value


def _count_tests():
    loader = unittest.TestLoader()
    suite = loader.discover(str(REPO_ROOT / "tests"), top_level_dir=str(REPO_ROOT))
    return suite.countTestCases()


def _remote_fetches(text):
    hits = []
    for pattern in FETCH_RES:
        for match in pattern.finditer(text):
            hits.append(text[match.start():match.start() + 80])
    return hits


def expected_metrics():
    rules = RULE_DEF_RE.findall(RULES_MD.read_text(encoding="utf-8"))
    reqs = REQ_DEF_RE.findall(REQS_MD.read_text(encoding="utf-8"))
    acs = set(AC_DEF_RE.findall(ACS_MD.read_text(encoding="utf-8")))
    findings = set(FINDING_DEF_RE.findall(LEDGER_MD.read_text(encoding="utf-8")))
    totals = json.loads(EVIDENCE_JSON.read_text(encoding="utf-8"))["control_totals"]
    clean = json.loads((RECON_OUT / "clean" / "summary.json").read_text(encoding="utf-8"))
    broken = json.loads((RECON_OUT / "broken" / "summary.json").read_text(encoding="utf-8"))
    clean_legacy = clean["control_totals"]["legacy_expected"]
    clean_hcm = clean["control_totals"]["hcm_output"]

    code_order = sorted(c for c in clean_legacy["count_by_msg_nr"] if c != "0")

    def codes(side):
        return " · ".join(str(side["count_by_msg_nr"].get(c, 0)) for c in code_order)

    def price_sum(side):
        return f"{float(side['price_sum']):,.2f}"

    cataloged = totals["message_codes_cataloged"]
    never = totals["message_codes_cataloged_never_emitted"]
    broken_diff = broken["control_totals"]["price_sum_diff_cents"]
    return {
        "rules": str(len(rules)),
        "requirements-acceptance": f"{len(reqs)} / {len(acs)}",
        "findings": str(len(findings)),
        "tests": str(_count_tests()),
        "codes-never-emitted-of-catalogued": f"{never} of {cataloged}",
        "codes-never-emitted-per-catalogued": f"{never} / {cataloged}",
        "codes-commented-out": str(totals["commented_out_message_emits"]),
        "pda-never-assigned": str(len(totals["pda_fields_never_assigned"])),
        "ddm-never-referenced": str(totals["ddm_fields_never_referenced"]),
        "commented-out-statements": str(totals["commented_out_statements"]),
        "clean-matched": f"{clean['records_matched']} / {clean['records_expected']}",
        "clean-exceptions": str(clean["exception_count"]),
        "clean-variance": _money(clean["control_totals"]["price_sum_diff_cents"]),
        "clean-legacy-accepted-rejected":
            f"{clean_legacy['accepted_count']} / {clean_legacy['rejected_count']}",
        "clean-hcm-accepted-rejected":
            f"{clean_hcm['accepted_count']} / {clean_hcm['rejected_count']}",
        "clean-code-columns": "Codes " + " · ".join(code_order),
        "clean-legacy-codes": codes(clean_legacy),
        "clean-hcm-codes": codes(clean_hcm),
        "clean-legacy-price-sum": price_sum(clean_legacy),
        "clean-hcm-price-sum": price_sum(clean_hcm),
        "clean-legacy-distinct-ids":
            f"{clean_legacy['distinct_contract_id_count']} of {clean_legacy['contract_id_count']}",
        "clean-hcm-distinct-ids":
            f"{clean_hcm['distinct_contract_id_count']} of {clean_hcm['contract_id_count']}",
        "broken-matched": f"{broken['records_matched']} / {broken['records_expected']}",
        "broken-exceptions": str(broken["exception_count"]),
        "broken-checks": str(len(broken["exceptions_by_check"])),
        "broken-variance": _money(broken_diff, signed=True),
        "broken-price-diff-cents": f"{broken_diff:+,d}",
    }


class MethodologyOverviewPage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = PAGE.read_text(encoding="utf-8")
        cls.page = _page_metrics(cls.text)
        cls.expected = expected_metrics()

    def test_metric_keys_match_in_both_directions(self):
        on_page = {key for key, _ in self.page}
        self.assertEqual(on_page, set(self.expected))

    def test_every_quoted_metric_matches_its_generated_source(self):
        for key, shown in self.page:
            with self.subTest(metric=key):
                self.assertEqual(shown, self.expected[key])

    def test_clean_batch_is_reported_reconciled(self):
        clean = json.loads((RECON_OUT / "clean" / "summary.json").read_text(encoding="utf-8"))
        self.assertEqual(clean["result"], "RECONCILED")
        self.assertIn("RESULT: RECONCILED", self.text)
        self.assertIn("RESULT: EXCEPTIONS (", self.text)

    def test_page_makes_no_network_requests(self):
        self.assertEqual(_remote_fetches(self.text), [])
        self.assertNotIn("fonts.googleapis.com", self.text)
        self.assertNotIn("fonts.gstatic.com", self.text)
        for family in ("Inter", "Inter Tight", "JetBrains Mono"):
            with self.subTest(font=family):
                self.assertIn(f"@font-face{{font-family:'{family}'", self.text)

    def test_page_has_no_unresolved_placeholders(self):
        self.assertNotIn("{{", self.text)


if __name__ == "__main__":
    unittest.main()
