# CONEW-N Retry / Concurrency Re-architecture

`CONEW-N` (library `CRUISE16`) has two race points, both closed today by
**hold-and-wait** (see [concurrency-refactor.md](concurrency-refactor.md)):

| # | Race point | Current-state protection | Rule |
|---|------------|--------------------------|------|
| R1 | Decrement of `NCCRUISE.CRUISE-STATUS` | `GET NCCRUISE *ISN(R1.)` re-reads the record in hold; `UPDATE (G1.)` writes the buffered decrement (`CONEW-N.NSN:79-92`) | BR-006 |
| R2 | `NCCONTRACT.CONTRACT-ID` = MAX+1 | "fake" `UPDATE (R2.)` inside `READ (1) ... DESCENDING` holds the highest contract while the id is computed (`CONEW-N.NSN:95-102`) | BR-007 |

Hold-and-wait is correct, but it has no *retry strategy*: a session that
meets a held record simply waits in the ADABAS hold queue for as long as
the holder keeps its transaction open. There is no bounded wait, no defined
outcome for "could not be serialised", and the only re-drive in the
repository today is the test that re-invokes the model after the first
session commits (`tests/test_concurrency.py:88-92`).

This document compares five re-architecture options, recommends a
target-state approach, and points at the executable models and tests that
make each option provable in the Python harness. **Nothing here changes the
shipped Natural source**: `CONEW-N.NSN`, its message codes and
`tests/harness/natural_model.py:conew_refactored` (the current-state model)
are unchanged. Every option is implemented as a *separate* model function
so current-state and target-state behaviour can be compared side by side.

Message-code contract that every option must preserve:

| Code | Meaning | Emitted by | Must stay |
|------|---------|-----------|-----------|
| 9800 → 0 | booking successful (CAMSG-N remaps to response 0) | success path | yes |
| 9902 | cruise no longer available (sold out, empty-file guard) | R1 `ELSE`, guard | yes |
| 9904 / 9905 | customer / cruise identifier edit failed | `DECIDE` block | yes |
| 9918 | customer not found (after `BACKOUT`) | customer edit | yes |
| 9999 | unspecified error (`ON ERROR`) | abend path | yes |

## Vocabulary used below

```
 ET   END TRANSACTION       commits buffered updates, releases every hold
 BT   BACKOUT TRANSACTION   discards buffered updates, releases every hold
 hold queue                 sessions waiting for a held record, in arrival order
 re-drive                   run the whole read-check-decrement-store again
 attempt budget             maximum number of re-drives (or of hold-queue parks)
 guard                      the value a conditional update requires to still hold
```

The harness is single-threaded and deterministic. "Concurrency" is an
explicit interleaving: a session either raises `RecordHeldError` (the
existing behaviour), or — when submitted through `AdabasSim.submit` — is
*parked* on a `WaitTicket` and re-driven when the holder issues ET/BT.
Because the simulation never blocks, both a hold-queue timeout and a
wait-for cycle (deadlock) are surfaced as typed outcomes
(`HoldTimeoutError`, `DeadlockError`) instead of a hung test.

---

## Option 1 — Bounded blocking wait (current hold-and-wait) + explicit hold-queue timeout

**How it works.** Keep the pessimistic `GET`-in-hold and fake-`UPDATE`
serialisation exactly as shipped. Add a wait budget: a session that lands
in the hold queue is granted the record when the holder ends its
transaction (FIFO), but if it has been re-parked more than *N* times it is
abandoned with BT and a defined message code.

```
 Time   Holder (user1)                Waiter (user2)
 ----   ---------------------------   ----------------------------------
  t1    GET NCCRUISE  -> held
  t2                                  GET NCCRUISE  -> PARKED (wait 1 of N)
  t3    STORE, ET     -> releases
  t4                                  resumes: GET -> held, status re-read
  t5                                  0 places -> BT, 9902     (or books)
```

