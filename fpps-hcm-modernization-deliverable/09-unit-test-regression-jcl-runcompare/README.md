# Unit-test, regression, and JCL run-compare generation

Generated unit tests and regression suites for extracted rules, CI integration, and a run-compare design for batch/JCL output — the test-automation ask, not migration.

| | |
|---|---|
| **Capability** | Unit-test, regression, and JCL run-compare generation |
| **Why it matters to an SI implementing an HCM** | Regression coverage protects the pay run during and after cut-over and is the fastest way to demonstrate that a rule extracted in 02 still holds after HCM configuration. |
| **Builds on** | `../tests/`, `../.github/workflows/regression-tests.yml`, `../.github/workflows/codeql-analysis.yml`, `../docs/testing-and-ci.md` |
| **Maturity** | Demonstrated for unit/regression on the sample; JCL run-compare is Designed (no FPPS JCL in this repository) |

## Contents

- `test-generation-approach.md` — rule → test derivation and CI gating
- `regression-suite-map.md` — existing tests mapped to rules and requirements
- `jcl-runcompare-design.md` — run-compare for batch outputs (designed)
- `diagrams/` — CI and run-compare flows

## How an SI consumes this

Adopt the rule → test mapping as the acceptance-test backbone; run the regression suite on every configuration change; plan the batch run-compare against the ~7,800-job inventory once JCL and Control-M exports are available.

## Synthetic data and scope

All evidence in this directory is produced from the Sunny Islands Cruise sample sources and synthetic data in `../../tests/harness/`. No production system, production data, or FPPS source is used or required. FPPS statements are analogies to a Software AG Natural 9.x / ADABAS 8.6 estate (~7M lines of Natural, 100k+ modules, ~7,800 JCL jobs); nothing here proposes a language rewrite.

← [Back to the navigation hub](../README.md)
