# Executive value brief

Executive brief (Markdown source, branded DOCX, and PDF) for systems-integrator and agency leadership: three body pages plus cover, contents, and About Cognition.

| | |
|---|---|
| **Capability** | Executive value brief |
| **Why it matters to an SI implementing an HCM** | Leadership sponsors the requirements-first approach only if the value, the scope split, the proof points, and the honest maturity of each capability are stated in a few pages. |
| **Builds on** | All capability directories 01–10; `../../docs/concurrency-refactor.md` |
| **Maturity** | Demonstrated (the brief is built and checked in; every claim inside it carries its own Demonstrated / Designed / Roadmap label) |

## Contents

- [`executive-value-brief.md`](executive-value-brief.md) — content master, following the Cognition white-paper structure (challenge and approach, work streams, testing as the deliverable, audit trail, learning loop, roadmap and responsibilities)
- [`Cognition-FPPS-HCM-Executive-Value-Brief.pdf`](Cognition-FPPS-HCM-Executive-Value-Brief.pdf) — branded PDF rendered from the DOCX; [`Cognition-FPPS-HCM-Executive-Value-Brief.docx`](Cognition-FPPS-HCM-Executive-Value-Brief.docx) — editable branded source
- [`diagrams/value-chain.mmd`](diagrams/value-chain.mmd) — Figure 1 source (Mermaid), exported to [`value-chain.png`](diagrams/value-chain.png) and [`value-chain.svg`](diagrams/value-chain.svg)
- [`build.sh`](build.sh) — reproducible build: Mermaid → PNG/SVG, Markdown → branded DOCX via the Cognition collateral toolkit, DOCX → PDF via LibreOffice

## Rebuilding

```bash
# Requires node (npx), LibreOffice, and a checkout of the Cognition collateral toolkit
# that provides scripts/build_cognition_docx.py and templates/_TEMPLATE - COPY THIS.docx
RFP_REPO=/path/to/federal_RFP_responses ./build.sh
pdftoppm -r 110 -png Cognition-FPPS-HCM-Executive-Value-Brief.pdf /tmp/brief-page   # then inspect every page
```

## How an SI consumes this

Read this first. It states what is Demonstrated in this repository versus Designed or Roadmap, who owns which workstream (AI software-engineering scope versus payroll SME, ATO, and SI backbone), and which directories to open next.

## Synthetic data and scope

All evidence in this directory is produced from the Sunny Islands Cruise sample sources and synthetic data in `../../tests/harness/`. No production system, production data, or FPPS source is used or required. FPPS statements are analogies to a Software AG Natural 9.x / ADABAS 8.6 estate (~7M lines of Natural, 100k+ modules, ~7,800 JCL jobs); nothing here proposes a language rewrite.

← [Back to the navigation hub](../README.md)
