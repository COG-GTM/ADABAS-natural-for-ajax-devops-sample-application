# Business rules extracted from the CRUISE16 service library

Every rule below is written the way a payroll systems integrator reads an eligibility or validation edit: what the system accepts, what it rejects, which code it returns, and what happens to the transaction. Every citation is a `path:start-end` into the shipped Natural source; the tables marked "generated" are produced from the sources by `generate_rule_evidence.py` (a validation generator, not a conversion), which also fails if a citation points outside its file, if a confidence score disagrees with the rubric in [`confidence-model.md`](confidence-model.md), or if a rule identifier used elsewhere is not defined here.

Maturity: the rules and their source citations are Demonstrated (the source is in this repository and the conformance tests in `tests/test_source_conformance.py:20-124` assert the key constructs). HCM analogs and dispositions are Designed; they become Roadmap items once a payroll SME signs each row.

Analogy used throughout (from the hub README): a booking is a pay or personnel transaction; the `CAMSG-N` message codes are the payroll edit catalogue; the record hold, test-and-set, and serialized MAX+1 key are pay-run integrity.

## How to read a rule entry

| Field | Meaning |
|---|---|
| Statement | The rule in plain language, as an edit an SI would configure or test |
| Rule class | validation edit, integrity/concurrency, derivation, lookup, message/translation, workflow/transaction boundary, presentation |
| Source | Exact `path:start-end` of the lines that implement the rule |
| Message code(s) | Codes moved to `MSG-GROUP-PARA.MSG-NR` on the rule's paths; `0` is what the caller sees for success |
| Confidence | Score from [`confidence-model.md`](confidence-model.md); letters are the evidence classes (S static citation, C conformance test, H harness execution, D repository documentation, N inferred runtime semantics, R data-dependent) |
| HCM analog | Where the rule lands in Oracle HCM (or an alternate HCM): element entry validation, fast formula, approval rule, HDL business-object validation, platform feature |
| Disposition | carry, replace-with-standard-HCM, redesign, retire, SME-required |

## Section 1 — Active rules

Rules that executable code enforces today. The table is generated from the seven service sources; each rule entry below cites the exact lines.

<!-- generated:emitted-codes-by-service -->
| Service | Code | Executable source line(s) | English catalog text | Response code returned to caller |
|---|---|---|---|---|
| `CONEW-N` | 9800 | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:153` | Travel Booking successful | 0 |
| `CONEW-N` | 9902 | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN` lines 130, 136 | Cruise no longer available | 9902 |
| `CONEW-N` | 9904 | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN` lines 56, 70 | Customer Id missing | 9904 |
| `CONEW-N` | 9905 | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN` lines 58, 64 | Cruise Id missing | 9905 |
| `CONEW-N` | 9918 | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:159` | Customer Id not found | 9918 |
| `CONEW-N` | 9999 | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:50` | Function not yet supported | 9999 |
| `CRLIST-N` | 9807 | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CRLIST-N.NSN:92` | List of Cruises shown | 0 |
| `CRLIST-N` | 9857 | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CRLIST-N.NSN:90` | no Cruise Data found | 9857 |
| `CRLIST-N` | 9999 | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CRLIST-N.NSN:43` | Function not yet supported | 9999 |
| `CRGET-N` | 9934 | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CRGET-N.NSN:116` | Customer changed from another user | 9934 |
| `CUGET-N` | 9923 | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CUGET-N.NSN:76` | Customer Id missing | 9923 |
| `CUGET-N` | 9924 | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CUGET-N.NSN:61` | Customer Id not found | 9924 |
| `CUGET-N` | 9999 | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CUGET-N.NSN:52` | Function not yet supported | 9999 |
| `CUNEW-N` | 9999 | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CUNEW-N.NSN:37` | Function not yet supported | 9999 |
| `CUMOD-N` | 9924 | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CUMOD-N.NSN:46` | Customer Id not found | 9924 |
| `CUMOD-N` | 9934 | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CUMOD-N.NSN:67` | Customer changed from another user | 9934 |
| `CUMOD-N` | 9999 | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CUMOD-N.NSN:37` | Function not yet supported | 9999 |
<!-- /generated:emitted-codes-by-service -->

### Booking transaction (`CONEW-N`)

### BR-001 — Customer identifier is required

| | |
|---|---|
| Statement | A booking is rejected with edit 9904 ("Customer Id missing") when the customer identifier is blank or the literal `0`. |
| Rule class | Validation edit |
| Source | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:54-56` |
| Message code(s) | 9904 |
| Confidence | 0.95 (S+C+H+D) — the `WHEN` clause is asserted by `tests/test_source_conformance.py:86-89`, the behaviour by `tests/test_conew_booking.py:66-73`, and the outcome table in `docs/transaction-flows.md:86-97` |
| HCM analog | Required-attribute validation on the transaction business object (HDL `PersonId`/`AssignmentId` resolution; element entry requires an assignment) |
| Disposition | Replace with standard HCM — required keys are enforced by the platform |

### BR-002 — Offering identifier is required

| | |
|---|---|
| Statement | A booking is rejected with edit 9905 ("Cruise Id missing") when the offering (cruise) identifier is blank or the literal `0`. |
| Rule class | Validation edit |
| Source | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:57-58` |
| Message code(s) | 9905 |
| Confidence | 0.95 (S+C+H+D) — `tests/test_source_conformance.py:86-89`, `tests/test_conew_booking.py:75-82`, `docs/transaction-flows.md:86-97` |
| HCM analog | Required-attribute validation (element or position reference must be supplied) |
| Disposition | Replace with standard HCM |

### BR-003 — Required-field edits fire one at a time, customer first

| | |
|---|---|
| Statement | When both identifiers are missing only 9904 is reported; the offering edit is evaluated only if the customer edit passes (`DECIDE FOR FIRST CONDITION`). |
| Rule class | Validation edit (edit sequencing) |
| Source | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:54-59` |
| Message code(s) | 9904 before 9905 |
| Confidence | 0.70 (S+H) — `tests/test_conew_booking.py:84-90` |
| HCM analog | HCM validation frameworks report all failed edits on a transaction at once; first-error-only reporting is an artifact of the legacy edit chain |
| Disposition | Redesign — report all failed edits together; keep 9904/9905 as distinct messages |

### BR-004 — Offering identifier must be numeric, at most eight digits

