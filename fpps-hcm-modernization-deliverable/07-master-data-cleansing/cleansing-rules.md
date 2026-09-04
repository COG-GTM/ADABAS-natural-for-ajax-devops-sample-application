# Cleansing rules: catalogue keyed to dictionary fields

Each rule is keyed to one or more `(file, field)` pairs of `../03-data-model-data-dictionary/data-dictionary-hcm.md`, which lists the rule IDs in its "Cleansing rules" column. The rules are executable: `harness/cleanse_reconcile.py` holds them as `RULES`, runs them on synthetic data and writes `harness/sample-output/`. The generated `harness/sample-output/rule-catalogue.md` is the machine view of the same catalogue; this page is the explanation. Two mechanical ties keep the three from drifting: the harness `--check` fails if the rule IDs here differ from `RULES`, and the 03 generator fails if a rule is keyed to a field the DDMs do not have.

Outcomes have a fixed meaning throughout. A record's disposition is the worst outcome any rule gave it.

| Outcome | Meaning | Loadable | Where it goes |
|---|---|---|---|
| pass | Rule satisfied | yes | Loadable set |
| correct | Value changed by a deterministic, logged correction | yes | Loadable set, exception row records the change |
| flag | Loadable in principle but needs a steward decision | not yet | Held set (steward queue) |
| reject | Not loadable as it stands | no | Rejected set (source remediation) |

Python here is a validation and cleansing harness, never a rewrite target. The rules become HDL transformation rules, HCM configuration (lookups, validation) and steward procedures; the harness proves the rules behave as written.

## Rule catalogue

