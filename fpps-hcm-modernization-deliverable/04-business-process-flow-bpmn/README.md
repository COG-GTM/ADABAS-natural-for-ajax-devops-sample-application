# Business-process flow (BPMN-oriented)

Process flows for listing, detail, booking, and customer maintenance expressed as BPMN-oriented diagrams with lanes, gateways, error events, and compensation, plus notes on import into BPMN tooling.

An HCM configuration team implements processes, not subprograms. This directory turns the four user-facing processes of the Sunny Islands Cruise sample — the analog of FPPS personnel/payroll transactions — into swimlane flows whose every gateway is an executable validation in the Natural source, whose every error end-event carries the message code the source emits, and whose transaction boundary (`END TRANSACTION` / `BACKOUT TRANSACTION`) is drawn as a BPMN transaction with compensation. The same structure is hand-authored as BPMN 2.0 XML for the booking process so an SI can import it, redraw it, and annotate each activity with its Oracle HCM (or alternate HCM) equivalent. Nothing here converts Natural into another language; the Python in this directory is a generator/validation harness that keeps the hand-authored documents consistent with the source.

| | |
|---|---|
| **Capability** | Business-process flow (BPMN-oriented) |
| **Why it matters to an SI implementing an HCM** | An HCM configuration team implements processes, not subprograms. BPMN-oriented flows let them map legacy behaviour to HCM transaction and approval flows and spot steps the HCM already provides. |
| **Builds on** | `../../docs/transaction-flows.md`, `RDCRUISP.NSP` event handlers, `CONEW-N.NSN` transaction boundaries |
| **Maturity** | Demonstrated for the flows; Designed for the BPMN 2.0 XML export |

## Contents

| Artifact | What it contains | Maturity |
|---|---|---|
| [`process-flows.md`](process-flows.md) | Narrated flows for (1) list cruises, (2) cruise detail, (3) customer lookup / create / modify, (4) book cruise — one Mermaid flowchart each with four swimlanes (Browser / NJX adapter / Business service / ADABAS), a gateway per executable validation, error end-events labelled with message codes, and the transaction scope drawn as a compensation boundary. Includes the UI event inventory (handled, `IGNORE`, presentation-only, unreachable from the page) and the commented-out `IMG-LOAD` image loading | Demonstrated (flows describe code that runs in the repository today); candidate findings are labelled as such |
| [`bpmn/booking-process.bpmn`](bpmn/booking-process.bpmn) | Hand-authored BPMN 2.0 XML for the booking process: the same four lanes, a `bpmn:transaction` with `method="##Compensate"`, cancel end-events for 9902 / 9918, a compensation handler for `BACKOUT TRANSACTION`, an error boundary for `ON ERROR`, and one `bpmn:error` per executable message code | Designed — well-formed and reference-checked by the generator, not validated against the OMG XSD; no BPMNDI layout |
| [`bpmn/import-notes.md`](bpmn/import-notes.md) | How an SI imports or redraws the XML in a BPMN tool, what to check after import (element counts, references), and where Oracle HCM security, transaction save, approval, rollback, message configuration, and notifications replace the legacy adapter / service / ADABAS steps | Designed |
| [`process-to-hcm-mapping.md`](process-to-hcm-mapping.md) | Every legacy activity ↔ HCM equivalent with a Standard / Configured / Extension / Retired disposition, the booking ≈ personnel-payroll transaction analogy carried through, DDM → HCM data-object mapping, message codes → HCM validation rules, and the presentation-only / inactive inventory | Demonstrated (legacy side) / Designed (HCM side) |
| [`diagrams/`](diagrams/) | SVG and PNG exports of the four Mermaid flowcharts plus the extracted `.mmd` source, produced by [`export_diagrams.sh`](export_diagrams.sh) with `@mermaid-js/mermaid-cli`. The Mermaid source in `process-flows.md` remains authoritative | Demonstrated |
| [`evidence/process-evidence.md`](evidence/process-evidence.md), [`evidence/process-evidence.json`](evidence/process-evidence.json) | Generated from source: UI event inventory and adapter branch classification, per-service emitted and comment-only message codes, `END TRANSACTION` / `BACKOUT TRANSACTION` / `ON ERROR` positions, `CAMSG-N` catalog, control totals. Do not edit by hand | Demonstrated |
| [`generate_process_evidence.py`](generate_process_evidence.py) | Generator / validation harness (not a conversion of Natural). Reads `RDCRUISP.NSP`, `rdcruisx.xml` and the CRUISE16 subprograms through `tests/harness/source_parser.py` and `tools/analyze_disposition.py`; `--check` exits non-zero if the committed evidence differs or if the hand-authored flows, BPMN XML, import notes or mapping disagree with the source (counts, message codes, citations, BPMN references) | Demonstrated |

## What the flows show

