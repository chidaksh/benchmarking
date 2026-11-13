# TaxCalcBench trial

A check of whether known tax calculation failures of Opus 5.5 carry over to Claude Code with Opus 5.5 on Harbor.

- Source: [TaxCalcBench](https://github.com/column-tax/tax-calc-bench) tax year 2025 set (50 cases, MIT license, commit `9ccca924`).
- Picked three cases that plain Opus 5.5 failed at all five effort levels in the benchmark's published results without web search.
- Checked reproducibility with the benchmark's own runner: plain Opus 5.5 failed 3 of 3, on the same lines as the published runs.
- Wrapped each case as a Harbor task with the benchmark's prompt and evaluator, and ran Claude Code with Opus 5.5: it failed the same 3 of 3, on the same lines.
- Both setups used effort `high` (the benchmark calls this level "medium") and had no web access.
- Harbor settings: Claude Code 2.1.322, 20-minute agent limit, no memory, CPU or cost limits, and Python, `poppler-utils` and `pypdf` in the container.
- The only change to the prompt for Harbor is two lines saying where the input files are and where to write the answer.
- `ty25-ca-003` failed because California's 2025 Earned Income Tax Credit table was not in the container; with the official FTB 3514 booklet added to the inputs, it passed.
- `ty25-ny-003` has an inconsistent input: the data file answers "no" to "Paid interest on student loans" and still lists $98 of interest, and the expected return deducts the $98.
- The model left the $98 out, so its federal adjusted gross income is $98 too high, and that error reaches every other failing line.
- The $204 difference in total payments for `ty25-ny-003` has two parts: $5 in the New York State earned income credit, which follows from the $98, and $199 in the New York City earned income credit.
- For the New York City credit the model used 10% of the federal credit and the expected return uses 15% ($592 of $3,944); the rate table was not among the inputs, and the 15% has not been checked against the official instructions.
- The expected return for `ty25-ny-003` also counts the $845 in box 3 ("Other income") of the 1099-MISC as business income, which no input states; this run made the same choice, so it caused no failing line here.
- Every configuration was run once, so these are single outcomes and not rates.

| Case | Sufficient information | Plain Opus 5.5 | Claude Code with Opus 5.5 on Harbor |
|---|---|---|---|
| `ty25-ca-003` | No | Fail, 10 of 14 lines correct | Fail, 10 of 14 lines correct |
| `ty25-ca-003` with FTB 3514 booklet | Yes | Not run | Pass, 14 of 14 lines correct |
| `ty25-ny-003` | No | Fail, 8 of 18 lines correct | Fail, 8 of 18 lines correct |
| `ty25-us-006` | Yes | Fail, 17 of 19 lines correct | Fail, 17 of 19 lines correct |

- `ty25-us-006` is off by $1 from a rounding step: the expected Schedule SE rounds the 12.4% part ($11,451) and the 2.9% part ($2,678) separately for $14,129, and the model applied 15.3% once and rounded to $14,130.

## Saved runs

The repository's `jobs/` folder holds only the Claude Code with Opus 5.5 runs for these four samples, and `harbor view jobs` opens them without Docker or an API key.

- `jobs/taxcalcbench-ca-003-claude-code-opus-5-5-high`: `ty25-ca-003`.
- `jobs/taxcalcbench-ca-003-with-ftb3514-booklet-claude-code-opus-5-5-high`: `ty25-ca-003` with the booklet.
- `jobs/taxcalcbench-us-006-ny-003-claude-code-opus-5-5-high`: `ty25-us-006` and `ty25-ny-003`.

The plain Opus 5.5 runs are not in `jobs/`; their output is in `reproduction-logs/`.