| | |
|---|---|
| Statement | A non-numeric or over-long offering identifier is rejected with 9905; a valid one is converted to the numeric key used for the record lookup. |
| Rule class | Validation edit |
| Source | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:60-65` |
| Message code(s) | 9905 |
| Confidence | 0.90 (S+C+H) — `IS (N8)` asserted by `tests/test_source_conformance.py:86-89`; `tests/test_conew_booking.py:92-98` |
| HCM analog | Attribute format validation on the business object (numeric key, length 8) |
| Disposition | Replace with standard HCM — key format is a data-type property of the target object |

### BR-005 — Customer identifier must be numeric; a format failure does not stop the transaction

| | |
|---|---|
| Statement | A non-numeric customer identifier sets 9904, but processing continues with a zero customer key; the later existence check (BR-010) then overwrites the code with 9918 ("Customer Id not found"). The caller never sees 9904 for a format error when the offering exists. |
| Rule class | Validation edit (with a fall-through defect) |
| Source | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:66-71` and `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:153-160` |
| Message code(s) | 9904 (set), 9918 (returned) |
| Confidence | 0.90 (S+C+H) — `tests/test_conew_booking.py:100-108` reproduces the overwrite |
| HCM analog | Attribute format validation; the fall-through is the kind of behaviour a language converter copies verbatim |
| Disposition | Redesign — validate format, stop, and report 9904; see also BR-M004 |

### BR-006 — A booking consumes one free place, decided on the held record

| | |
|---|---|
| Statement | The offering record is re-read in hold (`GET` after `FIND`), the free-place count is taken from that held copy, and the booking proceeds only if the count is greater than zero, decrementing it by one. If the count is zero the hold is released with `BACKOUT TRANSACTION` and 9902 ("Cruise no longer available") is returned. Two sessions cannot both pass the check for the same last place. |
| Rule class | Integrity / concurrency |
| Source | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:79-92` and `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:133-138` |
| Message code(s) | 9902 (sold out); 9800 → 0 on the success path |
| Confidence | 0.95 (S+C+H+D) — `tests/test_source_conformance.py:35-43` and `tests/test_source_conformance.py:63-73`; `tests/test_concurrency.py:67-97`; `docs/concurrency-refactor.md:12-77` |
| HCM analog | Atomic headcount/FTE check on a position or a balance-limited element entry; must execute as a single serialized database operation, not as read-then-write in application code |
| Disposition | Carry as integrity requirement REQ-I-001 — the platform must guarantee it; do not re-implement as application logic |

### BR-007 — Booking identifier is the previous maximum plus one, generated under hold

| | |
|---|---|
| Statement | The highest existing booking record is read descending by key and placed in hold with a no-change `UPDATE` before `MAX+1` is computed, so concurrent sessions cannot compute the same new key. |
| Rule class | Integrity / derivation |
| Source | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:95-102` |
| Message code(s) | none |
| Confidence | 0.95 (S+C+H+D) — `tests/test_source_conformance.py:45-53`; `tests/test_concurrency.py:99-127`; `docs/concurrency-refactor.md:78-133` |
| HCM analog | Platform-generated identifiers (Person Number / object IDs); HDL `SourceSystemId` for legacy keys |
| Disposition | Replace with standard HCM for key generation; carry the uniqueness guarantee as REQ-I-002 |

### BR-008 — Booking price is the one-week price

| | |
|---|---|
| Statement | The price recorded on the booking is always the offering's one-week price; week count is not an input (the field exists but is never populated, see `what-we-will-not-build.md` in 05). |
| Rule class | Derivation |
| Source | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:103` |
| Message code(s) | none |
| Confidence | 0.70 (S+H) — `tests/test_conew_booking.py:42-50` |
| HCM analog | Element rate / fast formula returning the rate for the entry |
| Disposition | SME-required — confirm that a single rate is the business intent (the commented code in BR-D001 implies three durations) |

### BR-009 — Booking date is the system date

| | |
|---|---|
| Statement | The booking date stored on the record is the current system date at commit time; the caller cannot supply it. |
| Rule class | Derivation |
| Source | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:105-106` |
| Message code(s) | none |
| Confidence | 0.50 (S) — the harness takes the date as a parameter rather than deriving it |
| HCM analog | Effective start date / creation date defaulted by the platform |
| Disposition | Replace with standard HCM |

### BR-010 — The customer must exist; otherwise the whole booking is undone

| | |
|---|---|
| Statement | After the free-place decrement is buffered, the customer key is looked up. If no customer record exists, 9918 is returned and `BACKOUT TRANSACTION` discards the decrement; no booking record is written. Because the check runs inside the availability branch, a sold-out offering reports 9902 even for an unknown customer. |
| Rule class | Lookup / validation edit |
| Source | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:112-123` and `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:151-162` |
| Message code(s) | 9918 |
| Confidence | 0.80 (S+H+D) — `tests/test_conew_booking.py:132-140` and `tests/test_conew_booking.py:165-175`; `docs/concurrency-refactor.md:134-155` |
| HCM analog | Foreign-key resolution on the business object (HDL user-key or `SourceSystemId` lookup for the person) |
| Disposition | Replace with standard HCM for the lookup; carry the rollback guarantee as REQ-I-007 |

### BR-011 — Booking is all-or-nothing

| | |
|---|---|
| Statement | The booking record is stored and the transaction committed only when the working code is 9800; any other code backs out the decrement and releases every held record. |
| Rule class | Workflow / transaction boundary |
| Source | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:114-123` |
| Message code(s) | 9800 → 0 (commit); all others (backout) |
| Confidence | 0.95 (S+C+H+D) — `tests/test_source_conformance.py:55-61`; `tests/test_conew_booking.py:200-210`; `docs/concurrency-refactor.md:134-155` |
| HCM analog | Business-object transaction atomicity (HDL loads a business object atomically; REST transactions roll back on validation failure) |
| Disposition | Carry as integrity requirement REQ-I-003 |

### BR-012 — Every service reports outcome as a code and a typed text

| | |
|---|---|
| Statement | Each service passes its working code through `CAMSG-N`, then returns `P-RSPCODE` = the (possibly remapped) code and `P-RSPTXT` = `type '-' text`. The adapter treats exactly `'0'` as success. |
| Rule class | Message / translation |
| Source | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:143-146`; same pattern at `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CRLIST-N.NSN:96-99`, `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CRGET-N.NSN:121-124`, `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CUGET-N.NSN:82-85`, `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CUNEW-N.NSN:62-65`, `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CUMOD-N.NSN:72-75`; consumer at `SunnyIslands/Natural-Libraries/RDCRUISE/Programs/RDCRUISP.NSP:584-590` |
| Message code(s) | all |
| Confidence | 0.90 (S+C+H) — `tests/test_source_conformance.py:120-123`; `tests/test_conew_booking.py:18-25` |
| HCM analog | Message dictionary / lookup type keyed by message code; REST error payload |
| Disposition | Replace with standard HCM — keep the code catalogue as the acceptance-test vocabulary |

### BR-013 — An empty booking file is reported as "no longer available"

| | |
|---|---|
| Statement | If the booking file has no records the `MAX+1` loop body never runs; a guard backs out the decrement and returns 9902. The condition is an infrastructure state, but the code shown to the user means "sold out". |
| Rule class | Workflow / transaction boundary |
| Source | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:126-131` |
| Message code(s) | 9902 |
| Confidence | 0.95 (S+C+H+D) — `tests/test_source_conformance.py:75-84`; `tests/test_conew_booking.py:185-198`; `docs/concurrency-refactor.md:105-133` |
| HCM analog | Not applicable — platform-generated keys remove the condition |
| Disposition | Retire (condition disappears with generated keys); see BR-M003 for the message misuse |

