# Confidence model for extracted rules

Every rule in [`business-rules.md`](business-rules.md) carries a confidence score of the form `0.nn (S+C+H+D)`. The letters are the evidence classes that support the rule; the number is computed from them with the rubric below. `generate_rule_evidence.py --check` recomputes every score and fails if a hand-edited number disagrees with its evidence classes, so the model cannot drift from the catalogue.

Maturity: the rubric and its enforcement are Demonstrated. The SME sign-off class is Roadmap — it needs a named payroll or personnel SME and cannot be produced from this repository.

## Why a rubric instead of a judgement call

A payroll SI receiving a requirements baseline needs to know which statements are safe to configure against immediately and which need a decision first. A single number per rule, computed the same way every time, lets the SI sort the baseline by risk, and lets the client audit any score by checking whether the cited evidence exists. The rubric rewards evidence that can be re-run (tests, harness) over evidence that can only be read (static citation), and penalises inferences about Natural runtime behaviour that this repository does not execute.

## Evidence classes

| Class | Letter | Weight | What qualifies | What does not qualify |
|---|---|---|---|---|
| Static citation | S | 0.50 (mandatory) | An executable line range in the shipped Natural source that implements the rule, opened and cited as `path:start-end` | A commented-out statement alone (it qualifies the rule for Section 2, not for a higher score); a citation to documentation |
| Conformance test | C | +0.20 | A test in `tests/test_source_conformance.py` or `tests/test_disposition_analysis.py` that parses the source and asserts the construct (message-code set, hold-before-update ordering, never-assigned field) | A test that asserts behaviour without reading the source (that is class H) |
| Harness execution | H | +0.20 | A test in `tests/` that executes the behavioural model in `tests/harness/natural_model.py` against the synthetic ADABAS simulation and asserts the observable outcome (code, record state, holds) | A model function that exists but is not asserted for this rule's path |
| Repository documentation | D | +0.10 | A passage in `docs/` that describes the same semantics independently of this deliverable (`docs/concurrency-refactor.md`, `docs/transaction-flows.md`) | Text in this deliverable; the research report (it is an input, not independent evidence) |
| Inferred runtime semantics | N | −0.20 | The rule's observable outcome depends on Natural runtime behaviour that is inferred from language documentation rather than observed here (`READ ... BY key = value` start-value semantics, `VAL` on non-numeric input, `ON ERROR` / `ESCAPE ROUTINE` flow) | Ordinary statement semantics that the conformance tests already rely on (`MOVE`, `DECIDE`, `FIND`, `UPDATE`) |
| Data-dependent | R | −0.10 | The rule's effect depends on data content the synthetic set does not contain (blank e-mails, non-numeric status characters) | Rules whose inputs are fully covered by `tests/harness/fixtures.py` |
| SME sign-off | — | sets 1.00 | A named SME confirms the rule statement and disposition in writing; recorded in the rule entry with date and role | Absence of objection; verbal agreement without a record |

Score = 0.50 + Σ(weights), capped at 0.95 without SME sign-off and floored at 0.20. The cap is deliberate: nothing extracted from a sample reaches certainty about the client's intent until an SME says so.

## Score bands and what an SI does with them

| Band | Score | Reading | SI action |
|---|---|---|---|
| High | 0.85–0.95 | Source, conformance test and harness agree; documented independently | Configure against it now; the acceptance criterion in 05 is executable today |
| Medium | 0.60–0.84 | Source plus one executable class, or source plus documentation | Configure, but schedule the missing test or harness before user acceptance |
| Low | 0.20–0.59 | Source only, or source with an inference penalty | Treat as a candidate; confirm on a Natural session or with an SME before configuring |

## Worked examples

| Rule | Classes | Computation | Score | Why |
|---|---|---|---|---|
| BR-006 test-and-set on the held offering record | S+C+H+D | 0.50 + 0.20 + 0.20 + 0.10 = 1.00 → cap | 0.95 | `tests/test_source_conformance.py:35-43` asserts the `GET *ISN` re-read; `tests/test_concurrency.py:68-97` executes the blocked competitor; `docs/concurrency-refactor.md:45-77` describes it |
| BR-005 customer format fall-through | S+C+H | 0.50 + 0.20 + 0.20 | 0.90 | Behaviour reproduced by `tests/test_conew_booking.py:100-108`; no independent doc passage describes the overwrite |
| BR-032 optimistic version check | S+D | 0.50 + 0.10 | 0.60 | `docs/concurrency-refactor.md:156-167` classifies the pattern; no harness model of `CUMOD-N` exists |
| BR-023 retrieval by numeric identifier | S | 0.50 | 0.50 | Executable source only; the harness has no `CUGET-N` model |
| BR-C001 detail read uses a start value | S+N | 0.50 − 0.20 | 0.30 | Start-value semantics of `READ ... BY key = value` are inferred, not observed |
| BR-C003 blank identifier matches blank e-mail | S+R | 0.50 − 0.10 | 0.40 | Depends on whether blank e-mails exist in the customer master |

## How a score moves

| Event | Effect | Who |
|---|---|---|
| A behavioural model for `CUGET-N`, `CUNEW-N`, `CUMOD-N`, `CRGET-N` is added to `tests/harness/natural_model.py` with asserting tests | Eleven active rules move from 0.50 to 0.70 (S+H); BR-032 moves to 0.80 | Integrating team (Designed → Demonstrated) |
| A Natural session confirms `READ ... BY key = value` start-value behaviour and `VAL` on a dashed date | N penalty removed from BR-C001 and BR-C004 (0.30 → 0.50); the rules move from Section 4 to Section 1 or Section 3 | Client Natural administrator (Roadmap) |
| An SME signs a rule | Score set to 1.00; disposition becomes binding | Client SME (Roadmap) |
| A source citation is found to be wrong | `--check` fails on the line range; the rule is re-read before anything else | Any reviewer |

## Distribution of scores in the current catalogue

Computed by `generate_rule_evidence.py` from the confidence rows in `business-rules.md`.

<!-- generated:confidence-distribution -->
| Section | Rules | Mean score | High (≥0.85) | Medium (0.60–0.84) | Low (<0.60) |
|---|---|---|---|---|---|
| Section 1 — Active rules | 36 | 0.73 | 14 | 12 | 10 |
| Section 2 — Commented-out and disabled rules | 10 | 0.50 | 0 | 0 | 10 |
| Section 3 — Misapplied codes and silent outcomes | 6 | 0.64 | 2 | 1 | 3 |
| Section 4 — Candidate rules needing SME confirmation | 8 | 0.56 | 1 | 3 | 4 |
<!-- /generated:confidence-distribution -->

## Synthetic data and scope

Harness evidence (class H) runs against the synthetic ADABAS simulation in `tests/harness/adabas_sim.py`; no production system or data is involved. Class D refers to documentation of the Sunny Islands Cruise sample; nothing in this rubric claims that FPPS source was analysed.

← [Back to the directory README](README.md) · [Navigation hub](../README.md)
