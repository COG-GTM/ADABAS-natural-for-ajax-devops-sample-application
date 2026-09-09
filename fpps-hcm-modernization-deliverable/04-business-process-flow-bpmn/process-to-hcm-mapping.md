# Process-to-HCM mapping

Each legacy activity in the four process flows of [`process-flows.md`](process-flows.md) mapped to its equivalent in Oracle HCM (or an alternate HCM), with a disposition from the fixed vocabulary below. The sample facts are read from the Natural source at the cited lines; the HCM column is a design target for the SI, and the FPPS column is an analogy for a Software AG Natural 9.x / ADABAS 8.6 / z/OS 2.5 personnel-payroll estate.

| Property | Value |
|---|---|
| Maturity | Legacy column: Demonstrated (read from shipped source; the `tests/harness/` model executes the booking and customer paths today). HCM and FPPS columns: **designed** — no HCM instance and no FPPS source were used |
| Disposition vocabulary | **Standard** — delivered HCM behaviour, no configuration beyond enabling it. **Configured** — delivered feature that needs setup (validation rule, message, lookup, flexfield, approval rule, security). **Extension** — behaviour the delivered product does not offer; needs an extension mechanism (rule extension, integration, or a companion component) and an explicit business decision. **Retired** — legacy behaviour with no business intent to preserve (technical scaffolding, exercise gates, defects) |
| Generated inputs | `evidence/process-evidence.md` (events, codes, transaction boundaries); `docs/data-dictionary.md` (DDM fields). `generate_process_evidence.py --check` fails if a code emitted by any service is missing from this document or if a code here is not in the `CAMSG-N` catalog |
| Data | Synthetic only; no production access |

## Analogy carried through this document

| Sunny Islands element (fact) | Personnel-payroll analogue (FPPS analogy) | Why the SI cares |
|---|---|---|
| Book cruise (`CONEW-N`) | Personnel action or pay transaction: hold the master record, check eligibility/capacity, assign a serial identifier, store, commit or back out as one unit | The integrity properties, not the Natural statements, are the requirement |
| `CAMSG-N` message codes | Payroll validation edit catalogue (code, severity, text per language) | Each code becomes one configured validation message; the numeric-zero success convention is retired |
| DDMs `NCCUSTOMER`, `NCCRUISE`, `NCCONTRACT`, `NCYACHT` | Person, position/assignment reference data, element entry / transaction, lookup reference data | Field-level mapping feeds HCM Data Loader templates |
| Timestamp concurrency (`CUMOD-N`), record holds and MAX+1 (`CONEW-N`, `CUNEW-N`) | Pay-run integrity: no lost update on the employee record, no duplicate transaction number | Verified by acceptance tests against the platform's locking and numbering, not by porting the code |

## P1 — List cruises

| # | Legacy activity | Source | HCM equivalent | Disposition | Analogy |
|---|---|---|---|---|---|
| 1.1 | Raise `onShowAll` / `onFav1button`…`onFav4button`; clear or preset `P-STARTHARBOR` | `RDCRUISP.NSP:321-364` | Saved search / list page filter; favourite filters are user-saved searches | Standard | Payroll inquiry screen with pre-set filters |
| 1.2 | `#STUDENT` gate → 9999 | `CRLIST-N.NSN:40-43` | None — exercise toggle | Retired | Training-environment switch |
| 1.3 | Read `NCCRUISE` descending by `START-DATE` | `CRLIST-N.NSN:51` | Default sort on the list (most recent first) | Configured | Default sort of a transaction list |
| 1.4 | Skip `CRUISE-STATUS = 0` (fully booked) | `CRLIST-N.NSN:53-57` | Row-level filter: only objects with capacity are offered for selection | Configured | Only eligible positions/elements offered |
| 1.5 | Optional start-harbour / destination-harbour filters | `CRLIST-N.NSN:59-64` | List filters on two reference attributes | Standard | Filter by organisation / location |
| 1.6 | Edit dates (`YYYY-MM-DD`) and prices into display strings | `CRLIST-N.NSN:66-76` | Presentation formatting by user locale / currency settings | Standard | Locale formatting |
| 1.7 | Resolve `YACHT-NAME` from `NCYACHT` | `CRLIST-N.NSN:79-83` | Reference lookup joined on the list (value set / lookup type) | Standard | Code-to-description lookup |
| 1.8 | 9857 *no Cruise Data found*; 9807 *List of Cruises shown* (remapped to 0) | `CRLIST-N.NSN:88-93` (emits at `:90`, `:92`), `CAMSG-N.NSN:132-138` | Empty-list state and no message on success; 9857 becomes an information-level message only if the business wants one | Configured (9857) / Retired (9807) | Informational edit vs. success code |
| 1.9 | Adapter fills the result rows on `P-RSPCODE = '0'` (capped at 30 rows), otherwise shows code + text in the status line | `RDCRUISP.NSP:767-794` | Page-level message region | Standard | Screen message line |