### Offering list (`CRLIST-N`)

### BR-014 — Only offerings with at least one free place are listed

| | |
|---|---|
| Statement | An offering whose free-place count is zero is skipped from the list. |
| Rule class | Validation edit (eligibility filter) |
| Source | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CRLIST-N.NSN:51-57` |
| Message code(s) | none |
| Confidence | 0.90 (S+C+H) — `tests/test_source_conformance.py:109-112`; `tests/test_crlist_listing.py:10-15` and `tests/test_crlist_listing.py:71-77` |
| HCM analog | Eligibility profile / list-of-values filter on open positions or eligible elements |
| Disposition | Replace with standard HCM |

### BR-015 — Optional filter on start harbor

| | |
|---|---|
| Statement | When a start-harbor value is supplied only offerings with that exact start harbor are listed; blank means no filter. (The destination-harbor filter on the following lines exists in code but its input is never populated by the adapter — see BR-C005.) |
| Rule class | Lookup (filter) |
| Source | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CRLIST-N.NSN:59-61` |
| Message code(s) | none |
| Confidence | 0.90 (S+C+H) — `tests/test_source_conformance.py:109-112`; `tests/test_crlist_listing.py:36-39` |
| HCM analog | Query parameter / saved search criterion |
| Disposition | Replace with standard HCM |

### BR-016 — Offerings are listed newest start date first

| | |
|---|---|
| Statement | The list is produced in descending start-date order. |
| Rule class | Presentation |
| Source | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CRLIST-N.NSN:51` |
| Message code(s) | none |
| Confidence | 0.90 (S+C+H) — `tests/test_source_conformance.py:106-107`; `tests/test_crlist_listing.py:17-21` |
| HCM analog | Default sort on a list page or report |
| Disposition | Replace with standard HCM |

### BR-017 — Vessel name is resolved from the vessel master

| | |
|---|---|
| Statement | Each listed offering carries the name of its vessel, looked up by vessel identifier; the first match is used. |
| Rule class | Lookup |
| Source | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CRLIST-N.NSN:79-83` |
| Message code(s) | none |
| Confidence | 0.70 (S+H) — `tests/test_crlist_listing.py:65-69` |
| HCM analog | Reference-data join (lookup code to meaning) |
| Disposition | Replace with standard HCM |

### BR-018 — Dates and prices are formatted for display inside the service

| | |
|---|---|
| Statement | Dates are returned as `YYYY-MM-DD` and prices as zero-suppressed amounts with two decimals; the service, not the screen, applies the edit masks. |
| Rule class | Presentation |
| Source | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CRLIST-N.NSN:72-76` |
| Message code(s) | none |
| Confidence | 0.70 (S+H) — `tests/test_crlist_listing.py:52-63` |
| HCM analog | Locale/format handled by the UI layer |
| Disposition | Retire — formatting moves to the presentation layer of the target |

### BR-019 — An empty list is an information code, a non-empty list is success

| | |
|---|---|
| Statement | No qualifying offering returns 9857 ("no Cruise Data found"); otherwise 9807 ("List of Cruises shown"), which `CAMSG-N` remaps to response code 0. |
| Rule class | Message / translation |
| Source | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CRLIST-N.NSN:88-93` |
| Message code(s) | 9857; 9807 → 0 |
| Confidence | 0.90 (S+C+H) — `tests/test_source_conformance.py:103-104`; `tests/test_crlist_listing.py:23-34` |
| HCM analog | Empty-result handling on a query; informational message |
| Disposition | Replace with standard HCM |

### BR-020 — Free places are stored as a single numeric character

| | |
|---|---|
| Statement | The offering status field is one alphanumeric character interpreted as the number of free places (`VAL` into a one-digit numeric), so the observable capacity range is 0–9. |
| Rule class | Derivation (data semantics) |
| Source | `SunnyIslands/Natural-Libraries/CRUISE16/Local Data Areas/NCDATA-L.NSL:24`; `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CRLIST-N.NSN:53`; `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:83` |
| Message code(s) | none |
| Confidence | 0.70 (S+H) — `tests/test_conew_booking.py:27-33` and `tests/test_conew_booking.py:150-161` exercise the decrement on synthetic values 1–5 |
| HCM analog | Position headcount / FTE (integer attribute with range validation) |
| Disposition | SME-required — confirm whether the 0–9 range is a business limit or a sample artifact before sizing the target attribute (REQ-D-001) |

### Offering detail (`CRGET-N`)

### BR-021 — Price shown for an offering depends on its duration

| | |
|---|---|
| Statement | Duration in days is end date minus start date; 7 days selects the one-week price, 14 the two-week price, 21 the three-week price. Any other duration falls back to the two-week price without an edit (the 9915 edit on that path is commented out, BR-D009). |
| Rule class | Derivation |
| Source | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CRGET-N.NSN:75-95` |
| Message code(s) | none |
| Confidence | 0.70 (S+H) — `tests/test_crlist_listing.py:80-101` |
| HCM analog | Fast formula / rate definition selected by duration band |
| Disposition | SME-required — the silent fallback for non-standard durations is a business decision, not a rule |

### BR-022 — Offering detail is read by key without an availability filter

| | |
|---|---|
| Statement | The detail service reads one record starting at the requested identifier and returns it regardless of free places; a sold-out offering is still shown. |
| Rule class | Lookup |
| Source | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CRGET-N.NSN:47-52` |
| Message code(s) | 9934 when no record is read (see BR-M001) |
| Confidence | 0.50 (S) — no harness model of `CRGET-N`'s read exists |
| HCM analog | Get-by-key on the business object |
| Disposition | Replace with standard HCM; see BR-C001 for the start-value semantics of the read |

### Customer services (`CUGET-N`, `CUNEW-N`, `CUMOD-N`)

