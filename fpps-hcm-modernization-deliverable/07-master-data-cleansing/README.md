# Master-data cleansing and reconciliation

Profiling, cleansing-rule, and reconciliation pattern for legacy master data before HCM loading, executed against synthetic ADABAS data.

| | |
|---|---|
| **Capability** | Master-data cleansing and reconciliation |
| **Why it matters to an SI implementing an HCM** | Dirty master data — orphaned keys, inconsistent name fields, missing supervisors, invalid organisation relationships — is the leading cause of failed loads and post-go-live defects. |
| **Builds on** | 03, `../tests/harness/adabas_sim.py`, `../tests/harness/fixtures.py`, DDM field-usage evidence from 10 |
| **Maturity** | Demonstrated for the pattern on synthetic data; Designed for FPPS field rules |

## Contents

- `cleansing-approach.md` — profile → rule → cleanse → reconcile method
- `cleansing-rules.md` — rule catalogue keyed to dictionary fields
- `harness/` — executable profiling/cleansing/reconciliation on synthetic data with checked-in output
- `diagrams/` — pipeline and reconciliation diagrams

## How an SI consumes this

Run the profiling step against extracted legacy data, apply the rule catalogue, and load only records that pass reconciliation into HCM Data Loader; carry exceptions to a data-steward queue.

## Synthetic data and scope

All evidence in this directory is produced from the Sunny Islands Cruise sample sources and synthetic data in `../../tests/harness/`. No production system, production data, or FPPS source is used or required. FPPS statements are analogies to a Software AG Natural 9.x / ADABAS 8.6 estate (~7M lines of Natural, 100k+ modules, ~7,800 JCL jobs); nothing here proposes a language rewrite.

← [Back to the navigation hub](../README.md)