## P2 — Cruise detail

| # | Legacy activity | Source | HCM equivalent | Disposition | Analogy |
|---|---|---|---|---|---|
| 2.1 | Raise `onShowdetails1`…`4` / `lines.onpvLineClick`; convert selected id with `VAL` | `RDCRUISP.NSP:367-415`, `:703-746` | Drill from list row to object detail page | Standard | Drill-down from inquiry to record |
| 2.2 | `READ (1) NCCRUISE BY CRUISE-ID = P-SELCRUISEID` | `CRGET-N.NSN:49` | Fetch by primary key | Standard | Record fetch by key |
| 2.3 | Copy cruise fields, edit dates and the three prices | `CRGET-N.NSN:55-71` | Detail page fields | Standard | — |
| 2.4 | Select the displayed price by duration (7 / 14 / 21 days); the `NONE` branch defaults to the two-week price and the 9915 *only 1-3 Weeks possible* emit is a comment | `CRGET-N.NSN:73-96` (emit comment at `:93`) | Derived rate by duration is a configured calculation; the 1–3-week duration rule needs a business decision before it exists in HCM | Configured (derivation) / Extension or Retired (duration edit) | Inactive validation candidate |
| 2.5 | Resolve yacht details and picture (`YACHT-PICTURE`, `MAKEURL`) | `CRGET-N.NSN:100-108`, `RDCRUISP.NSP:730-736` | Attachment / image on the reference object | Standard | Document attachment |
| 2.6 | 9934 when no record was read (*Customer changed from another user* text misapplied to *cruise not found*) | `CRGET-N.NSN:114-119` (emit at `:116`), `CAMSG-N.NSN:174-176` | Object-not-found handling with a correct message; the legacy text is **not** carried over. Candidate: `READ (1) … BY` on a missing key returns the next higher key rather than no record — runtime/SME confirmation needed | Configured (message) / Retired (text mismatch) | Message-catalog defect |
| 2.7 | Six `CALLNAT 'IMG-LOAD'` lines are comments; `onCrdetClose` `IGNORE` | `RDCRUISP.NSP:85-91`, `:418-426` | None — presentation scaffolding | Retired | UI plumbing without a business rule |

## P3 — Customer lookup, create, modify

