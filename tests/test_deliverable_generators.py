"""Every generated artifact in the modernization deliverable must match what
its generator produces from the current sources.

Each capability generator exposes ``--check`` (regenerate in memory, exit 1 on
drift).  Running them here puts the drift gates in the CI regression suite
instead of leaving them as hand-run commands.  The inventory test is
bidirectional: every listed generator must exist, and every ``*.py`` under the
deliverable that implements ``--check`` must be listed.
"""

import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE = REPO_ROOT / "fpps-hcm-modernization-deliverable"

GENERATORS = (
    "01-discoverability-comprehension-baseline/generate_inventory.py",
    "02-business-rule-extraction/generate_rule_evidence.py",
    "03-data-model-data-dictionary/generate_dictionary_hcm.py",
    "04-business-process-flow-bpmn/generate_process_evidence.py",
    "06-interface-dependency-mapping/generate_dependency_map.py",
    "07-master-data-cleansing/harness/cleanse_reconcile.py",
    "08-equivalence-testing-reconciliation/harness/reconcile.py",
    "09-unit-test-regression-jcl-runcompare/generator/build_suite_map.py",
    "10-migration-disposition-dead-code/generate_ledger.py",
)


def _scripts_with_check_flag():
    found = set()
    for path in sorted(PACKAGE.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        if '"--check"' in path.read_text(encoding="utf-8"):
            found.add(path.relative_to(PACKAGE).as_posix())
    return found


class DeliverableGenerators(unittest.TestCase):
    def test_generator_inventory_is_bidirectional(self):
        self.assertEqual(set(GENERATORS), _scripts_with_check_flag())
        for rel in GENERATORS:
            self.assertTrue((PACKAGE / rel).is_file(), rel)

    def test_every_generated_artifact_matches_its_generator(self):
        for rel in GENERATORS:
            with self.subTest(generator=rel):
                result = subprocess.run(
                    [sys.executable, str(PACKAGE / rel), "--check"],
                    cwd=REPO_ROOT, capture_output=True, text=True, timeout=600,
                )
                self.assertEqual(
                    result.returncode, 0,
                    f"drift detected:\n{result.stdout}\n{result.stderr}")


if __name__ == "__main__":
    unittest.main()
