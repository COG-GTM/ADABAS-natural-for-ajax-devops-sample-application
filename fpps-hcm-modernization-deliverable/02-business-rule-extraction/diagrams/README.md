# Diagrams — business-rule extraction

Mermaid source is the artifact of record; each `.mmd` file is reproduced below so the diagrams render on any Markdown viewer with Mermaid support. Rendered `.svg`/`.png` files, where present, were produced with `npx -y @mermaid-js/mermaid-cli -i <file>.mmd -o <file>.svg` from the same source. Every node cites the executable line it represents; labels carry the maturity tag where the behaviour is not Demonstrated in this repository.

| File | Shows | Rules | Maturity |
|---|---|---|---|
| `conew-decision-flow.mmd` | The booking service's validation edits, the held re-read / test-and-set, the serialized MAX+1 identifier and every exit code | BR-001 – BR-013, BR-M003 – BR-M005 | Demonstrated (source and `tests/`) |
| `conew-race-before-after.mmd` | The two concurrency defects of the pre-refactor logic and how the refactor removes them | BR-006, BR-007 | Demonstrated (`tests/test_concurrency.py`) |
| `cumod-optimistic-concurrency.mmd` | Timestamp compare-and-update in the customer modify service and the adapter's stale-value restore | BR-029, BR-031, BR-032 | Demonstrated (source); harness needed for execution |
| `message-code-lifecycle.mmd` | How a four-digit code becomes a response code and typed text, including the success remap to 0 | BR-012, BR-030, BR-033 – BR-035 | Demonstrated (source, `tests/test_source_conformance.py`) |

## Booking decision flow (`conew-decision-flow.mmd`)

```mermaid
flowchart TD
    classDef edit fill:#fff4e5,stroke:#b26a00,color:#000
    classDef integrity fill:#e6f2ff,stroke:#1f4e99,color:#000
    classDef txn fill:#e9f7ef,stroke:#1e7e34,color:#000
    classDef fail fill:#fbe9e7,stroke:#b71c1c,color:#000
    classDef note fill:#f5f5f5,stroke:#777,color:#000,stroke-dasharray: 4 2

    A([Booking request: customer id, offering id<br/>Demonstrated - CONEW-N.NSN:54]) --> G{"#STUDENT gate<br/>CONEW-N.NSN:48-50<br/>(exercise scaffolding, retire)"}
    G -- true --> G9999["9999 Function not yet supported"]:::fail
    G -- false --> V1{"BR-001 customer id blank or '0'?<br/>CONEW-N.NSN:55"}:::edit
    V1 -- yes --> M9904["9904 Customer Id missing"]:::fail
    V1 -- no --> V2{"BR-002 offering id blank or '0'?<br/>CONEW-N.NSN:57"}:::edit
    V2 -- yes --> M9905["9905 Cruise Id missing"]:::fail
    V2 -- no --> V3{"BR-004 offering id IS (N8)?<br/>CONEW-N.NSN:60"}:::edit
    V3 -- no --> M9905b["9905 set (processing continues)"]:::fail
    V3 -- yes --> V4
    M9905b --> V4{"BR-005 customer id IS (N8)?<br/>CONEW-N.NSN:66"}:::edit
    V4 -- no --> M9904b["9904 set (processing continues, BR-M004)"]:::fail
    V4 -- yes --> F1
    M9904b --> F1["FIND NCCRUISE by offering id<br/>CONEW-N.NSN:79-80"]:::integrity
    F1 -- no record --> NF["No code set: response 0, booking id 0<br/>BR-M005 (missing edit 9916)"]:::fail
    F1 -- record --> H1["BR-006 GET *ISN - re-read in HOLD<br/>fresh CRUISE-STATUS<br/>CONEW-N.NSN:82-83"]:::integrity
    H1 --> AV{"free places > 0 on the HELD copy?<br/>CONEW-N.NSN:86"}:::integrity
    AV -- no --> B1["BACKOUT TRANSACTION (release hold)<br/>CONEW-N.NSN:134"]:::txn
    B1 --> M9902["9902 Cruise no longer available"]:::fail
    AV -- yes --> DEC["decrement, UPDATE held record<br/>CONEW-N.NSN:90-92"]:::integrity
    DEC --> R2["BR-007 READ (1) NCCONTRACT DESCENDING<br/>UPDATE (R2.) = fake update, HOLD highest record<br/>CONEW-N.NSN:95-98"]:::integrity
    R2 -- file empty --> B2["BACKOUT TRANSACTION<br/>CONEW-N.NSN:126-130 (BR-013 / BR-M003)"]:::txn
    B2 --> M9902
    R2 -- record held --> ID["new id = MAX+1 (serialized)<br/>price = PRICE-1W, date = *DATN<br/>CONEW-N.NSN:100-110"]:::integrity
    ID --> CU{"BR-010 FIND NCCUSTOMER exists?<br/>CONEW-N.NSN:157"}:::edit
    CU -- no --> B3["BACKOUT TRANSACTION (undo decrement)<br/>CONEW-N.NSN:122"]:::txn
    B3 --> M9918["9918 Customer Id not found"]:::fail
    CU -- yes --> ST["BR-011 STORE NCCONTRACT + END TRANSACTION<br/>CONEW-N.NSN:116-118"]:::txn
    ST --> OK["9800 -> CAMSG-N -> response 0 'S-Travel Booking successful'<br/>CONEW-N.NSN:143-146"]:::txn

    M9904 --> CAM["CAMSG-N translation (BR-012 / BR-034)<br/>P-RSPCODE = code, P-RSPTXT = type-text"]
    M9905 --> CAM
    M9902 --> CAM
    M9918 --> CAM
    NF --> CAM
    G9999 --> CAM
    OK --> CAM

    N1["Pay-run integrity analogy: the HOLD + test-and-set is the rule a<br/>language converter drops when it copies read-then-write into application code.<br/>Requirement REQ-I-001 / REQ-I-002 (Designed for the target HCM)"]:::note
    H1 -.-> N1
    R2 -.-> N1
```