| # | Legacy activity | Source | HCM equivalent | Disposition | Analogy |
|---|---|---|---|---|---|
| 3.1 | Login: `PVLOGINIDENT` compressed into `P-PERSON-ID`; no password check in executable scope | `RDCRUISP.NSP:493-494`, `:514` | Platform authentication and person search; the legacy "login" is a lookup, not authentication | Retired (as authentication) / Standard (person search) | Employee self-service sign-on |
| 3.2 | `P-COM.P-USER` / `P-PASSWORD` declared in the service interface, never assigned or read in analyzed scope | `NCCOMM-P.NSA:9-12`; only `P-LANG` is referenced (`CRLIST-N.NSN:37`, `CRGET-N.NSN:44`, `CUGET-N.NSN:44`, `CUNEW-N.NSN:31`, `CUMOD-N.NSN:32`, `CONEW-N.NSN:44`) | Not carried into HCM security; credentials never travel in a service payload | Retired | Legacy interface contract, not a security design |
| 3.3 | `#STUDENT` gates → 9999 | `CUGET-N.NSN:50-52`, `CUMOD-N.NSN:35-37`, `CUNEW-N.NSN:34-37` | None | Retired | Training switch |
| 3.4 | Numeric id → `FIND NCCUSTOMER WITH PERSON-ID`; otherwise `READ NCCUSTOMER` comparing `EMAIL(1)` | `CUGET-N.NSN:56-80` | Person search by person number or by work e-mail (indexed search, not a file scan) | Standard | Employee lookup by id or e-mail |
| 3.5 | 9924 *Customer Id not found*; 9923 *Customer Id missing* (returned when e-mail scan fails) | `CUGET-N.NSN:61`, `:76`, `CAMSG-N.NSN:170-172` | Two distinct messages: required-field and not-found; 9923's misuse for "e-mail not found" is corrected in the message design | Configured | Validation-edit catalogue |
| 3.6 | Copy `FIRST-NAME-OLD`, `TIMESTAMP` into the response | `CUGET-N.NSN:88-104` | Person name fields, plus the platform's own object version | Standard | — |
| 3.7 | Modify: `FIND (1) NCCUSTOMER WITH PERSON-ID`, compare `TIMESTAMP` to `P-TIMESTAMP`, `UPDATE`, `END TRANSACTION`; 9924 when the record is gone, 9934 on mismatch | `CUMOD-N.NSN:43-69` (emits at `:46`, `:67`) | Optimistic locking of the person record by the platform (object version number); the user sees a "record changed by another user" message | Standard | No lost update on the employee record |
| 3.8 | Create: `READ (1) NCCUSTOMER DESCENDING BY PERSON-ID`, `UPDATE` (fake update to hold), `PERSON-ID := MAX+1`, `STORE`, `END TRANSACTION` | `CUNEW-N.NSN:40-58` | Person number generation by the application's numbering (automatic, gap-tolerant) | Standard | Unique employee number |
| 3.9 | Create with an empty file: `READ (1)` loop body never runs, service returns '0' without a `STORE` | `CUNEW-N.NSN:41-58` (loop structure) | Impossible in HCM (numbering does not depend on an existing row); acceptance test on an empty target confirms | Retired (candidate defect) | Edge case of MAX+1 numbering |
| 3.10 | Page writes `FIRST-NAME-1` (U40), services persist/read `FIRST-NAME-OLD` (A20) | `RDCRUISP.NSP:619`, `:663`; `CUNEW-N.NSN:48`; `CUMOD-N.NSN:53`; `CUGET-N.NSN:96`; `NCDATA-L.NSL:56`; `docs/data-dictionary.md` § NCCUSTOMER | One person first-name attribute; the two legacy columns are reconciled in cleansing before load (rule: prefer `FIRST-NAME-1` when populated, else `FIRST-NAME-OLD`; report conflicts) | Configured (data-load mapping) | Data-cleansing defect |
| 3.11 | `ON ERROR` in create/modify: log, `ESCAPE ROUTINE`, no explicit `BACKOUT TRANSACTION` | `CUNEW-N.NSN:24-27`, `CUMOD-N.NSN:25-28` | Platform rollback on error is implicit; nothing to configure, but the acceptance test must include a failed save | Standard | Abend leaves master file unchanged |
| 3.12 | Adapter copies customer into GDA, toggles icons, restores old values on failed modify | `RDCRUISP.NSP:515-556`, `:626-656` | Page state managed by the application | Standard | — |
| 3.13 | `onCloseMydata` `IGNORE`; `onMydataClose`, `onLoginClose`, `onLogouticon` visibility only | `RDCRUISP.NSP:261-264`, and *UI state only* rows in `evidence/process-evidence.md` | None | Retired | Presentation scaffolding |

## P4 — Book cruise

