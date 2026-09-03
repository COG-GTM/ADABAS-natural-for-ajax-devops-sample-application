# Disposition taxonomy

The ledger classifies every finding twice: by **what kind of thing it is** (the finding class) and by **what kind of evidence supports it** (the evidence class). The two axes are independent; a finding can be a high-confidence *commented-out logic* item or a low-confidence one depending on the evidence behind it. The classes are chosen so that a payroll SI can map each one to a scope decision without reading Natural.

## Finding classes

| Class | Definition | Detected in the sample by | Default disposition | Payroll analog |
|---|---|---|---|---|
| Dead interface contract | Parameter fields every service accepts and no caller ever sets or reads | PDA field population (assignments = 0, reads = 0) | do not map | Userid/password parameters on batch calls that a security layer replaced years ago |
| Unreachable by integration gap | Logic that exists and would run if a caller set a value, but no caller ever does | PDA field population (assignments = 0, reads > 0) | decide (intent may be real) | An edit path whose control flag the front-end never sets |
| Implemented but unreferenced | Objects, message codes, or copycode with no static reference from any analyzed object | Call graph; message-catalogue reconciliation | retire candidate | Orphaned Natural subprograms; edit messages nobody raises |
| Time-bombed rule | Literals that were valid only for a period (years, rates, thresholds) | Marker and literal scan; commented-out message emissions | never re-implement literally | Hard-coded pay-year or rate tables |
| Commented-out logic | Executable statements that are present only as comments | Comment scan | candidate rule only | Edits disabled "temporarily" and never re-enabled |
| Data-lineage defect | A value captured by the page that never reaches the record it is meant for | DDM field usage cross-checked against page bindings | correct, then map | A half-migrated field rename that leaves two columns |
| Misapplied rule | An outcome reported with a message that means something else | Source reading, confirmed by the conformance tests | correct, then map | The wrong edit message on a pay transaction |
| Unused data | DDM fields no executable statement reads or writes through any view | DDM field usage | profile, then decide | Dormant master-record fields |
| Operational utility | Programs that maintain the database rather than implement business behaviour | Standalone-program detection (no UI path) | replace with platform | DBA fix-it utilities |
| Inactive presentation utility | Presentation helpers whose only call sites are commented out | Call graph plus comment scan | retire | Dead report or print routines |
| Presentation or content infrastructure | Code that exists to serve one channel (page, image, URL, work file) | Library and object-type classification | out of scope for requirements | Screen-handling and print-spool code |
| Training or exercise scaffolding | Constants, gates, and comments that exist because the sample is a course exercise | Marker scan; constant analysis | exclude | Training-region toggles |
| Unimplemented interface field | Fields declared "not yet used" or reserved for an exercise | Marker scan; PDA population | exclude | Reserved fields in copybooks |
| Unused data item or dead statement | Level-1 variables never referenced; blocks that can never execute | Variable usage; source reading | ignore | Working-storage clutter |
| Unused data area | Parameter or local data areas with no `USING` reference | Call graph (`USING` edges) | retire | Unused PDAs and LDAs |
| Dead copycode | Copycode whose every statement is a comment | Comment scan on `INCLUDE`d objects | record the gap; platform concern | Commented-out audit hooks |
| UI scaffolding | Literals and handlers in the page adapter that carry no business meaning | Source reading of the adapter | exclude | Screen-level hard-coding |
| Keep: converter-fragile logic | Behaviour an HCM must preserve and a source-to-source converter loses | Concurrency harness (`../../tests/test_concurrency.py`) | requirement; HCM native | Pay-run integrity |

## Evidence classes

| Class | Meaning | Confidence it supports alone | What raises it |
|---|---|---|---|
| S1 | No static reference from any analyzed object (`CALLNAT` / `FETCH` / `INCLUDE` / `USING`) | Medium — the analyzed scope is partial by definition | Natural Predict/XRef across the whole estate; dynamic-call scan; runtime trace (R1) |
| S2 | Interface field declared but never assigned by any analyzed caller | High within scope | XRef on every caller of the PDA; R1 |
| S3 | Catalogued value never produced by executable code | High within scope | XRef on the catalogue; R1 |
| S4 | Statement present only as a comment | High (the statement cannot run) | SME decision on whether the intent survives (R2) |
| S5 | Literal, marker, or gate identifying training, sample, or channel scaffolding | High | R2 |
| S6 | Executable logic contradicting its surrounding contract | High (confirmed by executing tests where possible) | R2 on the corrected requirement |
| R1 | Runtime trace, profiler, or ADABAS command log showing the path did or did not execute over a representative period | Raises any S-class to High | Coverage of at least one full processing cycle (for FPPS: a full pay year including year-end) |
| R2 | SME confirmation and a signed decision | Closes the row | — |

## How the two axes map to verification

Static evidence answers *consistency* (does the code agree with itself) and *completeness* (is everything declared also used). Runtime and SME evidence answer *correctness* (does the behaviour still matter). Every ledger row starts with an S-class and a **Proposed** status; it moves to **Confirmed** only with R1 or R2, which is why the SME-required column exists.

```
  S1..S6  static candidate ──► R1 runtime evidence ──► R2 SME decision ──► Confirmed
     │                              │                        │
     │ (analyzed scope only)        │ (representative cycle) │ (signed)
     ▼                              ▼                        ▼
  "unreferenced in scope"      "never executed"         "retire" / "keep"
```

← [Back to the disposition capability](README.md)
