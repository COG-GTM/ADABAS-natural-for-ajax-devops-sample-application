"""In-memory simulation of the ADABAS record model used by the test harness.

Models the subset of ADABAS semantics that the CRUISE16 business logic
depends on:

* files addressed by name, records addressed by ISN
* record hold (row lock) with hold-queue conflict detection
* transactions: buffered updates/stores applied on ET (END TRANSACTION)
  and discarded on BT (BACKOUT TRANSACTION)
* descriptor lookups (FIND) and logical reads (READ ... BY descriptor)

The simulation is single-threaded and deterministic: concurrency tests
interleave two sessions explicitly at the statement level, which mirrors
how two Natural sessions interleave against one ADABAS nucleus.

Retry and wait semantics (see docs/retry-rearchitecture.md) are layered on
top of the same primitives:

* ``retry_on_hold`` — bounded application-level retry of a whole operation
  when it ends in ``RecordHeldError`` (design option 3);
* ``AdabasSim.submit`` — hold-queue mode: an operation that meets a held
  record is parked on that record and re-driven, FIFO, when the holder's
  ET/BT releases it, with an optional wait limit that turns into
  ``HoldTimeoutError`` and cycle detection that turns into
  ``DeadlockError`` (design option 1);
* ``Session.update_if`` — compare-and-swap guarded update (option 2);
* ``Session.decrement_if_positive`` — atomic conditional decrement
  (option 5) and ``Session.next_id`` — platform-generated identifier
  (option 4); once a file's identifier is platform-generated, ET refuses a
  STORE that supplies its own value (``GeneratedKeyError``).
"""

import copy


class RecordHeldError(Exception):
    """Raised when a session tries to hold a record held by another session."""

    def __init__(self, key, holder, requester):
        super().__init__(
            f"{key} held by {holder.name}, requested by {requester.name}")
        self.key = key
        self.holder = holder
        self.requester = requester


class HoldTimeoutError(RecordHeldError):
    """The hold could not be granted within the configured wait budget.

    Analog of a hold-queue / transaction time limit expiring on the nucleus
    (the caller sees a non-zero ADABAS response instead of waiting forever).
    """


class DeadlockError(RecordHeldError):
    """Two parked sessions each wait for a record the other holds."""


class DuplicateRequestError(Exception):
    """A request id would be recorded twice: ET would commit an id that is
    already in the ledger, or a transaction claims an id it has already
    claimed (the unique-constraint violation of an idempotency table)."""

    def __init__(self, request_id):
        super().__init__(f"request {request_id!r} already recorded")
        self.request_id = request_id


class GeneratedKeyError(Exception):
    """ET would store a record whose identifier is platform-generated
    (``next_id`` is in use on that file) with a value this transaction did
    not draw from the sequence, or one that already exists — the
    ``GENERATED ALWAYS`` identity / unique-key violation of the target
    platform. The transaction is backed out before this is raised."""

    def __init__(self, file_name, field, value):
        super().__init__(
            f"{file_name}.{field}={value!r} was not issued to this transaction"
            " or already exists")
        self.file_name = file_name
        self.field = field
        self.value = value


class RetryBudgetExhausted(Exception):
    """Every attempt of ``retry_on_hold`` ended in ``RecordHeldError``."""

    def __init__(self, attempts, last_error):
        super().__init__(
            f"{attempts} attempt(s) exhausted; last conflict: {last_error}")
        self.attempts = attempts
        self.last_error = last_error


def retry_on_hold(operation, session, attempts=3, before_retry=None):
    """BT + re-drive: run ``operation(attempt)`` on ``session`` until it
    returns, retrying on a hold conflict.

    Every failed attempt is a complete transaction: whatever it left
    buffered or held is backed out (``session.backout()``) before
    ``before_retry`` runs and before the next attempt, and once more before
    ``RetryBudgetExhausted`` is raised, so no attempt can commit another
    attempt's work. An operation that already backed out is not backed out
    a second time.
    ``attempts`` bounds the total number of invocations (1 = no retry).
    ``before_retry(attempt, error)`` is called between attempts; tests use it
    to interleave the competitor (or to model backoff) at exactly that point.
    A returned value is terminal: a completed attempt is never re-driven.
    """
    if attempts < 1:
        raise ValueError("attempts must be at least 1")
    last = None
    for attempt in range(1, attempts + 1):
        try:
            return operation(attempt)
        except RecordHeldError as exc:
            last = exc
            if session.in_transaction():
                session.backout()
            if attempt < attempts and before_retry is not None:
                before_retry(attempt, exc)
    raise RetryBudgetExhausted(attempts, last)