### BR-023 — Customer retrieval by numeric identifier

| | |
|---|---|
| Statement | If the identifier supplied is numeric (at most eight digits) the customer is found by key; no record returns 9924 ("Customer Id not found"). |
| Rule class | Lookup / validation edit |
| Source | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CUGET-N.NSN:56-67` |
| Message code(s) | 9924 |
| Confidence | 0.50 (S) — no harness model; acceptance criteria in 05 flag the harness |
| HCM analog | Person search by Person Number |
| Disposition | Replace with standard HCM |

### BR-024 — Customer retrieval by e-mail when the identifier is not numeric

| | |
|---|---|
| Statement | A non-numeric identifier is treated as an e-mail address; the customer file is read sequentially and the first record whose primary e-mail equals the input is returned. No match returns 9923 ("Customer Id missing"). |
| Rule class | Lookup |
| Source | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CUGET-N.NSN:68-78` |
| Message code(s) | 9923 |
| Confidence | 0.50 (S) |
| HCM analog | Person search by e-mail (alternate identifier) |
| Disposition | Replace with standard HCM; see BR-M002 (message misuse) and BR-C003 (blank-identifier match) |

### BR-025 — "Login" is a customer lookup with no credential check

| | |
|---|---|
| Statement | The adapter's login handler calls the customer retrieval service with the typed identifier and treats response `'0'` as logged in. The user and password fields in the common parameter area are passed to every service but never assigned or read. |
| Rule class | Workflow |
| Source | `SunnyIslands/Natural-Libraries/RDCRUISE/Programs/RDCRUISP.NSP:514-528`; `SunnyIslands/Natural-Libraries/CRUISE16/Parameter Data Areas/NCCOMM-P.NSA:9-12` |
| Message code(s) | 9923 / 9924 shown as login failure at `SunnyIslands/Natural-Libraries/RDCRUISE/Programs/RDCRUISP.NSP:556-563` |
| Confidence | 0.70 (S+C) — `tests/test_disposition_analysis.py:69-75` asserts the never-assigned fields |
| HCM analog | Platform identity (SSO), roles and data security — never application code |
| Disposition | Replace with standard HCM; the unused credential fields are excluded (see 05 `what-we-will-not-build.md`) |

### BR-026 — Customer data returned to the caller

| | |
|---|---|
| Statement | Retrieval returns identifier, birth date formatted `YYYY-MM-DD`, sex, surname, the legacy first-name column, primary e-mail, street, country, postal code, city, and the record's timestamp (used later for BR-032). |
| Rule class | Derivation (mapping) |
| Source | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CUGET-N.NSN:88-104` |
| Message code(s) | none |
| Confidence | 0.50 (S) |
| HCM analog | Person / address / e-mail business objects (HDL `Worker`, `PersonAddress`, `PersonEmail`) |
| Disposition | Redesign — see BR-C006 for the first-name lineage break that must be resolved in the mapping |

### BR-027 — New customer identifier is the previous maximum plus one, generated under hold

| | |
|---|---|
| Statement | The highest customer record is read descending by key and held with a no-change `UPDATE`; the new identifier is that key plus one. This is the idiom the booking refactor adopted (BR-007). |
| Rule class | Integrity / derivation |
| Source | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CUNEW-N.NSN:41-44` |
| Message code(s) | none |
| Confidence | 0.80 (S+C+D) — `tests/test_source_conformance.py:91-95`; `docs/concurrency-refactor.md:105-133` and `docs/concurrency-refactor.md:156-167` |
| HCM analog | Person Number generation (platform sequence) |
| Disposition | Replace with standard HCM; carry uniqueness as REQ-I-005 |

### BR-028 — New customer record content and commit

| | |
|---|---|
| Statement | The service stores legacy first name, surname, primary e-mail, street, postal code, city, birth date converted with `VAL`, and a server timestamp, then commits. No edit is applied to any field; success returns code 0 with an empty text (BR-030). |
| Rule class | Workflow / transaction boundary |
| Source | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CUNEW-N.NSN:46-57` |
| Message code(s) | none (0 on success) |
| Confidence | 0.50 (S) |
| HCM analog | Worker create (HDL `Worker.dat` with `PersonName`, `PersonEmail`, `PersonAddress`) — with the platform's own required-field and format validation |
| Disposition | Replace with standard HCM; birth-date format inconsistency is BR-C004 |

### BR-029 — Modify requires an existing customer

| | |
|---|---|
| Statement | The identifier is converted to numeric and the customer read in hold; no record returns 9924. |
| Rule class | Lookup / validation edit |
| Source | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CUMOD-N.NSN:41-48` |
| Message code(s) | 9924 |
| Confidence | 0.50 (S) |
| HCM analog | Update-by-key with existence validation |
| Disposition | Replace with standard HCM |

### BR-030 — Customer services return success without a catalogue code

| | |
|---|---|
| Statement | Retrieval, create and modify never set a success code; the working code stays at its initial `0`, `CAMSG-N` finds no catalogue entry (`NONE IGNORE`), sets type `S`, and the caller receives `0` with the text `S-`. The catalogue's success entries for these functions (9801, 9803–9806) are never used. |
| Rule class | Message / translation |
| Source | `SunnyIslands/Natural-Libraries/CRUISE16/Local Data Areas/NCDATA-L.NSL:76-80`; `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CAMSG-N.NSN:180-189`; `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CUNEW-N.NSN:62-65` |
| Message code(s) | 0 |
| Confidence | 0.50 (S) |
| HCM analog | Standard success response; message text optional |
| Disposition | Replace with standard HCM |

### BR-031 — Modify writes the same field set and refreshes the timestamp

| | |
|---|---|
| Statement | On a successful version check the service writes legacy first name, surname, primary e-mail, street, postal code, city and birth date (dashes removed before numeric conversion), sets a new server timestamp, updates the held record and commits. |
| Rule class | Workflow / transaction boundary |
| Source | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CUMOD-N.NSN:53-64` |
| Message code(s) | none (0 on success) |
| Confidence | 0.50 (S) |
| HCM analog | Worker update (date-effective person record) |
| Disposition | Replace with standard HCM |

### BR-032 — A customer change is rejected if someone else changed the record first

| | |
|---|---|
| Statement | The timestamp the client received on retrieval must equal the timestamp on the held record; if it does not, no update is written and 9934 ("Customer changed from another user") is returned. The adapter then restores the last-read values on screen. |
| Rule class | Integrity / concurrency (optimistic version check) |
| Source | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CUMOD-N.NSN:50-52` and `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CUMOD-N.NSN:65-68`; adapter at `SunnyIslands/Natural-Libraries/RDCRUISE/Programs/RDCRUISP.NSP:644-657` |
| Message code(s) | 9934 |
| Confidence | 0.60 (S+D) — `docs/concurrency-refactor.md:156-167` classifies the pattern; no harness model exists yet |
| HCM analog | Object version number / `If-Match` ETag on REST updates; lost-update protection is a platform property |
| Disposition | Carry as integrity requirement REQ-I-004 — the target must reject stale updates, whatever mechanism it uses |

