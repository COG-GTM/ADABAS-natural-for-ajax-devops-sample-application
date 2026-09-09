# Requirements baseline

A requirements baseline reconstructed from observed behaviour: functional, data, integrity, interface and non-functional requirements, each with rationale, source evidence, linked rule identifiers, HCM fit and disposition; Given/When/Then acceptance criteria linked to the tests that already run in `../../tests/`; and a signed exclusion list. This directory is the artifact that replaces months of interview-driven requirements gathering: every requirement in it is traced to a line of shipped source or to an executable check, not to a recollection.

| | |
|---|---|
| **Capability** | Requirements baseline |
| **Why it matters to an SI implementing an HCM** | This is the artifact traditional requirements gathering produces slowly and expensively. Structured for direct use in HCM fit-gap, configuration workbooks, and acceptance testing. |
| **Builds on** | `../02-business-rule-extraction/business-rules.md` (rule identifiers), `../10-migration-disposition-dead-code/evidence/disposition-evidence.md` (exclusion evidence), `../../tests/test_conew_booking.py`, `../../tests/test_crlist_listing.py`, `../../tests/test_concurrency.py`, `../../tests/test_source_conformance.py`, `../../tests/test_disposition_analysis.py`, `../../docs/*.md` |
| **Maturity** | Demonstrated for the sample (29 requirements, 59 acceptance criteria, generated cross-checks pass); the method is Designed for FPPS scale; SME sign-off of dispositions is Roadmap |

## Interview-driven versus source-derived

```
  Interview-driven (months)                     Source-derived (this directory)
  ─────────────────────────                     ───────────────────────────────
  workshop ─► recollection ─► draft ─► review    source line ─► rule (02) ─► requirement ─► criterion
  "the system checks the customer first"        CONEW-N.NSN:54-59 ─► BR-003 ─► REQ-F-003 ─► AC-REQ-F-003-4
  "I think it locks the record"                 CONEW-N.NSN:82-92 ─► BR-006 ─► REQ-I-001 ─► test_concurrency.py:68-97
  "there's a German version somewhere"          NCCOMM-P.P-LANG never assigned ─► BR-033 ─► REQ-N-001 (SME)
  disputes settled by seniority                 disputes settled by opening the cited line
```

The right-hand column is what an SI receives here. Where the source does not settle a question (a data-content range, an inferred runtime semantic), the requirement says so and names the SME question instead of guessing.

## Contents

| File | Purpose |
|---|---|
| `requirements-baseline.md` | 29 numbered requirements — REQ-F (functional), REQ-D (data), REQ-I (integrity), REQ-X (interface), REQ-N (non-functional) — each with rationale, source evidence, linked BR identifiers, HCM fit (standard / configured / extension / integration / out of scope), disposition and maturity; generated index, fit summary and rule-to-requirement reverse index |
| `acceptance-criteria.md` | Given/When/Then criteria for every requirement, the existing test in `../../tests/` that proves each today, "harness needed" where none exists, and the target-side verification the SI performs; generated evidence-class summary |
| `what-we-will-not-build.md` | Eight explicit exclusions (E-01 – E-08) with evidence class and cited lines, cross-referenced to `../10-migration-disposition-dead-code/evidence/disposition-evidence.md`, plus the executed behaviours the baseline deliberately replaces; generated tables for never-assigned fields, never-emitted codes, training gates and unreferenced objects |
| `diagrams/` | Mermaid source and rendered SVG/PNG for the requirement-coverage view (services → rules → requirements → HCM fit) and the traceability view (source line → rule → requirement → criterion → evidence) |

The generated blocks in this directory are written and verified by `../02-business-rule-extraction/generate_rule_evidence.py` (a validation generator; it converts nothing). Its `--check` mode fails if a requirement is not linked from the traceability matrix, if a rule has no requirement or exclusion carrying it, if a requirement has no acceptance criterion, if the matrix and the baseline disagree about which requirements carry a rule, or if any cited line range is outside its file.

## The integrity requirements

Seven requirements (REQ-I-001 – REQ-I-007) exist because the concurrency refactor in `../../docs/concurrency-refactor.md` was read as behaviour to preserve, not as code to translate. Two of them are the differentiator:

| Requirement | Sample defect it prevents | Executable proof today | What the target must do |
|---|---|---|---|
| REQ-I-001 Capacity is decremented atomically under contention | Two users each read one remaining place and both book it (`tests/test_concurrency.py:24-45`) | `tests/test_concurrency.py:68-97`, `tests/test_concurrency.py:129-141` | Read-check-decrement under a lock or with a conditional update; never a negative balance |
| REQ-I-002 Booking identifiers are unique under contention | Two users each read MAX=1000 and both store 1001 (`tests/test_concurrency.py:46-66`) | `tests/test_concurrency.py:99-127` | Platform-generated identifiers; the MAX+1 idiom is not carried |

Pay-run analogy: an entitlement balance read, decided on and written back without a lock is the same defect; a sequence number computed from the highest existing value is the same defect.

## Reproduce

```bash
# from the repository root
python3 fpps-hcm-modernization-deliverable/02-business-rule-extraction/generate_rule_evidence.py --check
python3 -m unittest discover -s tests -v
```

## How an SI consumes this

1. Load `requirements-baseline.md` into the requirements tool with the identifier, HCM fit and disposition columns as attributes; the generated index table is already in that shape.
2. Run fit-gap in the order of the HCM-fit column: `standard` rows are confirmed against Oracle HCM element-entry, person and lookup validation with no design; `configured` rows (REQ-F-002 duration pricing, REQ-D-001 capacity range) each name the configuration object (fast formula, value set) and the SME decision that precedes it; `integration` rows (REQ-X-001 – REQ-X-004) become the REST / HCM Data Loader contract specifications.
3. Carry the seven REQ-I requirements into the technical design as non-negotiable: platform-generated keys (REQ-I-002, REQ-I-005), object version numbers on person records (REQ-I-004), atomic balance updates (REQ-I-001), all-or-nothing transactions (REQ-I-003), no silent success (REQ-I-006), referential existence checks (REQ-I-007).
4. Port `acceptance-criteria.md` into the test plan: rows with an existing test are regression cases whose expected results are already known; rows marked "harness needed" are tests to write before user acceptance; the "Target verification" column is the Oracle HCM-side check for each.
5. Treat `what-we-will-not-build.md` as signed scope. Its "Reopen if" column is the only route back in; anything reopened is written as a new requirement from policy, not carried from the sample.
6. Run `../02-business-rule-extraction/generate_rule_evidence.py --check` after every edit to any file in this directory; a failing check means the baseline and the rule catalogue no longer agree.

## Synthetic data and scope

All evidence in this directory is produced from the Sunny Islands Cruise sample sources and synthetic data in `../../tests/harness/`. No production system, production data, or FPPS source is used or required. FPPS statements are analogies to a Software AG Natural 9.x / ADABAS 8.6 estate (~7M lines of Natural, 100k+ modules, ~7,800 JCL jobs); nothing here proposes a language rewrite. Static findings ("unreferenced in analyzed scope", "declared but never assigned") are candidates for SME confirmation, not conclusions.

← [Back to the navigation hub](../README.md)
