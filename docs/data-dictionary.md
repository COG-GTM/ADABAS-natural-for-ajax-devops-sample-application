# Data Dictionary

Derived automatically from the ADABAS DDM sources in
`SunnyIslands/Natural-Libraries/CRUISE16/DDMs/` by
`tools/generate_data_dictionary.py`. **Do not edit by hand** —
regenerate with `python3 tools/generate_data_dictionary.py`.

Column legend: **T** = field class (blank scalar, G group,
M multiple-value, P periodic group), **Lv** = level, **F** = ADABAS
format, **Len** = length, **D** = descriptor (D = descriptor /
search key, S = sub-/superdescriptor).

## NCCRUISE

Source file: `NCCRUISE.NSD` — DB 12, file 41. Cruise catalogue: one record per scheduled cruise. `CRUISE-STATUS` (A1) holds the number of free places and is decremented by `CONEW-N` on every booking.

| T | Lv | Field | F | Len | D | Remark |
|---|----|-------|---|-----|---|--------|
|  | 1 | `CRUISE-ID` | Numeric (unpacked) | 8.0 | D |  |
|  | 1 | `CRUISE-STATUS` | Alphanumeric | 1 |  | number of available places |
| G | 1 | `CRUISE-START` |  |  |  |  |
|  | 2 | `START-DATE` | Numeric (unpacked) | 8.0 | D |  |
|  | 2 | `START-TIME` | Numeric (unpacked) | 6.0 |  |  |
| G | 1 | `CRUISE-END` |  |  |  |  |
|  | 2 | `END-DATE` | Numeric (unpacked) | 8.0 | D |  |
|  | 2 | `END-TIME` | Numeric (unpacked) | 6.0 |  |  |
|  | 1 | `START-HARBOR` | Alphanumeric | 20 | D |  |
|  | 1 | `DESTINATION-HARBOR` | Alphanumeric | 20 | D |  |
|  | 1 | `ID-YACHT` | Numeric (unpacked) | 8.0 | D | ID of yacht sailing cruise |
| G | 1 | `PRICES` |  |  |  |  |
|  | 2 | `PRICE-1W` | Packed numeric | 10.3 |  | price for one week |
|  | 2 | `PRICE-2W` | Packed numeric | 10.3 |  | price for two weeks |
|  | 2 | `PRICE-3W` | Packed numeric | 10.3 |  | price for three weeks |

Descriptors (search keys): `CRUISE-ID`, `START-DATE`, `END-DATE`, `START-HARBOR`, `DESTINATION-HARBOR`, `ID-YACHT`

## NCCONTRACT

Source file: `NCCONTRA.NSD` — DB 12, file 43. Booking contracts: one record per booking created by `CONEW-N`. `CONTRACT-ID` is generated as MAX+1 under a record hold.

| T | Lv | Field | F | Len | D | Remark |
|---|----|-------|---|-----|---|--------|
|  | 1 | `CONTRACT-ID` | Packed numeric | 6.0 | D |  |
|  | 1 | `PRICE` | Packed numeric | 10.3 |  |  |
|  | 1 | `DID-CONDITIONS` | Alphanumeric | 8 | D | ID of document including contract conditions |
|  | 1 | `DATE-RESERVATION` | Numeric (unpacked) | 8.0 | D |  |
|  | 1 | `DATE-BOOKING` | Numeric (unpacked) | 8.0 | D |  |
|  | 1 | `DATE-CANCELLATION` | Numeric (unpacked) | 8.0 | D |  |
| G | 1 | `DEPOSIT` |  |  |  |  |
|  | 2 | `DATE-D` | Numeric (unpacked) | 8.0 |  |  |
|  | 2 | `AMOUNT-D` | Packed numeric | 10.3 |  |  |
| G | 1 | `PAYMENT-OF-BALANCE` |  |  |  |  |
|  | 2 | `DATE-P` | Numeric (unpacked) | 8.0 |  |  |
|  | 2 | `AMOUNT-P` | Packed numeric | 10.3 |  |  |
|  | 1 | `ID-CUSTOMER` | Numeric (unpacked) | 8.0 | D | PERSON-ID of customer |
|  | 1 | `ID-CRUISE` | Numeric (unpacked) | 8.0 | D | CRUISE-ID, subject of contract |