### Message catalogue (`CAMSG-N`)

### BR-033 — Message text is selected by language; only English is reachable

| | |
|---|---|
| Statement | Language `'2'` selects the German catalogue, anything else the English one. Every service copies the caller's language field into the message group, but the adapter never assigns that field, so the German branch is unreachable from the UI adapter. |
| Rule class | Message / translation |
| Source | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CAMSG-N.NSN:17-19` and `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CAMSG-N.NSN:101-102`; `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:44`; `SunnyIslands/Natural-Libraries/CRUISE16/Parameter Data Areas/NCCOMM-P.NSA:10` |
| Message code(s) | all |
| Confidence | 0.70 (S+C) — `tests/test_disposition_analysis.py:69-75` asserts `P-LANG` is never assigned |
| HCM analog | Translated message dictionary (platform multilingual support) |
| Disposition | SME-required — multilingual intent is evident in the catalogue but not in the running path (REQ-N-001) |

### BR-034 — Success codes are remapped to response code 0 and typed `S`

| | |
|---|---|
| Statement | The catalogue entries for success outcomes translate the text and then set the code to `0`; after translation, code `0` yields type `S` and any other code type `I`. |
| Rule class | Message / translation |
| Source | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CAMSG-N.NSN:104-106`; `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CAMSG-N.NSN:185-189` |
| Message code(s) | success codes listed in the generated reconciliation table below → 0 |
| Confidence | 0.90 (S+C+H) — `tests/test_source_conformance.py:120-123`; `tests/test_crlist_listing.py:23-27` |
| HCM analog | Message severity (success / information / error) on the message dictionary |
| Disposition | Replace with standard HCM |

### BR-035 — Unknown codes pass through untranslated

| | |
|---|---|
| Statement | A code with no catalogue entry leaves the text unchanged and the code unchanged (`NONE IGNORE`); the caller receives the raw code with type `I`. |
| Rule class | Message / translation |
| Source | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CAMSG-N.NSN:180-183` |
| Message code(s) | any uncatalogued code |
| Confidence | 0.50 (S) — no service emits an uncatalogued code today (generated reconciliation table below) |
| HCM analog | Default message for unknown codes |
| Disposition | Replace with standard HCM |

### Exercise scaffolding

### BR-036 — Training gate returns "Function not yet supported"

| | |
|---|---|
| Statement | Five services test a local flag initialised to false; when true they return 9999 and skip all business logic. The flag exists for the training exercises in `docs/training-guide.md` and is never true in the shipped configuration. |
| Rule class | Workflow (scaffolding) |
| Source | generated table below; `SunnyIslands/Natural-Libraries/CRUISE16/Local Data Areas/NCDATA-L.NSL:86` |
| Message code(s) | 9999 |
| Confidence | 0.70 (S+C) — `tests/test_source_conformance.py:25-28` and `tests/test_source_conformance.py:103-104` include 9999 in the asserted code sets |
| HCM analog | none |
| Disposition | Retire — exercise scaffolding is not a requirement |

<!-- generated:student-gates -->
| Object | `IF #STUDENT` gate (executable line) |
|---|---|
| `CONEW-N` | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:48` |
| `CRLIST-N` | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CRLIST-N.NSN:41` |
| `CUGET-N` | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CUGET-N.NSN:50` |
| `CUNEW-N` | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CUNEW-N.NSN:34` |
| `CUMOD-N` | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CUMOD-N.NSN:35` |
| `NCDATA-L` | `SunnyIslands/Natural-Libraries/CRUISE16/Local Data Areas/NCDATA-L.NSL:86` (`#STUDENT (L) INIT <FALSE>`) |
<!-- /generated:student-gates -->

### Message catalogue reconciliation (generated)

<!-- generated:catalog-reconciliation -->
| Measure | Value |
|---|---|
| Codes translated by `CAMSG-N` (catalog) | 31 |
| Codes emitted by executable statements | 11 |
| Cataloged but never emitted in analyzed scope | 20 |
| Emitted but missing from the catalog | 0 |
| Success codes remapped to response code 0 | 7 (9800, 9801, 9803, 9804, 9805, 9806, 9807) |
| Commented-out `MOVE nnnn TO MSG-NR` statements | 10 |
<!-- /generated:catalog-reconciliation -->

## Section 2 — Commented-out and disabled rules

These rules exist only as commented statements. They are recorded as candidates for a business decision, never as active requirements; a language converter would either drop them silently or resurrect them wholesale. The table is generated from the sources; the entries below give the plain-language reading.

<!-- generated:commented-out-emits -->
| Object | Commented line | Code | English catalog text | Catalog status |
|---|---|---|---|---|
| `CONEW-N` | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:164` | 9800 | Travel Booking successful | also emitted by executable code |
| `CONEW-N` | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:170` | 9915 | only 1-3 Weeks possible | cataloged, never emitted |
| `CONEW-N` | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:174` | 9919 | wrong Format for Customer Id | cataloged, never emitted |
| `CONEW-N` | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:181` | 9917 | Format of Cruise Id invalid | cataloged, never emitted |
| `CONEW-N` | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:186` | 9916 | Cruise Id not found | cataloged, never emitted |
| `CONEW-N` | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:194` | 9914 | Format Date of Reservation invalid | cataloged, never emitted |
| `CONEW-N` | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:199` | 9913 | Year of Reservation invalid (2015-2020) | cataloged, never emitted |
| `CONEW-N` | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:206` | 9912 | invalid Date Format | cataloged, never emitted |
| `CONEW-N` | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:211` | 9911 | Year of Booking invalid (2015-2020) | cataloged, never emitted |
| `CRGET-N` | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CRGET-N.NSN:93` | 9915 | only 1-3 Weeks possible | cataloged, never emitted |
<!-- /generated:commented-out-emits -->

### BR-D001 — Week count must be 1, 2 or 3 and selects the price

