# What we will not build

Explicit exclusions from the requirements baseline, each with the evidence class that supports it and the line(s) an SI can open to confirm it. Treat this list as signed scope: anything here is out of the initial implementation unless an SME reopens it through the review path named in the last column. Every static finding below is a candidate produced by `tools/analyze_disposition.py` and reproduced in [`../10-migration-disposition-dead-code/evidence/disposition-evidence.md`](../10-migration-disposition-dead-code/evidence/disposition-evidence.md); the wording "unreferenced in analyzed scope", "no UI path" and "declared but never assigned" is deliberate — the analyzed scope is the 31 objects of the sample, and none of these findings is a claim about FPPS.

```
  Catalogue / interface / library            Observed behaviour              Baseline
  ───────────────────────────────            ──────────────────              ────────
  31 message codes ─────────────────────►    11 emitted ───────────────────► REQ-F-007
                                        └►   20 never emitted ────────────► this file, E-05
  NCCONW-P: 5 input fields ─────────────►    2 assigned ──────────────────► REQ-X-002
                                        └►   3 never assigned ────────────► this file, E-04
  31 Natural objects ───────────────────►    23 referenced ──────────────► REQ-F-001..007 (services) / E-02, E-06 (infrastructure)
                                        └►   7 unreferenced + 1 no UI path► this file, E-01..E-03, E-08
```

## Evidence classes

| Class | Meaning | Where produced |
|---|---|---|
| Static reachability | No `CALLNAT`/`FETCH`/`INCLUDE`/`USING` literal names the object anywhere in the analyzed libraries; zero dynamic invocations exist in the sample, so the finding is not weakened by unresolvable calls | `disposition-evidence.md`, "Object reachability from the NJX page adapter" |
| Static assignment | The field is read or declared but no statement assigns it (`MOVE`/`COMPRESS INTO`/`:=`/`RESET`) in any caller or service | `disposition-evidence.md`, "PDA interface fields: assignments vs reads" |
| Catalogue reconciliation | Code has catalogue text but no executable `MOVE nnnn TO MSG-NR` anywhere | `disposition-evidence.md`, "Message catalog reconciliation (CAMSG-N)" |
| Source marker | The author's own comment marks the item as an exercise, "not yet used" or a placeholder | `disposition-evidence.md`, "Source markers" |
| Behavioural | The item performs an action with no business audit, or reads infrastructure rather than business data | Source lines cited |

## Exclusions

### E-01 — `CA3900-N` (unreferenced subprogram)

| Field | Value |
|---|---|
| What it is | A subprogram whose whole body is `READ (1) NCCUSTOMER` / `END-READ`: it reads one customer record and returns nothing. |
| Evidence | Static reachability: no caller in analyzed scope (`../10-migration-disposition-dead-code/evidence/disposition-evidence.md`, control totals row "Objects unreferenced in analyzed scope"; `tests/test_disposition_analysis.py:38-43`). Source marker: the generated placeholder comment "Enter your code here" at `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CA3900-N.NSN:8`. Body: `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CA3900-N.NSN:15-16`. |
| Why not build | No observable behaviour to reconstruct a requirement from. |
| Linked rules | BR-C007 (the catalogue implies functions that exist nowhere; this object is the nearest candidate and does nothing) |
| Reopen if | An estate-wide reference scan finds a caller outside the analyzed libraries. |

### E-02 — `IMG-LOAD` and `MAKEURL` (picture infrastructure)