Descriptors (search keys): `CONTRACT-ID`, `DID-CONDITIONS`, `DATE-RESERVATION`, `DATE-BOOKING`, `DATE-CANCELLATION`, `ID-CUSTOMER`, `ID-CRUISE`

## NCCUSTOMER

Source file: `NCCUSTOM.NSD` — DB 12, file 44. Customer master data, maintained by `CUNEW-N`/`CUMOD-N` and read by `CUGET-N` and `CONEW-N`.

| T | Lv | Field | F | Len | D | Remark |
|---|----|-------|---|-----|---|--------|
|  | 1 | `PERSON-ID` | Numeric (unpacked) | 8.0 | D |  |
|  | 1 | `BIRTH-DATE` | Numeric (unpacked) | 8.0 |  |  |
|  | 1 | `SEX` | Alphanumeric | 1 | D | 2 values: 'M' for 'male',  'F' for 'female' |
| G | 1 | `NAME` |  |  |  |  |
|  | 2 | `SURNAME` | Alphanumeric | 20 | D |  |
|  | 2 | `FIRST-NAME-OLD` | Alphanumeric | 20 |  |  |
|  | 2 | `FIRST-NAME-2` | Alphanumeric | 20 |  |  |
|  | 2 | `TITLE` | Alphanumeric | 20 |  |  |
|  | 2 | `FORM-OF-ADDRESS` | Alphanumeric | 8 |  |  |
| G | 1 | `ADDRESS` |  |  |  |  |
| M | 2 | `EMAIL` | Alphanumeric | 20 |  |  |
|  | 2 | `STREET-NUMBER` | Alphanumeric | 20 |  |  |
|  | 2 | `COUNTRY` | Alphanumeric | 3 | D |  |
|  | 2 | `ZIP-CODE` | Alphanumeric | 10 | D |  |
|  | 2 | `CITY` | Alphanumeric | 20 | D |  |
| P | 1 | `PHONE` |  |  |  | 2 occ.:  1. phone private,  2. phone company |
|  | 2 | `AREA-CODE` | Alphanumeric | 6 |  |  |
|  | 2 | `PHONE-NUMBER` | Alphanumeric | 15 |  |  |
|  | 1 | `TIMESTAMP` | Binary | 8 |  |  |
|  | 1 | `FIRST-NAME-1` | Unicode | 40 |  |  |

Descriptors (search keys): `PERSON-ID`, `SEX`, `SURNAME`, `COUNTRY`, `ZIP-CODE`, `CITY`

## NCYACHT

Source file: `NCYACHT.NSD` — DB 12, file 42. Yacht master data, joined by `CRLIST-N`/`CRGET-N` via `ID-YACHT` to display yacht details.

| T | Lv | Field | F | Len | D | Remark |
|---|----|-------|---|-----|---|--------|
|  | 1 | `YACHT-ID` | Numeric (unpacked) | 8.0 | D |  |
|  | 1 | `YACHT-NAME` | Alphanumeric | 30 | D |  |
|  | 1 | `YACHT-TYPE` | Alphanumeric | 30 | D |  |
|  | 1 | `LENGTH` | Packed numeric | 3.2 |  | in meters |
|  | 1 | `WIDTH` | Packed numeric | 3.2 |  | in meters |
|  | 1 | `DRAFT` | Packed numeric | 3.2 |  | in meters |
|  | 1 | `SAIL-SURFACE` | Packed numeric | 3.0 |  | in square meters |
|  | 1 | `MOTOR` | Packed numeric | 3.0 |  | output in HP |
|  | 1 | `HEAD-ROOM` | Packed numeric | 3.2 |  | headroom in saloon in meters |
|  | 1 | `BUNKS` | Packed numeric | 3.0 |  | number of bunks |
|  | 1 | `L@PICTURE` | Integer | 4 |  |  |
|  | 1 | `PICTURE` | Alphanumeric |  |  | Lob |

Descriptors (search keys): `YACHT-ID`, `YACHT-NAME`, `YACHT-TYPE`