| # | Legacy activity | Source | HCM equivalent | Disposition | Analogy |
|---|---|---|---|---|---|
| 4.1 | `G-LOGGEDIN` check in the adapter; login text shown otherwise | `RDCRUISP.NSP:575`, `:592-597` | Role-based access to the transaction page | Standard | Only an authorised user starts the action |
| 4.2 | Build `P-CONTRACT-DATA` from GDA customer and displayed cruise | `RDCRUISP.NSP:577-579` | Transaction defaults from context (person, referenced object) | Standard | Action pre-filled from the employee record |
| 4.3 | `#STUDENT` gate → 9999 | `CONEW-N.NSN:48-50` | None | Retired | Training switch |
| 4.4 | Customer id blank/zero → 9904; cruise id blank/zero → 9905 | `CONEW-N.NSN:55-58` | Required-field rules with configured messages | Configured | Mandatory-field edits |
| 4.5 | `IS (N8)` format edits → 9905 / 9904 (cataloged 9917 / 9919 only in comments) | `CONEW-N.NSN:60-71` (emits at `:64`, `:70`), `:174`, `:181` | Data-type enforcement on the key fields; a distinct format message if the business wants one | Configured | Format edits |
| 4.6 | `FIND NCCRUISE WITH CRUISE-ID`; body skipped when no match → code 0 without a stored contract (9916 emitted only in comments) | `CONEW-N.NSN:80-139`, `:184-188`, `NCDATA-L.NSL:78` | Referential integrity: saving a transaction against a missing object fails with an error | Retired (candidate defect) | Referenced record must exist |
| 4.7 | `GET NCCRUISE *ISN(R1.)` — hold the cruise record | `CONEW-N.NSN:82` | Platform record lock during save | Standard | Hold the master record |
| 4.8 | Availability test on the held record → 9902 *Cruise no longer available*, `BACKOUT` | `CONEW-N.NSN:86`, `:133-136` | Capacity/eligibility rule evaluated at submit and, if required, re-evaluated at approval | Configured (rule) / Extension (data outside the transaction) | Position/headcount check on current data |
| 4.9 | Decrement `CRUISE-STATUS`, `UPDATE` | `CONEW-N.NSN:90-92` | Derived attribute maintained by the transaction (or computed from open transactions) | Standard or Configured | Encumbrance update |
| 4.10 | `READ (1) NCCONTRACT DESCENDING BY CONTRACT-ID`, fake `UPDATE`, `CONTRACT-ID := MAX+1` | `CONEW-N.NSN:95-102` | Application-generated document number | Standard | Unique transaction number |
| 4.11 | Empty contract file (`LOCAL-NEWCONTRACTID = 0`) → 9902, `BACKOUT` | `CONEW-N.NSN:126-131` | Not applicable (numbering independent of existing rows); message text misapplied in legacy | Retired (candidate defect) | — |
| 4.12 | `HANDLE-INPUT-DATA`: customer exists? → 9918 *Customer Id not found*, `BACKOUT` | `CONEW-N.NSN:112`, `:151-162`, `:120-123` | Person must exist and be in scope before the transaction opens; becomes a page precondition | Standard (ordering changes) | Employee must exist |
| 4.13 | Fill contract fields (price, booking date, ids) | `CONEW-N.NSN:103-110` | Transaction attributes; effective dates are the application's | Standard | Effective-dated transaction |
| 4.14 | Cataloged date edits 9911–9914 are comment-only; 2015–2020 year ranges are expired | `CONEW-N.NSN:192-213`, `CAMSG-N.NSN:148-157` | Date validity is a delivered rule; the hard-coded year range is not carried over | Retired (expired candidate) | Time-bound edit past its window |
| 4.15 | `STORE NCCONTRACT`, `END TRANSACTION`, 9800 *Travel Booking successful* (set at `:153`, remapped to 0) | `CONEW-N.NSN:114-118` | Transaction save; submit to the approval flow; confirmation notification instead of a success code | Standard | Committed personnel/pay transaction |
| 4.16 | `BACKOUT TRANSACTION` on any failed edit inside the scope | `CONEW-N.NSN:122`, `:129`, `:134` | Rollback of the save; for approved-then-withdrawn cases, the approval flow's withdraw/reject outcome | Standard (approval flow) | Rejected transaction, no partial change |
| 4.17 | `ON ERROR`: log, `BACKOUT TRANSACTION`, `ESCAPE ROUTINE`; adapter shows stale code/text | `CONEW-N.NSN:36-40`, `RDCRUISP.NSP:584-590` | Platform error handling; generic user message, detail in the log | Standard | Abend handling |
| 4.18 | `CAMSG-N` translates code → text per `P-LANG`; remaps 9800/9807 to 0 | `CAMSG-N.NSN:17-99`, `:101-183`, `:185-186` | Message dictionary with severity and translations | Configured | Validation-edit catalogue |
| 4.19 | Adapter shows contract id or code + text in the detail panel; `onBookingClose` hides the panel | `RDCRUISP.NSP:584-590`, `:232-238` | Transaction Console status and notifications | Standard | — |

