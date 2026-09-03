# Business-process flow (BPMN-oriented)

Process flows for listing, detail, booking, and customer maintenance expressed as BPMN-oriented diagrams with lanes, gateways, error events, and compensation, plus notes on import into BPMN tooling.

| | |
|---|---|
| **Capability** | Business-process flow (BPMN-oriented) |
| **Why it matters to an SI implementing an HCM** | An HCM configuration team implements processes, not subprograms. BPMN-oriented flows let them map legacy behaviour to HCM transaction and approval flows and spot steps the HCM already provides. |
| **Builds on** | `../docs/transaction-flows.md`, `RDCRUISP.NSP` event handlers, `CONEW-N.NSN` transaction boundaries |
| **Maturity** | Demonstrated for the flows; Designed for the BPMN 2.0 XML export |

## Contents

- `process-flows.md` — narrated flows with Mermaid diagrams
- `bpmn/` — BPMN-oriented diagrams and export notes
- `process-to-hcm-mapping.md` — each legacy step ↔ HCM process step or retire/replace decision

## How an SI consumes this

Import or redraw the flows in your BPMN tool, then annotate each activity with its HCM equivalent (standard, configured, extension, or retired). Error events map to the validation catalogue in 02.

## Synthetic data and scope

All evidence in this directory is produced from the Sunny Islands Cruise sample sources and synthetic data in `../../tests/harness/`. No production system, production data, or FPPS source is used or required. FPPS statements are analogies to a Software AG Natural 9.x / ADABAS 8.6 estate (~7M lines of Natural, 100k+ modules, ~7,800 JCL jobs); nothing here proposes a language rewrite.

← [Back to the navigation hub](../README.md)
