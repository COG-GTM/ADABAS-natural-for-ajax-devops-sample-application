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
"""

import copy


class RecordHeldError(Exception):
    """Raised when a session tries to hold a record held by another session."""


class AdabasFile:
    def __init__(self, name):
        self.name = name
        self.records = {}
        self._next_isn = 1

    def load(self, rows):
        for row in rows:
            self.insert(row)

    def insert(self, row):
        isn = self._next_isn
        self._next_isn += 1
        self.records[isn] = dict(row)
        return isn


class Session:
    """One Natural user session with its own transaction and hold state."""

    def __init__(self, db, name):
        self.db = db
        self.name = name
        self.holds = set()
        self._pending_updates = {}
        self._pending_stores = []

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
            raise RecordHeldError(
                f"{key} held by {owner.name}, requested by {self.name}"
            )
        self.db.hold_table[key] = self
        self.holds.add(key)

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

    # -- transaction end -----------------------------------------------

    def et(self):
        """END TRANSACTION: apply buffered changes, release holds."""
        for (file_name, isn), values in self._pending_updates.items():
            self.db.files[file_name].records[isn].update(values)
        for file_name, row in self._pending_stores:
            self.db.files[file_name].insert(row)
        self._reset()

    def backout(self):
        """BACKOUT TRANSACTION: discard buffered changes, release holds."""
        self._reset()

    def _reset(self):
        self._pending_updates = {}
        self._pending_stores = []
        for key in self.holds:
            if self.db.hold_table.get(key) is self:
                del self.db.hold_table[key]
        self.holds = set()


class AdabasSim:
    def __init__(self):
        self.files = {}
        self.hold_table = {}

    def add_file(self, name, rows=()):
        f = AdabasFile(name)
        f.load(rows)
        self.files[name] = f
        return f

    def session(self, name="user"):
        return Session(self, name)
