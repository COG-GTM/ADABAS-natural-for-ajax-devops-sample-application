# Business-rule extraction with source traceability

Plain-language business rules, each with an exact `.NSN` file and line citation, a rule class (validation edit, integrity, derivation, message, workflow), and a confidence score.

| | |
|---|---|
| **Capability** | Business-rule extraction with source traceability |
| **Why it matters to an SI implementing an HCM** | Rules are the eligibility and validation edits an HCM must reproduce exactly. Traceability lets the SI verify each rule against the source in minutes; confidence tells them where to spend SME time. |
| **Builds on** | `../SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN` (codes 9800/9902/9904/9905/9918), `CAMSG-N.NSN`, `CUMOD-N.NSN`, `../tests/test_source_conformance.py`, `../docs/concurrency-refactor.md` |
| **Maturity** | Demonstrated (rules cite shipped source; conformance tests assert the message-code sets) |

## Contents

- `business-rules.md` — the rule catalogue with traceability and confidence
- `rule-traceability-matrix.md` — rule ↔ source line ↔ message code ↔ test ↔ requirement
- `confidence-model.md` — how confidence scores are assigned and what raises them
- `diagrams/` — decision-flow diagrams for `CONEW-N` validation and integrity paths

## How an SI consumes this

Treat each rule as a candidate HCM validation (fast formula, element-entry validation, approval condition) or an integrity requirement. Confirm low-confidence rules with a payroll SME before configuration; use the matrix to prove coverage in the acceptance-test plan.

## Synthetic data and scope

All evidence in this directory is produced from the Sunny Islands Cruise sample sources and synthetic data in `../../tests/harness/`. No production system, production data, or FPPS source is used or required. FPPS statements are analogies to a Software AG Natural 9.x / ADABAS 8.6 estate (~7M lines of Natural, 100k+ modules, ~7,800 JCL jobs); nothing here proposes a language rewrite.

← [Back to the navigation hub](../README.md)
