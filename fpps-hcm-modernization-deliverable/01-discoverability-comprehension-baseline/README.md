# Discoverability and comprehension baseline

Architecture and comprehension map of the estate: library structure, module inventory, call graph, data-access map, extraction waves, and a narrated walk-through of both libraries.

| | |
|---|---|
| **Capability** | Discoverability and comprehension baseline |
| **Why it matters to an SI implementing an HCM** | Scoping, pricing, and configuration all start from knowing what exists, what calls what, and what touches which file. This is the baseline every later directory cites. |
| **Builds on** | `../docs/module-inventory.md`, `../docs/call-map.md`, `../tools/analyze_disposition.py` (object inventory and reference edges) |
| **Maturity** | Demonstrated (inventory and graph derive from the shipped sources) |

## Contents

| Artifact | What it is | How it is produced |
|---|---|---|
| [`discoverability-report.md`](discoverability-report.md) | Presentation-grade narrative: layering, entry points, purpose of every object in `CRUISE16` and `RDCRUISE`, data access, extraction waves, sample ↔ FPPS analogies, all with source-line citations | Authored; the "estate at a glance" and "waves" tables inside it are rewritten by the generator between `<!-- generated:… -->` markers |
| [`module-inventory.md`](module-inventory.md) | Every object in both libraries: type, LOC, executable LOC, callers, callees, ADABAS files touched (with verbs), reach status; per-file access table; derived extraction waves | Generated |
| [`diagrams/`](diagrams/README.md) | `architecture.mmd`, `call-graph.mmd`, `data-access.mmd` plus `.svg` / `.png` exports | Mermaid source generated; images exported with `@mermaid-js/mermaid-cli` |
| [`generate_inventory.py`](generate_inventory.py) | Generation harness (Python; a documentation generator, not a modernization target). Imports `tools.analyze_disposition.analyze()` and `tests.harness.source_parser`; `--check` exits 1 if any committed output differs | — |

Reproduce or verify:

```bash
python3 fpps-hcm-modernization-deliverable/01-discoverability-comprehension-baseline/generate_inventory.py --check
```

## How to read the evidence

- Counts and object lists are never typed by hand; if a number here disagrees with `module-inventory.md`, the generated file wins and `--check` will say so.
- Reach statuses are static candidates: "reachable from UI adapter", "unreferenced in analyzed scope", "stand-alone program; no UI path". They do not assert runtime behaviour; `../10-migration-disposition-dead-code/` owns the SME-confirmed disposition.
- FPPS statements are analogies from the hub table (`CRUISE16` ≈ FPPS core Natural service libraries, `RDCRUISE` ≈ web FPPS presentation layer, booking ≈ pay/personnel transaction, message-code edits ≈ payroll validation edits, DDMs ≈ personnel-payroll data model, concurrency integrity ≈ pay-run integrity).

## How an SI consumes this

| Step | Use this artifact | Into this HCM work product |
|---|---|---|
| 1. Size and scope | `module-inventory.md` control totals and per-library table | Estimate basis: objects, executable LOC, writers vs readers, candidates excluded from scope |
| 2. Sequence the extraction | "Extraction waves" in `discoverability-report.md` / `module-inventory.md` | Work plan: wave 1 message catalogue and static content → HCM messages and value sets; wave 2 read-only services → inquiry requirements; wave 2 writers → transaction requirements; wave 3 adapter → acceptance scripts only |
| 3. Map data | "ADABAS files" table (file, FNR, verbs, objects) and `diagrams/data-access.*` | HCM Data Loader object list and load order (referenced objects before referencing ones: yacht/cruise reference data before contracts; person before person-dependent records) |
| 4. Capture integrity rules | `CONEW-N`, `CUNEW-N`, `CUMOD-N` rows in the walk-through (hold-then-update, serialized MAX+1, optimistic timestamp) | HCM configuration: uniqueness and validation rules, and BPM approval/exception steps where the sample refuses a transaction (fully booked cruise, stale timestamp) |
| 5. Confirm the boundary | "Entry points" table and `diagrams/call-graph.*` | Acceptance-test plan: one scenario per UI event that reaches a service (`../06-interface-dependency-mapping/dependency-map.md` lists them), executed against the HCM configuration instead of the Natural adapter |
| 6. Hand off candidates | Rows with a candidate status (`CA3900-N`, `DELETECU`, `IMG-LOAD`, five unreferenced PDAs) | Disposition review in `../10-migration-disposition-dead-code/`; nothing is configured for them until an SME confirms |

Then open `02` (business rules) and `05` (data mapping) with the object list from this directory as the index.

## Synthetic data and scope

All evidence in this directory is produced from the Sunny Islands Cruise sample sources and synthetic data in `../../tests/harness/`. No production system, production data, or FPPS source is used or required. FPPS statements are analogies to a Software AG Natural 9.x / ADABAS 8.6 estate (~7M lines of Natural, 100k+ modules, ~7,800 JCL jobs); nothing here proposes a language rewrite.

← [Back to the navigation hub](../README.md)