| Rule | Field(s) | Category | Logic (as executed) | Default action | Payroll analog (designed) | Candidate HCM target (designed) | Source evidence |
|---|---|---|---|---|---|---|---|
| CR-01 Orphaned ID-CUSTOMER | `NCCONTRACT.ID-CUSTOMER` | referential integrity | `ID-CUSTOMER` must equal some `NCCUSTOMER.PERSON-ID` in the extract; otherwise reject | reject | Pay transaction whose employee identifier is not in the person master | Element Entry keyed to a Worker source key | Validation at booking: `CONEW-N.NSN:157-162` (message 9918); DDM remark `NCCONTRA.NSD:26-27` |
| CR-02 Orphaned ID-CRUISE | `NCCONTRACT.ID-CRUISE` | referential integrity | `ID-CRUISE` must equal some `NCCRUISE.CRUISE-ID`; otherwise reject | reject | Transaction referencing a retired element or unknown position | Element Entry referencing a Position / Element source key | Lookup at booking: `CONEW-N.NSN:79-83`; DDM remark `NCCONTRA.NSD:28-29` |
| CR-03 Orphaned ID-YACHT | `NCCRUISE.ID-YACHT` | referential integrity | `ID-YACHT` must equal some `NCYACHT.YACHT-ID`; otherwise flag (a catalogue row with a resolvable parent is held, not lost) | flag | Position whose department was merged or renamed | Position.OrganizationId / Department | Join on read: `CRLIST-N.NSN:80-83`; DDM remark `NCCRUISE.NSD:23-24` |
| CR-04 CRUISE-STATUS domain | `NCCRUISE.CRUISE-STATUS` | domain | Value must be a single character in `'0'..'9'` (the code applies `VAL` and subtracts 1); anything else, including blank, is rejected | reject | Open-headcount counter outside its coded domain | Position headcount / status lookup | Decrement under hold: `CONEW-N.NSN:82-92`; listing skips zero: `CRLIST-N.NSN:53-57`; DDM remark `NCCRUISE.NSD:13-14` |
| CR-05 SEX domain | `NCCUSTOMER.SEX` | domain | Blank → flag (target attribute needs a steward value); `'M'` / `'F'` → pass; anything else → flag | flag | Legislative or biographical code outside its lookup | PersonLegislativeData.Sex | Domain only in the DDM remark `NCCUSTOM.NSD:14-16`; read `CUGET-N.NSN:94`; never written by `CUNEW-N` / `CUMOD-N` |
| CR-06 EMAIL occurrences | `NCCUSTOMER.EMAIL` (MU) | occurrence / format | No populated occurrence → flag. Blank `EMAIL(1)` with a later occurrence populated → promoted (correct). Case-insensitive duplicates → removed (correct). Any occurrence without an address shape (`@` present, not leading or trailing) → flag. More than one distinct address after dedupe → flag, because only `EMAIL(1)` has code meaning | correct | Multiple-value contact field where only the first occurrence is used by code | PersonEmail: one row per occurrence, occurrence 1 primary | Only `EMAIL(1)` written/read: `CUNEW-N.NSN:50`, `CUMOD-N.NSN:55`, `CUGET-N.NSN:69-74`, `:97`; DDM `NCCUSTOM.NSD:24` |
| CR-07 PHONE occurrences | `NCCUSTOMER.PHONE`, `AREA-CODE`, `PHONE-NUMBER` (PE) | occurrence / format | More than 2 occurrences → flag (DDM documents private and company). Occurrence with `AREA-CODE` but no `PHONE-NUMBER` → flag. `PHONE-NUMBER` not 3-15 digits/spaces → flag | flag | Periodic group never referenced by executable code; semantics rest on the DDM remark | PersonPhone: PhoneType by occurrence position (1 home, 2 work) | DDM remark `NCCUSTOM.NSD:29-33`; unreferenced in analyzed scope (`tools/analyze_disposition.py`) |
| CR-08 ZIP-CODE format | `NCCUSTOMER.ZIP-CODE` | format | Blank with blank `COUNTRY` and `CITY` → flag "address group entirely blank"; blank with other address fields set → flag. Leading/trailing spaces → trimmed (correct). Otherwise must match an alphanumeric postal shape of 2-10 characters → else flag | correct | Postal code that fails the target country's address validation | PersonAddress.PostalCode | DDM `NCCUSTOM.NSD:27`; written `CUNEW-N.NSN:52`, `CUMOD-N.NSN:57` |
| CR-09 COUNTRY format | `NCCUSTOMER.COUNTRY` | format | Blank → flag. Exactly 3 upper-case letters → pass. 3 letters in mixed case → upper-cased (correct). Anything else → flag | correct | Country code that fails the target lookup | PersonAddress.Country (crosswalk to the target code list is a separate designed step) | DDM `NCCUSTOM.NSD:26`; read `CUGET-N.NSN:99`; never written by `CUNEW-N` / `CUMOD-N` |
| CR-10 BIRTH-DATE validity | `NCCUSTOMER.BIRTH-DATE` | validity | Blank or zero → flag. Not a calendar `YYYYMMDD` → reject. After the as-of date → reject. Implies age over 110 → flag | reject | Date of birth that is not a date, is in the future, or implies an implausible age | Worker.DateOfBirth | DDM `NCCUSTOM.NSD:13`; written `CUNEW-N.NSN:54`, `CUMOD-N.NSN:59-61`; read `CUGET-N.NSN:93` |
| CR-11 TIMESTAMP presence | `NCCUSTOMER.TIMESTAMP` | presence | Blank → flag: the source's own optimistic-lock check (`TIMESTAMP` compared before update) could not have run on the row | flag | Missing last-update audit token | Not loaded; drives extract cut-off reconciliation | DDM `NCCUSTOM.NSD:34`; set `CUNEW-N.NSN:55`, `CUMOD-N.NSN:62`; compared `CUMOD-N.NSN:50-67` |
| CR-12 Duplicate PERSON-ID | `NCCUSTOMER.PERSON-ID` | uniqueness | Blank → reject. Unique → pass. Duplicated: the lowest ISN is the survivor (flag, for steward confirmation); every later occurrence is rejected | reject | Two person-master records with the same employee identifier | Worker.SourceSystemId must be unique | Uniqueness is a MAX+1 code convention: `CUNEW-N.NSN:41-46`; DDM `NCCUSTOM.NSD:12` |
| CR-13 Name-field lineage | `NCCUSTOMER.SURNAME`, `FIRST-NAME-OLD`, `FIRST-NAME-1` | lineage | Blank `SURNAME` → reject (target LastName is mandatory). Both first-name columns blank → flag. `FIRST-NAME-OLD` blank and `FIRST-NAME-1` set → derived (correct). Both set and different (case-insensitive) → flag. Otherwise pass | correct | Two candidate columns for one legal-name attribute, populated by different code paths | PersonName.FirstName = `FIRST-NAME-OLD`, fallback `FIRST-NAME-1`; LastName = `SURNAME` | Persisted: `CUNEW-N.NSN:48-49`, `CUMOD-N.NSN:53-54`; read `CUGET-N.NSN:95-96`; adapter-only: `RDCRUISP.NSP:619`, `:663`, `NCCUGE-P.NSA:29`; view: `NCDATA-L.NSL:44-45`, `:56` |
| CR-14 Duplicate CONTRACT-ID | `NCCONTRACT.CONTRACT-ID` | uniqueness | Blank → reject. Unique → pass. Duplicated: lowest ISN survives (flag); later occurrences rejected | reject | Two pay transactions with the same transaction identifier | ElementEntry.SourceSystemId must be unique | MAX+1 under hold: `CONEW-N.NSN:96-102`; DDM `NCCONTRA.NSD:12` |
| CR-15 DATE-BOOKING validity | `NCCONTRACT.DATE-BOOKING` | validity | Blank → reject. Not a calendar `YYYYMMDD` → reject. After the as-of date → flag | reject | Transaction effective date that is not a date or lies after the extract cut-off | ElementEntry.EffectiveStartDate | Set from `*DATN`: `CONEW-N.NSN:105-106`; DDM `NCCONTRA.NSD:18` |