| | |
|---|---|
| Statement | A booking would carry a week count of `1`, `2` or `3` (else 9915) and price the booking with the matching one-, two- or three-week rate. |
| Rule class | Validation edit + derivation (disabled) |
| Source | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:168-171` and `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:216-225`; input field `SunnyIslands/Natural-Libraries/CRUISE16/Parameter Data Areas/NCCONW-P.NSA:11` |
| Message code(s) | 9915 (catalogued, never emitted); 9901 "Week Count missing" is catalogued but has no code path even in comments |
| Confidence | 0.50 (S) |
| HCM analog | Element input value with a list-of-values and rate selection |
| Disposition | SME-required — decide whether multi-week pricing is a requirement (BR-008 is the active single-rate behaviour) |

### BR-D002 — Customer identifier format edit under a different code

| | |
|---|---|
| Statement | The disabled block rejects a non-numeric customer identifier with 9919; the active code (BR-005) uses 9904 for the same condition. |
| Rule class | Validation edit (disabled, superseded) |
| Source | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:173-176` |
| Message code(s) | 9919 |
| Confidence | 0.50 (S) |
| HCM analog | Attribute format validation |
| Disposition | Retire — superseded by BR-005 |

### BR-D003 — Offering identifier format edit under a different code

| | |
|---|---|
| Statement | The disabled block rejects a non-numeric offering identifier with 9917; the active code (BR-004) uses 9905. |
| Rule class | Validation edit (disabled, superseded) |
| Source | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:180-183` |
| Message code(s) | 9917 |
| Confidence | 0.50 (S) |
| HCM analog | Attribute format validation |
| Disposition | Retire — superseded by BR-004 |

### BR-D004 — Offering must exist

| | |
|---|---|
| Statement | The disabled block rejects an unknown offering identifier with 9916 ("Cruise Id not found"). No active code performs this edit: an unknown offering today returns code 0 with booking identifier 0 (BR-M005). |
| Rule class | Validation edit (disabled, not superseded) |
| Source | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:184-190` |
| Message code(s) | 9916 |
| Confidence | 0.50 (S) |
| HCM analog | Foreign-key resolution on the referenced object |
| Disposition | Carry the intent as REQ-F-003 acceptance criterion — the platform lookup supplies it |

### BR-D005 — Reservation date format

| | |
|---|---|
| Statement | A supplied reservation date must match `YYYYMMDD` (else 9914). |
| Rule class | Validation edit (disabled) |
| Source | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:192-196` |
| Message code(s) | 9914 |
| Confidence | 0.50 (S) |
| HCM analog | Date attribute type |
| Disposition | Retire — reservation date is a never-populated input (05 `what-we-will-not-build.md`) |

### BR-D006 — Reservation year must be 2015–2020

| | |
|---|---|
| Statement | A reservation year outside 2015–2020 would be rejected with 9913. The range is a literal that expired; the rule is time-bombed. |
| Rule class | Validation edit (disabled, time-bombed) |
| Source | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:197-202` |
| Message code(s) | 9913 |
| Confidence | 0.50 (S) |
| HCM analog | Never a literal; a date-range validation would reference a configured calendar |
| Disposition | Retire — never re-implement a hard-coded year range |

### BR-D007 — Booking date format

| | |
|---|---|
| Statement | A supplied booking date must match `YYYYMMDD` (else 9912). The active code derives the booking date from the system date instead (BR-009). |
| Rule class | Validation edit (disabled) |
| Source | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:204-208` |
| Message code(s) | 9912 |
| Confidence | 0.50 (S) |
| HCM analog | Date attribute type |
| Disposition | Retire |

### BR-D008 — Booking year must be 2015–2020

| | |
|---|---|
| Statement | A booking year outside 2015–2020 would be rejected with 9911; time-bombed like BR-D006. |
| Rule class | Validation edit (disabled, time-bombed) |
| Source | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:209-214` |
| Message code(s) | 9911 |
| Confidence | 0.50 (S) |
| HCM analog | Configured payroll calendar / period validation |
| Disposition | Retire |

### BR-D009 — Non-standard duration should be an edit

| | |
|---|---|
| Statement | In the detail service, a duration other than 7, 14 or 21 days would return 9915; the statement is commented and the two-week price is used silently (BR-021). |
| Rule class | Validation edit (disabled) |
| Source | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CRGET-N.NSN:92-94` |
| Message code(s) | 9915 |
| Confidence | 0.50 (S) |
| HCM analog | Rate-band validation |
| Disposition | SME-required — together with BR-021 |

### BR-D010 — Preset success before the disabled edit chain

| | |
|---|---|
| Statement | The disabled edit chain began by presetting 9800; the active code presets 9800 at the start of the customer check instead (`SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:153`). |
| Rule class | Message / translation (disabled) |
| Source | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:164` |
| Message code(s) | 9800 |
| Confidence | 0.50 (S) |
| HCM analog | none |
| Disposition | Retire |

## Section 3 — Misapplied codes and silent outcomes

Each row is a place where the code returned does not mean what the catalogue says, or where a failure is reported as success. These are the defects a naive conversion preserves exactly; the requirements baseline corrects the semantics instead of cloning them.

### BR-M001 — Detail read reports a concurrency message for "not found"

| | |
|---|---|
| Statement | When the detail read returns no record, the service sets 9934 ("Customer changed from another user"). The condition is "offering not found"; the catalogue has 9857 ("no Cruise Data found") and 9916 ("Cruise Id not found") for it. |
| Rule class | Message / translation (misapplied) |
| Source | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CRGET-N.NSN:114-119`; text at `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CAMSG-N.NSN:174-175` |
| Message code(s) | 9934 (should be 9857 or 9916) |
| Confidence | 0.50 (S) — a harness for `CRGET-N` is flagged in 05 |
| HCM analog | Not-found error on get-by-key |
| Disposition | Redesign — REQ-F-002 specifies the correct outcome |

### BR-M002 — E-mail lookup reports "identifier missing" for "not found"

| | |
|---|---|
| Statement | When no customer has the supplied e-mail, the service returns 9923 ("Customer Id missing") although an identifier was supplied; 9855 ("no Customer Data found") or 9924 would match the condition. The adapter treats 9923 and 9924 alike as "not found". |
| Rule class | Message / translation (misapplied) |
| Source | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CUGET-N.NSN:75-77`; adapter at `SunnyIslands/Natural-Libraries/RDCRUISE/Programs/RDCRUISP.NSP:556-559` |
| Message code(s) | 9923 (should be 9924 or 9855) |
| Confidence | 0.50 (S) |
| HCM analog | Not-found on alternate-key search |
| Disposition | Redesign — REQ-F-005 |

### BR-M003 — Empty booking file reported as "no longer available"

