# Rule traceability matrix

One row per rule in [`business-rules.md`](business-rules.md): the source lines that implement it, the message code(s) it emits, the existing test in `tests/` that exercises it, and the requirement in [`../05-requirements-baseline/requirements-baseline.md`](../05-requirements-baseline/requirements-baseline.md) that carries it forward. `generate_rule_evidence.py --check` fails if a rule identifier appears here without a definition (or vice versa), if a requirement identifier is not defined in 05, or if any cited line range is outside its file.

Maturity: rows whose test column names a file in `tests/` are Demonstrated (the test runs in this repository). Rows marked "harness needed" are Designed — the acceptance criterion is written in 05 but no executable check exists yet.

Column key: S = static citation, C = conformance test, H = harness execution, D = repository documentation.

## Active rules

| Rule | Source lines | Code(s) | Existing test | Requirement(s) | Disposition |
|---|---|---|---|---|---|
| BR-001 Customer identifier required | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:54-56` | 9904 | `tests/test_conew_booking.py:66-73`; `tests/test_source_conformance.py:86-89` | REQ-F-003, REQ-X-002 | replace-with-standard-HCM |
| BR-002 Offering identifier required | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:57-58` | 9905 | `tests/test_conew_booking.py:75-82`; `tests/test_source_conformance.py:86-89` | REQ-F-003, REQ-X-002 | replace-with-standard-HCM |
| BR-003 Edits fire one at a time, customer first | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:54-59` | 9904 then 9905 | `tests/test_conew_booking.py:84-90` | REQ-F-003 | redesign |
| BR-004 Offering identifier numeric N8 | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:60-65` | 9905 | `tests/test_conew_booking.py:92-98` | REQ-F-003, REQ-X-002 | replace-with-standard-HCM |
| BR-005 Customer identifier numeric, fall-through | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:66-71` | 9904 set, 9918 returned | `tests/test_conew_booking.py:100-108` | REQ-F-003, REQ-X-002 | redesign |
| BR-006 Test-and-set on held offering record | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:79-92`, `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:133-138` | 9902 | `tests/test_concurrency.py:24-45` (defect), `tests/test_concurrency.py:68-97` (fix); `tests/test_source_conformance.py:35-43` | REQ-I-001, REQ-N-002 | carry |
| BR-007 MAX+1 booking identifier under hold | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:95-102` | none | `tests/test_concurrency.py:46-66` (defect), `tests/test_concurrency.py:99-127` (fix); `tests/test_source_conformance.py:45-53` | REQ-I-002, REQ-D-002, REQ-N-002 | replace-with-standard-HCM (carry uniqueness) |
| BR-008 Price is the one-week price | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:103` | none | `tests/test_conew_booking.py:42-50` | REQ-F-003, REQ-D-002 | SME-required |
| BR-009 Booking date is system date | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:105-106` | none | harness needed (date is a parameter in `tests/harness/natural_model.py:172-173`) | REQ-D-002 | replace-with-standard-HCM |
| BR-010 Customer must exist; backout otherwise | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:112-123`, `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:151-162` | 9918 | `tests/test_conew_booking.py:165-175`, `tests/test_conew_booking.py:132-140` | REQ-I-007, REQ-F-003 | replace-with-standard-HCM (carry rollback) |
| BR-011 Booking is all-or-nothing | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:114-123` | 9800 → 0 | `tests/test_conew_booking.py:200-210`; `tests/test_source_conformance.py:55-61` | REQ-I-003 | carry |
| BR-012 Outcome as code + typed text | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:143-146` | all | `tests/test_conew_booking.py:18-25`; `tests/test_source_conformance.py:120-123` | REQ-X-001, REQ-F-007 | replace-with-standard-HCM |
| BR-013 Empty booking file guard | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:126-131` | 9902 | `tests/test_conew_booking.py:185-198`; `tests/test_source_conformance.py:75-84` | REQ-I-003 | retire |
| BR-014 Only offerings with free places listed | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CRLIST-N.NSN:51-57` | none | `tests/test_crlist_listing.py:10-15`, `tests/test_crlist_listing.py:71-77` | REQ-F-001 | replace-with-standard-HCM |
| BR-015 Optional start-harbor filter | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CRLIST-N.NSN:59-61` | none | `tests/test_crlist_listing.py:36-39` | REQ-F-001, REQ-X-003 | replace-with-standard-HCM |
| BR-016 Newest start date first | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CRLIST-N.NSN:51` | none | `tests/test_crlist_listing.py:17-21`; `tests/test_source_conformance.py:106-107` | REQ-F-001 | replace-with-standard-HCM |
| BR-017 Vessel name lookup | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CRLIST-N.NSN:79-83` | none | `tests/test_crlist_listing.py:65-69` | REQ-F-001 | replace-with-standard-HCM |
| BR-018 Service-side formatting | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CRLIST-N.NSN:72-76` | none | `tests/test_crlist_listing.py:52-63` | REQ-X-003 | retire |
| BR-019 9857 empty / 9807 → 0 | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CRLIST-N.NSN:88-93` | 9857, 9807 | `tests/test_crlist_listing.py:23-34` | REQ-F-001, REQ-F-007 | replace-with-standard-HCM |
| BR-020 Free places as one numeric character | `SunnyIslands/Natural-Libraries/CRUISE16/Local Data Areas/NCDATA-L.NSL:24` | none | `tests/test_conew_booking.py:150-161` | REQ-D-001 | SME-required |
| BR-021 Price by duration band | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CRGET-N.NSN:75-95` | none | `tests/test_crlist_listing.py:80-101` | REQ-F-002 | SME-required |
| BR-022 Detail read without availability filter | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CRGET-N.NSN:47-52` | 9934 on not found | harness needed | REQ-F-002 | replace-with-standard-HCM |
| BR-023 Retrieval by numeric identifier | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CUGET-N.NSN:56-67` | 9924 | harness needed | REQ-F-005, REQ-D-005 | replace-with-standard-HCM |
| BR-024 Retrieval by e-mail | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CUGET-N.NSN:68-78` | 9923 | harness needed | REQ-F-005, REQ-D-005 | replace-with-standard-HCM |
| BR-025 Login without credential check | `SunnyIslands/Natural-Libraries/RDCRUISE/Programs/RDCRUISP.NSP:514-528` | 9923/9924 | `tests/test_disposition_analysis.py:69-75` (never-assigned credential fields) | REQ-N-004 | replace-with-standard-HCM |
| BR-026 Customer data returned | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CUGET-N.NSN:88-104` | none | harness needed | REQ-X-004, REQ-D-003, REQ-D-006 | redesign |
| BR-027 MAX+1 customer identifier under hold | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CUNEW-N.NSN:41-44` | none | `tests/test_source_conformance.py:91-95` (idiom); harness needed for execution | REQ-I-005, REQ-F-004 | replace-with-standard-HCM (carry uniqueness) |
| BR-028 New customer content and commit | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CUNEW-N.NSN:46-57` | 0 | harness needed | REQ-F-004, REQ-D-004 | replace-with-standard-HCM |
| BR-029 Modify requires existing customer | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CUMOD-N.NSN:41-48` | 9924 | harness needed | REQ-F-006 | replace-with-standard-HCM |
| BR-030 Success without catalogue code | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CAMSG-N.NSN:180-189` | 0 | harness needed | REQ-F-007, REQ-X-001 | replace-with-standard-HCM |
| BR-031 Modify field set and timestamp refresh | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CUMOD-N.NSN:53-64` | 0 | harness needed | REQ-F-006, REQ-D-006, REQ-D-004 | replace-with-standard-HCM |
| BR-032 Optimistic version check | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CUMOD-N.NSN:50-52`, `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CUMOD-N.NSN:65-68` | 9934 | harness needed | REQ-I-004, REQ-D-006, REQ-F-006, REQ-X-004, REQ-N-002 | carry |
| BR-033 Language selection, English only reachable | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CAMSG-N.NSN:17-19`, `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CAMSG-N.NSN:101-102` | all | `tests/test_disposition_analysis.py:69-75` | REQ-N-001 | SME-required |
| BR-034 Success codes → 0, type S | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CAMSG-N.NSN:104-106`, `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CAMSG-N.NSN:185-189` | success set → 0 | `tests/test_source_conformance.py:120-123`; `tests/test_crlist_listing.py:23-27` | REQ-X-001, REQ-F-007 | replace-with-standard-HCM |
| BR-035 Unknown codes pass through | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CAMSG-N.NSN:180-183` | any | harness needed | REQ-F-007 | replace-with-standard-HCM |
| BR-036 Training gate 9999 | `SunnyIslands/Natural-Libraries/CRUISE16/Local Data Areas/NCDATA-L.NSL:86` | 9999 | `tests/test_source_conformance.py:25-28` | REQ-N-005 (gate excluded from the harness); 05 `what-we-will-not-build.md` E-07 | retire |

## Commented-out and disabled rules

| Rule | Source lines | Code(s) | Existing test | Requirement(s) | Disposition |
|---|---|---|---|---|---|
| BR-D001 Week count 1–3 selects price | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:168-171`, `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:216-225` | 9915 | `tests/test_disposition_analysis.py:53-68` (never emitted) | REQ-F-003, REQ-X-002 (SME decision) | SME-required |
| BR-D002 Customer format under 9919 | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:173-176` | 9919 | `tests/test_disposition_analysis.py:53-68` | superseded by BR-005 | retire |
| BR-D003 Offering format under 9917 | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:180-183` | 9917 | `tests/test_disposition_analysis.py:53-68` | superseded by BR-004 | retire |
| BR-D004 Offering must exist | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:184-190` | 9916 | `tests/test_conew_booking.py:177-183` (shows the gap) | REQ-F-003 | carry intent |
| BR-D005 Reservation date format | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:192-196` | 9914 | `tests/test_disposition_analysis.py:69-75` (input never assigned) | REQ-D-002, REQ-X-002 (recorded as excluded); 05 `what-we-will-not-build.md` E-04 | retire |
| BR-D006 Reservation year 2015–2020 | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:197-202` | 9913 | none | REQ-D-002 (recorded as excluded); E-04 | retire |
| BR-D007 Booking date format | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:204-208` | 9912 | `tests/test_disposition_analysis.py:69-75` | REQ-D-002, REQ-X-002 (recorded as excluded); E-04 | retire |
| BR-D008 Booking year 2015–2020 | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:209-214` | 9911 | none | REQ-D-002 (recorded as excluded); E-04 | retire |
| BR-D009 Non-standard duration edit | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CRGET-N.NSN:92-94` | 9915 | `tests/test_crlist_listing.py:97-101` (shows the silent fallback) | REQ-F-002 (SME decision) | SME-required |
| BR-D010 Preset 9800 in disabled chain | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:164` | 9800 | none | REQ-F-007 (recorded as superseded by the active preset BR-011) | retire |

## Misapplied codes and silent outcomes

| Rule | Source lines | Code(s) | Existing test | Requirement(s) | Disposition |
|---|---|---|---|---|---|
| BR-M001 Detail not-found reports 9934 | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CRGET-N.NSN:114-119` | 9934 | harness needed | REQ-F-002, REQ-I-006 | redesign |
| BR-M002 E-mail not-found reports 9923 | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CUGET-N.NSN:75-77` | 9923 | harness needed | REQ-F-005 | redesign |
| BR-M003 Empty booking file reported as 9902 | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:126-131` | 9902 | `tests/test_conew_booking.py:185-198` | REQ-I-003 | retire |
| BR-M004 Format error reported as 9918 | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:66-71` | 9904/9918 | `tests/test_conew_booking.py:100-108` | REQ-F-003 | redesign |
| BR-M005 Unknown offering returns 0 | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:79-80`, `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN:139-146` | 0 | `tests/test_conew_booking.py:177-183` (identifier 0; response code not asserted — harness extension needed) | REQ-F-003, REQ-I-006 | redesign |
| BR-M006 Runtime error reported as success | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CRLIST-N.NSN:48`, `SunnyIslands/Natural-Libraries/CRUISE16/Copycodes/ERRLOG-I.NSC:8-21` | 0 | harness needed (fault injection) | REQ-I-006, REQ-N-003 | replace-with-standard-HCM |

## Candidate rules needing SME confirmation

| Rule | Source lines | Code(s) | Existing test | Requirement(s) | Disposition |
|---|---|---|---|---|---|
| BR-C001 Detail read uses start value | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CRGET-N.NSN:49-52` | 9934 | harness needed (Natural session) | REQ-F-002 | SME-required |
| BR-C002 Capacity range 0–9 | `SunnyIslands/Natural-Libraries/CRUISE16/Local Data Areas/NCDATA-L.NSL:24` | none | `tests/test_conew_booking.py:150-161` | REQ-D-001 | SME-required |
| BR-C003 Blank identifier matches blank e-mail | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CUGET-N.NSN:68-74` | 0 | harness needed | REQ-F-005 | SME-required |
| BR-C004 Birth-date format differs create vs modify | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CUNEW-N.NSN:54`, `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CUMOD-N.NSN:59-61` | none | harness needed | REQ-D-004, REQ-F-004 | SME-required |
| BR-C005 Destination filter never wired | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CRLIST-N.NSN:62-64` | none | `tests/test_crlist_listing.py:41-50` (service level); `tests/test_disposition_analysis.py:69-75` (never assigned) | REQ-F-001, REQ-X-003 (excluded unless SME asks) | SME-required |
| BR-C006 First-name lineage broken | `SunnyIslands/Natural-Libraries/RDCRUISE/Programs/RDCRUISP.NSP:619`, `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CUGET-N.NSN:96` | none | `tests/test_disposition_analysis.py:76-85` | REQ-D-003, REQ-F-004 | SME-required |
| BR-C007 Catalogue implies absent functions | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CAMSG-N.NSN:108-131` | 9801, 9803–9806, 9855, 9856 | `tests/test_disposition_analysis.py:53-68` | excluded pending SME — 05 `what-we-will-not-build.md` | SME-required |
| BR-C008 Always-false date block | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CUGET-N.NSN:26-34` | none | `tests/test_disposition_analysis.py:86-92` | REQ-F-005 (recorded as never executing) | retire |

## Message code ↔ test coverage (generated)

Every emitted code, the services that emit it, and the test modules whose lines mention it. "none (harness needed)" marks a code with no executable check today.

<!-- generated:code-test-coverage -->
| Code | Emitting service(s) | Test modules referencing the code (line hits) | Behavioural model referencing the code |
|---|---|---|---|
| 9800 | `CONEW-N` | `tests/test_concurrency.py` (8), `tests/test_conew_booking.py` (3), `tests/test_source_conformance.py` (1) | `tests/harness/natural_model.py` (4) |
| 9807 | `CRLIST-N` | `tests/test_crlist_listing.py` (2), `tests/test_source_conformance.py` (1) | `tests/harness/natural_model.py` (3) |
| 9857 | `CRLIST-N` | `tests/test_crlist_listing.py` (3), `tests/test_source_conformance.py` (1) | `tests/harness/natural_model.py` (2) |
| 9902 | `CONEW-N` | `tests/test_concurrency.py` (4), `tests/test_conew_booking.py` (11), `tests/test_source_conformance.py` (7) | `tests/harness/natural_model.py` (3) |
| 9904 | `CONEW-N` | `tests/test_conew_booking.py` (6), `tests/test_source_conformance.py` (1) | `tests/harness/natural_model.py` (3) |
| 9905 | `CONEW-N` | `tests/test_conew_booking.py` (5), `tests/test_source_conformance.py` (1) | `tests/harness/natural_model.py` (3) |
| 9918 | `CONEW-N` | `tests/test_conew_booking.py` (5), `tests/test_source_conformance.py` (1) | `tests/harness/natural_model.py` (3) |
| 9923 | `CUGET-N` | none (harness needed) | none |
| 9924 | `CUGET-N`, `CUMOD-N` | none (harness needed) | none |
| 9934 | `CRGET-N`, `CUMOD-N` | none (harness needed) | none |
| 9999 | `CONEW-N`, `CRLIST-N`, `CUGET-N`, `CUMOD-N`, `CUNEW-N` | `tests/test_source_conformance.py` (2) | none |
<!-- /generated:code-test-coverage -->

## Coverage summary (generated from the tables above)

<!-- generated:coverage-summary -->
| Section | Rules | Existing test cited | No executable check yet (harness needed or none) |
|---|---|---|---|
| Active rules | 36 | 24 | 12 (BR-009, BR-022, BR-023, BR-024, BR-026, BR-027, BR-028, BR-029, BR-030, BR-031, BR-032, BR-035) |
| Commented-out and disabled rules | 10 | 7 | 3 (BR-D006, BR-D008, BR-D010) |
| Misapplied codes and silent outcomes | 6 | 3 | 3 (BR-M001, BR-M002, BR-M006) |
| Candidate rules needing SME confirmation | 8 | 5 | 3 (BR-C001, BR-C003, BR-C004) |
<!-- /generated:coverage-summary -->

The harness gap is concentrated in the customer services (`CUGET-N`, `CUNEW-N`, `CUMOD-N`) and the detail read (`CRGET-N`), for which `tests/harness/natural_model.py` has no behavioural model yet. The acceptance criteria in 05 flag each one; building those models is the first Designed-to-Demonstrated step for the integrating team.

## Synthetic data and scope

Tests cited here run against the synthetic ADABAS simulation in `tests/harness/adabas_sim.py` and fixtures in `tests/harness/fixtures.py`; no production data or system is involved.

← [Back to the directory README](README.md) · [Navigation hub](../README.md)