## DDM to HCM data-object mapping

Field names, formats and descriptor flags come from `docs/data-dictionary.md` (generated from the DDM sources). Target objects are named at the level an HCM Data Loader template is chosen; attribute-level mapping is the SI's next step.

| DDM (file) | Fields used by the four processes | HCM data object (Oracle HCM naming; alternate HCM equivalent in brackets) | Disposition | Notes |
|---|---|---|---|---|
| `NCCUSTOMER` (person) | `PERSON-ID` (N8, descriptor), `SURNAME` (A20), `FIRST-NAME-OLD` (A20), `FIRST-NAME-1` (U40), `BIRTH-DATE` (N8), `EMAIL(1)` (A20, multiple-value), `STREET-NUMBER`, `ZIP-CODE`, `CITY`, `COUNTRY`, `TIMESTAMP` (B8) | Worker / Person: person number, names, date of birth, e-mail, address [person master] | Standard | Two first-name columns reconciled in cleansing (row 3.10); `TIMESTAMP` is replaced by the platform's object version; `EMAIL` occurrence 1 only is used |
| `NCCRUISE` (offer) | `CRUISE-ID` (N8, descriptor), `CRUISE-STATUS` (A1, free places), `START-DATE`, `END-DATE`, `START-HARBOR`, `DESTINATION-HARBOR` (A20, descriptors), `ID-YACHT`, `PRICE-1W/2W/3W` (P10.3) | Reference object the transaction points at: position / job requisition with headcount [assignment reference]; prices as rate values | Configured | `CRUISE-STATUS` as a one-character counter is a legacy encoding; the target keeps a numeric capacity or derives it |
| `NCCONTRACT` (transaction) | `CONTRACT-ID` (P6, descriptor), `ID-CUSTOMER` (N8), `ID-CRUISE` (N8), `DATE-RESERVATION`, `DATE-BOOKING`, `PRICE` | Personnel action / element entry / absence-style transaction with effective dates [pay transaction] | Standard | Serial `CONTRACT-ID` becomes the application's transaction identifier; `DATE-CANCELLATION`, `DEPOSIT`, `PAYMENT-OF-BALANCE`, `DID-CONDITIONS` are declared but never assigned in analyzed scope (candidates, see capability 10) |
| `NCYACHT` / `YACHT-PICTURE` (reference) | `YACHT-ID`, `YACHT-NAME`, `YACHT-TYPE`, `PICTURE` (LOB) | Lookup type / reference data with attachment | Standard | Descriptive only; no rule depends on it |

## Message codes to HCM validation rules

Only codes emitted on executable lines are mapped as rules; comment-only codes are listed as candidates. Texts are the English `CAMSG-N` entries.

