# FPPS → HCM modernization deliverable package

**Requirements-first extraction of validated business logic from a Software AG Natural / ADABAS estate, packaged so a payroll systems integrator can read, verify, and implement it in Oracle HCM (or an alternate HCM) — with Python used only to build the test harnesses that prove the HCM output is right.**

| | |
|---|---|
| **Prepared by** | Cognition AI, Inc. |
| **Prepared for** | Payroll/ERP systems-integrator partners and the Department of the Interior, Interior Business Center (IBC) — Federal Personnel and Payroll System (FPPS) modernization |
| **Source estate modelled** | Sunny Islands Cruise — a real Software AG Natural for AJAX / ADABAS sample application (libraries `CRUISE16`, `RDCRUISE`) that structurally mirrors FPPS |
| **Data** | Synthetic only. No production data, no production access, no FPPS source was used or is required to reproduce anything in this package. |

---

## Why this package exists

FPPS is **Software AG Natural 9.x (~7M lines of Natural, 100k+ modules) on ADABAS 8.6, z/OS 2.5, with ~7,800 JCL jobs.** It is not COBOL, and the path to a modern HCM is not a language-to-language conversion. The path is:

1. **Extract** what the estate actually does — every rule, edit, data element, process, and interface — with a citation back to the exact Natural source line.
2. **Validate** it — bidirectional traceability, confidence scoring, and executable harnesses on synthetic data that anyone can rerun.
3. **Decide** what to carry, replace, redesign, or retire — including the dead, unreachable, and obsolete logic that must **not** be re-implemented.
4. **Hand it to the SI** as a requirements baseline, data-mapping input, BPMN process set, and acceptance harness that feeds straight into Oracle HCM configuration and HCM Data Loader.

Traditional requirements gathering for an estate of this size has been quoted at roughly **$30M**. This package demonstrates — on a real Natural/ADABAS application, end to end — how that baseline is produced provably and in a fraction of the time.

> **Differentiator — the rule a naive converter loses.** `CONEW-N.NSN` (booking = the pay/personnel transaction analog) originally read `CRUISE-STATUS` outside a record hold and generated `CONTRACT-ID` as MAX+1 without holding the highest record. Under multi-user load that silently oversells the cruise and raises duplicate-key errors — the exact class of defect that silently corrupts a pay run. The extraction surfaces this as an *integrity requirement* (test-and-set under hold; serialized key generation), not as code to translate. See [`docs/concurrency-refactor.md`](../docs/concurrency-refactor.md) and [`02-business-rule-extraction/`](02-business-rule-extraction/).

---

## Navigation hub

Each directory contains presentation-grade artifacts, Mermaid diagrams (with exported images where available), traceability tables, an explicit synthetic-data statement, and a short **"How an SI consumes this"** note.

| # | Directory | Capability | Why it matters to an SI implementing an HCM | Builds on (existing repository artifacts) |
|---|---|---|---|---|
| 00 | [`00-executive-value-brief/`](00-executive-value-brief/) | Executive value brief (Markdown master + branded [PDF](00-executive-value-brief/Cognition-FPPS-HCM-Executive-Value-Brief.pdf)) | Gives program leadership the positioning, scope split, proof points, and honest maturity statement needed to sponsor the approach | Everything below; [`docs/concurrency-refactor.md`](../docs/concurrency-refactor.md) |
| 01 | [`01-discoverability-comprehension-baseline/`](01-discoverability-comprehension-baseline/) | Discoverability & comprehension baseline | You cannot scope, price, or configure what you cannot see. Architecture map, module inventory, and call graph across the business-logic (`CRUISE16`) and presentation (`RDCRUISE`) libraries | [`docs/module-inventory.md`](../docs/module-inventory.md), [`docs/call-map.md`](../docs/call-map.md) |
| 02 | [`02-business-rule-extraction/`](02-business-rule-extraction/) | Business-rule extraction with source traceability & confidence | Rules are the eligibility/validation edits an HCM must reproduce. Every rule cites file + line in the real `.NSN` source and carries a confidence score | `CRUISE16/Subprograms/CONEW-N.NSN` (codes 9800/9902/9904/9905/9918), `CAMSG-N.NSN`, [`tests/test_source_conformance.py`](../tests/test_source_conformance.py) |
| 03 | [`03-data-model-data-dictionary/`](03-data-model-data-dictionary/) | Master-data model & field-level data dictionary | The definition of master data that HCM Data Loader mapping starts from — formats, lengths, descriptors, usage, lineage, source keys | [`docs/data-dictionary.md`](../docs/data-dictionary.md), [`tools/generate_data_dictionary.py`](../tools/generate_data_dictionary.py), the four DDMs |
| 04 | [`04-business-process-flow-bpmn/`](04-business-process-flow-bpmn/) | Business-process flows (BPMN-oriented) | Process definitions an HCM configuration/BPM team can ingest and map to Oracle HCM approval and transaction flows | [`docs/transaction-flows.md`](../docs/transaction-flows.md) |
| 05 | [`05-requirements-baseline/`](05-requirements-baseline/) | Requirements baseline (the strategic prize) | The SI-consumable requirements document — with acceptance criteria and disposition — that replaces months of interview-driven requirements gathering | 01, 02, 03, 04, 10 |
| 06 | [`06-interface-dependency-mapping/`](06-interface-dependency-mapping/) | Interface & dependency mapping | `CALLNAT`/`FETCH`/`INCLUDE`/`USING` relationships, STEPLIB/deployment configuration, and how the pattern scales to FPPS's bidirectional interfaces, datamarts, batch/JCL, and client agencies | [`docs/call-map.md`](../docs/call-map.md), `SunnyIslands/deploy/natdeploy*.xml` |
| 07 | [`07-master-data-cleansing/`](07-master-data-cleansing/) | Master-data cleansing & reconciliation pattern | Dirty legacy master data is the leading cause of failed HCM loads and post-go-live defects; profile → cleanse → reconcile before HDL | 03, [`tests/harness/adabas_sim.py`](../tests/harness/adabas_sim.py), [`tests/harness/fixtures.py`](../tests/harness/fixtures.py) |
| 08 | [`08-equivalence-testing-reconciliation/`](08-equivalence-testing-reconciliation/) | Equivalence testing & penny-level reconciliation | Proves HCM output equals legacy behaviour: clean vs broken batch, control totals, record-level audit trail, exception review — all executable on synthetic data | [`tests/harness/natural_model.py`](../tests/harness/natural_model.py), [`tests/harness/source_parser.py`](../tests/harness/source_parser.py) |
| 09 | [`09-unit-test-regression-jcl-runcompare/`](09-unit-test-regression-jcl-runcompare/) | Unit-test, regression & JCL run-compare generation | Test automation is what the HRD RFI asked for; regression coverage is what protects a pay run during and after cut-over | [`tests/`](../tests/), [`.github/workflows/regression-tests.yml`](../.github/workflows/regression-tests.yml), [`docs/testing-and-ci.md`](../docs/testing-and-ci.md) |
| 10 | [`10-migration-disposition-dead-code/`](10-migration-disposition-dead-code/) | Migration disposition: dead, unreachable & obsolete logic | What **not** to build. Systems, functions, fields, messages, and paths that do not map to an HCM — with evidence, confidence, and SME sign-off columns so nothing is retired by guesswork | [`tools/analyze_disposition.py`](../tools/analyze_disposition.py), [`tests/test_disposition_analysis.py`](../tests/test_disposition_analysis.py) |

