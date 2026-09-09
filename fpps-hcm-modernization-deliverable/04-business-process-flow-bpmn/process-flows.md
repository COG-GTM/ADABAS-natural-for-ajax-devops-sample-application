# Process flows (BPMN-oriented)

Four narrated business processes of the Sunny Islands Cruise sample, each drawn as a Mermaid flowchart with four swimlanes (browser, NJX adapter, business service, ADABAS), a gateway for every validation in the executable source, an error end-event for every message code the service can return, and the transaction boundary (`END TRANSACTION` / `BACKOUT TRANSACTION`) drawn as a compensation boundary. Every event, code and line number below is taken from `evidence/process-evidence.md`, which `generate_process_evidence.py` regenerates from source (`--check` guards drift).

FPPS analogy: each flow is the shape of a personnel or payroll transaction in a Software AG Natural 9.x / ADABAS 8.6 estate — a screen event, a dispatching program, a service subprogram that owns the edits, and ADABAS files behind it. The sample facts are facts; the FPPS statements are analogies.

| Property | Value |
|---|---|
| Maturity | Demonstrated for the flows (they are read off shipped source and the `tests/harness/` model runs them today); designed for the BPMN 2.0 XML in `bpmn/` |
| Source of truth | `SunnyIslands/Natural-Libraries/RDCRUISE/Programs/RDCRUISP.NSP` (adapter), `SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/*.NSN` (services), `SunnyIslands/User-Interface-Components/CruisePages/xml/rdcruisx.xml` (page) |
| Generated evidence | `evidence/process-evidence.md`, `evidence/process-evidence.json` |
| Data | Synthetic only (`tests/harness/`); no production system or FPPS source is used |

## Notation

| Shape | Meaning | BPMN 2.0 equivalent |
|---|---|---|
| `([text])` | Start event (UI event raised by the page) | `startEvent` |
| `[text]` | Activity | `task` / `serviceTask` |
| `{text}` | Validation or decision gateway; every `IF`/`DECIDE`/`IF NO RECORDS FOUND` in executable code | `exclusiveGateway` |
| `((nnnn text))` | Error end-event labelled with the `CAMSG-N` message code | `endEvent` + `errorEventDefinition` |
| `[[text]]` | Success end-event | `endEvent` |
| `[/END TRANSACTION/]` | Commit — closes the transaction scope | `transaction` subprocess completes |
| `[\BACKOUT TRANSACTION\]` | Compensation — undoes every `UPDATE`/`STORE` since the last commit and releases record holds | `compensateEventDefinition` / cancel end-event on the `transaction` |
| dotted edge `-.->` | Compensation flow | association to the compensation handler |
| dashed subgraph *Transaction scope* | Statements executed between the first hold (`UPDATE`/`GET` on a held record) and `END TRANSACTION` / `BACKOUT TRANSACTION` | `transaction` subprocess |

Lane names are the same in every diagram: **Browser** (`rdcruisx.xml` controls), **NJX adapter** (`RDCRUISP.NSP` `DECIDE ON FIRST *PAGE-EVENT` branch and its `PERFORM`ed subroutine), **Business service** (CRUISE16 subprogram), **ADABAS** (logical files `NCCRUISE`, `NCCONTRACT`, `NCCUSTOMER`, `NCYACHT`/`YACHT-PICTURE`).

## Event inventory (generated)

The page declares 27 distinct UI events (28 `method=` attributes; the row-grid method `lines.onpvLineClick` is bound to both click and double-click of a result row). The adapter's `DECIDE ON FIRST *PAGE-EVENT` (`RDCRUISP.NSP:112-438`) has 34 branches. Counts and classifications come from `evidence/process-evidence.md` § *UI events → adapter branches → services*.

| Classification (from generator) | Branches | Events | In this document |
|---|---|---|---|
| Dispatches to business service | 14 | `onLoginbutton`, `onMydataSave`, `onBookingSave`, `onHotcruises`, `onShowAll`, `onFav1button`…`onFav4button`, `onShowdetails1`…`onShowdetails4`, `lines.onpvLineClick` | Processes P1–P4 |
| UI state only (visibility / GDA moves) | 10 | `onHome`, `onQuestion`, `onLoginicon`, `onNewdataicon`, `onLoginClose`, `onFavorites`, `onMydataClose`, `onBookingClose`, `onLogouticon`, `onMydataicon` | Presentation-only; noted under each process where they open or close its panel |
| Language switch (`FETCH RETURN 'RDCRINIP'`) | 4 | `onSeten`, `onSetge`, `onSetpo`, `onSetsp` | Presentation-only; sets `G-LANGUAGE` and re-runs the text initialiser (`RDCRUISP.NSP:271-319`) |
| Page refresh only (`PROCESS PAGE UPDATE`) | 4 | `nat:page.end`, `onFacebook`, `onTwitter`, `NONE VALUE` | Presentation-only; no business effect |
| Ignored (`IGNORE`) | 2 | `onCloseMydata` (`RDCRUISP.NSP:261-264`), `onCrdetClose` (`RDCRUISP.NSP:418-426`, replacement logic is commented out) | Unhandled events |
| Session end (`TERMINATE`) | 1 | `onExit` (`RDCRUISP.NSP:429-432`) | Out of process scope |

Reachability notes (static candidates, see `evidence/process-evidence.md` § *Control totals*):