| Process | Trigger events (`RDCRUISP.NSP`) | Service | Executable validations → message codes | Transaction boundary |
|---|---|---|---|---|
| P1 — List cruises | `onShowAll`, `onFav1button`…`onFav4button` | `CRLIST-N` | `#STUDENT` → 9999; no rows → 9857; rows → 9807 (remapped to 0) | none (read-only) |
| P2 — Cruise detail | `onShowdetails1`…`4`, `lines.onpvLineClick`, `onHotcruises` | `CRGET-N` | no record read → 9934 (catalogued as *Customer changed from another user* — text mismatch) | none (read-only) |
| P3 — Customer lookup / create / modify | `onLoginbutton`, `onMydataSave` (`G-LOGGEDIN` selects modify vs create) | `CUGET-N`, `CUNEW-N`, `CUMOD-N` | lookup: 9924 / 9923; modify: 9924 (record gone), 9934 (timestamp mismatch); `#STUDENT` → 9999 | `END TRANSACTION` in `CUNEW-N` and `CUMOD-N`; `ON ERROR` without explicit backout (candidate) |
| P4 — Book cruise | `onBookingSave` | `CONEW-N` | 9904 / 9905 (missing or non-numeric ids), 9902 (no availability or empty contract file), 9918 (customer not found), 9800 → 0 on success; cruise-record-found candidate (code 0 without a stored contract) | `END TRANSACTION` after `STORE`; `BACKOUT TRANSACTION` on every failed edit and in `ON ERROR` — drawn as a BPMN transaction with compensation |

Codes, line numbers and counts in the table above are cross-checked by `generate_process_evidence.py --check` against the generated evidence; the narrative documents cite the exact `path.NSN:start-end` for every claim.

## Presentation-only and unhandled events

The adapter's `DECIDE ON FIRST *PAGE-EVENT` has 34 branches for 27 distinct UI events. `process-flows.md` § *UI event inventory* classifies each branch: handled (calls a service), UI state only (visibility toggles), explicit `IGNORE` (`onCloseMydata`, `onCrdetClose`), menu-registered without a page declaration (`onQuestion`, `onExit`), and framework / presentation branches without a page declaration or menu registration (`nat:page.end`, `onFacebook`, `onTwitter`). Six `CALLNAT 'IMG-LOAD'` lines at `RDCRUISP.NSP:85-91` are comments; the active picture path is `YACHT-PICTURE.PICTURE` through `MAKEURL` (`RDCRUISP.NSP:730-736`). These are candidates for retirement, recorded with their evidence class, not proof of runtime deadness.

## How an SI consumes this

1. **Process inventory into Oracle HCM configuration.** Take the four processes in `process-to-hcm-mapping.md` and, per row, record the disposition (Standard / Configured / Extension / Retired) in the configuration workbook. Standard rows need no build; Configured rows become approval rules, validation messages, lookups and page-level defaults; Extension rows (for example, capacity re-check at approval time) go to the extension backlog with the cited source line as their requirement.
2. **Validation rules into the HCM message dictionary.** Use the *Message codes to HCM validation rules* table to create the message set (severity, text, translation) and to retire the codes whose text is misapplied in the legacy catalogue (9934 used for cruise-not-found, 9923 used for e-mail-not-found, 9902 used for an empty contract file). Confirm the comment-only candidates (9911–9919) with the business before configuring them.
3. **Data objects into HCM Data Loader.** The *DDM to HCM data-object mapping* table names the target object per DDM (Worker/Person, reference object, transaction, lookup). Pair it with `../03-data-model-data-dictionary/` for field-level mapping and with `../07-master-data-cleansing/` for the `FIRST-NAME-1` / `FIRST-NAME-OLD` lineage defect before any load.
4. **Approval and transaction flow into BPM.** Import `bpmn/booking-process.bpmn` following `bpmn/import-notes.md`, redraw the layout, and replace the adapter / service / ADABAS lanes with the platform's security, transaction save, approval routing and rollback as described in the notes. The transaction/compensation structure is the requirement: a booking (personnel action) must commit atomically or leave no trace.
5. **Acceptance-test plan.** Every gateway in `process-flows.md` is an acceptance case: one test per message code, one per transaction outcome (commit, backout on 9902, backout on 9918, backout on `ON ERROR`), one per concurrency scenario (two sessions booking the last place; two sessions modifying the same person). Take the executable scenarios from `../08-equivalence-testing-reconciliation/` and `../../tests/harness/`.
6. **Keep it consistent.** Rerun `python3 fpps-hcm-modernization-deliverable/04-business-process-flow-bpmn/generate_process_evidence.py --check` from the repository root after any edit; regenerate the images with `export_diagrams.sh` when the Mermaid source changes.

## Synthetic data and scope

All evidence in this directory is produced from the Sunny Islands Cruise sample sources and synthetic data in `../../tests/harness/`. No production system, production data, or FPPS source is used or required. FPPS statements are analogies to a Software AG Natural 9.x / ADABAS 8.6 estate (~7M lines of Natural, 100k+ modules, ~7,800 JCL jobs); nothing here proposes a language rewrite. Static findings (unreferenced, unreachable from the UI adapter, comment-only) are candidates that need runtime evidence or SME confirmation before anything is retired.

← [Back to the navigation hub](../README.md)