| Aspect | Mapping |
|--------|---------|
| R1 capacity | unchanged: test-and-set on the held record |
| R2 MAX+1 | unchanged: serialised behind the fake `UPDATE (R2.)` |
| Pros | smallest delta from production; FIFO fairness comes from the hold queue; no lost updates by construction |
| Cons | throughput is bounded by the longest-held transaction; both hotspots stay hotspots (every booking on every cruise queues on the single highest `NCCONTRACT` record); a wait budget still needs a message when it is spent |
| Failure modes | starvation is impossible while FIFO holds; a waiting session keeps the holds and buffered writes it already has (that is what "hold-and-wait" means — a booking parked on the highest `NCCONTRACT` record still owns its cruise record), so deadlock is possible if two sessions take the two hotspots in opposite order — `CONEW-N` avoids this by always taking `NCCRUISE` before `NCCONTRACT`; a timeout must BT before returning or the cruise hold leaks |
| Message codes | 9800/9902/9904/9905/9918/9999 unchanged. Timeout returns **9902 by default** (the customer sees "not available"); optionally a new code `9936` "booking busy, try again" *if* the catalogue is extended — see [Message-code impact](#message-code-impact) |

Harness: `AdabasSim(wait_limit=N)`, `AdabasSim.submit`, `WaitTicket`,
`HoldTimeoutError`, `DeadlockError` (`tests/harness/adabas_sim.py`);
`conew_hold_and_wait` is the booking body for this mode and
`booking_outcome` translates a finished ticket into a `BookingResult`
(`tests/harness/natural_model.py`). Tests: `tests/test_retry.py`
`HoldQueueWaitTests`.

`conew_hold_and_wait` has `conew_refactored`'s statements in
`conew_refactored`'s order; the two differ only in what a hold conflict
does. `conew_refactored` treats it as a response to the program — BT,
then `RecordHeldError` to the caller — which ends the transaction *before*
the session could be parked; wrapped in `submit` that is a BT + re-drive
(Option 3 semantics), not a wait. `conew_hold_and_wait` leaves the
conflict to the nucleus: `submit` parks the session with its transaction
open, so a booking blocked at R2 still owns its cruise record and its
buffered decrement, and the resumed run finishes that same transaction
(one ET, no BT, one decrement —
`test_parked_waiter_keeps_its_open_transaction_and_resumes_it`; the kept
hold is what a third session runs into, and what the timeout's BT has to
release — `test_bounded_wait_gives_up_after_repeated_reparking`).

## Option 2 — Optimistic concurrency with retry loop (compare-and-swap on CRUISE-STATUS)

**How it works.** Read `CRUISE-STATUS` *without* a hold, decide on the
copy, then write a *conditional* update whose guard is the value that was
read ("set status to 1 only if it is still 2"). If the guard is stale, or
the record is momentarily held, re-read and try again up to *N* attempts;
after the cap return 9902.

```
 Time   Session A                      Session B
 ----   ----------------------------   -----------------------------------
  t1    read status "2" (no hold)
  t2                                   read status "2" (no hold)
  t3    swap "2" -> "1"  OK
  t4    STORE, ET
  t5                                   swap "2" -> "1"  STALE (now "1")
  t6                                   re-read "1", swap "1" -> "0"  OK
  t7                                   STORE, ET
```

| Aspect | Mapping |
|--------|---------|
| R1 capacity | guarded update replaces test-and-set-under-hold; the guard *is* the check, so a lost update cannot happen |
| R2 MAX+1 | untouched — the fake-`UPDATE` hold is still needed unless combined with Option 4 |
| Pros | no hold across the decision; readers never block; under low contention one round trip |
| Cons | Natural has no native compare-and-swap; the guard must be implemented as re-read-in-hold + compare + `UPDATE` (a short hold) or as an ADABAS conditional command; under high contention on one cruise the loop spins and *late arrivals can starve* (no ordering) |
| Failure modes | livelock on a hot cruise; a guard that compares an `A1` string needs exact normalisation; the retry loop must BT between attempts or the swap's short hold leaks; the guard protects *only* the guarded field — every other value the contract copies from the cruise (`PRICE-1W`) must be re-read under the swap's hold, not taken from the unheld snapshot, or a concurrent re-pricing is booked at the old price |
| Message codes | unchanged; exhaustion → 9902 (or 9936 by opt-in) |

Harness: `Session.update_if` (`tests/harness/adabas_sim.py`), model
`conew_optimistic` (`tests/harness/natural_model.py`). Tests:
`tests/test_retry.py` `OptimisticRetryTests`.

## Option 3 — Application-level retry loop around the whole transaction (BT + re-drive)

**How it works.** Treat *any* serialisation signal — record held, hold
timeout, deadlock, stale guard — as "this transaction must be redone".
`BACKOUT TRANSACTION`, optionally back off with jitter, and re-run the
*entire* read-check-decrement-store sequence. Stop after *N* attempts with a
defined outcome. The existing `conew_refactored` is the body of each
attempt; nothing inside it changes.

```
        ┌──────────────────────────────────────────────┐
        │ attempt k (k = 1..N)                          │
        │  validate → GET cruise (hold) → check/decr    │
        │  → READ(1) DESC contract (hold) → MAX+1       │
        │  → customer check → STORE → ET               │
        └──────────────┬───────────────────────────────┘
        ok / 9902 / 9918 ───────► return (no retry: business outcome)
        held / timeout / deadlock ► BT ─► backoff ─► k+1
        k = N exhausted ──────────► BT ─► 9902 (or 9936), attempts = N
        abend (ON ERROR) ─────────► BT ─► propagate (never retried)
```

| Aspect | Mapping |
|--------|---------|
| R1 capacity | each attempt still uses the held test-and-set; retry only decides *whether to queue again* |
| R2 MAX+1 | each attempt recomputes MAX+1 under the fake-`UPDATE` hold, so a re-drive never reuses an id computed in a backed-out attempt |
| Pros | orthogonal to Options 1/2/4/5 (wraps any body); BT between attempts guarantees no partial state and no leaked hold; naturally hosts an idempotency key |
| Cons | re-does validation and reads on every attempt; the correct retryable set must be chosen (a 9902/9918 *business* outcome must not be retried); needs an idempotency key or a re-drive after a lost ET acknowledgement can double-book |
| Failure modes | retrying a business outcome (double 9918 side effects); re-driving after a successful ET (double booking) — mitigated by the request ledger; two *concurrent* submits of the same request id (a client double-submit) — the ledger row must be claimed under a lock and unique at commit, or both book; a re-used request id carrying *different* inputs — the ledger entry must be bound to the request's inputs or the wrong booking is replayed as if it were the new one (`RequestMismatchError`); a ledger entry written outside the booking's ET (or filled in after it) — a concurrent waiter would read an incomplete outcome; unbounded jitter hiding a hot spot |
| Message codes | unchanged; exhaustion → 9902 by default (`exhausted_msg`), 9936 by opt-in; 9999 abends propagate after BT |

Harness: `retry_on_hold`, `RetryBudgetExhausted`, request ledger
(`Session.record_request` / `Session.completed_request`) in
`tests/harness/adabas_sim.py`; model `conew_with_retry` in
`tests/harness/natural_model.py`. Tests: `tests/test_retry.py`
`BoundedRetryTests`.

## Option 4 — Eliminate the MAX+1 race entirely

**How it works.** Stop deriving `CONTRACT-ID` from the data. The platform
issues the identifier (a database sequence / identity column, a GUID, or —
in the HCM target — the object's system-generated key plus an HDL source
key). The `READ (1) ... DESCENDING` + fake `UPDATE (R2.)` block disappears,
and with it the single hottest record in the system (every booking on
*every* cruise queues on the same highest contract row today).

```
 current:  every booking ──► hold highest NCCONTRACT ──► MAX+1 ──► STORE
                             (one global serialisation point)

 target:   every booking ──► id := next-value(sequence) ──► STORE
                             (no shared row, no hold, no retry)
```

| Aspect | Mapping |
|--------|---------|
| R1 capacity | not addressed — combine with Option 1, 3 or 5 |
| R2 MAX+1 | removed; uniqueness becomes a platform guarantee (REQ-I-002 "the MAX+1 idiom is not carried") |
| Pros | removes one of the two hotspots and the empty-file guard (BR-013) with it; identifiers stay unique under any interleaving; no message-code change |
| Cons | ids are no longer dense/monotonic (a gap appears when an attempt backs out after drawing a value) — any downstream that *sorts by* or *reports gaps in* `CONTRACT-ID` must be checked; not expressible in the shipped ADABAS DDM without a platform feature or an id-service |
| Failure modes | a consumer relying on MAX+1 density; sequence exhaustion (N8) |
| Message codes | unchanged; 9902 from the empty-file guard becomes unreachable (guard retired) |

Harness: `Session.next_id` / `AdabasFile.next_id` (a monotonic counter that
is *not* rolled back by BT, like a database sequence). Model:
`conew_target_state` (`tests/harness/natural_model.py`). Tests:
`tests/test_retry.py` `TargetStateTests.test_sequence_ids_remove_the_contract_hotspot`.

## Option 5 — Atomic conditional decrement

**How it works.** Replace read → compare → write with a single conditional
write: "decrement `CRUISE-STATUS` where `CRUISE-STATUS > 0`". The check
and the set are one operation, so no retry is needed for the capacity
step; a session that finds the guard false gets 9902 straight away.

```
 Time   Session A                      Session B
 ----   ----------------------------   -----------------------------------
  t1    decr-if-positive  status 1->0  OK (record held until ET)
  t2                                   decr-if-positive -> record held: waits/retries
  t3    STORE, ET
  t4                                   decr-if-positive  status 0 -> guard false -> 9902
```

| Aspect | Mapping |
|--------|---------|
| R1 capacity | the conditional decrement *is* the rule "never below zero" (REQ-I-001); no separate test-and-set |
| R2 MAX+1 | not addressed — pair with Option 4 |
| Pros | shortest possible critical section; the invariant lives in the data layer, not in every caller; the model is trivially portable to any SQL/HCM balance API (`UPDATE ... SET n = n-1 WHERE n > 0`) |
| Cons | still a row-level lock until ET (two sessions on the same last place serialise, one gets 9902); `CRUISE-STATUS` is `A1`, so the target column must be numeric (REQ-D-001 / BR-020) |
| Failure modes | a contended row still needs a bounded wait or a re-drive (Option 1 or 3) for a *defined* outcome |
| Message codes | unchanged; guard false → 9902 |

Harness: `Session.decrement_if_positive` (`tests/harness/adabas_sim.py`),
model `conew_target_state`. Tests: `tests/test_retry.py`
`TargetStateTests.test_atomic_decrement_never_goes_negative`,
`test_capacity_contention_resolves_via_lock_wait`.

---

## Decision matrix

| Option | Handles contention | Fairness | Starvation risk | Deadlock risk | Complexity | HCM-target portability |
|--------|--------------------|----------|-----------------|---------------|------------|------------------------|
| 1 Bounded wait + timeout | medium (serialises on two hotspots) | FIFO (hold queue) | none while FIFO | low (fixed lock order, BT before wait); timeout bounds it | low | low — ADABAS hold queue has no HCM equivalent; the *timeout → defined outcome* rule ports |
| 2 Optimistic CAS + retry | low–medium (spins when hot) | none (last writer wins) | **yes** under sustained contention | none (no hold across decision) | medium | medium — CAS/version columns are standard; retry cap ports |
| 3 BT + re-drive | any (wraps 1/2/4/5) | inherits the body's | bounded by the attempt budget | none added (BT releases before re-drive) | medium | **high** — an application retry with an idempotency key is platform-neutral |
| 4 Platform-generated id | removes R2 entirely | n/a | none | none | low (target) / n/a (Natural) | **high** — required by REQ-I-002 |
| 5 Atomic conditional decrement | high (one-op critical section) | row lock order | none | none (single row) | low | **high** — `UPDATE ... WHERE n > 0` / balance API |

## Recommended target-state approach

**Options 4 + 5 as the data-layer primitives, wrapped by Option 3 as the
control loop.** Option 1's timeout rule ("a wait that is too long ends in a
defined code, never a hang") is kept as the behaviour the wrapper enforces;
Option 2 is not recommended as the primary mechanism because it is the only
option with a real starvation risk and adds nothing once Option 5 exists.

```
 target-state booking (one attempt)                bounded control loop
 ┌──────────────────────────────────────────┐      ┌───────────────────────┐
 │ validate ids (9904/9905)                 │      │ idempotency key seen? │
 │ decrement-if-positive(cruise)   ── R1    │ ◄──  │  yes → replay result  │
 │   guard false → 9902                     │      │  no  → attempt 1..N   │
 │ id := next-value(sequence)      ── R2    │      │ held/timeout/deadlock │
 │ customer exists? else BT, 9918           │      │   → BT → backoff → k+1│
 │ STORE contract; write ledger; ET → 9800  │      │ N spent → 9902 (9936) │
 └──────────────────────────────────────────┘      └───────────────────────┘
```

Why this combination:

* R1 stops being a race at all (Option 5), so the *only* thing a retry has
  to handle is a momentarily locked row — a small, bounded set of cases.
* R2 stops existing (Option 4), removing the global hotspot and BR-013.
* Option 3 provides the properties none of the primitives give alone:
  a hard attempt budget, no partial state between attempts (BT), an
  idempotency key so a lost acknowledgement cannot double-book, and one
  place to translate exhaustion into a message code.
* Every message code the UI depends on is preserved; the only *proposed*
  addition (`9936`) is optional and off by default.

For the **current Natural production code**, no change is recommended as a
result of this analysis: hold-and-wait remains correct, and the bounded
wait of Option 1 would need either a nucleus/`TT` parameter change or an
application-level retry. If a defined "busy" outcome is required *before*
migration, Option 3 around the existing subprogram is the least invasive
change and is what `conew_with_retry` models.

## Message-code impact

| Code | Option 1 | Option 2 | Option 3 | Option 4 | Option 5 |
|------|----------|----------|----------|----------|----------|
| 9800 → 0 | kept | kept | kept | kept | kept |
| 9902 | kept; also the default timeout outcome | kept; also the default retry-cap outcome | kept; also the default exhaustion outcome | kept (empty-file guard path becomes unreachable) | kept; guard false |
| 9904 / 9905 | kept (edits run before any hold) | kept | kept; never retried | kept | kept |
| 9918 | kept (BT first) | kept | kept; never retried | kept | kept |
| 9999 | kept (`ON ERROR` → BT) | kept | kept; an abend is backed out and propagated, never re-driven | kept | kept |
| **9936** (proposed) | "Booking busy — please retry" on timeout | on retry cap | on exhaustion | — | — |

`9936` is a *proposal*, not a change: `CAMSG-N` has no text for it, and
the models emit it only when a caller passes `exhausted_msg=` /
`timeout_msg=MSG_BOOKING_BUSY`. The default in every model is 9902, so the
production message set is preserved unless the catalogue is deliberately
extended (`tests/test_retry.py:test_exhaustion_can_opt_into_distinct_target_state_code`
shows the opt-in; `test_customer_not_found_and_sold_out_codes_are_preserved`
shows the preserved set on the target-state model).

**Outcome precedence is preserved too.** Preserving the *set* of codes is
not enough for run-compare: a request can fail more than one check, and
CONEW-N answers with the first one in its statement order — identifier
edits (9904/9905), then the cruise's capacity (9902), then the customer
(9918, after BT), then the store/ET. An unknown customer asking for a
sold-out cruise therefore gets 9902, not 9918. Every model in this PR keeps
that order (`conew_target_state` checks capacity with the atomic decrement
*before* it looks the customer up, and backs the decrement out on 9918);
`test_outcome_precedence_matches_the_current_state` proves it for all four
variants. Validating the customer before the first write would be a
reasonable target-state simplification (no write for an invalid request),
but it changes the answer for that one input class and is therefore *not*
proposed here — it would need its own equivalence-test waiver.

## Mapping to business rules and requirements

| Rule / requirement | Current-state proof | Option 1 | Option 2 | Option 3 | Option 4 | Option 5 | Recommendation |
|--------------------|---------------------|----------|----------|----------|----------|----------|----------------|
| BR-006 Test-and-set on held offering record | `tests/test_concurrency.py:68-97` | kept as is | replaced by guarded update | kept inside each attempt | — | replaced by conditional decrement | Option 5 carries the *outcome* (REQ-I-001), not the hold idiom |
| BR-007 MAX+1 booking identifier under hold | `tests/test_concurrency.py:99-127` | kept | kept | kept inside each attempt; a backed-out attempt never leaks an id | **retired** | — | Option 4: uniqueness carried, mechanism retired (REQ-I-002) |
| BR-010 Customer must exist; backout otherwise | `tests/test_conew_booking.py:165-175` | BT then 9918 | BT then 9918 | BT then 9918, **not** retried | unchanged | unchanged | unchanged |
| BR-011 Booking is all-or-nothing | `tests/test_conew_booking.py:200-210` | BT on timeout | BT between attempts | BT between attempts; ledger written in the same ET | unchanged | unchanged | Option 3 makes this hold *across* attempts as well |
| REQ-I-001 Capacity decremented atomically under contention | `tests/test_concurrency.py:68-97`, `:129-141` | via hold | via guard | via body | — | **native** | Option 5 |
| REQ-I-002 Identifiers unique under contention | `tests/test_concurrency.py:99-127` | via hold | via hold | via hold per attempt | **native** | — | Option 4 |

Target-state proofs added by this work, per requirement (all in
`tests/test_retry.py`):

| Requirement | Scenario | Test |
|-------------|----------|------|
| REQ-I-001 | last place, loser re-drives → 9902, no overbooking | `test_loser_retries_after_commit_and_gets_9902_for_last_place`, `test_waiter_resumes_at_holders_et_and_gets_9902_for_last_place`, `test_stale_guard_retries_and_gets_9902_for_last_place` |
| REQ-I-001 | retry succeeds when capacity remains after the competitor's ET | `test_retry_succeeds_when_capacity_remains_after_commit`, `test_waiter_succeeds_when_capacity_remains`, `test_stale_guard_retries_and_succeeds_when_capacity_remains` |
| REQ-I-001 | budget/wait exhausted → defined code, no partial booking | `test_budget_exhausted_under_sustained_contention_is_defined`, `test_bounded_wait_gives_up_after_repeated_reparking`, `test_retry_cap_under_sustained_contention_returns_9902`, `test_bounded_redrive_of_target_state_is_defined_on_exhaustion` |
| REQ-I-001 | conditional decrement never goes negative | `test_atomic_decrement_never_goes_negative`, `test_capacity_contention_resolves_via_lock_wait` |
| REQ-I-002 | no duplicate CONTRACT-ID under hold or retry | `test_maxid_contention_never_duplicates_contract_ids`, `test_interleaved_cruise_and_contract_holds_resolve`, `test_sequence_ids_remove_the_contract_hotspot` |
| BR-011 / REQ-I-003 | backout leaves no hold, no decrement; abend mid-retry backs out | `test_backout_on_retry_leaves_no_dangling_state`, `test_abend_mid_retry_backs_out_cleanly`, `test_customer_not_found_during_retry_still_backs_out` |
| BR-011 | idempotent re-drive after a committed ET; concurrent same-id submits book once; the ledger entry is complete in the committing ET and bound to the request's inputs | `test_completed_attempt_is_never_redriven`, `test_redrive_with_same_request_id_replays_committed_outcome`, `test_failed_request_is_not_recorded_and_can_be_redriven`, `test_concurrent_same_request_id_books_once_and_replays`, `test_same_request_id_retry_finds_the_replay`, `test_waiter_resumed_by_ledger_release_sees_complete_outcome`, `test_reused_request_id_with_different_inputs_is_rejected`, `test_commit_between_lookup_and_claim_is_replayed_not_rebooked`, `test_duplicate_at_et_is_backed_out_and_replayed`, `test_ledger_uniqueness_is_enforced_at_et` |
| BR-011 / REQ-I-003 | an abend after the decrement or after the identifier backs out in every variant; a waiter's abend stays with the waiter | `test_abend_after_swap_backs_out`, `test_abend_after_decrement_backs_out`, `test_resumed_waiter_abend_stays_with_the_waiter` |
| BR-011 | a failed BT + re-drive attempt, and an exhausted budget, leave nothing buffered for a later ET; a hold-queue re-drive applies pre-conflict work once | `test_failed_attempt_is_backed_out_before_the_next_one`, `test_exhausted_retry_leaves_nothing_to_commit`, `test_resumed_waiter_does_not_repeat_its_pre_conflict_work` |
| REQ-N-002 | no starvation / no deadlock under interleaved holds; a bounded wait expires even behind a holder that never releases | `test_fifo_hold_queue_is_fair_and_starvation_free`, `test_wait_for_cycle_is_detected_instead_of_blocking_forever`, `test_model_releases_before_waiting_so_no_cycle_forms`, `test_bounded_wait_gives_up_after_repeated_reparking`, `test_bounded_wait_expires_behind_a_holder_that_never_releases`, `test_simultaneous_timeouts_do_not_resume_each_other` |
| BR-006 / BR-011 | a parked booking keeps its open transaction (cruise hold + buffered decrement) and the resumed run completes *that* transaction | `test_parked_waiter_keeps_its_open_transaction_and_resumes_it`, `test_interleaved_cruise_and_contract_holds_resolve` |

## What the harness adds (and what it does not)

`tests/harness/adabas_sim.py`:

* `retry_on_hold(operation, session, attempts, before_retry)` — bounded
  BT + re-drive of any callable on `RecordHeldError`; raises
  `RetryBudgetExhausted`. The helper owns the rollback: whatever a failed
  attempt left buffered or held on `session` is backed out before
  `before_retry`, before the next attempt and before the exhaustion error,
  so an operation that does not clean up after itself still cannot carry
  one attempt's STORE into the next (an operation that already backed out
  is not backed out twice).