| Finding | Evidence | Reading |
|---|---|---|
| 0 declared events lack an adapter branch | generator: *Declared in UI but not handled in adapter* = none | Every button on the page reaches a handler |
| `onQuestion`, `onExit` have no `method=` attribute | registered in the `DLMENU` dynamic menu, `RDCRUISP.NSP:77-78` | Reachable through the navigation bar (`menuprop="dlmenu"`, `rdcruisx.xml:92`), not a page control |
| `nat:page.end`, `onFacebook`, `onTwitter`, `onCloseMydata`, `onCrdetClose` have no `method=` attribute and no menu entry | generator: *Handled in adapter but neither declared in UI nor in the menu* | Unreachable from the page in analyzed scope; `nat:page.end` is a framework lifecycle event; the other four are presentation scaffolding candidates for retirement |
| Image loading is commented out | 6 `CALLNAT 'IMG-LOAD'` lines are comments, `RDCRUISP.NSP:85-91` | `IMG-LOAD` is presentation-only content infrastructure, unreferenced in executable scope; no business rule depends on it. Detail images instead come from `YACHT-PICTURE.PICTURE` through `MAKEURL` (`RDCRUISP.NSP:730-736`) |

## P1 — List cruises

**Trigger.** *Show all* (`onShowAll`) or one of the four favourite-harbour buttons (`onFav1button`…`onFav4button`). `onShowAll` clears the start-harbour filter (`RDCRUISP.NSP:323`); a favourite button copies its harbour constant into `P-SELETION.P-STARTHARBOR` (`RDCRUISP.NSP:333`, `342`, `351`, `360`). Both then `PERFORM SHOWALL` (`RDCRUISP.NSP:760-795`), which calls `CRLIST-N` (`RDCRUISP.NSP:765`).

**Service.** `CRLIST-N` (`SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CRLIST-N.NSN`) reads `NCCRUISE` descending by `START-DATE` (`:51`), skips fully booked cruises (`CRUISE-STATUS = 0`, `:53-57`), applies the optional start- and destination-harbour filters (`:59-64`), appends each surviving record to a dynamic output array with edited dates and prices (`:66-76`), resolves the yacht name from `NCYACHT` (`:79-83`), and ends with 9857 when nothing matched or 9807 otherwise (`:88-93`). `CAMSG-N` remaps 9807 to 0 so the adapter reads it as success (`CAMSG-N.NSN:136-138`).

**Transaction boundary.** None — read-only. No `UPDATE`, `STORE`, `END TRANSACTION` or `BACKOUT TRANSACTION` appears in `CRLIST-N` (generator § *Service summary*).

```mermaid
flowchart LR
  subgraph B["Browser (rdcruisx.xml)"]
    B1(["onShowAll / onFav1..4button"])
    B2[["Result panel with cruise rows"]]
    B3(("Alert text in PVMYTOPMAIL"))
  end
  subgraph A["NJX adapter (RDCRUISP.NSP)"]
    A1["Set or clear P-STARTHARBOR filter<br/>:323 / :333-360"]
    A2["PERFORM SHOWALL<br/>CALLNAT CRLIST-N :765"]
    A3{"P-RSPCODE = '0'?<br/>:767"}
    A4["Copy rows to LINES array<br/>show result panel :772-789"]
    A5["Compose code + text alert<br/>:791-792"]
  end
  subgraph S["Business service (CRLIST-N.NSN)"]
    S0{"#STUDENT?<br/>:41"}
    S1["READ NCCRUISE DESCENDING BY START-DATE<br/>:51"]
    S2{"CRUISE-STATUS = 0<br/>(fully booked)? :55"}
    S3{"Start-harbour filter set<br/>and mismatch? :59"}
    S4{"Destination filter set<br/>and mismatch? :62"}
    S5["Append row, edit dates and prices<br/>:66-76"]
    S6["Resolve yacht name<br/>:79-83"]
    S7{"C-RECCNT = 0?<br/>:89"}
    S8["MOVE 9807 → CAMSG-N remaps to 0<br/>:92, :96"]
    E1(("9857 no cruise data found"))
    E2(("9999 function not yet supported<br/>(#STUDENT=FALSE in shipped source)"))
  end
  subgraph D["ADABAS"]
    D1[("NCCRUISE")]
    D2[("NCYACHT")]
  end
  B1 --> A1 --> A2 --> S0
  S0 -- yes --> E2
  S0 -- no --> S1
  S1 --> D1
  D1 -- next record --> S2
  S2 -- yes: skip --> S1
  S2 -- no --> S3
  S3 -- yes: skip --> S1
  S3 -- no --> S4
  S4 -- yes: skip --> S1
  S4 -- no --> S5 --> S6 --> D2 --> S1
  S1 -- end of file --> S7
  S7 -- yes --> E1
  S7 -- no --> S8 --> A3
  E1 --> A3
  E2 --> A3
  A3 -- yes --> A4 --> B2
  A3 -- no --> A5 --> B3
  classDef err fill:#fde2e2,stroke:#b00020,stroke-width:2px
  classDef comp fill:#fff3cd,stroke:#b8860b,stroke-dasharray:4 2
  classDef commit fill:#d4edda,stroke:#1e7b34,stroke-width:2px
  classDef lane fill:#f7f9fc,stroke:#8a94a6
  classDef tx fill:#fffdf5,stroke:#b8860b,stroke-dasharray:6 3
  class B3,E1,E2 err
  class B,A,S,D lane
```

Traceability:

| Gateway / event | Source | Message code | Note |
|---|---|---|---|
| `#STUDENT` training switch | `CRLIST-N.NSN:41-43` | 9999 | `#STUDENT` is `INIT <FALSE>` in `SunnyIslands/Natural-Libraries/CRUISE16/Local Data Areas/NCDATA-L.NSL:86`; the branch is present in executable code but not taken with the shipped configuration |
| Fully booked | `CRLIST-N.NSN:53-57` | — | Skip, not an error: availability is a listing filter, not a validation |
| Start-harbour filter | `CRLIST-N.NSN:59-61` | — | Populated by the favourite buttons only |
| Destination filter | `CRLIST-N.NSN:62-64` | — | `P-DESTHARBOR` is declared in `NCCRUL-P` but never assigned by the adapter (declared but never assigned, `../10-migration-disposition-dead-code/evidence/disposition-evidence.md`); the gateway is always "no" in analyzed scope |
| No rows | `CRLIST-N.NSN:89-90` | 9857 | Only error end-event reachable from the page |
| Rows shown | `CRLIST-N.NSN:92`, `CAMSG-N.NSN:136-138` | 9807 → 0 | Informational code remapped to success |
| Presentation-only around P1 | `onFavorites` (`RDCRUISP.NSP:197-202`) opens the favourites panel without calling a service; the 30-row cap in `SHOWALL` (`RDCRUISP.NSP:785-789`) is a page-size rule, not a business rule | — | Candidate for retirement / HCM list paging |

## P2 — Cruise detail

**Trigger.** A result row (`lines.onpvLineClick`, `RDCRUISP.NSP:408-415`), one of the four offer tiles (`onShowdetails1`…`4`, `RDCRUISP.NSP:367-406`), or *Hot cruises* (`onHotcruises`, `RDCRUISP.NSP:189-195`), whose `INI-OFFERS` subroutine calls `CRGET-N` four times for hard-coded favourite cruise IDs (`RDCRUISP.NSP:827`, `857`, `887`, `917`). The row and tile paths `PERFORM FILL-CRUISEDETAILS` (`RDCRUISP.NSP:703-746`), which converts the selected ID with `VAL` (`:713`) and calls `CRGET-N` (`:716`).

**Service.** `CRGET-N` (`SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CRGET-N.NSN`) performs `READ (1) NCCRUISE BY CRUISE-ID = P-SELCRUISEID` (`:49`), copies harbours, dates and the three prices (`:55-71`), selects the price by duration (`:73-96`; the `NONE` branch defaults to the two-week price and the 9915 emit is commented out at `:93`), resolves yacht name and picture from `YACHT-PICTURE` (`:100-108`), and emits 9934 when no record was read (`:114-119`).

**Transaction boundary.** None — read-only.

```mermaid
flowchart LR
  subgraph B["Browser (rdcruisx.xml)"]
    B1(["lines.onpvLineClick / onShowdetails1..4 / onHotcruises"])
    B2[["Cruise detail panel: harbours, dates, yacht, price, image"]]
    B3(("Alert text in PVMYTOPMAIL"))
  end
  subgraph A["NJX adapter (RDCRUISP.NSP)"]
    A1["COMPRESS selected ID into V-SELCRID<br/>:369 / :410"]
    A2{"VAL(V-SELCRID) numeric?<br/>:713 (implicit — runtime error otherwise)"}
    A3["CALLNAT CRGET-N<br/>:716"]
    A4{"P-RSPCODE = '0'?<br/>:718"}
    A5{"PICTURELEN = 0?<br/>:730"}
    A6["Default image noyacht1.jpg<br/>:732"]
    A7["CALLNAT MAKEURL for picture<br/>:734"]
    A8["Compose code + text alert<br/>:740"]
  end
  subgraph S["Business service (CRGET-N.NSN)"]
    S1["READ (1) NCCRUISE BY CRUISE-ID = P-SELCRUISEID<br/>:49"]
    S2{"Record read?<br/>:114-116"}
    S3["Copy harbours, dates, prices<br/>:55-71"]
    S4{"Duration 7 / 14 / 21 days?<br/>:73-96"}
    S5["Price = 1W / 2W / 3W<br/>NONE → 2W"]
    S6["Resolve yacht name and picture<br/>:100-108"]
    S7["MSG-NR stays 0 → CAMSG-N → '0'<br/>:121-124"]
    E1(("9934 'customer changed from another user'<br/>misapplied text for cruise-not-found"))
  end
  subgraph D["ADABAS"]
    D1[("NCCRUISE")]
    D2[("YACHT-PICTURE / NCYACHT")]
  end
  B1 --> A1 --> A2
  A2 -- yes --> A3 --> S1 --> D1 --> S2
  S2 -- no --> E1 --> A4
  S2 -- yes --> S3 --> S4 --> S5 --> S6 --> D2 --> S7 --> A4
  A4 -- yes --> A5
  A5 -- yes --> A6 --> B2
  A5 -- no --> A7 --> B2
  A4 -- no --> A8 --> B3
  classDef err fill:#fde2e2,stroke:#b00020,stroke-width:2px
  classDef comp fill:#fff3cd,stroke:#b8860b,stroke-dasharray:4 2
  classDef commit fill:#d4edda,stroke:#1e7b34,stroke-width:2px
  classDef lane fill:#f7f9fc,stroke:#8a94a6
  classDef tx fill:#fffdf5,stroke:#b8860b,stroke-dasharray:6 3
  class B3,E1 err
  class B,A,S,D lane
```

Traceability:

| Gateway / event | Source | Message code | Note |
|---|---|---|---|
| Numeric selection | `RDCRUISP.NSP:713` | — | No explicit validation; the page supplies IDs from its own list, so the gateway is implicit. In an HCM this becomes a typed key, not an edit |
| Record read | `CRGET-N.NSN:49`, `:114-116` | 9934 | Two candidate findings for SME review: (a) the catalog text for 9934 is "Customer changed from another user" (`CAMSG-N.NSN:174-176`) — a semantic mismatch, the code is reused for cruise-not-found; (b) `READ (1) … BY CRUISE-ID = value` is a logical read starting at the key value, so a non-existent ID is expected to return the next higher cruise rather than 9934 (Natural `READ LOGICAL` semantics — confirm on the sample runtime before treating the 9934 path as reachable) |
| Duration → price | `CRGET-N.NSN:73-96` | 9915 (commented out, `:93`) | Inactive validation candidate: "only 1–3 weeks possible". The `NONE` branch silently defaults to the two-week price |
| Picture present | `RDCRUISP.NSP:730-736` | — | Presentation-only; `IMG-LOAD` calls that once populated page images are commented out (`RDCRUISP.NSP:85-91`) |
| `#STUDENT` | — | — | `CRGET-N` has no `#STUDENT` gate (generator § *Service summary*) |
| Presentation-only around P2 | `onCrdetClose` is `IGNORE` (`RDCRUISP.NSP:418-426`); the tiles carry hard-coded images (`RDCRUISP.NSP:370`, `381`, `391`, `401`) | — | Unhandled event; retire in HCM |

## P3 — Customer lookup, create, modify

Three sub-flows share one page panel and one adapter subroutine pair. Whether *Save* creates or modifies is decided by the session flag `G-LOGGEDIN` in `UPDATEMYDATA` (`RDCRUISP.NSP:610`, `:659`).

| Sub-flow | Trigger | Adapter | Service | Codes |
|---|---|---|---|---|
| Lookup (login) | `onLoginbutton` (`RDCRUISP.NSP:159-162`) | `CUSTLOGIN` `:489-568`, `CALLNAT 'CUGET-N'` `:514` | `CUGET-N.NSN` | 9923, 9924, 9999 |
| Create | `onMydataSave` with `G-LOGGEDIN = FALSE` | `UPDATEMYDATA` `:659-698`, `CALLNAT 'CUNEW-N'` `:672` | `CUNEW-N.NSN` | 9999 (no explicit success code) |
| Modify | `onMydataSave` with `G-LOGGEDIN = TRUE` | `UPDATEMYDATA` `:610-657`, `CALLNAT 'CUMOD-N'` `:626` | `CUMOD-N.NSN` | 9924, 9934, 9999 |

**Lookup.** `CUGET-N` (`SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CUGET-N.NSN`) tests whether the login identifier is numeric (`IS (N8)`, `:56`). If so it `FIND`s by `PERSON-ID` (`:58`) and emits 9924 when nothing is found (`:60-62`); otherwise it scans `NCCUSTOMER` sequentially comparing `EMAIL(1)` (`:69-74`) and emits 9923 when no e-mail matched (`:75-77`). On success `MOVE-DB-TO-PARA` (`:88-104`) returns the record including `FIRST-NAME-OLD` (`:96`) and the ADABAS `TIMESTAMP` (`:102`) that the modify flow later uses for optimistic concurrency. The adapter treats 9923 and 9924 alike as "customer not found" (`RDCRUISP.NSP:556-559`).

**Create.** `CUNEW-N` (`SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CUNEW-N.NSN`) reads the highest `PERSON-ID` descending (`:41`), issues a fake `UPDATE` to put that record on hold (`:42`), computes MAX+1 (`:43-44`), fills the new record (`:46-55`), `STORE`s it (`:56`) and commits (`END TRANSACTION`, `:57`). The hold on the highest record serialises concurrent creators — the same pattern `CONEW-N` uses for contract IDs.

**Modify.** `CUMOD-N` (`SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CUMOD-N.NSN`) `FIND`s the customer (`:44`), emits 9924 if absent (`:45-48`), compares the stored `TIMESTAMP` with the one the page received at login (`:50`), and only on a match writes the fields, refreshes the timestamp, `UPDATE`s and commits (`:53-64`); on a mismatch it emits 9934 and leaves the record unchanged (`:65-68`).

**Transaction boundary.** `CUNEW-N` and `CUMOD-N` each end with `END TRANSACTION`; neither contains `BACKOUT TRANSACTION` (generator § *Service summary*). Their `ON ERROR` blocks log and `ESCAPE ROUTINE` (`CUNEW-N.NSN:24-27`, `CUMOD-N.NSN:25-28`) without an explicit backout — release of the held record then depends on the session's next transaction end (candidate for SME confirmation; drawn as an implicit compensation below).

