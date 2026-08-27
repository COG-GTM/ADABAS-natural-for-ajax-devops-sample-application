# Sunny Islands Cruise — System Documentation

Documentation for the Natural/ADABAS "Sunny Islands" cruise-booking sample
application (Natural for AJAX / NJX).

| Document | Contents |
|----------|----------|
| [module-inventory.md](module-inventory.md) | Every Natural object in both libraries (`CRUISE16`, `RDCRUISE`) and what it does |
| [call-map.md](call-map.md) | Which routines call which (`CALLNAT`/`FETCH`/`INCLUDE` relationships) |
| [data-dictionary.md](data-dictionary.md) | Field-level dictionary of the four ADABAS DDMs — generated, do not edit by hand |
| [transaction-flows.md](transaction-flows.md) | End-to-end flow diagrams for the cruise-listing and booking transactions |
| [training-guide.md](training-guide.md) | New-developer onboarding: prerequisites, repository layout, conventions, workflow |
| [testing-and-ci.md](testing-and-ci.md) | The regression test approach, why a driver harness was chosen, and the CI workflow |
| [concurrency-refactor.md](concurrency-refactor.md) | Why the original `CONEW-N` fails under multi-user load and how the refactor fixes it |

Regenerate the data dictionary after changing any DDM:

```bash
python3 tools/generate_data_dictionary.py
```

Run the regression suite:

```bash
python3 -m unittest discover -s tests -v
```
