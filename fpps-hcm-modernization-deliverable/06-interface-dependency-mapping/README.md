# Interface and dependency mapping

`CALLNAT` / `FETCH` / `INCLUDE` / `USING` dependency map, STEPLIB and deployment configuration, external touch-points (work files, images, content objects), and how the method scales to FPPS's bidirectional interfaces, datamarts, batch/JCL jobs, and client agencies.

| | |
|---|---|
| **Capability** | Interface and dependency mapping |
| **Why it matters to an SI implementing an HCM** | Dependencies decide cut-over sequencing, interface redesign, and what breaks when a module is retired. Interfaces are where HCM programmes overrun. |
| **Builds on** | `../docs/call-map.md`, `../SunnyIslands/deploy/natdeployDev.xml` / `natdeployTest.xml` / `natdeployProd.xml`, `../tools/analyze_disposition.py` (reference edges) |
| **Maturity** | Demonstrated for the sample; FPPS interface inventory is Roadmap (requires agency inputs) |

## Contents

- `dependency-map.md` — full edge list with statement type and line
- `deployment-config.md` — STEPLIB and environment configuration as shipped
- `fpps-interface-model.md` — how the sample pattern extends to FPPS interfaces, clearly separating verified sample facts from FPPS analogies
- `diagrams/` — dependency and interface diagrams

## How an SI consumes this

Use the edge list to plan retirement order and to identify every interface an HCM integration (HCM Extracts, REST, HDL inbound) must replace.

## Synthetic data and scope

All evidence in this directory is produced from the Sunny Islands Cruise sample sources and synthetic data in `../../tests/harness/`. No production system, production data, or FPPS source is used or required. FPPS statements are analogies to a Software AG Natural 9.x / ADABAS 8.6 estate (~7M lines of Natural, 100k+ modules, ~7,800 JCL jobs); nothing here proposes a language rewrite.

← [Back to the navigation hub](../README.md)
