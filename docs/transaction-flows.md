# End-to-End Transaction Flows

The two core user journeys are *finding a cruise* and *booking a cruise*.
Both start on the NJX page (`rdcruisx.xml`), are handled by the adapter
program `RDCRUISP` (library `RDCRUISE`), and execute business logic in
library `CRUISE16` against ADABAS.

## 1. Cruise listing (CRLIST-N)

```mermaid
sequenceDiagram
    actor User
    participant UI as rdcruisx (NJX page)
    participant ADP as RDCRUISP
    participant CRL as CRLIST-N
    participant DB as ADABAS

    User->>UI: enter optional start/destination harbor, click Search
    UI->>ADP: page event
    ADP->>CRL: CALLNAT 'CRLIST-N' P-COM P-RESPONSE P-SELETION ...
    CRL->>DB: READ NCCRUISE DESCENDING BY START-DATE
    loop each cruise
        alt CRUISE-STATUS = 0 (fully booked)
            CRL->>CRL: ESCAPE TOP (skip)
        else harbor filter mismatch
            CRL->>CRL: ESCAPE TOP (skip)
        else match
            CRL->>DB: FIND NCYACHT WITH YACHT-ID = ID-YACHT
            CRL->>CRL: append row (dates YYYY-MM-DD, prices 2 decimals)
        end
    end
    alt no rows
        CRL->>CRL: MSG-NR := 9857 (no cruise data found)
    else rows found
        CRL->>CRL: MSG-NR := 9807 (cruise list shown)
    end
    CRL->>CRL: CALLNAT 'CAMSG-N' (9807 -> response code 0)
    CRL-->>ADP: P-CRUISE-DATA(*), P-RSPCODE, P-RSPTXT
    ADP-->>UI: render result grid
```

## 2. Booking a cruise (CONEW-N, refactored)

```mermaid
sequenceDiagram
    actor User
    participant UI as rdcruisx (NJX page)
    participant ADP as RDCRUISP
    participant CON as CONEW-N
    participant DB as ADABAS

    User->>UI: select cruise, enter customer ID, click Book
    UI->>ADP: page event
    ADP->>CON: CALLNAT 'CONEW-N' P-COM P-RESPONSE P-CONTRACT-DATA P-NEW-CONTRACTID
    alt customer ID blank/0
        CON->>CON: MSG-NR := 9904
    else cruise ID blank/0
        CON->>CON: MSG-NR := 9905
    else IDs present
        CON->>CON: numeric format check (else 9905/9904)
        CON->>DB: FIND NCCRUISE WITH CRUISE-ID
        CON->>DB: GET NCCRUISE *ISN(R1.)  [record hold]
        alt VAL(CRUISE-STATUS) = 0
            CON->>CON: MSG-NR := 9902 (no longer available)
        else places left
            CON->>DB: UPDATE CRUISE-STATUS := status - 1  [held]
            CON->>DB: READ (1) NCCONTRACT DESCENDING BY CONTRACT-ID
            CON->>DB: UPDATE (fake)  [hold highest contract record]
            CON->>CON: CONTRACT-ID := MAX + 1, fill price/dates/IDs
            CON->>DB: FIND NCCUSTOMER PERSON-ID (HANDLE-INPUT-DATA)
            alt customer not found
                CON->>CON: MSG-NR := 9918
                CON->>DB: BACKOUT TRANSACTION (undo decrement, release holds)
            else customer OK (MSG-NR = 9800)
                CON->>DB: STORE NCCONTRACT
                CON->>DB: END TRANSACTION (commit, release holds)
                CON->>CON: P-NEW-CONTRACTID := new CONTRACT-ID
            end
        end
    end
    CON->>CON: CALLNAT 'CAMSG-N' (9800 -> response code 0 + text)
    CON-->>ADP: P-RSPCODE, P-RSPTXT, P-NEW-CONTRACTID
    ADP-->>UI: show confirmation or error message
```

### Message-code outcomes

| Code | Meaning | Response code after CAMSG-N |
|------|---------|------------------------------|
| 9800 | Booking successful | 0 |
| 9807 | Cruise list shown | 0 |
| 9857 | No cruise data found | 9857 |
| 9902 | Cruise no longer available | 9902 |
| 9904 | Customer number input missing | 9904 |
| 9905 | Cruise number input missing | 9905 |
| 9918 | Customer number not found | 9918 |
| 9999 | Student-mode placeholder (`#STUDENT`) | 9999 |

## 3. Customer maintenance (CUGET-N / CUNEW-N / CUMOD-N)

```
User action            RDCRUISP CALLNAT      ADABAS access
-----------            -----------------     -------------------------------
Log in / show data ->  CUGET-N               FIND NCCUSTOMER PERSON-ID
Register           ->  CUNEW-N               READ(1) DESC PERSON-ID + UPDATE
                                             (hold) -> MAX+1 -> STORE -> ET
Change my data     ->  CUMOD-N               FIND + UPDATE (held) -> ET
```

`CUNEW-N`'s ID generation is the model for the contract-ID fix in `CONEW-N`
— see [concurrency-refactor.md](concurrency-refactor.md).