```mermaid
flowchart LR
  subgraph B["Browser (rdcruisx.xml)"]
    B1(["onLoginbutton"])
    B2(["onMydataSave"])
    B3[["Logged in: my-data icon, logout icon, GDA filled"]]
    B4(("Login alert: 9923 / 9924 → 'not found' text; other codes → code + text"))
    B5[["Customer stored or updated; GDA refreshed"]]
    B6(("My-data alert: code + text; original values restored on modify"))
  end
  subgraph A["NJX adapter (RDCRUISP.NSP)"]
    A1["CUSTLOGIN: COMPRESS PVLOGINIDENT → P-PERSON-ID<br/>:493-494, CALLNAT CUGET-N :514"]
    A2{"P-RSPCODE = '0'?<br/>:515"}
    A3["G-LOGGEDIN := TRUE, copy customer to GDA<br/>:519-535"]
    A4{"RSPCODE 9924 or 9923?<br/>:556"}
    A5{"G-LOGGEDIN?<br/>:610"}
    A6["Map page fields incl. FIRST-NAME-1,<br/>P-TIMESTAMP from GDA :614-623<br/>CALLNAT CUMOD-N :626"]
    A7["Map page fields incl. FIRST-NAME-1<br/>:663-669, CALLNAT CUNEW-N :672"]
    A8{"P-RSPCODE = '0'?<br/>:628 / :673"}
  end
  subgraph S["Business service (CUGET-N / CUNEW-N / CUMOD-N)"]
    G0{"#STUDENT?<br/>CUGET-N :50"}
    G1{"Login ID IS (N8)?<br/>CUGET-N :56"}
    G2["FIND NCCUSTOMER WITH PERSON-ID<br/>CUGET-N :58"]
    G3{"Record found?<br/>CUGET-N :60"}
    G4["READ NCCUSTOMER, compare EMAIL 1<br/>CUGET-N :69-74"]
    G5{"E-mail matched?<br/>CUGET-N :75"}
    G6["MOVE-DB-TO-PARA incl. FIRST-NAME-OLD, TIMESTAMP<br/>CUGET-N :88-104"]
    EG1(("9924 customer id not found"))
    EG2(("9923 'customer id missing'<br/>misapplied text for e-mail-not-found"))
    EG9(("9999 function not yet supported"))
    N0{"#STUDENT?<br/>CUNEW-N :34"}
    subgraph TN["Transaction scope — CUNEW-N"]
      N1["READ (1) NCCUSTOMER DESCENDING BY PERSON-ID<br/>UPDATE = fake update, record held :41-42"]
      N2["PERSON-ID := MAX+1; fill record incl. FIRST-NAME-OLD,<br/>BIRTH-DATE := VAL, TIMESTAMP :43-55"]
      N3["STORE NCCUSTOMER<br/>:56"]
      N4[/"END TRANSACTION<br/>:57"/]
    end
    N5{"Any record read?<br/>(empty file → loop body skipped)"}
    NE[\"ON ERROR: log, ESCAPE ROUTINE<br/>no explicit BACKOUT :24-27"\]
    M0{"#STUDENT?<br/>CUMOD-N :35"}
    subgraph TM["Transaction scope — CUMOD-N"]
      M1["FIND (1) NCCUSTOMER WITH PERSON-ID<br/>:44"]
      M2{"Record found?<br/>:45"}
      M3{"TIMESTAMP = P-TIMESTAMP?<br/>:50 (optimistic concurrency)"}
      M4["Write fields incl. FIRST-NAME-OLD,<br/>new *TIMESTMP, UPDATE :53-63"]
      M5[/"END TRANSACTION<br/>:64"/]
    end
    EM1(("9924 customer id not found"))
    EM2(("9934 customer changed from another user<br/>no update, no explicit backout"))
    ME[\"ON ERROR: log, ESCAPE ROUTINE<br/>no explicit BACKOUT :25-28"\]
  end
  subgraph D["ADABAS"]
    D1[("NCCUSTOMER")]
  end
  B1 --> A1 --> G0
  G0 -- yes --> EG9 --> A2
  G0 -- no --> G1
  G1 -- yes --> G2 --> D1 --> G3
  G3 -- no --> EG1 --> A2
  G3 -- yes --> G6
  G1 -- no --> G4 --> D1 --> G5
  G5 -- no --> EG2 --> A2
  G5 -- yes --> G6 --> A2
  A2 -- yes --> A3 --> B3
  A2 -- no --> A4
  A4 -- yes --> B4
  A4 -- no --> B4
  B2 --> A5
  A5 -- no: create --> A7 --> N0
  N0 -- yes --> EG9
  N0 -- no --> N1 --> D1 --> N5
  N5 -- yes --> N2 --> N3 --> D1 --> N4 --> A8
  N5 -- "no (returns '0' without STORE — candidate)" --> A8
  N1 -.-> NE -.-> A8
  A5 -- yes: modify --> A6 --> M0
  M0 -- yes --> EG9
  M0 -- no --> M1 --> D1 --> M2
  M2 -- no --> EM1 --> A8
  M2 -- yes --> M3
  M3 -- yes --> M4 --> D1 --> M5 --> A8
  M3 -- no --> EM2 --> A8
  M1 -.-> ME -.-> A8
  A8 -- yes --> B5
  A8 -- no --> B6
  classDef err fill:#fde2e2,stroke:#b00020,stroke-width:2px
  classDef comp fill:#fff3cd,stroke:#b8860b,stroke-dasharray:4 2
  classDef commit fill:#d4edda,stroke:#1e7b34,stroke-width:2px
  classDef lane fill:#f7f9fc,stroke:#8a94a6
  classDef tx fill:#fffdf5,stroke:#b8860b,stroke-dasharray:6 3
  class B4,B6,EG1,EG2,EG9,EM1,EM2 err
  class NE,ME comp
  class N4,M5 commit
  class B,A,S,D lane
  class TN,TM tx
```

Traceability:

| Gateway / event | Source | Message code | Note |
|---|---|---|---|
| Login ID numeric | `CUGET-N.NSN:56` | — | Selects ID lookup vs e-mail scan; the e-mail scan is a full sequential `READ` of `NCCUSTOMER` (`:69`), acceptable for the sample, a performance candidate at FPPS scale |
| Customer by ID not found | `CUGET-N.NSN:60-62` | 9924 | Adapter shows the generic login-alert text (`RDCRUISP.NSP:556-559`) |
| Customer by e-mail not found | `CUGET-N.NSN:75-77` | 9923 | Catalog text is "Customer Id missing" (`CAMSG-N.NSN:170-171`): misapplied text, same adapter handling as 9924 |
| Create — highest record held | `CUNEW-N.NSN:41-42` | — | Fake `UPDATE` serialises MAX+1 ID generation; analogous to serialised employee/contract numbering in a pay system |
| Create — empty file | `CUNEW-N.NSN:41-58` | — (returns '0') | Candidate: with an empty `NCCUSTOMER` the `READ (1)` loop body never runs, so nothing is stored yet the adapter reports success (`RDCRUISP.NSP:673-689`). Not reachable with the seeded synthetic data; `CONEW-N` has the equivalent guard (`CONEW-N.NSN:126-131`) |
| Create — birth date | `CUNEW-N.NSN:54` vs `CUMOD-N.NSN:59-61` | — | `CUNEW-N` applies `VAL` directly to `BIRTH-DATE`; `CUMOD-N` first strips `-` (`EXAMINE … DELETE`). A `YYYY-MM-DD` value from the page would raise a Natural runtime error on create and fall into `ON ERROR` — candidate defect for SME confirmation |
| Modify — record absent | `CUMOD-N.NSN:45-48` | 9924 | |
| Modify — timestamp mismatch | `CUMOD-N.NSN:50`, `:65-68` | 9934 | Optimistic concurrency; the adapter restores the original values on the page (`RDCRUISP.NSP:648-653`). This is the one place 9934 is used with its catalog meaning |
| Commit | `CUNEW-N.NSN:57`, `CUMOD-N.NSN:64` | — | Single `END TRANSACTION` per service; no `BACKOUT TRANSACTION` in either |
| First-name lineage | `RDCRUISP.NSP:619`, `:663` (page → `FIRST-NAME-1`); `CUNEW-N.NSN:48`, `CUMOD-N.NSN:53`, `CUGET-N.NSN:96` (persist/read `FIRST-NAME-OLD`); `NCDATA-L.NSL:56` (`FIRST-NAME-1` view commented out) | — | The page writes `FIRST-NAME-1` but the services persist and read `FIRST-NAME-OLD`; a first name typed on the page is not what is stored. Mapping/cleansing defect — carried into `process-to-hcm-mapping.md` |
| Presentation-only around P3 | `onLoginicon`, `onNewdataicon`, `onLoginClose`, `onLogouticon`, `onMydataicon`, `onMydataClose` toggle panels and reset GDA fields (`RDCRUISP.NSP:138-157`, `:177-187`, `:204-258`); `onCloseMydata` is `IGNORE` (`:261-264`) | — | Session and panel state; replaced by HCM security session and page navigation |
| `P-COM` credentials | `NCCOMM-P.NSA` (`P-LANG`, `P-USER`, `P-PASSWORD`) are passed on every `CALLNAT` but never assigned by the adapter (`RDCRUISP.NSP:514`, `:581`, `:626`, `:672`, `:716`, `:765`) | — | Legacy interface contract, not an authentication model; must not be copied into HCM security (see mapping document) |

## P4 — Book cruise

**Trigger.** *Book* on the detail panel (`onBookingSave`, `RDCRUISP.NSP:171-174`) → `UPDATEBOOKING` (`RDCRUISP.NSP:572-601`). If the session is not logged in the adapter stops with the login-alert text and calls no service (`:592-597`). Otherwise it builds `P-CONTRACT-DATA` from the session's customer and the displayed cruise (`:577-579`) and calls `CONEW-N` (`:581`).

**Service.** `CONEW-N` (`SunnyIslands/Natural-Libraries/CRUISE16/Subprograms/CONEW-N.NSN`) is the only service with both `END TRANSACTION` and `BACKOUT TRANSACTION` (generator § *Service summary*). Input edits (`:54-71`) precede any database access. The cruise is located with `FIND` (`:80`) and re-read on hold with `GET … *ISN(R1.)` (`:82`), so the availability test-and-set (`:84-92`) is atomic. The highest contract is read descending and put on hold with a fake `UPDATE` (`:96-97`) so MAX+1 (`:99`) is serialised. `HANDLE-INPUT-DATA` (`:151-162`) verifies the customer exists (9918). Only when the pending code is 9800 does the service `STORE` the contract and `END TRANSACTION` (`:115-118`); every other outcome after the hold is a `BACKOUT TRANSACTION` (`:122`, `:129`, `:134`) that releases the held cruise and contract records and undoes the decrement. `ON ERROR` also backs out (`:36-40`).

**Why the boundary matters.** This is the sample's analogue of a pay-run or personnel action: a held availability record (≈ position/encumbrance), a serialised contract number (≈ document/transaction number), and an all-or-nothing commit of the decrement plus the new contract. `../../docs/concurrency-refactor.md:45-76` and `:105-145` describe the race the holds close, and `tests/harness/natural_model.py:172-217` runs both the original and refactored variants against synthetic data.