| Field | Value |
|---|---|
| What it is | `IMG-LOAD` reads a JPEG from `/opt/resources/images/CR16-<part>.jpg` through a work file and calls `MAKEURL`, which wraps binary content into a page content object with a timestamp-derived identifier. |
| Evidence | Static reachability: `IMG-LOAD` unreferenced in analyzed scope; `MAKEURL` is reachable only from `IMG-LOAD` and from the page adapter (`disposition-evidence.md`, reachability table). Source: `SunnyIslands/Natural-Libraries/RDCRUISE/Subprograms/IMG-LOAD.NSN:21-28`, `SunnyIslands/Natural-Libraries/RDCRUISE/Subprograms/MAKEURL.NSN:29-40`. Source marker: `PICTURE`/`PICTURELEN` are "exercise 11" fields at `SunnyIslands/Natural-Libraries/CRUISE16/Parameter Data Areas/NCCRUL-P.NSA:29-30`. |
| Why not build | Presentation/content plumbing of the Natural for Ajax page framework; the target HCM has its own document and image handling. No business rule depends on it. |
| Linked rules | BR-018 (display formatting inside the service — same class of presentation logic, retired with it) |
| Reopen if | The business confirms images are part of the offering master data (then it is a content-migration item under 07, not a rule). |

### E-03 — `DELETECU` (interactive physical-ISN delete)

| Field | Value |
|---|---|
| What it is | A standalone program that prompts for an ADABAS ISN on the terminal, deletes the customer record at that ISN and ends the transaction; no audit record, no business key, no confirmation. |
| Evidence | Static reachability: standalone program with no UI path (`disposition-evidence.md`, control totals row "Standalone programs with no UI path"). Behavioural: `SunnyIslands/Natural-Libraries/RDCRUISE/Programs/DELETECU.NSP:18-28`. |
| Why not build | A physical-key delete utility is not a business function; the HCM equivalent (person purge / data-retention processing) is a controlled, audited platform process. Carrying this forward would be carrying a maintenance back door. |
| Linked rules | none (no rule was extracted from it; listed so the absence is deliberate) |
| Reopen if | The business identifies a customer-deletion requirement — then it becomes a data-retention requirement written from policy, not from this program. |

### E-04 — Interface fields declared but never assigned

