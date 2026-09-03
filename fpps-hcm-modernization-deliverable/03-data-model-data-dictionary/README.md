# Data model and data dictionary

Master-data model and field-level dictionary derived from the four ADABAS DDMs, with usage, lineage, source-key, and HCM-mapping columns.

| | |
|---|---|
| **Capability** | Data model and data dictionary |
| **Why it matters to an SI implementing an HCM** | HCM Data Loader mapping starts from a definition of master data: every attribute, its format, its descriptor role, whether it is used, and what it maps to. Unused and ambiguous fields are as important as used ones. |
| **Builds on** | `../../docs/data-dictionary.md`, `../../tools/generate_data_dictionary.py`, `../../SunnyIslands/Natural-Libraries/CRUISE16/DDMs/*.NSD`, `../../tools/analyze_disposition.py` (field-usage matrix) |
| **Maturity** | Demonstrated (dictionary is generated from the DDMs and drift-tested) |

## Contents

- `data-model.md` — entity-relationship view and file roles
- `data-dictionary-hcm.md` — field-level dictionary extended with usage, lineage, and candidate HCM object/attribute
- `diagrams/` — ER and lineage diagrams

## How an SI consumes this

Use the dictionary as the source side of the HCM Data Loader mapping workbook. Fields flagged never-referenced go to 10 for disposition rather than into the mapping; fields with inconsistent lineage go to 07 for cleansing rules.

## Synthetic data and scope

All evidence in this directory is produced from the Sunny Islands Cruise sample sources and synthetic data in `../../tests/harness/`. No production system, production data, or FPPS source is used or required. FPPS statements are analogies to a Software AG Natural 9.x / ADABAS 8.6 estate (~7M lines of Natural, 100k+ modules, ~7,800 JCL jobs); nothing here proposes a language rewrite.

← [Back to the navigation hub](../README.md)
