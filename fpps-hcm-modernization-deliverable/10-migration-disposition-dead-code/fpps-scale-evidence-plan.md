# Evidence plan at FPPS scale

The sample proves the *method*: a static analyzer produces candidates with an evidence class, a ledger binds every candidate to a decision, and drift tests keep the two synchronised. At the scale of FPPS — Software AG Natural 9.x, ADABAS 8.6, z/OS 2.5, roughly 7M lines of Natural in 100k+ modules with about 7,800 JCL jobs — static candidates alone are not enough to retire anything. This plan lists what raises confidence, in the order it is normally available, and what each source rules in or out. Everything below the first row is **Roadmap**: it depends on FPPS artefacts that a sample repository cannot contain.

## Evidence sources and what they settle

| Order | Source | Maturity | What it adds | Ledger effect |
|---|---|---|---|---|
| 1 | Static analysis of the Natural sources (this repository's `../../tools/analyze_disposition.py`, extended to the full library list) | Demonstrated on the sample | Literal `CALLNAT` / `FETCH` / `INCLUDE` / `USING` graph, message-catalogue reconciliation, DDM and PDA field usage, comment and marker scan, library-aware resolution through the steplib chain | Populates every S-class row |
| 2 | Natural Predict / XRef export (or Natural Engineer inventory) | Roadmap | Estate-wide cross-reference including objects outside the libraries under analysis, dynamic call targets resolved from data, and DDM-to-program usage | Converts "unreferenced in analyzed scope" into "unreferenced estate-wide"; closes S1 gaps |
| 3 | JCL and scheduler evidence (job libraries, Control-M or equivalent schedules, last-run dates) | Roadmap | Which batch programs are still scheduled, how often, and which have not run in a full cycle | Reclassifies standalone programs: scheduled → operational requirement; unscheduled for a full pay year → retire candidate |
| 4 | Runtime evidence: Natural profiler or trace, ADABAS command log or utility statistics over a representative period | Roadmap | Which objects and DDM fields were actually executed or read/updated | R1 on every row; the period must include a full pay year with year-end and any off-cycle processing |
| 5 | Data profiling on a masked extract | Roadmap (method Demonstrated in `../07-master-data-cleansing/`) | Whether "unused" fields are populated at all, and by what | Splits D-08-class rows into drop (empty) versus SME question (populated by another feed) |
| 6 | Client-agency interface inventories | Roadmap | Which interface fields are consumed by downstream agencies and datamarts even when no FPPS program reads them | Prevents retiring fields that only exist for an external consumer |
| 7 | SME review and signed decision | Roadmap | Business intent behind commented-out logic, unreachable paths, and misapplied messages | R2; moves rows from Proposed to Confirmed |

## Representative period

Payroll systems have paths that execute once a year or once a career. A runtime window shorter than one complete pay year (including year-end tax and reporting, open season, and any retroactive-pay cycles) produces false "never executed" evidence. The plan therefore treats R1 evidence from a shorter window as *supporting* rather than *sufficient*, and the ledger's SME-required flag stays set until the window is complete or an SME has confirmed the path is obsolete.

## Scaling the analyzer

The analyzer is deliberately built on the same parser the regression harness uses (`../../tests/harness/source_parser.py`) and keys every object by `LIBRARY/OBJECT` with Natural's current-library-then-steplib resolution. At FPPS scale the additions are mechanical rather than conceptual:

| Sample behaviour | FPPS-scale extension | Maturity |
|---|---|---|
| Steplib chain read from `SunnyIslands/.natural` | Steplib chains per environment from the Natural parameter modules / `NATPARM` | Designed |
| Literal call targets | Dynamic targets resolved from XRef (order 2) and reported as "data-driven" where XRef cannot | Designed |
| One UI root (`RDCRUISP`) | Roots per channel: online maps, batch job steps from JCL (order 3), RPC servers, and interface entry points | Designed |
| One message catalogue | One reconciliation per catalogue object, already implemented for shadowed libraries | Demonstrated |
| Four DDMs | DDMs and Predict file definitions for every file in the ADABAS database list | Designed |
| One ledger for two libraries | Ledger generated per library with the same total-and-exclusive binding rule, reviewed in tranches by business area | Designed |

## What the SI receives

At each stage the SI receives the same three artefacts the sample ships: the evidence (`evidence/`), the ledger (`disposition-ledger.md`), and the reachability diagram (`diagrams/`), regenerated from source with `generate_ledger.py --check` guarding drift. Rows only change class or status when a listed evidence source is attached to them, which is what makes the ledger defensible in front of a control board.

← [Back to the disposition capability](README.md) · [Taxonomy](taxonomy.md)