| Field | Value |
|---|---|
| What it is | Seven scalar fields in the service contracts that no caller or service ever assigns. |
| Evidence | Static assignment (`disposition-evidence.md`, control totals row "PDA fields never assigned anywhere"; `tests/test_disposition_analysis.py:69-75`). Declarations: `SunnyIslands/Natural-Libraries/CRUISE16/Parameter Data Areas/NCCOMM-P.NSA:9-12` (`P-LANG`, `P-USER`, `P-PASSWORD`), `SunnyIslands/Natural-Libraries/CRUISE16/Parameter Data Areas/NCCONW-P.NSA:11-13` (`WEEK-COUNT-IN`, `DATE-RESERVATION-IN`, `DATE-BOOKING-IN`, each with the author's "not yet used" marker), `SunnyIslands/Natural-Libraries/CRUISE16/Parameter Data Areas/NCCRUL-P.NSA:12` (`P-DESTHARBOR`). |
| Why not build | A field nobody populates carries no requirement. `P-LANG` would switch the German catalogue on (REQ-N-001); `P-USER`/`P-PASSWORD` would imply application-level authentication (REQ-N-004); the three booking inputs would imply the disabled edit chain 9911–9915; `P-DESTHARBOR` would imply a destination filter the page never offers (BR-C005). |
| Linked rules | BR-033, BR-025, BR-D001, BR-D002, BR-D003, BR-D005, BR-D006, BR-D007, BR-D008, BR-C005 |
| Reopen if | An SME confirms any of these inputs was live in a version of the application not in this repository. |

<!-- generated:never-assigned-pda-fields -->
| Interface field | Statement references | Reads | Static status |
|---|---|---|---|
| `NCCOMM-P.P-LANG` | 6 | 6 | declared but never assigned |
| `NCCOMM-P.P-USER` | 0 | 0 | declared but never assigned |
| `NCCOMM-P.P-PASSWORD` | 0 | 0 | declared but never assigned |
| `NCCONW-P.WEEK-COUNT-IN` | 0 | 0 | declared but never assigned |
| `NCCONW-P.DATE-RESERVATION-IN` | 0 | 0 | declared but never assigned |
| `NCCONW-P.DATE-BOOKING-IN` | 0 | 0 | declared but never assigned |
| `NCCRUL-P.P-DESTHARBOR` | 2 | 2 | declared but never assigned |
<!-- /generated:never-assigned-pda-fields -->

### E-05 — Twenty catalogued message codes that no executable statement emits

| Field | Value |
|---|---|
| What it is | The `CAMSG-N` catalogue carries 31 codes; executable code emits 11. The other 20 have text but no producer. |
| Evidence | Catalogue reconciliation (`disposition-evidence.md`, "Message catalog reconciliation (CAMSG-N)"; `tests/test_disposition_analysis.py:53-67`). Ten of the twenty appear only in commented-out statements — see the disabled-rule section of [`../02-business-rule-extraction/business-rules.md`](../02-business-rule-extraction/business-rules.md). |
| Why not build | The catalogue is not a specification. Building a validation from its text alone would be building from an intention, not from behaviour. Where a commented emit exists, the intention is recorded as a disabled rule (BR-D001–BR-D010) with an SME-required disposition; where none exists (BR-C007) there is nothing to reconstruct. |
| Linked rules | BR-D001, BR-D002, BR-D003, BR-D004, BR-D005, BR-D006, BR-D007, BR-D008, BR-D009, BR-C007 |
| Reopen if | An estate-wide scan finds a producer, or the business asks for the edit the text describes — then it is written as a new requirement, not carried. |

The table below is generated from source by `../02-business-rule-extraction/generate_rule_evidence.py`:

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

### E-06 — `RDREADWN` (home-page text loader)

| Field | Value |
|---|---|
| What it is | Reads a hard-coded Windows path to `CruiseDescriptions.txt` and concatenates records of type `HDE`/`HD1`/`HD2`/`HD3` for the requested language into home-page description strings. |
| Evidence | Behavioural: `SunnyIslands/Natural-Libraries/RDCRUISE/Subprograms/RDREADWN.NSN:34-36` (hard-coded file location with the author's "change the location" note), `SunnyIslands/Natural-Libraries/RDCRUISE/Subprograms/RDREADWN.NSN:39-50` (record-type dispatch). Reachable only from the page-initialisation program (`disposition-evidence.md`, reachability table). |
| Why not build | Static page content, not a business rule; the target's portal handles its own content. |
| Linked rules | none |
| Reopen if | Never as a rule; the text itself may be reused as content. |

### E-07 — Exercise scaffolding in `NCCRUL-P` and the training gate

| Field | Value |
|---|---|
| What it is | Fields marked "exercise 04" and "exercise 11" in the list interface (`PRICE`, `PICTURE`, `PICTURELEN`) and the `#STUDENT` flag that, when true, makes every service return 9999 "Function not yet supported". |
| Evidence | Source marker: `SunnyIslands/Natural-Libraries/CRUISE16/Parameter Data Areas/NCCRUL-P.NSA:28-30`; `SunnyIslands/Natural-Libraries/CRUISE16/Local Data Areas/NCDATA-L.NSL:86` (`#STUDENT` initialised false); gate sites listed in the generated table below. Exercise comment on the duration-price calculation: `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CRGET-N.NSN:73`. |
| Why not build | Training scaffolding of the public sample. The `PRICE` field's computation (BR-021) is kept as a requirement because it is executed; the field's presence in the interface and the picture fields are not. |
| Linked rules | BR-036, BR-018 |
| Reopen if | Never. |

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

### E-08 — Unreferenced parameter data areas

| Field | Value |
|---|---|
| What it is | `CONTPDA`, `MYPDA`, `NCCUSL-P`, `SYPDA`, `YACHTPDA` — interface definitions no object `USING`-references. |
| Evidence | Static reachability (`disposition-evidence.md`, reachability table; `tests/test_disposition_analysis.py:38-43`). Generated list below. |
| Why not build | A contract with no implementer and no caller defines no requirement. `NCCUSL-P` in particular suggests a customer-list function that was never built (BR-C007). |
| Linked rules | BR-C007 |
| Reopen if | An estate-wide scan finds a user. |

<!-- generated:unreferenced-objects -->
| Object | Type | Path | Static status |
|---|---|---|---|
| `CONTPDA` | parameter data area | `SunnyIslands/Natural-Libraries/CRUISE16/Parameter Data Areas/CONTPDA.NSA` | unreferenced in analyzed scope |
| `MYPDA` | parameter data area | `SunnyIslands/Natural-Libraries/CRUISE16/Parameter Data Areas/MYPDA.NSA` | unreferenced in analyzed scope |
| `NCCUSL-P` | parameter data area | `SunnyIslands/Natural-Libraries/CRUISE16/Parameter Data Areas/NCCUSL-P.NSA` | unreferenced in analyzed scope |
| `SYPDA` | parameter data area | `SunnyIslands/Natural-Libraries/CRUISE16/Parameter Data Areas/SYPDA.NSA` | unreferenced in analyzed scope |
| `YACHTPDA` | parameter data area | `SunnyIslands/Natural-Libraries/CRUISE16/Parameter Data Areas/YACHTPDA.NSA` | unreferenced in analyzed scope |
| `CA3900-N` | subprogram | `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CA3900-N.NSN` | unreferenced in analyzed scope |
| `DELETECU` | program | `SunnyIslands/Natural-Libraries/RDCRUISE/Programs/DELETECU.NSP` | standalone program; no UI path |
| `IMG-LOAD` | subprogram | `SunnyIslands/Natural-Libraries/RDCRUISE/Subprograms/IMG-LOAD.NSN` | unreferenced in analyzed scope |
<!-- /generated:unreferenced-objects -->

## Behaviours deliberately not reproduced

These are executed behaviours — they are Demonstrated in the sample — that the baseline replaces rather than carries. They are listed here so that a reviewer comparing the target against the sample does not file them as gaps.

| Sample behaviour | Rule | Replaced by | Why |
|---|---|---|---|
| MAX+1 identifier generation under hold (booking and customer) | BR-007, BR-027 | REQ-I-002, REQ-I-005 (platform-generated keys) | The obligation is uniqueness; the mechanism is an ADABAS idiom |
| Only the first failing edit is reported | BR-003 | REQ-F-003 | Payroll edits report all failures at once |
| Format failure on the customer identifier falls through to "not found" | BR-005, BR-M004 | REQ-F-003 | Wrong message for the condition |
| Unknown offering returns success with booking identifier 0 | BR-M005 | REQ-I-006 | Silent success |
| Detail read reports not-found as a concurrency conflict | BR-M001 | REQ-F-002, REQ-I-006 | Wrong message for the condition |
| E-mail lookup reports not-found as "identifier missing" | BR-M002 | REQ-F-005 | Wrong message for the condition |
| Empty booking file reported as "no longer available" | BR-M003, BR-013 | REQ-I-003 | Condition disappears with platform keys |
| Runtime error can be reported as success | BR-M006 | REQ-I-006, REQ-N-003 | Error handler commented out |
| Dates and prices formatted inside the service | BR-018 | REQ-X-003 | Presentation belongs to the consumer |
| Detail read by start value rather than exact key | BR-C001, BR-022 | REQ-F-002 | Returns the next record when the key is absent |
| "Login" by e-mail lookup without a credential check | BR-025 | REQ-N-004 | Authentication is the platform's |
| Customer services return success without a catalogue code | BR-030 | REQ-F-007 | One success representation |
| German catalogue branch | BR-033 | REQ-N-001 | Unreachable; decision deferred to SME |
| Unknown codes pass through untranslated | BR-035 | REQ-F-007 | Catalogue defect must be visible |
| Always-false date block in customer retrieval | BR-C008 | none | Never executes; nothing to carry |

## Synthetic data and scope

Every finding above is produced from the Sunny Islands Cruise sample sources by `tools/analyze_disposition.py` and the checks in `tests/`; no production system or production data was accessed and no FPPS source was analysed. The analogy to an FPPS-scale estate is that the same evidence classes — reachability, assignment, catalogue reconciliation, source markers — are the ones an estate-wide scan would produce, at larger counts and with dynamic invocations that this sample does not have.

← [Back to the directory README](README.md) · [Navigation hub](../README.md)