Reading the flow as a payroll SI: orange diamonds are validation edits (element-entry style), blue boxes are the integrity requirements (REQ-I-001, REQ-I-002), green boxes are the transaction boundary (REQ-I-003), red boxes are the outcomes that reach the caller. The dashed note marks the two steps a source-to-source converter reproduces as plain read-then-write, which reintroduces the defects shown in the next diagram.

## Concurrency defects and fix (`conew-race-before-after.mmd`)

```mermaid
sequenceDiagram
    autonumber
    participant A as User A (CONEW-N)
    participant DB as ADABAS NCCRUISE / NCCONTRACT (synthetic simulation)
    participant B as User B (CONEW-N)

    rect rgb(251, 233, 231)
    Note over A,B: Before refactor - Demonstrated defect, tests/test_concurrency.py:24-66
    A->>DB: FIND NCCRUISE (no hold) - CRUISE-STATUS = 1
    B->>DB: FIND NCCRUISE (no hold) - CRUISE-STATUS = 1
    A->>DB: UPDATE CRUISE-STATUS = 0
    B->>DB: UPDATE CRUISE-STATUS = 0 (lost update, second place sold)
    A->>DB: READ (1) NCCONTRACT DESCENDING (no hold) - MAX = 1000
    B->>DB: READ (1) NCCONTRACT DESCENDING (no hold) - MAX = 1000
    A->>DB: STORE contract 1001, END TRANSACTION
    B->>DB: STORE contract 1001 (duplicate key), END TRANSACTION
    Note over A,B: Two bookings for one place and two records with the same identifier
    end

    rect rgb(230, 242, 255)
    Note over A,B: After refactor - Demonstrated fix, CONEW-N.NSN:79-118, tests/test_concurrency.py:68-127
    A->>DB: FIND NCCRUISE, then GET *ISN (record HELD) - CRUISE-STATUS = 1
    B->>DB: FIND NCCRUISE, then GET *ISN - blocked on A's hold
    A->>DB: LOCAL-AVAIL = 1 > 0: decrement, UPDATE (held)
    A->>DB: READ (1) NCCONTRACT DESCENDING, UPDATE (R2.) - highest contract HELD
    A->>DB: new id = 1000 + 1 = 1001, FIND customer, STORE 1001, END TRANSACTION (holds released)
    DB-->>B: hold granted - re-read returns CRUISE-STATUS = 0
    B->>DB: LOCAL-AVAIL = 0: BACKOUT TRANSACTION
    B-->>B: 9902 Cruise no longer available
    Note over A,B: N free places produce exactly N successes (tests/test_concurrency.py:129-141)
    end

    Note over A,B: Target HCM (Designed): REQ-I-001 atomic decrement, REQ-I-002 platform-generated unique identifier
```