| Code | Text (EN) | Emitted by | HCM rule | Severity | Disposition |
|---|---|---|---|---|---|
| 9800 | Travel Booking successful | `CONEW-N.NSN:153` | None — success is a saved transaction and a notification | — | Retired |
| 9807 | List of Cruises shown | `CRLIST-N.NSN:92` | None | — | Retired |
| 9857 | no Cruise Data found | `CRLIST-N.NSN:90` | Empty-result information message | Information | Configured |
| 9902 | Cruise no longer available | `CONEW-N.NSN:130`, `:136` | Capacity rule at submit (and re-check at approval) | Error | Configured / Extension |
| 9904 | Customer Id missing | `CONEW-N.NSN:56`, `:70` | Required field / data type on person reference | Error | Configured |
| 9905 | Cruise Id missing | `CONEW-N.NSN:58`, `:64` | Required field / data type on object reference | Error | Configured |
| 9918 | Customer Id not found | `CONEW-N.NSN:159` | Person existence — page precondition | Error | Standard |
| 9923 | Customer Id missing | `CUGET-N.NSN:76` | Required field (its legacy use for "e-mail not found" is corrected) | Error | Configured |
| 9924 | Customer Id not found | `CUGET-N.NSN:61`, `CUMOD-N.NSN:46` | Person search: no match; person deleted before modify | Error | Standard |
| 9934 | Customer changed from another user | `CUMOD-N.NSN:67`; also `CRGET-N.NSN:116` for cruise-not-found | Optimistic-lock conflict message (person); a separate not-found message for the object | Error | Standard (lock) / Configured (message split) |
| 9999 | Function not yet supported | `CRLIST-N.NSN:43`, `CUGET-N.NSN:52`, `CUNEW-N.NSN:37`, `CUMOD-N.NSN:37`, `CONEW-N.NSN:50` (`#STUDENT`; `CRGET-N` has no gate) | None | — | Retired |
| 9911–9917, 9919 | date-format / year-range / id-format / cruise-not-found texts | comment lines only (`evidence/process-evidence.md` § *Commented-out message emits*) | Candidate rules; year ranges 2015–2020 are expired | — | Extension (if wanted) / Retired |

## Presentation-only and inactive elements

| Element | Evidence | Disposition | Reason |
|---|---|---|---|
| Language switch events `onSeten`, `onSetge`, `onSetpo`, `onSetsp` | `RDCRUISP.NSP:271-319`; 4 branches classified *language switch* by the generator | Standard | Session language is a platform preference; `P-LANG` on every service call disappears |
| UI state only events (10 branches) | generator classification *UI state only* | Retired | Panel visibility is owned by the target application |
| `nat:page.end`, `onFacebook`, `onTwitter` | generator: *handled in adapter, neither declared in UI nor in the menu* | Retired | Framework lifecycle / social links without business effect |
| `onCloseMydata`, `onCrdetClose` (`IGNORE`) | `RDCRUISP.NSP:261-264`, `:418-426` | Retired | Ignored events |
| `onExit` (`TERMINATE`) | `RDCRUISP.NSP:429-432` | Standard | Sign-out |
| `IMG-LOAD` (6 commented `CALLNAT`s) | `RDCRUISP.NSP:85-91` | Retired | Presentation-only content infrastructure, unreferenced in executable scope |
| `#STUDENT` gates | six services | Retired | Exercise toggles |
| Commented validation candidates (rows 2.4, 4.5, 4.6, 4.14) | `evidence/process-evidence.md` § *Commented-out message emits* | Decision required | Each is an intent the original authors wrote down and disabled; the SI takes them to the business owner |

## Synthetic data and scope

Legacy facts are read from the public Sunny Islands Cruise sample as shipped in this repository, with synthetic test data in `tests/harness/`. No production system, FPPS source or credential was accessed. HCM equivalents are design targets to be confirmed against the product documentation and a configured instance; the FPPS analogy column describes a Natural 9.x / ADABAS 8.6 estate by analogy only.

← [`process-flows.md`](process-flows.md) · [`bpmn/import-notes.md`](bpmn/import-notes.md) · [Capability README](README.md) · [Navigation hub](../README.md)