class WaitTicket:
    """An operation parked in the hold queue (``AdabasSim.submit``).

    ``done`` becomes true when the operation returned (``result``) or was
    abandoned (``error``: ``HoldTimeoutError``, ``DeadlockError`` or the
    operation's own exception, after its transaction was backed out);
    ``waits`` is the wait budget consumed (re-parks + clock ticks);
    ``attempts`` how often it ran. ``checkpoint`` is the session's buffered
    work at submission; a re-drive restores it first (see
    ``AdabasSim._drive``).
    """

    def __init__(self, session, operation):
        self.session = session
        self.operation = operation
        self.checkpoint = session._checkpoint()
        self.key = None
        self.result = None
        self.error = None
        self.done = False
        self.waits = 0
        self.attempts = 0


#: pseudo-file whose "ISNs" are request ids; only ever used as hold keys.
REQUEST_LEDGER = "__REQUEST_LEDGER__"


class AdabasFile:
    def __init__(self, name):
        self.name = name
        self.records = {}
        self._next_isn = 1
        self._sequence = None
        self.generated_field = None

    def load(self, rows):
        for row in rows:
            self.insert(row)

    def insert(self, row):
        isn = self._next_isn
        self._next_isn += 1
        self.records[isn] = dict(row)
        return isn

    def next_id(self, field):
        """Platform-generated identifier: a sequence seeded from the current
        maximum of ``field``. Not transactional (a backout leaves a gap),
        exactly like a database sequence. From the first draw on, ``field``
        is the file's generated key: a STORE may only carry a value drawn
        by the storing transaction (``Session.et`` enforces it), so a
        writer that still computes MAX+1 cannot collide with the sequence.
        """
        if self._sequence is None:
            self._sequence = max(
                (rec[field] for rec in self.records.values()), default=0)
            self.generated_field = field
        self._sequence += 1
        return self._sequence

    def has_value(self, field, value):
        return any(rec[field] == value for rec in self.records.values())