The identifiers 1000/1001 are illustrative; the executable tests use the synthetic fixture values (500100 → 500101/500102).

## Customer modify: timestamp optimistic concurrency (`cumod-optimistic-concurrency.mmd`)

```mermaid
sequenceDiagram
    autonumber
    participant UI as RDCRUISP adapter (RDCRUISP.NSP:612-657)
    participant S as CUMOD-N
    participant DB as NCCUSTOMER (synthetic simulation)

    UI->>S: P-PERSON-ID, P-TIMESTAMP (from the earlier CUGET-N read), new field values
    S->>DB: FIND (1) NCCUSTOMER WITH PERSON-ID (CUMOD-N.NSN:44)
    alt no record (BR-029)
        S-->>UI: 9924 Customer Id not found (CUMOD-N.NSN:46)
    else record found
        S->>S: stored TIMESTAMP = P-TIMESTAMP ? (CUMOD-N.NSN:50)
        alt equal (BR-031, BR-032)
            S->>DB: move surname, first name, e-mail, address, birth date, then TIMESTAMP = *TIMESTMP (CUMOD-N.NSN:53-62)
            S->>DB: UPDATE (F1.), END TRANSACTION (CUMOD-N.NSN:63-64)
            S-->>UI: response 0, refreshed timestamp returned in P-CUSTOMER-DATA
        else different (BR-032)
            S-->>UI: 9934 Customer changed from another user (CUMOD-N.NSN:67)
            UI->>UI: restore the previously read values into the screen fields (RDCRUISP.NSP:644-657)
        end
    end
    Note over UI,DB: Demonstrated in source - harness needed (no CUMOD-N model in tests/harness/natural_model.py). Target REQ-I-004 lost-update protection (Designed)
```

## Message-code lifecycle (`message-code-lifecycle.mmd`)

```mermaid
flowchart LR
    classDef ok fill:#e9f7ef,stroke:#1e7e34,color:#000
    classDef info fill:#fff4e5,stroke:#b26a00,color:#000
    classDef gap fill:#fbe9e7,stroke:#b71c1c,color:#000

    S["Service sets MSG-NR<br/>(11 codes emitted in analyzed scope)"] --> C["CALLNAT 'CAMSG-N' MSG-GROUP-PARA"]
    C --> L{"MSG-LANG = '2'?<br/>CAMSG-N.NSN:17, 101<br/>P-LANG never assigned by the adapter"}
    L -- "yes (unreachable in analyzed scope)" --> DE["German DECIDE block<br/>CAMSG-N.NSN:19-98"]
    L -- "no (always, in analyzed scope)" --> EN["English DECIDE block<br/>CAMSG-N.NSN:102-181"]
    EN --> K{"code in catalogue?"}
    K -- "success code (9800, 9807 and five never-emitted)" --> Z["MSG-NR := 0, text set<br/>CAMSG-N.NSN:104-106, 132-134"]:::ok
    K -- "other cataloged code" --> T["text set, MSG-NR unchanged"]:::info
    K -- "not cataloged" --> P["NONE IGNORE: code passes through, text empty<br/>CAMSG-N.NSN:180 (BR-035)"]:::gap
    Z --> TY{"MSG-NR = 0?<br/>CAMSG-N.NSN:185-189"}
    T --> TY
    P --> TY
    TY -- yes --> TS["MSG-TYPE 'S'"]:::ok
    TY -- no --> TI["MSG-TYPE 'I'"]:::info
    TS --> R["P-RSPCODE = MSG-NR; P-RSPTXT = type-text<br/>e.g. CONEW-N.NSN:143-146"]
    TI --> R
    R --> UI["Adapter tests P-RSPCODE = '0'<br/>RDCRUISP.NSP:584-590"]
```

## Rendering

```bash
cd fpps-hcm-modernization-deliverable/02-business-rule-extraction/diagrams
for f in *.mmd; do npx -y @mermaid-js/mermaid-cli -i "$f" -o "${f%.mmd}.svg"; done
```

## Synthetic data and scope

Sequence diagrams show the synthetic ADABAS simulation (`tests/harness/adabas_sim.py`) standing in for ADABAS; no production system was accessed. FPPS is referred to only by analogy.

← [Back to the directory README](../README.md) · [Navigation hub](../../README.md)
