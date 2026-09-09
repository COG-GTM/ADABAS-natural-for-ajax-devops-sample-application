# Diagrams — requirements baseline

Mermaid source is the artifact of record; each `.mmd` file is reproduced below so the diagrams render on any Markdown viewer with Mermaid support. Rendered `.svg`/`.png` files, where present, were produced with `npx -y @mermaid-js/mermaid-cli -i <file>.mmd -o <file>.svg` from the same source. Labels carry the maturity tag: Demonstrated for what runs in this repository, Designed for the target-side steps an SI performs.

| File | Shows | Maturity |
|---|---|---|
| `requirement-coverage.mmd` | Which services feed which rule sections, which requirement classes carry them, which exclusions absorb the rest, and the HCM fit each class lands in | Demonstrated for source → rules → requirements; Designed for the HCM fit column |
| `traceability-view.mmd` | One thread each for the two integrity differentiators (capacity race, lost update): source line → rule → requirement → acceptance criteria → evidence today → target verification, with the generated check that binds them | Demonstrated for the booking thread (`tests/test_concurrency.py`); the customer thread is Designed until a `CUMOD-N` harness exists |

## Requirement coverage (`requirement-coverage.mmd`)

Reading left to right: seven Natural services produce four rule sections; the rule sections are carried by five requirement classes or by the exclusion list; each requirement class resolves to an HCM fit. Bold edges mark the integrity path — the requirements that exist only because the concurrency refactor was read as a requirement rather than as code to convert.

```mermaid
flowchart LR
    classDef src fill:#f5f5f5,stroke:#777,color:#000
    classDef rule fill:#fff4e5,stroke:#b26a00,color:#000
    classDef req fill:#e6f2ff,stroke:#1f4e99,color:#000
    classDef integ fill:#e3f2fd,stroke:#0d47a1,color:#000,stroke-width:2px
    classDef fit fill:#e9f7ef,stroke:#1e7e34,color:#000
    classDef excl fill:#fbe9e7,stroke:#b71c1c,color:#000

    subgraph S["Natural services (Demonstrated - shipped source)"]
        CONEW["CONEW-N booking<br/>9800 9902 9904 9905 9918 9999"]:::src
        CRLIST["CRLIST-N list<br/>9807 9857 9999"]:::src
        CRGET["CRGET-N detail<br/>9934 (misapplied)"]:::src
        CUGET["CUGET-N retrieve<br/>9923 9924 9999"]:::src
        CUNEW["CUNEW-N create<br/>0 9999"]:::src
        CUMOD["CUMOD-N modify<br/>9924 9934 9999"]:::src
        CAMSG["CAMSG-N catalogue<br/>31 codes, 11 emitted"]:::src
    end

    subgraph R["02 rule catalogue (Demonstrated)"]
        RA["BR-001..036 active"]:::rule
        RD["BR-D001..010 disabled"]:::rule
        RM["BR-M001..006 misapplied / silent"]:::rule
        RC["BR-C001..008 SME candidates"]:::rule
    end

    subgraph Q["05 requirements baseline"]
        F["REQ-F-001..007 functional"]:::req
        D["REQ-D-001..006 data"]:::req
        I["REQ-I-001..007 integrity<br/>(the rules a converter loses)"]:::integ
        X["REQ-X-001..004 interface"]:::req
        N["REQ-N-001..005 non-functional"]:::req
        W["what-we-will-not-build.md<br/>E-01..E-08"]:::excl
    end

    subgraph H["HCM fit (Designed - SI configures)"]
        STD["standard: element-entry and<br/>person validation, lookups,<br/>audit reports, language packs"]:::fit
        CFG["configured: fast formula,<br/>value set"]:::fit
        INT["integration: REST / HDL contracts"]:::fit
    end

    CONEW --> RA
    CRLIST --> RA
    CRGET --> RA
    CUGET --> RA
    CUNEW --> RA
    CUMOD --> RA
    CAMSG --> RA
    CONEW -. commented 9911-9919 .-> RD
    CRGET -. commented 9915 .-> RD
    CRGET -. 9934 on not found .-> RM
    CONEW -. no 9916 edit .-> RM
    CUGET -. 9923 on not found .-> RM
    RA --> F
    RA --> D
    RA ==> I
    RA --> X
    RA --> N
    RD --> W
    RM --> I
    RM --> F
    RC --> D
    RC --> F
    RC --> W
    F --> STD
    D --> STD
    I ==> STD
    F --> CFG
    D --> CFG
    N --> STD
    X --> INT
```

