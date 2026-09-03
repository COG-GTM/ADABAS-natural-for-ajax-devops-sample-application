# Equivalence testing and penny-level reconciliation

Harnesses that compare HCM outputs to legacy behaviour: clean batch versus broken batch, control totals, penny-level amount reconciliation, record-level audit trail, and exception review — on synthetic data.

| | |
|---|---|
| **Capability** | Equivalence testing and penny-level reconciliation |
| **Why it matters to an SI implementing an HCM** | Proof of correctness is the deliverable. The SI loads HCM output back into the harness and gets a signed reconciliation, not an assertion. |
| **Builds on** | `../tests/harness/natural_model.py`, `../tests/harness/source_parser.py`, `../tests/harness/adabas_sim.py`, `../tests/test_conew_booking.py`, `../tests/test_concurrency.py` |
| **Maturity** | Demonstrated (harness output is checked in and reproducible) |

## Contents

- `equivalence-approach.md` — what is compared, how, and what a pass means
- `harness/` — executable reconciliation with clean and broken synthetic batches
- `sample-output/` — checked-in reconciliation reports and audit trails
- `diagrams/` — reconciliation flow

## How an SI consumes this

Export HCM results (e.g. payroll register / balances for the analog scenario) in the documented layout, run the harness, and attach the reconciliation report to the test evidence pack. Python here is a validation harness, not a rewrite target.

## Synthetic data and scope

All evidence in this directory is produced from the Sunny Islands Cruise sample sources and synthetic data in `../../tests/harness/`. No production system, production data, or FPPS source is used or required. FPPS statements are analogies to a Software AG Natural 9.x / ADABAS 8.6 estate (~7M lines of Natural, 100k+ modules, ~7,800 JCL jobs); nothing here proposes a language rewrite.

← [Back to the navigation hub](../README.md)