* `AdabasSim(wait_limit=N)` + `submit(session, operation)` — hold-queue
  mode. A parked `WaitTicket` is re-driven, in FIFO order, when the holder
  issues ET or BT. `wait_limit` is a budget in wait units: a unit is spent
  on every re-park and on every `AdabasSim.tick()` (the simulated clock),
  so a ticket times out with `HoldTimeoutError` both when it keeps meeting
  holders and when its holder simply never releases (tickets expiring in
  the same tick are all dequeued before any is backed out, so one
  waiter's give-up never resumes another that has also run out); a
  wait-for cycle ends with `DeadlockError` instead of hanging. A waiter that abends when
  re-driven is backed out and its exception recorded on the ticket; the
  holder's ET/BT that resumed it returns normally.

  A Python callable cannot be resumed at the statement that blocked, so a
  re-drive runs the callable again from its start. To make that equal to
  a resume, the ticket records the session's buffered writes at `submit`
  and a re-drive restores that checkpoint first: the failed run's STOREs
  and UPDATEs are discarded and produced once more by the re-run, work
  buffered *before* the submit is kept, and holds acquired by the failed
  run are kept as a waiting user's are (`conew_hold_and_wait` blocked at
  R2 resumes still owning its cruise record). The checkpoint belongs to
  the transaction that was open at `submit`: if the callable itself issued
  ET or BT before parking (as `conew_refactored` backs out on a conflict,
  turning the wait into a BT + re-drive), that transaction is over, its
  holds are gone, and nothing is restored —
  a pre-submit UPDATE cannot come back without the hold that protected it
  and overwrite what a competitor committed in the meantime. The callable
  must therefore be deterministic; side effects outside the session
  (hooks) run once per attempt (`WaitTicket.attempts`).

  Re-driving happens synchronously inside the holder's `et()`/`backout()`
  call. That is a scheduling convenience of a single-threaded simulator,
  not a claim about platform timing: tests assert *outcomes* (who booked,
  what the ticket ended with, what is left in the hold table), never the
  moment at which a waiter ran relative to the holder's return.