## Traceability view (`traceability-view.mmd`)

Two threads through the same chain. The first is fully Demonstrated: the defect and the fix both execute in `../../../tests/test_concurrency.py`. The second stops at "harness needed": the rule and the requirement are cited to source, the acceptance criteria are written, but no interleaving harness exists for `CUMOD-N` yet. The dotted node is `../../02-business-rule-extraction/generate_rule_evidence.py --check`, which fails if any link in either thread is broken.

```mermaid
flowchart TD
    classDef src fill:#f5f5f5,stroke:#777,color:#000
    classDef rule fill:#fff4e5,stroke:#b26a00,color:#000
    classDef req fill:#e6f2ff,stroke:#1f4e99,color:#000
    classDef test fill:#e9f7ef,stroke:#1e7e34,color:#000
    classDef gap fill:#fbe9e7,stroke:#b71c1c,color:#000
    classDef chk fill:#ede7f6,stroke:#4527a0,color:#000

    L1["Source line<br/>CONEW-N.NSN:82-92 (Demonstrated)"]:::src
    L2["Rule<br/>BR-006 test-and-set on the held offering record<br/>confidence 0.95 (S+C+H+D)"]:::rule
    L3["Requirement<br/>REQ-I-001 capacity is decremented atomically under contention<br/>HCM fit: standard - disposition: carry"]:::req
    L4["Acceptance criteria<br/>AC-REQ-I-001-1..3 (Given / When / Then)"]:::req
    L5["Executable evidence today<br/>tests/test_concurrency.py:24-45 (defect)<br/>tests/test_concurrency.py:68-97 (fix)"]:::test
    L6["Target verification (Designed)<br/>two concurrent element-entry submissions<br/>against a balance of 1"]:::test

    L1 --> L2 --> L3 --> L4
    L4 --> L5
    L4 --> L6

    M1["Source line<br/>CUMOD-N.NSN:50-52, 65-68 (Demonstrated)"]:::src
    M2["Rule<br/>BR-032 optimistic version check - 9934<br/>confidence 0.60 (S+D)"]:::rule
    M3["Requirement<br/>REQ-I-004 lost-update protection on customer data<br/>HCM fit: standard - disposition: carry"]:::req
    M4["Acceptance criteria<br/>AC-REQ-I-004-1..2"]:::req
    M5["Harness needed<br/>interleaving harness for CUMOD-N (Designed)"]:::gap
    M6["Target verification (Designed)<br/>object-version mismatch returns a conflict"]:::test

    M1 --> M2 --> M3 --> M4
    M4 --> M5
    M4 --> M6

    C["generate_rule_evidence.py --check (Demonstrated)<br/>every citation resolves - every BR is carried or excluded -<br/>every REQ has a criterion - matrix and baseline links agree"]:::chk
    C -.- L2
    C -.- L3
    C -.- L4
    C -.- M2
    C -.- M3
    C -.- M4
```

## Reproduce the renders

```bash
cd fpps-hcm-modernization-deliverable/05-requirements-baseline/diagrams
for f in *.mmd; do
  npx -y @mermaid-js/mermaid-cli -i "$f" -o "${f%.mmd}.svg"
  npx -y @mermaid-js/mermaid-cli -i "$f" -o "${f%.mmd}.png"
done
```

## Synthetic data and scope

Both diagrams describe the Sunny Islands Cruise sample and the artifacts in this deliverable; no production system or production data is involved. The HCM-fit column is the analogy an SI applies, not an observation.

← [Back to the directory README](../README.md) · [Navigation hub](../../README.md)