| | |
|---|---|
| Statement | See BR-013: an infrastructure state (no booking records at all) is reported with the sold-out code 9902. |
| Rule class | Message / translation (misapplied) |
| Source | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:126-131` |
| Message code(s) | 9902 |
| Confidence | 0.95 (S+C+H+D) — same evidence as BR-013 |
| HCM analog | none (condition removed by generated keys) |
| Disposition | Retire |

### BR-M004 — Format error on the customer identifier is reported as "not found"

| | |
|---|---|
| Statement | See BR-005: 9904 is set for a non-numeric customer identifier but the transaction continues and returns 9918. |
| Rule class | Validation edit (misapplied outcome) |
| Source | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:66-71`; `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:157-160` |
| Message code(s) | 9904 set, 9918 returned |
| Confidence | 0.90 (S+C+H) — `tests/test_conew_booking.py:100-108` |
| HCM analog | Format validation must stop the transaction |
| Disposition | Redesign — REQ-F-003 |

### BR-M005 — Unknown offering identifier returns success with booking identifier 0

| | |
|---|---|
| Statement | When the offering `FIND` returns no record, no code is set on the path; the working code is `0` (or a pending format code), `CAMSG-N` types it `S`, and the caller receives response `0`. The adapter then displays its booking-stored message with contract number 0. |
| Rule class | Validation edit (missing) |
| Source | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:79-80` and `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:139-146`; adapter at `SunnyIslands/Natural-Libraries/RDCRUISE/Programs/RDCRUISP.NSP:584-586` |
| Message code(s) | 0 (should be 9916) |
| Confidence | 0.70 (S+H) — `tests/test_conew_booking.py:177-183` shows booking identifier 0 and no stored record; the model's response code on this path is 0 (`tests/harness/natural_model.py:189-191`) |
| HCM analog | Foreign-key validation failure must be an error |
| Disposition | Redesign — REQ-F-003 acceptance criterion; BR-D004 is the disabled edit that would have caught it |

### BR-M006 — A runtime error can be reported as success

| | |
|---|---|
| Statement | The list and detail services preset the response code to `0` before reading; their `ON ERROR` blocks include a copycode whose every statement is commented out and then leave the service. A runtime error (for example a non-numeric status character in `VAL`) therefore returns response `0` with an empty result, which the adapter treats as success. |
| Rule class | Integrity (error handling) |
| Source | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CRLIST-N.NSN:48`; `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CRGET-N.NSN:47`; `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CUGET-N.NSN:37-40`; `SunnyIslands/Natural-Libraries/CRUISE16/Copycodes/ERRLOG-I.NSC:8-21` |
| Message code(s) | 0 on error |
| Confidence | 0.30 (S+N) — the `ON ERROR` / `ESCAPE ROUTINE` outcome is inferred from Natural semantics, not executed here; a fault-injection harness is flagged in 05 |
| HCM analog | Platform error handling and audit logging |
| Disposition | Replace with standard HCM; record the absence of logging as a gap (REQ-N-003, REQ-I-006) |

## Section 4 — Candidate rules needing SME confirmation

Candidates are behaviours the source exhibits whose business intent cannot be settled from the source alone. Each names the decision an SME must make.

### BR-C001 — Detail read uses a start value, not an exact match

| | |
|---|---|
| Statement | The detail service uses `READ (1) ... BY CRUISE-ID = value`, a logical read that starts at the given key. If the exact identifier does not exist, the next higher offering is returned as if it were the requested one; "not found" occurs only when the identifier exceeds every stored key. |
| Rule class | Lookup |
| Source | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CRGET-N.NSN:49-52` |
| Message code(s) | 9934 (not-found path, BR-M001) |
| Confidence | 0.30 (S+N) — start-value semantics of `READ ... BY descriptor = value` are inferred from Natural documentation, not observed on a Natural session |
| HCM analog | Get-by-key must be exact |
| Decision needed | Confirm on a Natural session with a non-existent identifier; the requirement (REQ-F-002) specifies exact match regardless |

### BR-C002 — Capacity range 0–9

| | |
|---|---|
| Statement | See BR-020: the one-character status field limits free places to nine. |
| Rule class | Derivation (data semantics) |
| Source | `SunnyIslands/Natural-Libraries/CRUISE16/Local Data Areas/NCDATA-L.NSL:24` |
| Message code(s) | none |
| Confidence | 0.50 (S) |
| HCM analog | Headcount attribute range |
| Decision needed | Is nine a business limit (small-vessel capacity) or a sample artifact? Sizes REQ-D-001 |

### BR-C003 — A blank identifier can match a customer with a blank e-mail

| | |
|---|---|
| Statement | A blank login identifier is not numeric, so the e-mail path runs and compares each customer's primary e-mail with a blank; a customer record with no e-mail would be returned as the logged-in customer. |
| Rule class | Lookup (data-dependent defect) |
| Source | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CUGET-N.NSN:68-74` |
| Message code(s) | 0 on such a match |
| Confidence | 0.40 (S+R) — depends on whether blank e-mails exist in the data |
| HCM analog | Alternate-key search must require a non-blank key |
| Decision needed | Profile e-mail completeness in the customer master (07); REQ-F-005 requires a non-blank key |

### BR-C004 — Birth-date input format differs between create and modify

| | |
|---|---|
| Statement | Create converts the birth-date input with `VAL` directly; modify first deletes dashes. Retrieval returns the date with dashes, and the adapter passes the same screen field to both services, so create receives `YYYY-MM-DD` while modify receives it dash-free. |
| Rule class | Derivation (data format) |
| Source | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CUNEW-N.NSN:54`; `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CUMOD-N.NSN:59-61`; `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CUGET-N.NSN:93`; adapter at `SunnyIslands/Natural-Libraries/RDCRUISE/Programs/RDCRUISP.NSP:617` and `SunnyIslands/Natural-Libraries/RDCRUISE/Programs/RDCRUISP.NSP:669` |
| Message code(s) | none (a `VAL` failure would follow BR-M006) |
| Confidence | 0.30 (S+N) — the outcome of `VAL` on a dashed string is inferred, not executed here |
| HCM analog | Single canonical date format on the person business object |
| Decision needed | Confirm the create path's behaviour on a Natural session; REQ-D-004 specifies one canonical format |

### BR-C005 — Destination-harbor filter is coded but never wired

| | |
|---|---|
| Statement | The list service filters on destination harbor when the input is non-blank, but the adapter never assigns that input, so the filter is unreachable from the UI adapter. |
| Rule class | Lookup (filter) |
| Source | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CRLIST-N.NSN:62-64`; `SunnyIslands/Natural-Libraries/CRUISE16/Parameter Data Areas/NCCRUL-P.NSA:12` |
| Message code(s) | none |
| Confidence | 0.90 (S+C+H) — `tests/test_source_conformance.py:109-112`; `tests/test_crlist_listing.py:41-50` exercise the service-level filter; `tests/test_disposition_analysis.py:69-75` asserts the input is never assigned |
| HCM analog | Additional search criterion |
| Decision needed | Requirement or leftover? Not carried unless an SME asks for it (05 `what-we-will-not-build.md`) |

