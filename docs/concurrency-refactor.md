# CONEW-N Concurrency Refactor

`CONEW-N` (library `CRUISE16`) creates a booking contract. The original
implementation contained two defects that only appear when several users book
at the same time on a multi-user ADABAS system. This document explains why
the original pattern fails, how the refactor resolves it, and how the
regression suite proves both.

All existing message-code behavior (9800, 9902, 9904, 9905, 9918, 9999) is
preserved; only the record-access pattern changed.

## Defect 1 — race condition on `NCCRUISE.CRUISE-STATUS`

`CRUISE-STATUS` (A1) holds the number of free places. The original code
copied it into a local variable, decided on the copy, and only then updated:

```natural
FIND NCCRUISE WITH NCCRUISE.CRUISE-ID = ID-CRUISE-IN-N
  COMPUTE LOCAL-AVAIL = VAL(NCCRUISE.CRUISE-STATUS)   /* unheld read
  IF LOCAL-AVAIL GT 0
    LOCAL-AVAIL := LOCAL-AVAIL - 1
    NCCRUISE.CRUISE-STATUS := LOCAL-AVAIL
    UPDATE (R1.)                                      /* hold comes too late
```

The decision ("is a place left?") and the write ("one place fewer") are not
atomic. Two sessions can both read the same value before either writes:

```
 Time   Session A                     Session B
 ----   ---------------------------   ---------------------------
  t1    read CRUISE-STATUS = "1"
  t2                                  read CRUISE-STATUS = "1"
  t3    check 1 > 0  -> book!
  t4                                  check 1 > 0  -> book!
  t5    write CRUISE-STATUS = "0"
  t6    STORE contract, ET
  t7                                  write CRUISE-STATUS = "0"   << lost update
  t8                                  STORE contract, ET

 Result: ONE free place, TWO contracts. The cruise is overbooked and
         the second decrement is silently lost (status "0", not "-1").
```

### Fix — test-and-set on a held record

The refactor re-reads the record **in hold** with `GET` before testing
availability. Because the `UPDATE` references the `GET` label, ADABAS places
the record in hold at `GET` time; a second session's `GET` waits in the hold
queue until the first session ends its transaction:

```natural
R1.
FIND NCCRUISE WITH NCCRUISE.CRUISE-ID = ID-CRUISE-IN-N
  G1.
  GET NCCRUISE *ISN(R1.)   /* re-read in hold: fresh CRUISE-STATUS
  COMPUTE LOCAL-AVAIL = VAL(NCCRUISE.CRUISE-STATUS)
  IF LOCAL-AVAIL GT 0
    LOCAL-AVAIL := LOCAL-AVAIL - 1
    NCCRUISE.CRUISE-STATUS := LOCAL-AVAIL
    UPDATE (G1.)
```

```
 Time   Session A                     Session B
 ----   ---------------------------   ---------------------------
  t1    GET (hold) STATUS = "1"
  t2                                  GET -> record in hold: WAITS
  t3    check, decrement, UPDATE
  t4    STORE contract, ET  ----+
  t5                            +-->  GET resumes, reads STATUS = "0"
  t6                                  check 0 > 0 fails -> MSG 9902

 Result: ONE free place, ONE contract, second user correctly told
         "Cruise no longer available" (9902).
```

## Defect 2 — duplicate `CONTRACT-ID` generation

The original code computed the next contract ID from an **unheld** read of
the highest existing ID:

```natural
READ (1) NCCONTRACT DESCENDING BY NCCONTRACT.CONTRACT-ID
  LOCAL-NEWCONTRACTID := NCCONTRACT.CONTRACT-ID +1    /* unheld MAX+1
```

`CONTRACT-ID` is a descriptor (search key), not a unique index enforced by
the nucleus, so two sessions that read the same MAX both store the same ID:

```
 Time   Session A                     Session B
 ----   ---------------------------   ---------------------------
  t1    READ(1) DESC -> MAX = 500100
  t2                                  READ(1) DESC -> MAX = 500100
  t3    new ID := 500101
  t4                                  new ID := 500101
  t5    STORE contract 500101, ET
  t6                                  STORE contract 500101, ET   << duplicate key

 Result: two NCCONTRACT records with CONTRACT-ID 500101; every later
         FIND by CONTRACT-ID is ambiguous.
```

### Fix — hold the highest record while generating the ID

The refactor applies the idiom already used by `CUNEW-N` for `PERSON-ID`:
a "fake" `UPDATE` inside the `READ (1) ... DESCENDING` loop, which puts the
highest contract record in hold before MAX+1 is computed:

```natural
R2.
READ (1) NCCONTRACT DESCENDING BY NCCONTRACT.CONTRACT-ID
  UPDATE (R2.)     /* fake update: hold the highest contract record
  LOCAL-NEWCONTRACTID := NCCONTRACT.CONTRACT-ID +1
```

```
 Time   Session A                     Session B
 ----   ---------------------------   ---------------------------
  t1    READ(1)+hold MAX = 500100
  t2                                  READ(1) -> record in hold: WAITS
  t3    new ID := 500101, STORE, ET --+
  t4                                  +--> resumes, reads MAX = 500101
  t5                                  new ID := 500102, STORE, ET

 Result: unique, gap-free contract IDs under any level of concurrency.
```

The hold is released by the same `END TRANSACTION` that commits the new
contract (or by `BACKOUT TRANSACTION` on any failure), so ID generation and
contract storage are one atomic unit.

## Transaction boundaries (unchanged)

* Success path: `STORE NCCONTRACT` → `END TRANSACTION` (commits the status
  decrement and the new contract together, releases all holds).
* Failure path (e.g. 9918 customer not found): `BACKOUT TRANSACTION`
  (undoes the buffered decrement, releases all holds — no partial booking).
* `ON ERROR` block: `BACKOUT TRANSACTION` before escaping, so an abend never
  leaves a half-booked state or dangling holds.
* Empty-file guard: if `NCCONTRACT` contains no records, the `READ (1)` loop
  body never executes, so neither `END TRANSACTION` nor `BACKOUT TRANSACTION`
  would run while the cruise record sits in hold with a buffered decrement.
  A guard after `END-READ` (`IF LOCAL-NEWCONTRACTID = 0` → `BACKOUT
  TRANSACTION` + `MSG-NR = 9902`) releases the hold, discards the decrement,
  and reports a defined failure code instead of a silent empty success.
  Unreachable with the seeded sample data, but defensive against an empty
  contract file.

## Root-cause survey of the codebase

Per root-cause methodology, all record-modifying objects were surveyed for
the same two patterns:

| Object | Pattern | Verdict |
|--------|---------|---------|
| `CONEW-N` | unheld read-then-decide on `CRUISE-STATUS`; unheld MAX+1 on `CONTRACT-ID` | **both defects — fixed here** |
| `CUNEW-N` | MAX+1 on `PERSON-ID` with fake `UPDATE` hold | already safe (source of the idiom) |
| `CUMOD-N` | `FIND` + `UPDATE` inside the same loop (record held at read) | safe |
| `CRLIST-N`, `CRGET-N`, `CUGET-N`, `CA3900-N` | read-only | not affected |

## How the regression suite proves it

CI has no ADABAS nucleus, so `tests/harness/adabas_sim.py` models the record
hold/ET/BT semantics and `tests/harness/natural_model.py` ports both the
original and refactored logic. `tests/test_concurrency.py` interleaves two
sessions at the exact vulnerable statement boundaries and asserts:

* original logic: last slot is overbooked, duplicate contract IDs occur;
* refactored logic: the competitor is forced to wait in the hold queue,
  gets 9902 after the last slot is taken, and IDs stay unique;
* N+1 attempts against N slots yield exactly N × 9800 and the rest 9902.

`tests/test_source_conformance.py` additionally parses `CONEW-N.NSN` itself
and asserts the `GET`-in-hold, the fake `UPDATE (R2.)`, the transaction
boundaries, and the exact message-code set — so the shipped Natural source
cannot silently regress.
