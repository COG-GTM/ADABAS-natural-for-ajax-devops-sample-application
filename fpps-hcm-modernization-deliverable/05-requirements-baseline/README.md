# Requirements baseline

A requirements baseline reconstructed from observed behaviour: functional, data, integrity, interface, and non-functional requirements with acceptance criteria, source traceability, and disposition.

| | |
|---|---|
| **Capability** | Requirements baseline |
| **Why it matters to an SI implementing an HCM** | This is the artifact traditional requirements gathering produces slowly and expensively. Structured for direct use in HCM fit-gap, configuration workbooks, and acceptance testing. |
| **Builds on** | 01, 02, 03, 04, 10; `../../docs/*.md` |
| **Maturity** | Demonstrated for the sample; the method is Designed for FPPS scale |

## Contents

- `requirements-baseline.md` — the baseline, numbered and traceable
- `acceptance-criteria.md` — testable criteria linked to 08 and 09 harnesses
- `what-we-will-not-build.md` — requirements explicitly excluded, cross-referenced to 10
- `diagrams/` — requirement coverage and traceability views

## How an SI consumes this

Load the baseline into your requirements tool; run fit-gap against Oracle HCM standard functionality; carry acceptance criteria into the test plan; treat the exclusion list as signed scope.

## Synthetic data and scope

All evidence in this directory is produced from the Sunny Islands Cruise sample sources and synthetic data in `../../tests/harness/`. No production system, production data, or FPPS source is used or required. FPPS statements are analogies to a Software AG Natural 9.x / ADABAS 8.6 estate (~7M lines of Natural, 100k+ modules, ~7,800 JCL jobs); nothing here proposes a language rewrite.

← [Back to the navigation hub](../README.md)