class Session:
    """One Natural user session with its own transaction and hold state."""

    def __init__(self, db, name):
        self.db = db
        self.name = name
        self.holds = set()
        self._pending_updates = {}
        self._pending_stores = []
        self._pending_requests = []
        self._issued_ids = set()  # (file, field, value) drawn via next_id
        self._transaction = 0  # bumped by every ET/BT

    # -- reads ---------------------------------------------------------

    def find(self, file_name, field, value):
        """FIND <file> WITH <field> = <value>; returns [(isn, record), ...]."""
        f = self.db.files[file_name]
        return [
            (isn, copy.deepcopy(rec))
            for isn, rec in sorted(f.records.items())
            if rec.get(field) == value
        ]

    def read_descending(self, file_name, descriptor, limit=None):
        """READ (limit) <file> DESCENDING BY <descriptor>."""
        f = self.db.files[file_name]
        ordered = sorted(
            f.records.items(), key=lambda kv: kv[1][descriptor], reverse=True
        )
        if limit is not None:
            ordered = ordered[:limit]
        return [(isn, copy.deepcopy(rec)) for isn, rec in ordered]

    # -- hold / update / store -----------------------------------------

    def hold(self, file_name, isn):
        """Place a record in hold (what ADABAS does on a held read)."""
        key = (file_name, isn)
        owner = self.db.hold_table.get(key)
        if owner is not None and owner is not self:
            raise RecordHeldError(key, owner, self)
        self.db.hold_table[key] = self
        self.holds.add(key)

    def release(self, file_name, isn):
        """Give up one hold without ending the transaction (no ADABAS
        statement does this for a single record; used by ``update_if`` to
        model a guard failure that leaves nothing behind)."""
        key = (file_name, isn)
        if self.db.hold_table.get(key) is self:
            del self.db.hold_table[key]
        self.holds.discard(key)
        self._pending_updates.pop(key, None)
        self.db._release(key)

    def get_held(self, file_name, isn):
        """Re-read a record's current committed value while holding it."""
        self.hold(file_name, isn)
        return copy.deepcopy(self.db.files[file_name].records[isn])

    def update(self, file_name, isn, new_values):
        """UPDATE: buffer changed values until ET. Requires the hold."""
        self.hold(file_name, isn)
        self._pending_updates.setdefault((file_name, isn), {}).update(new_values)

    def store(self, file_name, row):
        """STORE: buffer a new record until ET."""
        self._pending_stores.append((file_name, dict(row)))

    # -- retry-architecture primitives ----------------------------------

    def _current(self, file_name, isn, field):
        """The value of ``field`` as this transaction sees it: its own
        buffered update if any, else the committed value (a relational
        ``UPDATE ... WHERE`` reads through the transaction's earlier writes)."""
        pending = self._pending_updates.get((file_name, isn), {})
        if field in pending:
            return pending[field]
        return self.db.files[file_name].records[isn][field]

    def update_if(self, file_name, isn, field, expected, new_values):
        """Compare-and-swap: apply ``new_values`` only if the value of
        ``field`` (committed, or this transaction's own pending update)
        still equals ``expected``.

        Returns True and leaves the record held (until ET/BT) on success;
        returns False and leaves no hold behind when the guard fails. May
        raise ``RecordHeldError`` while acquiring the hold, like any UPDATE.
        """
        key = (file_name, isn)
        newly_held = key not in self.holds
        self.hold(file_name, isn)
        if self._current(file_name, isn, field) != expected:
            if newly_held:
                self.release(file_name, isn)
            return False
        self._pending_updates.setdefault(key, {}).update(new_values)
        return True

    def decrement_if_positive(self, file_name, isn, field):
        """Atomic conditional decrement of a numeric-in-alpha counter
        (``UPDATE ... SET f = f - 1 WHERE f > 0`` on a relational target).

        Returns the new value, or None when the counter was already zero
        (in which case no hold is left behind). Repeated calls in one
        transaction each consume one unit (the second reads the first's
        pending value). Contention on the row is still a hold conflict, as
        it is a row lock on a relational engine.
        """
        key = (file_name, isn)
        newly_held = key not in self.holds
        self.hold(file_name, isn)
        current = int(self._current(file_name, isn, field))
        if current <= 0:
            if newly_held:
                self.release(file_name, isn)
            return None
        self._pending_updates.setdefault(key, {})[field] = str(current - 1)
        return current - 1

    def next_id(self, file_name, field):
        """Platform-generated identifier for ``file_name`` (option 4). The
        value belongs to this transaction: only it may STORE a record
        carrying it, and only until its ET/BT."""
        value = self.db.files[file_name].next_id(field)
        self._issued_ids.add((file_name, field, value))
        return value

    def _check_generated_keys(self):
        """The ``GENERATED ALWAYS`` rule for every buffered STORE into a file
        whose identifier is platform-generated."""
        unused = set(self._issued_ids)
        for file_name, row in self._pending_stores:
            f = self.db.files[file_name]
            field = f.generated_field
            if field is None:
                continue
            issued = (file_name, field, row.get(field))
            if issued not in unused or f.has_value(field, row[field]):
                raise GeneratedKeyError(*issued)
            unused.discard(issued)

    def record_request(self, request_id, payload):
        """Claim ``request_id`` and buffer its ledger entry until ET.

        The claim is a hold on the ledger row, so a concurrent transaction
        for the same request meets ``RecordHeldError`` (and re-checks the
        ledger on its next attempt) instead of booking a second time. The
        ledger is read *under* the hold: if the id was committed in the
        meantime the committed entry (a copy) is returned and nothing is
        buffered, so lookup and claim are one atomic step; otherwise the
        claim is buffered and None is returned. One claim per id per
        transaction: claiming an id this transaction has already claimed
        raises ``DuplicateRequestError`` (a second INSERT of the same key
        fails on the unique index) and leaves the first claim as it was.
        ``payload`` is a dict, or a zero-argument callable evaluated at ET
        time (so the entry can describe the outcome the same ET commits).
        Either way the ledger stores its own copy.
        """
        self.hold(REQUEST_LEDGER, request_id)
        done = self.completed_request(request_id)
        if done is not None:
            return done
        if any(claimed == request_id for claimed, _ in self._pending_requests):
            raise DuplicateRequestError(request_id)
        self._pending_requests.append((request_id, payload))
        return None

    def completed_request(self, request_id):
        """A copy of the committed outcome of ``request_id``, or None."""
        return copy.deepcopy(self.db.request_ledger.get(request_id))

    def pending_stores(self, file_name):
        """Copies of the rows this transaction has buffered for STORE."""
        return [dict(row) for name, row in self._pending_stores
                if name == file_name]

    def in_transaction(self):
        """True while the session holds a record or has buffered work."""
        return bool(self.holds or self._pending_updates
                    or self._pending_stores or self._pending_requests)

    def _checkpoint(self):
        """Copy of the buffered (not yet committed) writes, tagged with the
        transaction they belong to."""
        return (self._transaction,
                copy.deepcopy(self._pending_updates),
                copy.deepcopy(self._pending_stores),
                list(self._pending_requests))

    def _restore(self, checkpoint):
        """Put the buffered writes back to ``checkpoint``; holds are kept.

        A checkpoint belongs to one transaction: if that transaction has
        since ended (the operation issued ET or BT, releasing its holds),
        there is nothing to put back — the writes went with it. An update
        is only ever restored for a record this session still holds."""
        transaction, updates, stores, requests = checkpoint
        if transaction != self._transaction:
            return
        self._pending_updates = {key: copy.deepcopy(values)
                                 for key, values in updates.items()
                                 if key in self.holds}
        self._pending_stores = copy.deepcopy(stores)
        self._pending_requests = list(requests)

    # -- transaction end -----------------------------------------------

    def et(self):
        """END TRANSACTION: apply buffered changes, release holds.

        A pending ledger entry whose id is already committed violates the
        ledger's uniqueness: the whole transaction is backed out and
        ``DuplicateRequestError`` is raised, nothing is applied. A STORE
        that supplies its own value for a platform-generated identifier is
        refused the same way (``GeneratedKeyError``). Likewise a ledger
        payload that fails to evaluate abends the ET: the transaction is
        backed out (holds released, nothing applied) before the error
        propagates.
        """
        for request_id, _ in self._pending_requests:
            if request_id in self.db.request_ledger:
                self.backout()
                raise DuplicateRequestError(request_id)
        try:
            self._check_generated_keys()
            entries = [(request_id,
                        dict(payload() if callable(payload) else payload))
                       for request_id, payload in self._pending_requests]
        except Exception:
            self.backout()
            raise
        for (file_name, isn), values in self._pending_updates.items():
            self.db.files[file_name].records[isn].update(values)
        for file_name, row in self._pending_stores:
            self.db.files[file_name].insert(row)
        for request_id, entry in entries:
            self.db.request_ledger[request_id] = entry
        self.db.et_count += 1
        self._reset()

    def backout(self):
        """BACKOUT TRANSACTION: discard buffered changes, release holds."""
        self.db.bt_count += 1
        self._reset()

    def _reset(self):
        self._transaction += 1
        self._pending_updates = {}
        self._pending_stores = []
        self._pending_requests = []
        self._issued_ids = set()
        released = []
        for key in self.holds:
            if self.db.hold_table.get(key) is self:
                del self.db.hold_table[key]
                released.append(key)
        self.holds = set()
        for key in released:
            self.db._release(key)


