# Business-rule extraction with source traceability

Plain-language business rules, each with an exact `.NSN` file and line citation, a rule class (validation edit, integrity/concurrency, derivation, lookup, message/translation, workflow/transaction boundary, presentation), the message code it emits, a computed confidence score, an HCM analog and a disposition. The catalogue is written the way a payroll SI reads an eligibility or validation edit, and every count in it is generated from the shipped source.

| | |
|---|---|
| **Capability** | Business-rule extraction with source traceability |
| **Why it matters to an SI implementing an HCM** | Rules are the eligibility and validation edits an HCM must reproduce exactly. Traceability lets the SI verify each rule against the source in minutes; confidence tells them where to spend SME time; the disposition tells them what not to rebuild. |
| **Builds on** | `../../SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN` (codes 9800/9902/9904/9905/9918), `CRLIST-N.NSN`, `CRGET-N.NSN`, `CUGET-N.NSN`, `CUNEW-N.NSN`, `CUMOD-N.NSN` (9934), `CAMSG-N.NSN`, `../../tests/test_source_conformance.py`, `../../tests/test_concurrency.py`, `../../tools/analyze_disposition.py`, `../../docs/concurrency-refactor.md` |
| **Maturity** | Demonstrated (rules cite shipped source; conformance and harness tests in `../../tests/` assert the message-code sets and the concurrency behaviour; generated tables are checked by `generate_rule_evidence.py --check`). SME sign-off is Roadmap. |

## What is in the catalogue

| Section of `business-rules.md` | Rules | What a payroll SI finds there |
|---|---|---|
| 1 Active rules | BR-001 – BR-036 | Edits, derivations, lookups and transaction boundaries that execute today, including the two integrity rules a source-to-source converter loses (BR-006 held test-and-set on the availability counter; BR-007 serialized MAX+1 identifier) |
| 2 Commented-out and disabled rules | BR-D001 – BR-D010 | The 9911–9919 edit chain in `CONEW-N` and the 9915 edit in `CRGET-N`: rules the original authors wrote, then switched off; each carries a retire / SME-required decision |
| 3 Misapplied codes and silent outcomes | BR-M001 – BR-M006 | Places where the code returned does not mean what the catalogue says (`CRGET-N` returning 9934 for a not-found read; an unknown offering reported as success) — the defects a faithful conversion would preserve |
| 4 Candidates needing SME confirmation | BR-C001 – BR-C008 | Behaviour that depends on inferred runtime semantics or data content, with the exact question the SME has to answer |

## The differentiator: integrity rules a naive converter loses

```
  Pre-refactor CONEW-N (defect)              Refactored CONEW-N (Demonstrated)
  ─────────────────────────────              ─────────────────────────────────
  FIND cruise ──► read STATUS=1              FIND cruise ──► GET *ISN (HELD) ──► STATUS=1
  [another user reads STATUS=1 here]         [another user BLOCKS here until ET]
  STATUS := 0 ──► UPDATE                     STATUS := 0 ──► UPDATE (held)
  READ MAX contract (no hold) = 1000         READ MAX contract ──► UPDATE (fake, HELD) = 1000
  [another user reads MAX=1000 here]         [another user BLOCKS here until ET]
  STORE 1001 ──► ET                          STORE 1001 ──► ET (holds released)
  result: 2 bookings / 1 place,              result: N places ⇒ exactly N bookings,
          duplicate key 1001                         unique identifiers
```

Both defects and both fixes execute in `../../tests/test_concurrency.py` against the synthetic ADABAS simulation. In the baseline they are REQ-I-001 and REQ-I-002 — requirements on the target HCM, not instructions to reproduce ADABAS hold logic. Pay-run analogy: a payroll run that reads an entitlement balance, decides, and writes back without a lock is the same defect.

## Contents

| File | Purpose |
|---|---|
| `business-rules.md` | The rule catalogue: 60 entries in four sections, each with ID, statement, class, citation, codes, confidence, HCM analog, disposition; generated message-code tables |
| `rule-traceability-matrix.md` | Rule ↔ source line ↔ message code ↔ existing test in `../../tests/` ↔ requirement ID in `../05-requirements-baseline/`; generated code-to-test coverage and coverage summary |
| `confidence-model.md` | The scoring rubric (static citation, conformance test, harness execution, documentation, inference and data penalties, SME sign-off), worked examples, and the generated score distribution |
| `diagrams/` | Mermaid source and rendered SVG/PNG for the `CONEW-N` decision flow, the before/after concurrency sequence, the `CUMOD-N` optimistic-concurrency sequence and the message-code lifecycle |
| `generate_rule_evidence.py` | Validation generator (Python is used only for this; it converts nothing). Rewrites every `<!-- generated:... -->` block in this directory and in `../05-requirements-baseline/` from `tests.harness.source_parser` and `tools.analyze_disposition`; `--check` exits non-zero if a committed block, a citation line range, a BR/REQ cross-reference or a confidence score is stale |

## Reproduce

```bash
# from the repository root
python3 fpps-hcm-modernization-deliverable/02-business-rule-extraction/generate_rule_evidence.py --check
python3 -m unittest discover -s tests -v
```

## How an SI consumes this

1. Sort `business-rules.md` by disposition. `carry` rules (BR-006, BR-011, BR-032) become integrity requirements in the Oracle HCM design — element-entry and balance updates that must be atomic, optimistic locking on person records — and go straight into the acceptance-test plan via `../05-requirements-baseline/acceptance-criteria.md`.
2. Map `replace-with-standard-HCM` rules to the configuration object named in the "HCM analog" field (element entry validation, fast formula, person lookup, HDL business-object validation, BPM approval). Record the object name against the rule ID so the traceability matrix extends into the configuration workbook.
3. Take `redesign` rules (fall-through edits, misapplied codes) to the business owner as decisions, using the rule statement as the question; do not configure them as-is.
4. Retire `retire` rules and confirm the `retire` list against `../05-requirements-baseline/what-we-will-not-build.md`.
5. Book SME time for `SME-required` rules in order of the confidence score (lowest first); each Section 4 entry states the exact question.
6. Load `rule-traceability-matrix.md` into the test-management tool: every row with an existing test is a regression case to port; every "harness needed" row is a test to write before user acceptance.
7. Re-run `generate_rule_evidence.py --check` whenever a citation or a rule is edited; a failing check means the catalogue no longer matches the source it claims to describe.

## Synthetic data and scope

All evidence in this directory is produced from the Sunny Islands Cruise sample sources and synthetic data in `../../tests/harness/`. No production system, production data, or FPPS source is used or required. FPPS statements are analogies to a Software AG Natural 9.x / ADABAS 8.6 estate (~7M lines of Natural, 100k+ modules, ~7,800 JCL jobs); nothing here proposes a language rewrite. Static findings ("unreferenced in analyzed scope", "declared but never assigned") are candidates for SME confirmation, not conclusions.

← [Back to the navigation hub](../README.md)
