# blastradius — know what a change breaks before CI does

A small, dependency-free CLI a team can drop into any Python repo. It answers the two questions the RWX "Blast Radius" problem is about, as an actual tool rather than a benchmark entry:

1. **`impact`** — given a set of changed files (default: your uncommitted changes), which tests actually need to run? Skip the rest and cut CI time.
2. **`culprit`** — given a failing test and a range of commits, which commit most likely broke it?

It builds a real import/dependency graph (direct imports, `from pkg import x` through `__init__`, dynamic `import_module("...")`, and data files opened by literal path), then reasons over it. No network, no services, standard library only — so it runs in any CI sandbox.

## Why a company would use this
Running the whole test suite on every PR is slow and expensive. `blastradius impact` lets CI run only the tests a change can actually affect, and `blastradius culprit` turns "main is red, which of these 12 commits did it" into one command instead of a manual bisect. Both are everyday costs in any monorepo — the exact problem space RWX builds tooling for.

## Use

```bash
# Which tests must run for my current uncommitted changes?
python3 -m blastradius impact

# ...for a specific set of files, as JSON (for a CI script):
python3 -m blastradius impact --files src/billing/rates.py --format json

# Which commit broke a test? (searches the last 20 commits by default)
python3 -m blastradius culprit tests/test_rates.py --since HEAD~20
```

`impact` exits non-zero if it can't build the graph; `culprit` prints a ranked list with the reason each commit is suspected (it changed a symbol on the failing test's dependency path). Run `python3 -m blastradius --help` for options.

## How it decides
- **impact:** compute the transitive dependency closure of each test; a test is affected if any changed file is in its closure. Conservative by design — when unsure it includes the test, because skipping a test that should run is the dangerous error.
- **culprit:** parse the failing test's dependency cone; rank commits by whether they changed a symbol something in that cone uses, preferring the change closest to the failure. Falls back to "nearest change in the cone" when the failure log names no symbol.

The algorithm is the one the practice harness (`practice/rwx_blast_radius`) scored to 100% on synthetic data and ~76–100% depending on how much the failure log reveals. This is that logic wired to a real git repo.

## Limits
Static analysis over Python source: it sees imports and literal-path file reads, not reflection, config-driven loading, or generated code. It errs toward over-including tests. It is a fast first pass, not a correctness proof.
