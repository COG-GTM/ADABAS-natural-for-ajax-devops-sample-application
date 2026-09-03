# Authoring conventions for this package

These rules apply to every file under `fpps-hcm-modernization-deliverable/`. They exist so that ten independently authored capability directories read as one deliverable.

## 1. Framing that must never drift

| Rule | Detail |
|---|---|
| FPPS is Natural/ADABAS | Software AG Natural 9.x, ADABAS 8.6, z/OS 2.5. Never describe the estate or the extraction as COBOL or "COBOL conversion". |
| Scale figures | Use **~7M lines of Natural, 100k+ modules, ~7,800 JCL jobs**. Do not use the ~63M LOC figure except to flag it as unverified. |
| Requirements-first, not conversion | The output is a validated requirements / business-logic baseline that an SI implements in Oracle HCM (or an alternate HCM). Never propose or imply a language-to-language rewrite. |
| Python is a harness | Python exists here only for validation, reconciliation, generators, and analyzers. Say so wherever Python appears. |
| Synthetic data only | Every directory README states that all evidence runs on synthetic data with no production access. |
| Sample ≠ FPPS | Sunny Islands Cruise is a public Software AG sample. Facts about it are facts; statements about FPPS are analogies or citations of public documentation. |

## 2. Every capability directory contains

1. `README.md` opening with a one-paragraph purpose, a **Capability / Why it matters to an SI / Builds on** table, and a **Maturity** line (Demonstrated / Designed / Roadmap — see hub README).
2. At least one Mermaid diagram. Export to PNG/SVG under `diagrams/` where a renderer is available; keep the Mermaid source in the Markdown regardless.
3. A traceability table whose rows cite **repository-relative path + line range** (for example `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:118-131`). Cite lines you have opened; never estimate them.
4. A **Sample ↔ FPPS analogy** table or paragraph using the vocabulary in the hub README.
5. A closing section titled **How an SI consumes this** — concrete steps into Oracle HCM configuration, HCM Data Loader, BPM, or the acceptance-test plan.
6. A **Synthetic data / no production access** statement.

## 3. Evidence discipline

- Derive counts, lists, and taxonomies from code at generation time (import the parser, run the analyzer) rather than hand-typing snapshots. If a value must be typed, add a drift test.
- Static analysis produces **candidates**. Never state that an object is dead; state that it is "unreferenced in the analyzed scope", "unreachable from the UI adapter", or "declared but never assigned", and list the evidence class. Confidence goes up only with additional evidence (Natural Predict/XRef, runtime traces, JCL/Control-M schedules, SME confirmation).
- Every external URL must have been opened and its content confirmed in the authoring session. Do not build URLs from memory or identifiers. If a URL cannot be verified, provide search terms instead.
- No internal review markers (`[TBD]`, `[TODO]`, `[VERIFY]`, `[CONFIRM]`) in committed artifacts.

## 4. Claim maturity

Present tense means "runs in this repository today". Anything else carries an explicit **(designed)** or **(roadmap)** qualifier in prose, in diagram labels, and in tables — all three must agree. Remove superlatives that no artifact in the repository substantiates.

## 5. Style

- Sentence-case headings. Short paragraphs. Plain business language first, Natural/ADABAS specifics second.
- Tables over prose for anything with more than three attributes.
- Cross-link to sibling directories with relative links; cross-link to the repository root from a capability directory with `../../docs/...`, `../../tests/...`, `../../tools/...`, `../../SunnyIslands/...` (the hub `README.md` is one level higher and uses `../docs/...`).
- Branding: deliverables intended for export (the executive brief, any PDF) use the Cognition wordmark and template; colours `#3969CA` (primary), `#21C19A` (accent), `#0294DE` (secondary); Inter / Inter Tight typography. Product names: Devin, DeepWiki, Devin Review, Devin Desktop.

## 6. Directory confinement for parallel authors

Each capability author edits only their own numbered directory. Shared files (`README.md`, this file, `tools/`, `tests/`) are edited only by the integrating session. Repository documentation under `docs/` is a source, not a target.
