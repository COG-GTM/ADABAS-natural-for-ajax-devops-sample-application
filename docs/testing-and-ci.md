# Testing & CI

## Why a driver harness

The repository contained no test framework, and the application requires a
licensed Natural runtime plus a running ADABAS nucleus (see the top-level
README) — neither is available on GitHub-hosted CI runners. The regression
suite therefore uses a **driver harness / executable specification**
approach, built only on the Python 3 standard library (no dependencies to
install):

```
tests/
  harness/
    adabas_sim.py       in-memory model of ADABAS record holds, ET/BT
    natural_model.py    faithful Python port of CRLIST-N / CONEW-N /
                        CAMSG-N / CRGET-N price selection (both the
                        original and the refactored CONEW-N variants)
    fixtures.py         shared cruise/customer/contract fixture data
    source_parser.py    parsers for .NSN sources and .NSD DDMs
  test_conew_booking.py       booking business rules (message codes,
                              availability decrement, price, validation)
  test_crlist_listing.py      listing rules (filters, ordering, formats)
  test_concurrency.py         deterministic two-session interleavings
  test_source_conformance.py  asserts the real .NSN/.NSD sources
tools/
  generate_data_dictionary.py regenerates docs/data-dictionary.md from DDMs
```

Two layers keep the harness honest:

1. **Behavioral tests** run the Python port of the business rules
   (`natural_model.py`) against the simulated ADABAS (`adabas_sim.py`).
   Concurrency tests interleave two sessions deterministically at the exact
   statement boundaries where the original `CONEW-N` was vulnerable.
2. **Source-conformance tests** parse the actual Natural sources and DDMs,
   asserting the message-code sets, the hold patterns in `CONEW-N.NSN`, the
   listing rules in `CRLIST-N.NSN`, DDM field formats/descriptors, and that
   `docs/data-dictionary.md` is byte-identical to its generator's output.
   If someone edits the Natural source or a DDM without updating the model
   or the docs, CI fails.

Trade-off: the harness validates the *business rules and access patterns*,
not the Natural compiler or the ADABAS nucleus itself. Full end-to-end
verification against a live nucleus still requires deploying to a Natural
environment (see `SunnyIslands/deploy/`).

## Running the suite locally

```bash
python3 -m unittest discover -s tests -v   # full regression suite
python3 -m compileall -q tests tools       # syntax check
python3 tools/generate_data_dictionary.py  # regen docs after DDM changes
```

## Coverage summary

* Availability decrement on booking (single and last slot).
* Input validation: blank/zero/non-numeric customer and cruise IDs.
* Message codes 9800, 9902, 9904, 9905 (plus 9918, 9807, 9857) and their
  CAMSG-N response-code mapping.
* Price selection (1/2/3-week and fallback) and contract price capture.
* Edge cases: booking the last available slot, invalid customer/cruise IDs,
  transaction backout, no dangling record holds.
* Concurrency: CRUISE-STATUS race and duplicate contract-ID generation
  (original defective vs. refactored safe behavior).

## CI workflow

`.github/workflows/regression-tests.yml` runs on every pull request and on
pushes to `master`:

1. checkout;
2. set up Python 3 (stdlib only — nothing to install);
3. `python3 -m compileall` syntax gate;
4. `python3 -m unittest discover -s tests -v`;
5. regenerate the data dictionary and fail on any diff (drift gate).

The pre-existing `codeql-analysis.yml` workflow is unchanged.