class AdabasSim:
    """The nucleus: files, the hold table and (optionally) a hold queue.

    ``wait_limit`` is a parked operation's wait budget in *wait units*: a
    unit is consumed each time the operation is re-parked after a resume
    and each time ``tick()`` advances the simulated clock while it waits.
    A ticket whose budget is spent is abandoned with ``HoldTimeoutError``
    (None = wait forever, 0 = never wait, i.e. the ADABAS "return
    immediately" hold option).
    """

    def __init__(self, wait_limit=None):
        self.files = {}
        self.hold_table = {}
        self.hold_queue = {}
        self.wait_limit = wait_limit
        self.request_ledger = {}
        self.et_count = 0
        self.bt_count = 0
        self._parked = {}

    def add_file(self, name, rows=()):
        f = AdabasFile(name)
        f.load(rows)
        self.files[name] = f
        return f

    def session(self, name="user"):
        return Session(self, name)

    # -- hold-queue mode -----------------------------------------------

    def submit(self, session, operation):
        """Run ``operation()`` for ``session`` in hold-queue mode.

        If the operation raises ``RecordHeldError`` it is parked on the
        contested record and re-driven when the holder ends its
        transaction; the returned ``WaitTicket`` reports the outcome. The
        record is handed to one waiter at a time, the oldest: the others
        stay queued (still ahead of any newcomer) until that waiter in turn
        releases it.
        The parked session keeps whatever holds it already owns (as a real
        session waiting in the hold queue does), which is why a wait cycle
        is possible and is detected as ``DeadlockError``.

        A Python callable cannot resume at the statement that blocked, so
        a re-drive runs ``operation`` again from its start. To make that
        equal to a resume, the writes the failed run buffered are discarded
        first (the session's buffers go back to what they were at
        ``submit``; holds are kept, as a waiting user's are): a store or
        update before the conflict point is applied once, not once per run.
        The operation must therefore be deterministic; side effects outside
        the session (hooks, counters) do run once per attempt.
        """
        ticket = WaitTicket(session, operation)
        self._drive(ticket)
        return ticket

    def waiting(self):
        """Tickets currently parked, in queue order."""
        return [t for waiters in self.hold_queue.values() for t in waiters]

    def tick(self, units=1):
        """Advance the simulated clock: every parked ticket consumes
        ``units`` of its wait budget, and those whose budget is spent time
        out now (backed out, dequeued) even though their holder has not
        released. No-op when ``wait_limit`` is None. Returns the tickets
        that timed out, in queue order."""
        expired = []
        if self.wait_limit is None:
            return expired
        for ticket in self.waiting():
            ticket.waits += units
            if ticket.waits >= self.wait_limit:
                expired.append(ticket)
        # Dequeue every expired ticket before abandoning any: a backout
        # releases holds and would otherwise re-drive a ticket that is
        # itself about to time out (same order of events as _release).
        errors = []
        for ticket in expired:
            self._dequeue(ticket)
            key, ticket.key = ticket.key, None
            errors.append(HoldTimeoutError(key, self.hold_table.get(key),
                                           ticket.session))
        for ticket, error in zip(expired, errors):
            self._abandon(ticket, error)
        return expired

    def _dequeue(self, ticket):
        waiters = self.hold_queue.get(ticket.key, [])
        if ticket in waiters:
            waiters.remove(ticket)
        if not waiters:
            self.hold_queue.pop(ticket.key, None)
        self._parked.pop(ticket.session, None)

    def _drive(self, ticket):
        """Run the ticket once. A hold conflict parks it; any other exception
        is the waiter's own abend: it is recorded on the ticket and the
        waiter's transaction is backed out, so a failure in a resumed waiter
        never surfaces through the holder's ET/BT that resumed it.
        A re-drive first drops what the previous run buffered."""
        if ticket.attempts:
            ticket.session._restore(ticket.checkpoint)
        ticket.attempts += 1
        try:
            ticket.result = ticket.operation()
        except RecordHeldError as exc:
            self._park(ticket, exc)
            return
        except Exception as exc:
            self._abandon(ticket, exc)
            return
        ticket.done = True

    def _park(self, ticket, exc):
        if self.wait_limit is not None and ticket.waits >= self.wait_limit:
            self._abandon(ticket, HoldTimeoutError(
                exc.key, exc.holder, exc.requester))
            return
        if self._would_deadlock(ticket.session, exc.holder):
            self._abandon(ticket, DeadlockError(
                exc.key, exc.holder, exc.requester))
            return
        ticket.waits += 1
        ticket.key = exc.key
        self.hold_queue.setdefault(exc.key, []).append(ticket)
        self._parked[ticket.session] = ticket

    def _abandon(self, ticket, error):
        ticket.error = error
        ticket.done = True
        ticket.session.backout()

    def _would_deadlock(self, session, holder):
        """Follow the wait-for chain from ``holder``; a path back to
        ``session`` means parking it would close a cycle."""
        seen = set()
        current = holder
        while current is not None and current not in seen:
            if current is session:
                return True
            seen.add(current)
            parked = self._parked.get(current)
            if parked is None:
                return False
            current = self.hold_table.get(parked.key)
        return False

    def _release(self, key):
        """``key`` was released: hand it to the oldest waiter. The rest stay
        queued, so a session that arrives while that waiter runs (even one
        it submits itself) queues behind them; they get their turn from the
        waiter's own ET/BT, or right away if it did not take ``key``."""
        while key not in self.hold_table:
            waiters = self.hold_queue.get(key)
            if not waiters:
                return
            ticket = waiters.pop(0)
            if not waiters:
                del self.hold_queue[key]
            self._parked.pop(ticket.session, None)
            ticket.key = None
            self._drive(ticket)