All `.NSN` / `.NSD` / `.NSA` / `.NSL` paths above are under `SunnyIslands/Natural-Libraries/CRUISE16/` (`RDCRUISP.NSP` under `SunnyIslands/Natural-Libraries/RDCRUISE/Programs/`); the generated `harness/sample-output/rule-catalogue.md` carries the full repository-relative paths.

## Coverage against the assignment

| Required rule area | Rule(s) |
|---|---|
| Orphaned `ID-CUSTOMER` / `ID-CRUISE` in `NCCONTRACT` | CR-01, CR-02 (and CR-03 for the third foreign key, `ID-YACHT`) |
| Invalid `CRUISE-STATUS` domain | CR-04 |
| Email array occurrences | CR-06 |
| Phone occurrences | CR-07 |
| ZIP / COUNTRY formats | CR-08, CR-09 |
| `BIRTH-DATE` validity | CR-10 |
| `TIMESTAMP` presence | CR-11 |
| Duplicate `PERSON-ID` | CR-12 (CR-14 applies the same pattern to `CONTRACT-ID`) |
| Name-field lineage | CR-13 |
| Domain codes documented only in the DDM | CR-05 |
| Effective date of the transaction | CR-15 |

## What each rule produces in the reconciliation

Every rule contributes one line to "Outcome per rule" in `harness/sample-output/reconciliation-report.md` (evaluated / passed / corrected / flagged / rejected), one or more rows in `harness/sample-output/exceptions.csv` for each non-pass outcome (file, ISN, business key, rule, field, outcome, message), and one line in "Injected defects versus detections", which proves that planted defects plus baseline-fixture presence exceptions equal the detections. The counts are generated; regenerate them with the harness rather than quoting them from this page.

## Rules not demonstrated on the sample (designed)

| Payroll rule the SI will need | Why the sample cannot demonstrate it | Sample rule it would reuse |
|---|---|---|
| Manager / supervisor exists and chains terminate | No self-referencing key on `NCCUSTOMER` | CR-01 pattern (key exists in loaded person set) plus cycle detection |
| Department hierarchy is a rooted tree | `NCYACHT` is flat | CR-03 pattern (parent exists) plus tree walk |
| Position active on the assignment effective date | `NCCRUISE` dates are not used as an effective window by the code | CR-15 pattern with `START-DATE` / `END-DATE` as the window |
| No overlapping effective-dated rows per person | The source keeps one current row per customer | CR-12 pattern extended from key uniqueness to (key, date-range) non-overlap |
| Statutory identifiers (national ID, tax reference) valid | No such field in the sample | CR-08 / CR-09 pattern (format plus lookup) |

## Traceability

| Claim | Evidence | Evidence class |
|---|---|---|
| Rule IDs, fields, categories, actions, analogs and evidence paths | `harness/cleanse_reconcile.py` `RULES`; generated `harness/sample-output/rule-catalogue.md` | Executable harness |
| Rule logic as described in the "Logic" column | `harness/cleanse_reconcile.py` functions `chk_orphan_customer` .. `chk_booking_date` | Executable harness |
| Source citations per rule | `SunnyIslands/Natural-Libraries/CRUISE16/...` lines listed in the catalogue, all opened while authoring | Source statement / DDM listing |
| Field keys resolve to real DDM fields | `../03-data-model-data-dictionary/generate_dictionary_hcm.py --check` (fails on an unknown field) | Generator gate |
| Rule IDs here match the harness | `harness/cleanse_reconcile.py --check` (`check_rule_ids_in_doc`) | Harness gate |
| Source data should be reviewed and cleansed before load; validate before upload | Oracle, *Guidelines for Preparing the Source Data*, https://docs.oracle.com/en/cloud/saas/human-resources/fahdl/guidelines-for-preparing-the-source-data.html | Vendor documentation (opened 2026-09-03) |

← [Back to the directory README](README.md) · [Back to the navigation hub](../README.md)