### BR-C006 — First-name lineage is broken

| | |
|---|---|
| Statement | The adapter writes the typed first name to the Unicode field `FIRST-NAME-1`; create and modify persist `FIRST-NAME-OLD`; retrieval returns `FIRST-NAME-OLD`; the database view has `FIRST-NAME-1` commented out. The first name a user types is never stored, and the stored one is never shown. |
| Rule class | Derivation (data lineage) |
| Source | `SunnyIslands/Natural-Libraries/RDCRUISE/Programs/RDCRUISP.NSP:619`; `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CUNEW-N.NSN:48`; `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CUMOD-N.NSN:53`; `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CUGET-N.NSN:96`; `SunnyIslands/Natural-Libraries/CRUISE16/Local Data Areas/NCDATA-L.NSL:56`; `SunnyIslands/Natural-Libraries/CRUISE16/Parameter Data Areas/NCCUGE-P.NSA:19-21` and `SunnyIslands/Natural-Libraries/CRUISE16/Parameter Data Areas/NCCUGE-P.NSA:29` |
| Message code(s) | none |
| Confidence | 0.70 (S+C) — `tests/test_disposition_analysis.py:76-85` asserts the never-referenced `FIRST-NAME-2` sibling and the field-usage totals |
| HCM analog | One `FirstName` attribute on `PersonName`; both legacy columns feed the cleansing rules in 07 |
| Decision needed | Which column holds the authoritative value in the data? REQ-D-003 |

### BR-C007 — Catalogue implies functions that do not exist in the analyzed scope

| | |
|---|---|
| Statement | The catalogue carries success texts for booking modify (9801), booking shown (9803), booking purge (9804), customer list (9805), booking list (9806) and no-data texts for customers and bookings (9855, 9856), and the booking record has deposit, balance, reservation-date and cancellation-date fields, but no service in the analyzed scope implements any of these functions. |
| Rule class | Workflow (absent) |
| Source | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CAMSG-N.NSN:108-119` and `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CAMSG-N.NSN:120-131`; `SunnyIslands/Natural-Libraries/CRUISE16/Local Data Areas/NCDATA-L.NSL:11-19` |
| Message code(s) | 9801, 9803, 9804, 9805, 9806, 9855, 9856 (all catalogued, never emitted) |
| Confidence | 0.70 (S+C) — `tests/test_disposition_analysis.py:53-68` asserts the 31/11/20 reconciliation |
| HCM analog | Standard transaction lifecycle (update, cancel, list) exists in every HCM; whether it is in scope is a business decision |
| Decision needed | Are booking change and cancellation requirements for the target, or were they never built? Recorded in 05 `what-we-will-not-build.md` pending SME |

### BR-C008 — Always-false date block in customer retrieval

| | |
|---|---|
| Statement | Retrieval starts with a mask test on a local variable that is never assigned; the block can never execute and has no observable effect. |
| Rule class | Derivation (never-executing statement candidate) |
| Source | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CUGET-N.NSN:26-34` |
| Message code(s) | none |
| Confidence | 0.70 (S+C) — `tests/test_disposition_analysis.py:86-92` asserts the unused-variable and comment totals |
| HCM analog | none |
| Decision needed | None expected; listed so the SME can confirm "no intent" and it can be excluded (05 `what-we-will-not-build.md`) |

## Codes cataloged but never emitted (generated)

<!-- generated:catalog-never-emitted -->
| Code | English text | German text | Kind | Appears only in commented-out code at |
|---|---|---|---|---|
| 9801 | Travel Booking successfully modified | Reisebuchung erfolgreich geändert | success (would remap to 0) | none |
| 9803 | Travel Booking successfully shown | Reisebuchung erfolgreich angezeigt | success (would remap to 0) | none |
| 9804 | Travel Booking successfully purged | Reisebuchung erfolgreich gelöscht | success (would remap to 0) | none |
| 9805 | Customer List shown | Kundenliste angezeigt | success (would remap to 0) | none |
| 9806 | Booking List shown | Buchungsliste angezeigt | success (would remap to 0) | none |
| 9855 | no Customer Data found | keine Kundendaten gefunden | edit / information | none |
| 9856 | no Booking Data found | keine Buchungsdaten gefunden | edit / information | none |
| 9901 | Week Count missing | Eingabe Anzahl Reisewochen fehlt | edit / information | none |
| 9903 | Date of Booking missing | Eingabe Buchungsdatum fehlt | edit / information | none |
| 9911 | Year of Booking invalid (2015-2020) | Jahr für Buchung ungültig (2015-2020) | edit / information | `CONEW-N:211` |
| 9912 | invalid Date Format | ungültiges Datumsformat | edit / information | `CONEW-N:206` |
| 9913 | Year of Reservation invalid (2015-2020) | Jahr für Reservierung ungültig (2015-2020) | edit / information | `CONEW-N:199` |
| 9914 | Format Date of Reservation invalid | Format für Reservierungsdatum ungültig | edit / information | `CONEW-N:194` |
| 9915 | only 1-3 Weeks possible | Nur 1-3 Reise-Wochen möglich | edit / information | `CONEW-N:170`, `CRGET-N:93` |
| 9916 | Cruise Id not found | Reise-Nummer nicht gefunden | edit / information | `CONEW-N:186` |
| 9917 | Format of Cruise Id invalid | falsches Format für Reisenummer | edit / information | `CONEW-N:181` |
| 9919 | wrong Format for Customer Id | falsche Format für Kunden-Nummer | edit / information | `CONEW-N:174` |
| 9921 | Booking Id missing | Eingabe Buchungsnummer fehlt | edit / information | none |
| 9922 | Bookig Id not found or wrong format | Buchungsnummer nicht gefunden oder falsches Format | edit / information | none |
| 9935 | no valid data found for update | keine Daten zum Update gefunden | edit / information | none |
<!-- /generated:catalog-never-emitted -->

## Synthetic data and scope

All evidence in this file is produced from the Sunny Islands Cruise sample sources and the synthetic data in `tests/harness/fixtures.py`. No production system, production data, or FPPS source is used or required. FPPS statements are analogies to a Software AG Natural 9.x / ADABAS 8.6 estate; nothing here proposes a language rewrite.

← [Back to the directory README](README.md) · [Navigation hub](../README.md)