```mermaid
flowchart LR
  subgraph B["Browser (rdcruisx.xml)"]
    B1(["onBookingSave"])
    B2[["Detail alert: contract-stored text + new contract ID"]]
    B3(("Detail alert: login required — no service call"))
    B4(("Detail alert: code + text"))
  end
  subgraph A["NJX adapter (RDCRUISP.NSP)"]
    A1{"G-LOGGEDIN?<br/>:575"}
    A2["P-CONTRACT-DATA ← GDA customer, displayed cruise<br/>:577-579; CALLNAT CONEW-N :581"]
    A3{"P-RSPCODE = '0'?<br/>:584"}
  end
  subgraph S["Business service (CONEW-N.NSN)"]
    S0{"#STUDENT?<br/>:48"}
    S1{"Customer ID blank or '0'?<br/>:55"}
    S2{"Cruise ID blank or '0'?<br/>:57"}
    S3{"Cruise ID IS (N8)?<br/>:60"}
    S4{"Customer ID IS (N8)?<br/>:66"}
    S5["FIND NCCRUISE WITH CRUISE-ID<br/>:80"]
    S6{"Cruise record found?<br/>:80-139 — FIND body runs only when found"}
    subgraph T["Transaction scope (compensation boundary)"]
      T1["GET NCCRUISE *ISN(R1.) — record held<br/>:82"]
      T2{"CRUISE-STATUS > 0?<br/>:86 (availability on held record)"}
      T3["CRUISE-STATUS := status − 1; UPDATE<br/>:89-92"]
      T4["READ (1) NCCONTRACT DESCENDING BY CONTRACT-ID<br/>UPDATE = fake update, record held :96-97"]
      T5["CONTRACT-ID := MAX+1; price ← PRICE-1W;<br/>booking date ← *DATN; cruise, customer :99-112"]
      T6["HANDLE-INPUT-DATA: MSG-NR := 9800<br/>FIND NCCUSTOMER :151-162"]
      T7{"Customer found?<br/>:158"}
      T8{"MSG-NR = 9800?<br/>:115"}
      T9["STORE NCCONTRACT<br/>:116"]
      T10[/"END TRANSACTION<br/>:117"/]
      T11{"LOCAL-NEWCONTRACTID = 0?<br/>:126 (empty contract file)"}
      C1[\"BACKOUT TRANSACTION<br/>:122 — undo decrement, release holds"\]
      C2[\"BACKOUT TRANSACTION<br/>:129 — release held cruise"\]
      C3[\"BACKOUT TRANSACTION<br/>:134 — undo decrement, release holds"\]
      C4[\"ON ERROR → BACKOUT TRANSACTION, ESCAPE ROUTINE<br/>:36-40"\]
    end
    S9["P-NEW-CONTRACTID ← new ID<br/>:118; CAMSG-N remaps 9800 → 0 :143"]
    E9(("9999 function not yet supported"))
    E1(("9904 customer id missing"))
    E2(("9905 cruise id missing"))
    E3(("9902 cruise no longer available"))
    E4(("9918 customer id not found"))
    E5(("code 0 without a stored contract —<br/>MSG-NR keeps INIT 0, NCDATA-L.NSL:78 (candidate defect)"))
  end
  subgraph D["ADABAS"]
    D1[("NCCRUISE")]
    D2[("NCCONTRACT")]
    D3[("NCCUSTOMER")]
  end
  B1 --> A1
  A1 -- no --> B3
  A1 -- yes --> A2 --> S0
  S0 -- yes --> E9 --> A3
  S0 -- no --> S1
  S1 -- yes --> E1
  S1 -- no --> S2
  S2 -- yes --> E2
  S2 -- no --> S3
  S3 -- no --> E2
  S3 -- yes --> S4
  S4 -- no --> E1
  S4 -- yes --> S5 --> D1 --> S6
  S6 -- no --> E5 --> A3
  S6 -- yes --> T1 --> T2
  T2 -- no --> C2 --> E3
  T2 -- yes --> T3 --> D1
  T3 --> T4 --> D2 --> T5 --> T6 --> D3 --> T7
  T7 -- no --> E4
  T7 -- yes --> T8
  E4 -.-> T8
  T8 -- yes --> T9 --> D2 --> T10 --> S9 --> A3
  T8 -- no --> C1
  C1 -.-> A3
  T4 -- "no record (empty file)" --> T11
  T11 -- yes --> C3 --> E3
  E1 --> A3
  E2 --> A3
  E3 --> A3
  T1 -.-> C4 -.-> A3
  A3 -- yes --> B2
  A3 -- no --> B4
  classDef err fill:#fde2e2,stroke:#b00020,stroke-width:2px
  classDef comp fill:#fff3cd,stroke:#b8860b,stroke-dasharray:4 2
  classDef commit fill:#d4edda,stroke:#1e7b34,stroke-width:2px
  classDef lane fill:#f7f9fc,stroke:#8a94a6
  classDef tx fill:#fffdf5,stroke:#b8860b,stroke-dasharray:6 3
  class B3,B4,E9,E1,E2,E3,E4,E5 err
  class C1,C2,C3,C4 comp
  class T10 commit
  class B,A,S,D lane
  class T tx
```

Traceability:

| Gateway / event | Source | Message code | Note |
|---|---|---|---|
| Logged in | `RDCRUISP.NSP:575`, `:592-597` | — (adapter text `G-LOGINALERTTXT`) | Adapter-side precondition; no service call. In HCM: security session / role check, not a business edit |
| `#STUDENT` | `CONEW-N.NSN:48-50` | 9999 | `INIT <FALSE>` (`NCDATA-L.NSL:86`); branch present, not taken in shipped configuration |
| Customer ID blank or '0' | `CONEW-N.NSN:55-56` | 9904 | Adapter always supplies the GDA customer ID, so the edit is unreachable from the page but reachable for any other caller of the service |
| Cruise ID blank or '0' | `CONEW-N.NSN:57-58` | 9905 | As above |
| Cruise ID `IS (N8)` | `CONEW-N.NSN:60-65` | 9905 | Same code as "missing"; the more specific 9917 "format of cruise id invalid" is cataloged but its emit is commented out (`:181`) |
| Customer ID `IS (N8)` | `CONEW-N.NSN:66-71` | 9904 | Same code as "missing"; 9919 "wrong format for customer id" cataloged, emit commented out (`:174`). Note the format checks do not stop execution — `FIND` at `:80` still runs with a zero key and finds nothing, so the pending code is returned |
| Cruise record found | `CONEW-N.NSN:80`, `:139` | 0 (no code) | Candidate defect, static evidence only: when the cruise id is well-formed but no `NCCRUISE` record matches, the `FIND` body is skipped, `MSG-NR` keeps its `INIT <0000>` (`NCDATA-L.NSL:78`), `CAMSG-N` types code 0 as success (`CAMSG-N.NSN:185-186`) and the adapter shows the contract-stored text with an unreset `P-NEW-CONTRACTID` (`RDCRUISP.NSP:584-586`). The cataloged 9916 "Cruise Id not found" is emitted only in commented code (`CONEW-N.NSN:184-188`). Reachable from the page only if the displayed cruise is deleted between detail and booking; runtime confirmation needed. HCM equivalent: a mandatory existence edit on the referenced object |
| Availability on held record | `CONEW-N.NSN:82-86` | 9902 (`:129-130`) | The `GET` places the record on hold before the test, closing the read-then-update race described in `../../docs/concurrency-refactor.md:45-76` |
| Contract ID serialised | `CONEW-N.NSN:96-99` | — | Fake `UPDATE` holds the highest contract; two concurrent bookings cannot compute the same MAX+1 |
| Customer exists | `CONEW-N.NSN:157-160` | 9918 | Checked after the decrement; the `ELSE` at `:119-122` backs the decrement out |
| Empty contract file | `CONEW-N.NSN:126-131` | 9902 | Defensive guard: releases the held cruise and undoes the decrement when `READ (1)` found no contract at all |
| Commit | `CONEW-N.NSN:115-118` | 9800 → 0 | `STORE` + `END TRANSACTION` + return new ID; `CAMSG-N.NSN:132-134` remaps 9800 to 0 |
| Runtime error | `CONEW-N.NSN:36-40` | — (no `CAMSG-N` call; `P-RSPCODE` left as passed in) | `ERRLOG-I` logs, `BACKOUT TRANSACTION`, `ESCAPE ROUTINE`; the adapter shows whatever code/text the response area held (`RDCRUISP.NSP:587-589`) |
| Inactive edits | `CONEW-N.NSN:164-211` (all comment lines) | 9800, 9915, 9919, 9917, 9916, 9914, 9913, 9912, 9911 | Nine commented-out emits (generator § *Commented-out message emits*); 9911/9913 hard-code the year window 2015–2020 (`CAMSG-N.NSN:65-71`, `:148-153`) — expired time-bound validation candidates |
| Presentation-only around P4 | `onBookingClose` (`RDCRUISP.NSP:232-238`) returns to the home panel | — | Retire |

## Cross-process observations for the HCM team

| Observation | Where seen | Consequence for extraction |
|---|---|---|
| One validation catalog, one choke point | Every service ends with `CALLNAT 'CAMSG-N'`; 31 cataloged codes, 11 emitted in executable lines, 7 remapped to success (`evidence/process-evidence.md`) | Message codes are the validation-rule inventory; `../02-*` owns the catalogue, this document owns where each code fires in the flow |
| Success is "code 0" | `CAMSG-N` resets 9800–9807 to 0; the adapter tests `P-RSPCODE = '0'` (`RDCRUISP.NSP:515`, `:584`, `:628`, `:673`, `:718`, `:767`) | HCM outcome model needs an explicit success/information/error type rather than a zero test |
| Read flows have no transaction boundary | `CRLIST-N`, `CRGET-N`, `CUGET-N` (generator § *Service summary*) | Map to HCM queries/reports; no approval or transaction flow needed |
| Write flows commit once | `CUNEW-N`, `CUMOD-N`: one `END TRANSACTION`, no `BACKOUT`; `CONEW-N`: one `END TRANSACTION`, four `BACKOUT TRANSACTION` | Only booking needs a compensation design in the HCM target; customer maintenance maps to a single-record save with optimistic locking |
| Language and credentials ride on `P-COM` but are never set | `NCCOMM-P.NSA`; disposition evidence *declared but never assigned* | German catalog texts (`CAMSG-N.NSN:17-99`) are unreachable from the page in analyzed scope; do not design HCM translations from the sample's language switch alone |
| Presentation scaffolding | 21 of 34 adapter branches never call a service; 6 commented `IMG-LOAD` lines; 2 `IGNORE` handlers; 5 handlers unreachable from the page | Retire; HCM pages own navigation, images and session state |

← [Back to the capability README](README.md) · [Navigation hub](../README.md)
