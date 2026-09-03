# Migration disposition: dead, unreachable, and obsolete logic

Evidence-backed ledger of everything in the legacy sources that should **not** be carried into an HCM — unreferenced objects, unreachable branches, never-emitted messages, never-populated interface fields, never-referenced data fields, commented-out logic, training scaffolding, presentation infrastructure, and administrative utilities — with confidence, evidence class, SME flag, and decision status.

| | |
|---|---|
| **Capability** | Migration disposition: dead, unreachable, and obsolete logic |
| **Why it matters to an SI implementing an HCM** | Blindly preserving legacy logic is how programmes re-implement bugs and dead paths at HCM prices. A defensible disposition ledger shrinks scope and de-risks sign-off. |
| **Builds on** | `../tools/analyze_disposition.py`, `../tests/test_disposition_analysis.py`, [`evidence/`](evidence/) (generated), Software AG Predict XRef verification concepts |
| **Maturity** | Demonstrated (evidence generated and drift-tested); SME confirmation columns are Roadmap by nature |

## Contents

- `disposition-ledger.md` — one row per finding with evidence, confidence, disposition, owner, status
- `taxonomy.md` — disposition categories aligned to consistency/completeness/correctness verification
- `copy-it-wrong-gallery.md` — subtle defects and obsolete logic a naive conversion would faithfully reproduce
- `evidence/` — generated reachability, message-catalogue, field-usage, and interface-population evidence
- `fpps-scale-evidence-plan.md` — what raises confidence at FPPS scale
- `diagrams/` — reachability diagram

## How an SI consumes this

Take the ledger into scope sign-off. Anything marked *retire* or *replace with standard HCM* leaves the requirements baseline; anything marked *SME required* is a discovery question, not a configuration item.

## Synthetic data and scope

All evidence in this directory is produced from the Sunny Islands Cruise sample sources and synthetic data in `../../tests/harness/`. No production system, production data, or FPPS source is used or required. FPPS statements are analogies to a Software AG Natural 9.x / ADABAS 8.6 estate (~7M lines of Natural, 100k+ modules, ~7,800 JCL jobs); nothing here proposes a language rewrite.

← [Back to the navigation hub](../README.md)
