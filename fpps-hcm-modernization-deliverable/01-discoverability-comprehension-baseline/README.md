# Discoverability and comprehension baseline

Architecture and comprehension map of the estate: library structure, module inventory, call graph, data-access map, and a narrated walk-through of both libraries.

| | |
|---|---|
| **Capability** | Discoverability and comprehension baseline |
| **Why it matters to an SI implementing an HCM** | Scoping, pricing, and configuration all start from knowing what exists, what calls what, and what touches which file. This is the baseline every later directory cites. |
| **Builds on** | `../../docs/module-inventory.md`, `../../docs/call-map.md`, `../../tools/analyze_disposition.py` (object inventory and reference edges) |
| **Maturity** | Demonstrated (inventory and graph derive from the shipped sources) |

## Contents

- `discoverability-report.md` — consolidated, presentation-grade report
- `diagrams/` — architecture, call graph, and data-access diagrams (Mermaid + exports)
- `module-inventory.md` — every object in `CRUISE16` and `RDCRUISE` with type, size, callers, callees, files touched

## How an SI consumes this

Use the inventory to size the estate and the call graph to sequence extraction waves (leaf services first). Map each `CRUISE16` service to a candidate HCM business object or process before opening 02 and 05.

## Synthetic data and scope

All evidence in this directory is produced from the Sunny Islands Cruise sample sources and synthetic data in `../../tests/harness/`. No production system, production data, or FPPS source is used or required. FPPS statements are analogies to a Software AG Natural 9.x / ADABAS 8.6 estate (~7M lines of Natural, 100k+ modules, ~7,800 JCL jobs); nothing here proposes a language rewrite.

← [Back to the navigation hub](../README.md)
