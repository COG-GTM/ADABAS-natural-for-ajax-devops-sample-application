# New-Developer Training Guide

Welcome to the Sunny Islands cruise-booking sample application. This guide
takes you from zero to making a safe change.

## 1. What this application is

A Natural for AJAX (NJX) web application: a browser UI for searching
cruises, registering customers, and booking cruise contracts. The
business logic is written in Software AG **Natural** and the data lives in
**ADABAS** files.

```
 Browser (rdcruisx page)
        |
        v
 NJX servlet / Ajax framework          SunnyIslands/webconfig, deploy/
        |
        v
 RDCRUISE library (adapter)            RDCRUISP.NSP + helpers
        |  CALLNAT
        v
 CRUISE16 library (services)           CRLIST-N, CRGET-N, CONEW-N,
        |                              CUGET-N, CUNEW-N, CUMOD-N, CAMSG-N
        v
 ADABAS files                          NCCRUISE, NCCONTRACT,
                                       NCCUSTOMER, NCYACHT
```

## 2. Prerequisites

* **NaturalONE** (Software AG's Eclipse-based IDE) to import, edit, and
  deploy the Natural sources — see the top-level `README.md`.
* Access to an **ADABAS** database loaded with the four application files.
* **Python 3** (any recent version, stdlib only) to run the regression
  suite locally.
* No credentials are stored in this repository; connection settings are
  environment-specific NaturalONE/deployment configuration.

## 3. Repository layout

| Path | Contents |
|------|----------|
| `SunnyIslands/Natural-Libraries/CRUISE16/` | Business-logic library: subprograms (`.NSN`), parameter data areas (`.NSA`), local data area (`.NSL`), copycode (`.NSC`), DDMs (`.NSD`) |
| `SunnyIslands/Natural-Libraries/RDCRUISE/` | NJX presentation library: programs (`.NSP`), subprograms, global/local data areas |
| `SunnyIslands/User-Interface-Components/CruisePages/` | NJX page definition (`xml/rdcruisx.xml`) and images |
| `SunnyIslands/deploy/`, `SunnyIslands/webconfig/` | Ant deployment descriptors and servlet configuration |
| `docs/` | This documentation set |
| `tests/`, `tools/` | Regression suite and doc generator (Python, stdlib only) |
| `.github/workflows/` | CI: regression tests on every PR + CodeQL |

## 4. Key concepts you must know

### Natural object types
* **Subprogram (`.NSN`)** — callable with `CALLNAT`, parameters defined by
  PDAs. All CRUISE16 services are subprograms.
* **Program (`.NSP`)** — entry points (`RDCRUISP` is the NJX adapter).
* **PDA (`.NSA`)** — parameter data area: the interface contract of a
  subprogram (e.g. `NCCONW-P` for `CONEW-N`).
* **LDA (`.NSL`)** / **GDA (`.NSG`)** — local/global data areas.
* **Copycode (`.NSC`)** — included source (e.g. `ERRLOG-I` error logging).
* **DDM (`.NSD`)** — the Natural view of an ADABAS file; see
  [data-dictionary.md](data-dictionary.md).

### The service pattern
Every CRUISE16 service follows the same shape:

1. `DEFINE DATA PARAMETER USING NCCOMM-P` (+ its own PDA);
2. an `ON ERROR` block including `ERRLOG-I` and backing out the transaction;
3. a `DECIDE`/validation block that sets `MSG-GROUP-PARA.MSG-NR`;
4. database access (`FIND` / `READ` / `STORE` / `UPDATE` + `END TRANSACTION`);
5. `CALLNAT 'CAMSG-N' MSG-GROUP-PARA` to translate the message number into
   language-specific text and remap success codes to response code 0;
6. results returned in `P-RESPONSE` (`P-RSPCODE`, `P-RSPTXT`).

Message-code ranges: 98xx are informational/success (remapped to 0 by
`CAMSG-N`), 99xx are errors (kept as-is). Add new texts to `CAMSG-N` for
every supported language (EN/DE/ES/PT).

### ADABAS transaction & hold rules (critical!)
* A record read in a loop that contains an `UPDATE`/`DELETE` (or re-read
  with `GET` referenced by an `UPDATE`) is placed **in hold**; other
  sessions wait in the hold queue until you issue `END TRANSACTION` (ET)
  or `BACKOUT TRANSACTION` (BT).
* **Never** decide on data you read without a hold and then write the
  decision back — that is a lost-update race. Read
  [concurrency-refactor.md](concurrency-refactor.md) before touching any
  updating code; it walks through the two real defects this codebase had.
* Generate sequential IDs only while holding the current highest record
  (the fake-`UPDATE` idiom in `CUNEW-N` and `CONEW-N`).
* Keep transactions short: hold → change → ET in one straight path.

## 5. Your first change, step by step

1. **Read the docs**: [module-inventory.md](module-inventory.md) to find the
   right object, [call-map.md](call-map.md) for who calls it,
   [transaction-flows.md](transaction-flows.md) for the user journey.
2. **Run the tests before changing anything**:
   `python3 -m unittest discover -s tests -v` — everything must pass.
3. **Make the change** in NaturalONE (or a text editor for docs/tests).
   Follow the service pattern above; preserve message-code behavior unless
   the change is explicitly about messages.
4. **Update the model if you changed business rules**: the Python port in
   `tests/harness/natural_model.py` must mirror the Natural source, and
   `tests/test_source_conformance.py` will fail if the source diverges from
   what the tests assert.
5. **Regenerate the data dictionary if you changed a DDM**:
   `python3 tools/generate_data_dictionary.py` (CI fails on drift).
6. **Run the suite again**, open a pull request, and let CI
   (`regression-tests.yml` + CodeQL) confirm.
7. Deployment to Dev/Test/Prod uses the Ant descriptors in
   `SunnyIslands/deploy/` from a NaturalONE/Jenkins-style pipeline.

## 6. Common pitfalls

| Pitfall | Consequence | Rule |
|---------|-------------|------|
| Read-then-write without hold | Lost updates, overbooking | Hold the record (`GET` + `UPDATE`) before test-and-set |
| MAX+1 IDs from an unheld read | Duplicate keys | Fake-`UPDATE` hold on the highest record first |
| Forgetting `BACKOUT TRANSACTION` on error paths | Partial bookings, dangling holds | Every failure path must BT (see `ON ERROR` blocks) |
| New message code only in one language | Blank texts for other languages | Add to all language blocks in `CAMSG-N` |
| Editing `docs/data-dictionary.md` by hand | CI drift-gate failure | Regenerate with the tool |
| `CRUISE-STATUS` is alphanumeric (A1) | Arithmetic on it fails | `VAL(...)` to read, move a numeric back as its string form |
