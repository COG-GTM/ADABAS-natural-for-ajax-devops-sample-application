# Acceptance criteria

One or more Given/When/Then criteria for every requirement in [`requirements-baseline.md`](requirements-baseline.md). Where an executable test already exists in `tests/` it is cited by file and line range; where none exists the criterion is flagged **harness needed** and the harness type is named so the SI can size it. Every criterion is expressed against the synthetic data in `tests/harness/fixtures.py`; none requires production data.

Reading guide:

| Column | Meaning |
|---|---|
| Criterion | `AC-<requirement>-<n>` |
| Given / When / Then | Precondition, action, observable outcome — written in HCM vocabulary where the analogy holds (offering ≈ pay element / entitlement with a capacity; booking ≈ personnel-payroll transaction; customer ≈ person record) |
| Evidence today | Test in `tests/` that executes the criterion against the synthetic ADABAS simulation, or **harness needed** with the harness type |
| Target verification | How the same criterion is checked in the target HCM (designed; nothing here has run against an HCM) |

Harness types used below: **service harness** (a model of one Natural service's observable behaviour, like `tests/harness/natural_model.py` today for `CONEW-N` and `CRLIST-N`); **interleaving harness** (two simulated operators with explicit interleaving points, like `tests/test_concurrency.py`); **fault injection** (forcing a runtime error inside a service); **catalogue check** (static comparison of code sets, like `tests/test_disposition_analysis.py`).

## Functional requirements

### REQ-F-001 — List offerings that still have capacity

| Criterion | Given | When | Then | Evidence today | Target verification |
|---|---|---|---|---|---|
| AC-REQ-F-001-1 | Offerings with free places 0, 1 and 3 exist | The list is requested with no filter | Only the offerings with 1 and 3 free places appear | `tests/test_crlist_listing.py:10-15` | Eligibility profile / list-of-values query returns only entitlements with balance > 0 |
| AC-REQ-F-001-2 | Two eligible offerings with different start dates | The list is requested | The later start date is first | `tests/test_crlist_listing.py:17-21` | Sort order of the delivered list |
| AC-REQ-F-001-3 | Eligible offerings exist from two start locations | The list is requested with a start-location filter | Only offerings from that location appear and the outcome is success (0) | `tests/test_crlist_listing.py:23-27`, `tests/test_crlist_listing.py:36-39` | Filtered list-of-values |
| AC-REQ-F-001-4 | No offering matches the filter | The list is requested | The outcome is "no data" (9857 in the sample), not success and not an error | `tests/test_crlist_listing.py:29-34` | Empty-result message of the delivered page |
| AC-REQ-F-001-5 | An offering with one free place | The last place is booked and the list is requested again | The offering no longer appears | `tests/test_crlist_listing.py:71-78` | End-to-end: entitlement balance reaches 0 and drops from the list |

### REQ-F-002 — Show offering detail with duration-dependent price

| Criterion | Given | When | Then | Evidence today | Target verification |
|---|---|---|---|---|---|
| AC-REQ-F-002-1 | Offerings lasting 7, 14 and 21 days | Detail is requested for each | The one-, two- and three-week rate is shown respectively | `tests/test_crlist_listing.py:85-95` | Rate definition / fast formula returns the band rate |
| AC-REQ-F-002-2 | An offering lasting 10 days | Detail is requested | An out-of-band error is reported (the sample silently shows the two-week rate — `tests/test_crlist_listing.py:97-101` documents the current defect) | **harness needed** — service harness for `CRGET-N`; current behaviour is asserted, target behaviour is not | Validation rule on duration band |
| AC-REQ-F-002-3 | No offering with the requested identifier | Detail is requested | The outcome is "offering not found", not "changed by another user" | **harness needed** — service harness for `CRGET-N` | Delivered not-found response |

### REQ-F-003 — Book an offering for a customer

| Criterion | Given | When | Then | Evidence today | Target verification |
|---|---|---|---|---|---|
| AC-REQ-F-003-1 | A valid customer and an offering with free places | A booking is submitted | Outcome is success (0), one booking exists for that customer and offering, priced at the one-week rate, dated today | `tests/test_conew_booking.py:18-63` | Element entry created with the expected input values |
| AC-REQ-F-003-2 | Blank or zero customer identifier | A booking is submitted | Outcome is "customer identifier missing" (9904) and no record changes | `tests/test_conew_booking.py:66-73`, `tests/test_conew_booking.py:110-121` | Required-field validation on the entry |
| AC-REQ-F-003-3 | Valid customer, blank or zero offering identifier | A booking is submitted | Outcome is "offering identifier missing" (9905) | `tests/test_conew_booking.py:75-82` | Required-field validation on the entry |
| AC-REQ-F-003-4 | Both identifiers blank | A booking is submitted | Both edits are reported (the sample reports only the customer edit — `tests/test_conew_booking.py:84-90` documents current behaviour) | **harness needed** — target-side test only; sample behaviour is asserted | Multiple validation messages returned together |
| AC-REQ-F-003-5 | Non-numeric offering identifier | A booking is submitted | Outcome is a format edit on the offering identifier (9905 in the sample) | `tests/test_conew_booking.py:92-98` | Field format validation |
| AC-REQ-F-003-6 | Non-numeric customer identifier, valid offering | A booking is submitted | Outcome is a format edit on the customer identifier; the sample instead reports "customer not found" (9918) after consuming and restoring a place — `tests/test_conew_booking.py:100-108` documents current behaviour | **harness needed** — target-side test only | Field format validation fires before any balance change |
| AC-REQ-F-003-7 | An offering with no free place | A booking is submitted | Outcome is "no longer available" (9902); no booking exists | `tests/test_conew_booking.py:124-148` | Balance validation on the entitlement |
| AC-REQ-F-003-8 | Offering identifier that matches no record | A booking is submitted | Outcome is "offering not found"; the sample returns success with booking identifier 0 — `tests/test_conew_booking.py:177-183` documents current behaviour | **harness needed** — target-side test only | Lookup validation on the element |

### REQ-F-004 — Register a new customer

| Criterion | Given | When | Then | Evidence today | Target verification |
|---|---|---|---|---|---|
| AC-REQ-F-004-1 | Valid name, address and birth date | Registration is submitted | A person record exists with a new unique identifier and a version stamp; both are returned to the caller | **harness needed** — service harness for `CUNEW-N` (idiom asserted statically by `tests/test_source_conformance.py:91-95`) | Worker created via REST / HDL; person number and object version returned |

### REQ-F-005 — Retrieve a customer by identifier or e-mail

| Criterion | Given | When | Then | Evidence today | Target verification |
|---|---|---|---|---|---|
| AC-REQ-F-005-1 | A customer with identifier 10000001 | Retrieval by 10000001 | The customer's data and version stamp are returned, outcome success | **harness needed** — service harness for `CUGET-N` | Person search by person number |
| AC-REQ-F-005-2 | A customer whose first e-mail is `a@example.org` | Retrieval by `a@example.org` | The same record is returned | **harness needed** — service harness for `CUGET-N` | Person search by e-mail |
| AC-REQ-F-005-3 | No customer with the given e-mail | Retrieval by that e-mail | Outcome is "customer not found"; the sample returns "identifier missing" (9923) | **harness needed** — service harness for `CUGET-N` | Not-found response |
| AC-REQ-F-005-4 | A blank search value | Retrieval is requested | Outcome is "identifier missing" and no lookup is performed | **harness needed** — service harness for `CUGET-N` | Required-field validation |

### REQ-F-006 — Modify an existing customer

| Criterion | Given | When | Then | Evidence today | Target verification |
|---|---|---|---|---|---|
| AC-REQ-F-006-1 | An existing customer and its current version stamp | Surname is changed and the update submitted with that stamp | The record shows the new surname, the version stamp has changed, the new stamp is returned | **harness needed** — service harness for `CUMOD-N` | Worker update via REST with object version number |
| AC-REQ-F-006-2 | No customer with the given identifier | An update is submitted | Outcome is "customer not found" (9924); nothing is written | **harness needed** — service harness for `CUMOD-N` | Not-found response |

### REQ-F-007 — Report every outcome as a code with typed text

| Criterion | Given | When | Then | Evidence today | Target verification |
|---|---|---|---|---|---|
| AC-REQ-F-007-1 | Any successful booking or non-empty list | The outcome is read | Response code is `0` and the text carries the success type | `tests/test_conew_booking.py:18-25`, `tests/test_crlist_listing.py:23-27`, `tests/test_source_conformance.py:120-123` | Delivered success message |
| AC-REQ-F-007-2 | Every code a service can emit | The catalogue is consulted | Every emitted code has catalogue text (emitted − catalogued = ∅) | `tests/test_source_conformance.py:30-33`, `tests/test_disposition_analysis.py:53-67` | Lookup-type completeness check on the message dictionary |
| AC-REQ-F-007-3 | A code with no catalogue text | The catalogue is consulted | The condition is reported as a catalogue defect, not passed through with empty text | **harness needed** — catalogue check on the target message dictionary | Message-dictionary completeness gate in the build |

## Data requirements

### REQ-D-001 — Free-place count is a bounded integer

| Criterion | Given | When | Then | Evidence today | Target verification |
|---|---|---|---|---|---|
| AC-REQ-D-001-1 | An offering with exactly one free place | Two bookings are submitted in sequence | The first succeeds, the second is "no longer available"; the count is 0, never −1 | `tests/test_conew_booking.py:150-161` | Balance cannot go negative |
| AC-REQ-D-001-2 | The business has stated the maximum capacity | The data model is reviewed | The free-place attribute's type and range hold that maximum | **harness needed** — SME decision, then a data-model check | Input value validation range |

### REQ-D-002 — Booking record content

| Criterion | Given | When | Then | Evidence today | Target verification |
|---|---|---|---|---|---|
| AC-REQ-D-002-1 | A successful booking | The booking record is read | It carries booking identifier, customer identifier, offering identifier, price, booking date; reservation date, cancellation date, conditions and week count are absent or unused | `tests/test_conew_booking.py:27-63` | Element entry input values match the agreed set |

### REQ-D-003 — One first-name attribute

| Criterion | Given | When | Then | Evidence today | Target verification |
|---|---|---|---|---|---|
| AC-REQ-D-003-1 | Legacy records where `FIRST-NAME-OLD` and `FIRST-NAME-1` differ or one is blank | The migration load runs | One first name is loaded per person under the agreed precedence; a reconciliation report lists every record where the rule was applied | **harness needed** — load reconciliation (07 master-data cleansing) | HDL load report plus reconciliation query |
| AC-REQ-D-003-2 | A first name entered through the UI | A customer is created and retrieved | The same first name comes back (the sample loses it — `tests/test_disposition_analysis.py:76-85` shows the unreferenced legacy fields) | **harness needed** — service harness for `CUNEW-N`/`CUGET-N` | Round-trip test on the person record |

### REQ-D-004 — One canonical birth-date format

| Criterion | Given | When | Then | Evidence today | Target verification |
|---|---|---|---|---|---|
| AC-REQ-D-004-1 | The agreed input format | Create and modify are each submitted with a birth date | Both accept the same format and store the same date | **harness needed** — service harness for `CUNEW-N`/`CUMOD-N` | Date attribute validation |

### REQ-D-005 — Customer identifiers

| Criterion | Given | When | Then | Evidence today | Target verification |
|---|---|---|---|---|---|
| AC-REQ-D-005-1 | Two customers, one of which has two e-mail addresses | Retrieval by the second e-mail of that customer | Behaviour matches the agreed rule (the sample matches on the first e-mail only) | **harness needed** — service harness for `CUGET-N` plus SME decision | Person search configuration |

### REQ-D-006 — Version attribute on the customer record

| Criterion | Given | When | Then | Evidence today | Target verification |
|---|---|---|---|---|---|
| AC-REQ-D-006-1 | A customer is created, then modified | The version stamp is read after each step | It is non-empty after create and different after modify; each service returned the stamp it stored | **harness needed** — service harness for `CUNEW-N`/`CUMOD-N`/`CUGET-N` | Object version number increments on update |

## Integrity requirements

### REQ-I-001 — Capacity is decremented atomically under contention

| Criterion | Given | When | Then | Evidence today | Target verification |
|---|---|---|---|---|---|
| AC-REQ-I-001-1 | An offering with one free place; two operators | Both read the count before either writes (interleaved) | Exactly one booking succeeds; the other receives "no longer available"; the count is 0 (the pre-refactor logic produces two bookings — `tests/test_concurrency.py:24-45` proves the defect) | `tests/test_concurrency.py:68-97` | Two concurrent element-entry submissions against a balance of 1 |
| AC-REQ-I-001-2 | An offering with N free places | N+1 bookings are submitted | N succeed, the last fails, the count is 0 | `tests/test_concurrency.py:129-141` | Sequential load test against the balance |
| AC-REQ-I-001-3 | The booking service source | The source is inspected | The record is re-read under lock before the check and decrement | `tests/test_source_conformance.py:35-43` | Not applicable in target — the outcome tests above replace the static check |

### REQ-I-002 — Booking identifiers are unique under contention

| Criterion | Given | When | Then | Evidence today | Target verification |
|---|---|---|---|---|---|
| AC-REQ-I-002-1 | Two operators booking different offerings at the same time | Both compute the next identifier before either stores (interleaved) | The two bookings have different identifiers (the pre-refactor logic produces a duplicate — `tests/test_concurrency.py:46-66` proves the defect) | `tests/test_concurrency.py:99-127` | Platform-generated key; uniqueness constraint on the object |
| AC-REQ-I-002-2 | The booking service source | The source is inspected | The highest booking record is held before the identifier is computed | `tests/test_source_conformance.py:45-53` | Not applicable in target — identifiers are platform-generated |

### REQ-I-003 — A booking is all-or-nothing

| Criterion | Given | When | Then | Evidence today | Target verification |
|---|---|---|---|---|---|
| AC-REQ-I-003-1 | A valid offering and an unknown customer | A booking is submitted | Outcome is "customer not found" (9918); the free-place count is unchanged; no booking exists; no lock remains | `tests/test_conew_booking.py:165-175`, `tests/test_conew_booking.py:200-210` | Transaction rolled back; balance unchanged |
| AC-REQ-I-003-2 | An empty booking file | A booking is submitted | The decrement is backed out and a failure outcome is returned; no lock remains | `tests/test_conew_booking.py:185-198`, `tests/test_source_conformance.py:75-84` | Not applicable in target (no MAX+1); covered by AC-REQ-I-002-1 |
| AC-REQ-I-003-3 | Any outcome path | The service returns | No record is left held | `tests/test_conew_booking.py:200-210` | Lock-wait monitoring during the acceptance run |

### REQ-I-004 — Lost-update protection on customer data

| Criterion | Given | When | Then | Evidence today | Target verification |
|---|---|---|---|---|---|
| AC-REQ-I-004-1 | Operators A and B both read customer X (stamp T1) | A saves (stamp becomes T2); B then saves with T1 | B receives "changed by another user" (9934); the record holds A's values; B is shown the stored values | **harness needed** — interleaving harness for `CUMOD-N` | Object version number mismatch returns a conflict |
| AC-REQ-I-004-2 | Operator A reads customer X (stamp T1) | A saves with T1 | The save succeeds and a new stamp is returned | **harness needed** — service harness for `CUMOD-N` | Update with matching version succeeds |

### REQ-I-005 — Customer identifiers are unique under contention

| Criterion | Given | When | Then | Evidence today | Target verification |
|---|---|---|---|---|---|
| AC-REQ-I-005-1 | Two operators registering at the same time | Both generate identifiers before either stores (interleaved) | The two customers have different identifiers | **harness needed** — interleaving harness for `CUNEW-N` (idiom asserted statically by `tests/test_source_conformance.py:91-95`) | Person number generation by the platform |

### REQ-I-006 — No silent success

| Criterion | Given | When | Then | Evidence today | Target verification |
|---|---|---|---|---|---|
| AC-REQ-I-006-1 | Offering identifier that matches no record | A booking is submitted | A failure outcome is returned (the sample returns 0 — `tests/test_conew_booking.py:177-183` documents current behaviour) | **harness needed** — target-side test only | Lookup validation |
| AC-REQ-I-006-2 | A runtime error injected inside a service after the success code is preset | The service is called | A failure outcome is returned and the error is logged | **harness needed** — fault injection | Error handling of the delivered platform |
| AC-REQ-I-006-3 | No offering with the requested identifier | Detail is requested | Outcome is "not found", not the concurrency message | **harness needed** — service harness for `CRGET-N` | Not-found response |

### REQ-I-007 — A booking requires an existing customer

| Criterion | Given | When | Then | Evidence today | Target verification |
|---|---|---|---|---|---|
| AC-REQ-I-007-1 | Unknown customer, valid offering with free places | A booking is submitted | Outcome is "customer not found" (9918); no booking exists; the free-place count is unchanged | `tests/test_conew_booking.py:165-175` | Person validation before balance adjustment |

## Interface requirements

### REQ-X-001 — Common response envelope

| Criterion | Given | When | Then | Evidence today | Target verification |
|---|---|---|---|---|---|
| AC-REQ-X-001-1 | Any service call | The response is read | Response code and text are present; success is exactly `0` | `tests/test_conew_booking.py:18-25`, `tests/test_crlist_listing.py:23-27` | API contract test on the REST response |

### REQ-X-002 — Booking interface

| Criterion | Given | When | Then | Evidence today | Target verification |
|---|---|---|---|---|---|
| AC-REQ-X-002-1 | The booking interface definition | It is compared with the shipped parameter area | Customer identifier, offering identifier in; booking identifier out; week count, reservation date, booking date absent | `tests/test_disposition_analysis.py:69-75` (the three fields are never assigned) | Interface design review |

### REQ-X-003 — Offering list and detail interface

| Criterion | Given | When | Then | Evidence today | Target verification |
|---|---|---|---|---|---|
| AC-REQ-X-003-1 | The list interface definition | An eligible offering is listed | Identifier, dates, locations, vessel name and three prices are present and typed (the sample returns display strings — `tests/test_crlist_listing.py:52-63` documents current formatting) | **harness needed** — target-side contract test | API contract test |
| AC-REQ-X-003-2 | The list interface definition | It is compared with the shipped parameter area | Destination filter, computed price and picture fields are absent | `tests/test_disposition_analysis.py:69-75` (`P-DESTHARBOR` never assigned) | Interface design review |

### REQ-X-004 — Customer interface

| Criterion | Given | When | Then | Evidence today | Target verification |
|---|---|---|---|---|---|
| AC-REQ-X-004-1 | The customer interface definition | It is compared with the shipped parameter areas | Search value and version stamp in; customer data and stamp out; no language, user or password field | `tests/test_disposition_analysis.py:69-75` | Interface design review |

## Non-functional requirements

### REQ-N-001 — Message language

| Criterion | Given | When | Then | Evidence today | Target verification |
|---|---|---|---|---|---|
| AC-REQ-N-001-1 | The shipped services and adapter | The language selector is traced | It is never assigned; only the English branch is reachable | `tests/test_disposition_analysis.py:69-75` | Language decision recorded in the configuration workbook |

### REQ-N-002 — Correctness under concurrent load

| Criterion | Given | When | Then | Evidence today | Target verification |
|---|---|---|---|---|---|
| AC-REQ-N-002-1 | The acceptance test plan | It is reviewed | It contains interleaved scenarios for AC-REQ-I-001-1, AC-REQ-I-002-1 and AC-REQ-I-004-1, not only sequential cases | `tests/test_concurrency.py:24-127` (the pattern) | Concurrency scenarios executed in the acceptance environment |

### REQ-N-003 — Errors are logged, not swallowed

| Criterion | Given | When | Then | Evidence today | Target verification |
|---|---|---|---|---|---|
| AC-REQ-N-003-1 | A runtime error injected in any service | The service is called | An error record with service name, error number and line exists and the caller receives a failure outcome | **harness needed** — fault injection | Platform diagnostic log inspection |

### REQ-N-004 — Authentication and authorization are the platform's

| Criterion | Given | When | Then | Evidence today | Target verification |
|---|---|---|---|---|---|
| AC-REQ-N-004-1 | The target design | It is reviewed | Operator identity comes from the platform's identity service; no application password attribute exists | Not testable in the sample (no credential check exists to compare against) | Security design review; role-based access test |

### REQ-N-005 — Every requirement is verifiable on synthetic data

| Criterion | Given | When | Then | Evidence today | Target verification |
|---|---|---|---|---|---|
| AC-REQ-N-005-1 | This document and `requirements-baseline.md` | `../02-business-rule-extraction/generate_rule_evidence.py --check` runs | Every requirement identifier appears in both files; every source citation resolves to existing lines; exit code 0 | `fpps-hcm-modernization-deliverable/02-business-rule-extraction/generate_rule_evidence.py:1-40` | Requirements-tool traceability report |

## Coverage summary

Counted from the criterion tables above by `../02-business-rule-extraction/generate_rule_evidence.py`, which also verifies that every requirement in the baseline has at least one criterion here and that every cited test range exists.

<!-- generated:acceptance-coverage -->
| Evidence class | Criteria | Requirements touched |
|---|---|---|
| Executable check in the repository today | 31 | REQ-D-001, REQ-D-002, REQ-F-001, REQ-F-002, REQ-F-003, REQ-F-007, REQ-I-001, REQ-I-002, REQ-I-003, REQ-I-007, REQ-N-001, REQ-N-002, REQ-N-005, REQ-X-001, REQ-X-002, REQ-X-003, REQ-X-004 |
| Design review (not testable in the sample) | 1 | REQ-N-004 |
| Harness needed — SME decision first | 1 | REQ-D-001 |
| Harness needed — catalogue check | 1 | REQ-F-007 |
| Harness needed — fault injection | 2 | REQ-I-006, REQ-N-003 |
| Harness needed — interleaving harness | 2 | REQ-I-004, REQ-I-005 |
| Harness needed — load reconciliation | 1 | REQ-D-003 |
| Harness needed — service harness | 15 | REQ-D-003, REQ-D-004, REQ-D-005, REQ-D-006, REQ-F-002, REQ-F-004, REQ-F-005, REQ-F-006, REQ-I-004, REQ-I-006 |
| Harness needed — target-side test only | 5 | REQ-F-003, REQ-I-006, REQ-X-003 |
| All criteria | 59 | 29 requirements |
<!-- /generated:acceptance-coverage -->

## Synthetic data and scope

All executable evidence runs against `tests/harness/adabas_sim.py` and the fixtures in `tests/harness/fixtures.py`. No production system or production data is used or required; FPPS is referenced only by analogy.

← [Back to the directory README](README.md) · [Navigation hub](../README.md)
