# Interface and dependency mapping

`CALLNAT` / `FETCH` / `INCLUDE` / `USING` dependency map, STEPLIB and deployment configuration, external touch-points (work files, images, content objects, the NJX page event contract), and how the method scales to FPPS's bidirectional interfaces, datamarts, batch/JCL jobs, and client agencies.

| | |
|---|---|
| **Capability** | Interface and dependency mapping |
| **Why it matters to an SI implementing an HCM** | Dependencies decide cut-over sequencing, interface redesign, and what breaks when a module is retired. Interfaces are where HCM programmes overrun. |
| **Builds on** | `../../docs/call-map.md`, `../../SunnyIslands/deploy/natdeployDev.xml` / `natdeployTest.xml` / `natdeployProd.xml`, `../../tools/analyze_disposition.py` (reference edges) |
| **Maturity** | Demonstrated for the sample; FPPS interface inventory is Roadmap (requires agency inputs) |

## Contents

| Artifact | What it is | How it is produced |
|---|---|---|
| [`dependency-map.md`](dependency-map.md) | Full static edge list (caller, statement, callee, callee type, source line), fan-in / fan-out, cross-library edges, external touch-points (work files in `RDREADWN` / `IMG-LOAD`, content objects in `MAKEURL`, page-processing statements), and the `rdcruisx.xml` ↔ `RDCRUISP` event contract (declared events, handler lines, subroutines, services reached, handlers with no page declaration) | Generated |
| [`deployment-config.md`](deployment-config.md) | What `natdeploy{Dev,Test,Prod}.xml`, `wardeploy{Dev,Test,Prod}.xml`, `.natural` and `.project` actually configure; STEPLIB chaining at edit, deploy and run time; dev → test → prod promotion differences | Authored from the cited files and lines |
| [`fpps-interface-model.md`](fpps-interface-model.md) | Sample touch-points set against FPPS interface categories (agency feeds, datamarts, ~7,800 JCL jobs, Control-M, client agencies), in two strictly separated columns: verified in this repository vs FPPS analogy / requires agency inputs | Authored |
| [`diagrams/`](diagrams/README.md) | `dependency-graph.mmd` (CALLNAT / FETCH / INCLUDE), `data-area-usage.mmd` (USING), `event-contract.mmd` (page event → handler → subroutine → service) plus `.svg` / `.png` exports; further Mermaid diagrams are embedded in the two authored documents | Mermaid source generated; images exported with `@mermaid-js/mermaid-cli` |
| [`generate_dependency_map.py`](generate_dependency_map.py) | Generation harness (Python; a documentation generator, not a modernization target). Imports `tools.analyze_disposition.analyze()` and `tests.harness.source_parser`; `--check` exits 1 if any committed output differs | — |

Reproduce or verify:

```bash
python3 fpps-hcm-modernization-deliverable/06-interface-dependency-mapping/generate_dependency_map.py --check
```

## How to read the evidence

- Every edge is a literal reference on an executable line; dynamic `CALLNAT #VAR` is counted separately (zero in the sample) because static analysis cannot resolve it.
- "Adapter handlers with no page declaration" and "unreferenced in analyzed scope" are static candidates, not findings of runtime deadness.
- No credentials are quoted: the deployment files carry empty passwords and `SunnyIslands/webconfig/web-inf/sessions.xml` is deliberately not read.

## How an SI consumes this

| Step | Use this artifact | Into this HCM work product |
|---|---|---|
| 1. Fix the service boundary | "Cross-library edges" in `dependency-map.md` (every `RDCRUISE → CRUISE16` call with its PDA) | The list of business services whose behaviour must exist in the HCM; the PDAs (`NCCOMM-P`, `NCCUGE-P`, `NCCRUL-P`, `NCCONW-P`) are the field-level input for HCM Data Loader object mapping in `05` |
| 2. Derive acceptance scenarios | "Declared events and their handlers" table (event → subroutine → service) | One acceptance-test case per event that reaches a service, with the sample's inputs and expected message codes; events that reach no service are UI-only and need no HCM test |
| 3. Replace external touch-points | "Work files" and "Content objects" tables | Inbound file interfaces become HCM Data Loader / HCM Extract or integration flows; content objects become document attachments or static content in the HCM UI |
| 4. Plan environments | `deployment-config.md` promotion tables | HCM instance strategy (development / test / production pods), promotion checklist including the "only production deletes" rule, and which instance each acceptance test runs against |
| 5. Build the interface inventory | Section 4 of `fpps-interface-model.md` (column layout) and section 5 (inputs to request) | The agency-scale interface register: id, direction, counterparty, carrier, Natural entry object, data contract, files, schedule, environment variants, HCM target (HDL object, integration, or report) |
| 6. Decide retirement order | Fan-in table in `dependency-map.md` | Cut-over: retire callers before callees (`RDCRUISP` before the services; `CAMSG-N` and `ERRLOG-I` last), approvals modelled as BPM steps where the sample refuses a transaction |

## Synthetic data and scope

All evidence in this directory is produced from the Sunny Islands Cruise sample sources and synthetic data in `../../tests/harness/`. No production system, production data, or FPPS source is used or required. FPPS statements are analogies to a Software AG Natural 9.x / ADABAS 8.6 estate (~7M lines of Natural, 100k+ modules, ~7,800 JCL jobs); nothing here proposes a language rewrite.

← [Back to the navigation hub](../README.md)