* `Session.update_if` (guarded update), `Session.decrement_if_positive`
  (atomic conditional decrement) — both read through the transaction's
  own pending update of the field, as a relational `UPDATE ... WHERE`
  does, so two decrements in one transaction take two places —,
  `Session.next_id` (sequence not rolled
  back by BT), `record_request` / `completed_request` (idempotency ledger:
  the id is claimed under a hold and the ledger is read *under that hold*
  — lookup and claim are one step, so a commit landing just before the
  claim is returned to the claimant instead of being booked twice; the
  entry — a dict or a callable evaluated at ET, so it can describe the
  contract the same ET stores — is copied into the ledger by that ET; a
  duplicate at ET is refused with `DuplicateRequestError` after a BT, and
  a payload that fails to evaluate is backed out the same way before the
  error propagates — ET never leaves a half-open transaction).
  `conew_with_retry` binds the entry to a fingerprint of the request's
  inputs and raises `RequestMismatchError` when a re-used id presents
  different inputs; a `DuplicateRequestError` at ET (a claim path that
  bypassed the hold) is turned into a replay of the committed outcome.
* `RecordHeldError` now carries `key`, `holder` and `requester`; the
  existing `hold`/`update`/`store`/`et`/`backout` semantics are unchanged
  and every pre-existing test runs against the same code.

`tests/harness/natural_model.py`: `conew_hold_and_wait` (Option 1 body:
a hold conflict is the nucleus's, not the program's, so the parked
transaction stays open), `conew_with_retry` (Option 3),
`conew_optimistic` (Option 2), `conew_target_state` (Options 4 + 5),
`booking_outcome` (Option 1 translation), `MSG_BOOKING_BUSY` (proposed
9936). `conew_original` and `conew_refactored` are untouched.

Not modelled: wall-clock time (backoff is a callback, never a sleep),
ADABAS response codes and nucleus parameters, and any Natural syntax for a
conditional update — the models prove the *outcome* each option must
deliver, which is what the requirements baseline carries into the HCM
target.