---

## Sample ↔ FPPS analogy (used consistently in every directory)

| Sunny Islands Cruise (this repository) | FPPS / federal payroll analog |
|---|---|
| Booking transaction (`CONEW-N`) | Pay / personnel transaction (e.g. a personnel action posting to payroll) |
| Message-code edits (`CAMSG-N` catalog; 9800/9902/9904/9905/9918) | Payroll validation edits and error catalogue |
| ADABAS DDMs (`NCCRUISE`, `NCCONTRACT`, `NCCUSTOMER`, `NCYACHT`) | FPPS personnel-payroll data model |
| Record-hold / test-and-set / serialized MAX+1 key in `CONEW-N` | Pay-run integrity (no double-posting, no duplicate keys under concurrent input) |
| `CRUISE16` business-logic library | FPPS core Natural service libraries |
| `RDCRUISE` Natural for AJAX presentation library | Web FPPS presentation layer |
| `natdeploy*.xml` STEPLIB / deployment configuration | Natural STEPLIB chains and Control-M / JCL job configuration |

---

## Reading the maturity labels

Every capability statement in this package is tagged so prose, diagrams, and tables tell the same story:

| Label | Meaning |
|---|---|
| **Demonstrated** | Runs in this repository today; output is checked in and reproducible with the commands below |
| **Designed** | Method and artifacts are specified against the sample; not yet executed at FPPS scale |
| **Roadmap** | Depends on inputs this repository does not contain (real FPPS JCL, Natural Predict/XRef exports, runtime traces, SME sign-off) |

---

## Reproduce the evidence

```bash
python3 -m unittest discover -s tests -v          # regression + source-conformance + disposition drift tests
python3 -m compileall -q tests tools
python3 tools/generate_data_dictionary.py          # regenerates docs/data-dictionary.md from the DDMs
python3 tools/analyze_disposition.py               # regenerates 10-.../evidence/ from the Natural sources
# every capability generator also supports --check (drift gate), e.g.:
python3 fpps-hcm-modernization-deliverable/10-migration-disposition-dead-code/generate_ledger.py --check
```

All generated artifacts carry a "generated — do not edit by hand" header, and the test suite fails if a committed artifact drifts from its generator.

---

## Scope and honesty statements

- **Synthetic data only.** The ADABAS files are simulated in `tests/harness/adabas_sim.py`; no production system is touched. This is what makes the offer "validate our output yourself" credible without an ATO or data-sharing agreement.
- **FPPS scale figures.** The documented figure used throughout is **~7M lines of Natural / 100k+ modules / ~7,800 JCL jobs**. A separate ~63M LOC figure has circulated in meeting notes; it is unverified and is not used as an equivalent. Which figure is right changes effort estimates, not the method.
- **Not a rewrite.** Nothing here proposes converting Natural to Python or any other language. Python appears only in validation harnesses and generators.
- **Sample, not FPPS.** Sunny Islands Cruise is a public Software AG sample. Findings about it are real; the FPPS analogies are analogies.

See [`AUTHORING-CONVENTIONS.md`](AUTHORING-CONVENTIONS.md) for the rules every artifact in this package follows.
