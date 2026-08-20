# Module Inventory

All Natural objects live under `SunnyIslands/Natural-Libraries/`. There are
two libraries:

* **CRUISE16** — the business-logic library: subprograms, parameter data
  areas (PDAs), and the ADABAS DDMs.
* **RDCRUISE** — the Natural for AJAX (NJX) presentation library: the
  generated adapter program that drives the browser UI and its helpers.

## Library CRUISE16 (business logic)

### Subprograms (`Subprograms/*.NSN`)

| Object | Purpose | Files touched |
|--------|---------|---------------|
| `CRLIST-N` | List available cruises (skips `CRUISE-STATUS = 0`), optional start/destination-harbor filters, newest `START-DATE` first; joins `NCYACHT` for yacht names. Sets 9807 (list shown) or 9857 (no data). | `NCCRUISE` (read), `NCYACHT` (read) |
| `CRGET-N` | Read the details of one cruise selected by `CRUISE-ID`, including duration-based price selection (1/2/3-week price). | `NCCRUISE` (read), `NCYACHT` (read) |
| `CONEW-N` | Create a booking contract: validates customer/cruise IDs (9904/9905), test-and-sets `CRUISE-STATUS` under record hold (9902 when full), generates `CONTRACT-ID` = MAX+1 under record hold, stores the contract (9800), 9918 when the customer does not exist. See [concurrency-refactor.md](concurrency-refactor.md). | `NCCRUISE` (update), `NCCONTRACT` (read/store), `NCCUSTOMER` (read) |
| `CUGET-N` | Read one customer by `PERSON-ID` (9923/9924 on bad input / not found). | `NCCUSTOMER` (read) |
| `CUNEW-N` | Create a customer; generates `PERSON-ID` = MAX+1 using a fake `UPDATE` to hold the highest record. | `NCCUSTOMER` (read/store) |
| `CUMOD-N` | Modify an existing customer (9924 not found, 9934 modified). | `NCCUSTOMER` (update) |
| `CAMSG-N` | Message-code translator: maps `MSG-NR` to language-specific text (EN/DE/ES/PT) and remaps success codes (98xx informational, e.g. 9800/9807) to response code 0. | none |
| `CA3900-N` | Utility/demo subprogram (single `READ (1) NCCUSTOMER`). | `NCCUSTOMER` (read) |

### Parameter Data Areas (`Parameter Data Areas/*.NSA`)

| Object | Purpose |
|--------|---------|
| `NCCOMM-P` | Common communication block: `P-COM` (language, user, password) and `P-RESPONSE` (`P-RSPCODE`, `P-RSPTXT`) used by every service subprogram. |
| `NCCONW-P` | `CONEW-N` interface: `P-CONTRACT-DATA` (week count, reservation/booking dates, customer/cruise IDs — all alphanumeric inputs) and `P-NEW-CONTRACTID (N8)`. |
| `NCCRUL-P` | `CRLIST-N`/`CRGET-N` interface: harbor filters (`P-SELETION`), record count, and the dynamic `P-CRUISE-DATA(1:*)` output array. |
| `NCCUGE-P` | `CUGET-N`/`CUNEW-N`/`CUMOD-N` interface: customer selection and customer data. |
| `NCCUSL-P` | Customer-list interface. |
| `CONTPDA`, `MYPDA`, `SYPDA`, `YACHTPDA` | Additional PDAs for contract, misc, system and yacht data. |

### Other objects

| Object | Type | Purpose |
|--------|------|---------|
| `NCDATA-L` | Local Data Area | Shared locals, including `MSG-GROUP-PARA` (`MSG-NR`, `MSG-LANG`, `MSG-TYPE`, `MSG-TEXT`) and the `#STUDENT` training switch. |
| `ERRLOG-I` | Copycode | `ON ERROR` logging block included by every service subprogram. |
| `NCCRUISE.NSD`, `NCCONTRA.NSD`, `NCCUSTOM.NSD`, `NCYACHT.NSD` | DDMs | ADABAS views for logical files `NCCRUISE`, `NCCONTRACT`, `NCCUSTOMER`, `NCYACHT` — see [data-dictionary.md](data-dictionary.md). |

## Library RDCRUISE (NJX presentation layer)

| Object | Type | Purpose |
|--------|------|---------|
| `RDCRUISP` | Program | The main NJX adapter program: processes the `rdcruisx` page events (search, select, book, login, customer maintenance) and `CALLNAT`s the CRUISE16 services. |
| `RDCRINIP` | Program | Initialization program; `FETCH RETURN`ed by `RDCRUISP` and calls `RDREADWN`. |
| `DELETECU` | Program | Utility program for deleting customers (maintenance/demo). |
| `RDREADWN` | Subprogram | Reads welcome/description texts (`resources/CruiseDescriptions.txt`). |
| `IMG-LOAD` | Subprogram | Loads image binaries and builds URLs via `MAKEURL`. |
| `MAKEURL` | Subprogram | Turns binary picture data into a browser-usable URL. |
| `RDCCRUIS` | Global Data Area | Session-wide state for the NJX application. |
| `RDCRUISL` | Local Data Area | Locals for the adapter program. |

## User interface

`SunnyIslands/User-Interface-Components/CruisePages/` contains the NJX page
definition (`xml/rdcruisx.xml`) and its images. The page layout is generated
into the adapter interface used by `RDCRUISP`.

## Deployment

`SunnyIslands/deploy/` holds Ant deployment descriptors for Dev/Test/Prod
(`natdeploy*.xml` for the Natural server parts, `wardeploy*.xml` for the web
archive), and `SunnyIslands/webconfig/` the servlet configuration.
