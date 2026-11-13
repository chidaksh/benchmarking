# tenforty engine check

A test of whether the open tax engine `tenforty` can supply the answer key for households we write, and whether it can drive a three-year chain with a capital loss carryover.
No model was called.

## Setup

- `tenforty==2025.14` on Python 3.12.13; all package versions are in `requirements.txt`.
- The default backend is OpenTaxSolver ("OTS"); the newer "graph" backend covers tax years 2024 and 2025 only.
- The README Quick Start household reproduces exactly (`smoke_check.py`): total tax $4,476, federal income tax $3,346, state tax $1,130.

## Calibration against TaxCalcBench (tax year 2025)

Expected amounts are from TaxCalcBench's expected returns, which come from a commercial tax engine.
Each case's inputs and their sources are in `cases/`; `compare.py` produces `calibration_results.json`.

| Case | Fully represented | Backend that ran | Result |
|---|---|---|---|
| `ty25-us-006` | Yes | OTS and graph | All 8 federal amounts within $1: AGI, QBI deduction, taxable income, income tax, self-employment tax, net investment income tax, Additional Medicare Tax, total tax |
| `ty25-ca-006` | Yes | OTS | Federal AGI, California AGI, taxable income, total tax exact |
| `ty25-ca-010` | Yes | OTS | Federal AGI, California AGI, taxable income, total tax exact |
| `ty25-ny-009` | Yes | OTS | Federal AGI, New York AGI, taxable income, total tax exact |
| `ty25-il-005` | Yes | Graph | Federal AGI, base income, net income, tax before credits exact |
| `ty25-il-006` | Yes | Graph | Federal AGI, base income, net income, tax before credits exact |
| `ty25-va-009` | Yes | OTS | AGI and taxable income exact; tax $26.40 where $0 is expected |
| `ty25-va-003` | Yes | Neither | Did not run |
| `ty25-ca-003` | Partly | OTS | All compared lines exact, after $6,000 of taxable dependent care benefits was added to wages by hand |
| `ty25-ny-003` | Partly | OTS | Federal AGI $1,256 too high |

### Cause of each mismatch

- `ty25-va-009`: engine error. Virginia's 2025 Form 760 instructions set the tax to $0 when Virginia AGI is below the $11,950 filing threshold, and the engine computes tax anyway.
- `ty25-va-003`: engine gap. For Virginia on OTS, tenforty refuses the head of household status and refuses dependents.
- `ty25-ny-003`: engine gap. There is no input for $1,646 of adjustments or for $390 of taxable Social Security; $34,126.26 + $390 - $1,646 equals the expected $32,870 to the dollar.
- Illinois total tax: engine gap. There is no input for the state credits of $301 and $500.
- California and New York "tax before credits": not an error. The engine reports only tax after the automatic exemption and household credits, and that equals the expected total tax exactly.
- The graph backend refuses California, New York and Virginia for 2025 as not yet validated, so the two backends were compared only on `ty25-us-006`, where they agree.

### Against the decision rule

- Federal amounts match within $5 on every fully represented case that ran.
- State amounts do not all match, because of Virginia.
- By the rule fixed in the plan, that is "usable for federal only".

## Three-year chain with a capital loss carryover (federal only, OTS), first household

This household has a net loss every year; its saved results are `chain_results_household1.json` and `policyengine_results_household1.json`.
The second household, further down, is the current one.

Household: single filer.

| Year | Wages | Interest | Short-term sales | Long-term sales |
|---|---|---|---|---|
| 2023 | $95,000 | $1,200 | -$6,000 | -$20,000 |
| 2024 | $98,000 | $1,300 | +$1,000 | +$4,000 |
| 2025 | $101,000 | $1,400 | +$2,000 | +$5,000 |

- `carryover_worksheet.py` is the IRS Capital Loss Carryover Worksheet from the 2025 Schedule D instructions, line by line.
- It reproduces the example in IRS Publication 550 (2025): loss $7,000, taxable income $26,000, deduct $3,000, carry over $4,000; and loss $2,000, no carryover.
- `independent_tax.py` computes each year from the IRS standard deduction, rate schedule and Tax Table method, without the engine.
- `chain.py` adds the carryover into the next year's gains by type and writes `chain_results.json`.

| Year | Carried in (short, long) | Engine AGI | Check AGI | Engine taxable income | Check taxable income | Engine tax | Check tax | Carried out (short, long) |
|---|---|---|---|---|---|---|---|---|
| 2023 | 0, 0 | 93,200 | 93,200 | 79,350 | 79,350 | 12,770 | 12,770 | 3,000, 20,000 |
| 2024 | 3,000, 20,000 | 96,300 | 96,300 | 81,700 | 81,700 | 13,033 | 13,033 | 0, 15,000 |
| 2025 | 0, 15,000 | 99,400 | 99,400 | 83,650 | 83,650 | 13,323 | 13,323 | 0, 5,000 |

- The engine applied the $3,000 limit in all three years.
- Engine and independent check agree exactly on all nine amounts.
- The chain counts as supported under the plan's rule.

### Effect of a year-1 mistake

| Year | Correct tax | Whole loss deducted in year 1, nothing carried | Carryover not reduced by the $3,000 used |
|---|---|---|---|
| 2024 | 13,033 | 14,513 (+1,480) | 13,033 (no change) |
| 2025 | 13,323 | 15,173 (+1,850) | 13,323 (no change) |
| Carryover out of 2025 | 5,000 | 0 | 8,000 |

- Dropping the carryover moves later tax by $1,480 and $1,850, so that mistake is visible in later years.
- A wrong carryover amount that is still larger than the later gains does not move tax at all; it shows only in the carryover figure.
- The second column is an addition to the plan, which asked for one mistake.

## Not checked

- Federal income tax was compared with the commercial engine on one case only (`ty25-us-006`).
- The lower capital gains rates were not checked independently, because the household has a net loss every year; they appear only in the "nothing carried" column, where they match a hand calculation at 22% and 15%.
- The Publication 550 example does not say whether its loss is short-term or long-term, so it checks the total carried, not the split by type.
- The worksheet text is from the 2025 instructions and was applied to 2023 and 2024 on the assumption that its structure is the same.
- The 2023 brackets, the 2025 brackets up to 22% and all three standard deductions were confirmed on irs.gov; the 2024 bracket thresholds were not, though the engine agrees with them to the dollar.
- No state return was run in the chain.
- The engine returns cents where forms round to dollars, which was within tolerance here and was not studied further.

## PolicyEngine-US as the second engine

- `policyengine-us==2.117.10` on Python 3.12.13, in its own environment; versions are in `requirements-policyengine.txt`.
- `policyengine_check.py` produces `policyengine_results.json`; tenforty's amounts are read from its saved results.
- One run of all cases took 46 seconds and peaked at 1.7 GB of memory.
- Agreement rule fixed in advance: AGI and taxable income within $1, tax within $10.

### Variable map

| Our amount | PolicyEngine variable |
|---|---|
| Wages | `employment_income` |
| Interest | `taxable_interest_income` |
| Qualified dividends | `qualified_dividend_income` |
| Other ordinary dividends | `non_qualified_dividend_income` |
| Net short-term gain or loss | `short_term_capital_gains` |
| Net long-term gain or loss | `long_term_capital_gains` |
| Self-employment profit | `self_employment_income` |
| Gambling winnings | `miscellaneous_income` (see below) |
| Filing status | `filing_status`, set directly |
| AGI, taxable income | `adjusted_gross_income`, `taxable_income` |
| Income tax, Form 1040 line 16 | `income_tax_before_credits` |
| Total tax, Form 1040 line 24 | `income_tax_before_refundable_credits` + `self_employment_tax` + `additional_medicare_tax` |

- PolicyEngine has a `gambling_winnings` variable, but in this version it is not counted in gross income; it only limits the deduction for gambling losses.
- The winnings therefore have to be entered as `miscellaneous_income`, its general "other income" variable; whether to accept that mapping is an open decision.
- Form 1040 line 24 has no single variable, because PolicyEngine keeps self-employment tax and Additional Medicare Tax outside its income tax.
- PolicyEngine assumes California when no state is given, so every run sets a state; the federal amounts were confirmed identical under Texas, California and Virginia, and for filer ages 30, 40 and 64.
- Every input is read back after the run to confirm PolicyEngine kept the value entered.

### `ty25-us-006`

| Amount | Expected | tenforty | PolicyEngine | PolicyEngine without the gambling income |
|---|---|---|---|---|
| AGI | 249,935 | 249,935.23 | 249,935.22 | 199,935.22 |
| QBI deduction | 4,875 | 4,875.30 | 4,875.30 | 18,587.04 |
| Taxable income | 229,310 | 229,309.93 | 229,309.92 | 165,598.17 |
| Income tax | 48,402 | 48,402.18 | 48,402.18 | 31,510.56 |
| Self-employment tax | 14,129 | 14,129.55 | 14,129.55 | 14,129.55 |
| Net investment income tax | 1,026 | 1,026.00 | 1,026.00 | 1,026.00 |
| Additional Medicare Tax | 426 | 426.15 | 426.15 | 426.15 |
| Total tax | 63,983 | 63,983.88 | 63,983.87 | 47,092.26 |

- With the winnings entered as `miscellaneous_income`, PolicyEngine matches tenforty to the cent and the commercial engine within $1 on all eight amounts.

### Three-year chain

| Year | AGI (both engines) | Taxable income (both engines) | PolicyEngine tax | tenforty tax | Independent script | Carried out (both engines) |
|---|---|---|---|---|---|---|
| 2023 | 93,200 | 79,350 | 12,764.50 | 12,770 | 12,770 | 3,000 short, 20,000 long |
| 2024 | 96,300 | 81,700 | 13,027.00 | 13,033 | 13,033 | 0 short, 15,000 long |
| 2025 | 99,400 | 83,650 | 13,317.00 | 13,323 | 13,323 | 0 short, 5,000 long |

- AGI, taxable income and both carryover amounts are identical in every year.
- Tax differs by $5.50 or $6.00 each year, and the cause is rounding: the IRS Tax Table taxes the middle of a $50 row and rounds to a dollar, and PolicyEngine applies the rate schedule to the exact amount.
- For this household the IRS Tax Table figure, which tenforty and the independent script produce, is the one a filed return would show.

### Year-1 mistake variants

| Variant | Year | PolicyEngine tax | tenforty tax | Difference |
|---|---|---|---|---|
| Nothing carried forward | 2024 | 14,507 | 14,513 | -6.00 |
| Nothing carried forward | 2025 | 15,167 | 15,173 | -6.00 |
| Carryover not reduced by the $3,000 used | 2024 | 13,027 | 13,033 | -6.00 |
| Carryover not reduced by the $3,000 used | 2025 | 13,317 | 13,323 | -6.00 |

- The "nothing carried forward" years have net long-term gains, so the two engines also agree on the lower capital gains rates, apart from the same rounding.

### Virginia cases

| Case | Federal AGI | Virginia AGI | Virginia taxable income | Virginia tax |
|---|---|---|---|---|
| `ty25-va-009` | 11,000, exact | 11,000, exact | 1,320, exact | 0, exact |
| `ty25-va-003` | 46,311, exact | 46,311, exact | 34,771, exact | 1,741.83 against 1,741 |

- PolicyEngine applies the Virginia filing-threshold rule that tenforty missed, and it accepts head of household with dependents, which tenforty refused.
- For `ty25-va-003` PolicyEngine's tax after credits is 1,278.55, because it subtracts the low-income credit (463.28) from tax; the expected return shows the same $463 on line 23 as a payment, so this is a difference in where the credit sits, not in its amount.

### Against the agreement rule

- Chain and mistake variants: agree except explained rounding.
- `ty25-us-006`: agree, provided the gambling winnings are entered as `miscellaneous_income`.
- Both Virginia cases: agree with the expected return.

### Not checked

- No fully independent source was used for the net-gain years; they rest on the two engines agreeing and on the earlier hand calculation.
- Only two Virginia cases exist to test PolicyEngine's state amounts, and both are simple.
- PolicyEngine is licensed AGPL-3.0, which matters only if it is shipped inside the task's verifier image.

## Second household and the carryover cross-check

The first household never used up its carryover, so a wrong carryover amount could not change any tax.
The second household keeps the same wages and interest and changes the sales, so the carryover runs out in 2025 with both gain types left to tax.

| Year | Wages | Interest | Short-term sales | Long-term sales |
|---|---|---|---|---|
| 2023 | $95,000 | $1,200 | -$6,000 | -$14,000 |
| 2024 | $98,000 | $1,300 | +$1,000 | +$4,000 |
| 2025 | $101,000 | $1,400 | +$5,000 | +$12,000 |

### Carryover calculation checked three ways

- `carryover_worksheet.py`: the IRS 13-line worksheet.
- `carryover_crosscheck.py`, second method: the tax code's own rule, 26 U.S.C. 1212(b), which treats the allowed loss as a short-term gain and then nets the two buckets.
- `carryover_crosscheck.py`, third version: a port of the carryover function in OpenTaxSolver's 2023 federal program, which its authors wrote from the same IRS worksheet.
- All three agree on 305,880 generated cases, of which 145,433 have a carryover and 15,022 are in the low-income branch; both loss limits ($3,000 and $1,500) are covered.
- The comparison is sensitive: a deliberately wrong "long-term first" rule is caught in 12,675 of 55,880 cases, and a "one total" rule in 19,219.
- The OpenTaxSolver version is my port of its C code, not a run of its binary.
- IRS Publication 550 has no worked example with a short-term and long-term split; it has the one total-only example and the "use short-term losses first" rule.

### Independent script extended

- `independent_tax.py` now includes the Qualified Dividends and Capital Gain Tax Worksheet, lines 1 to 25, read from the 2025 Form 1040 instructions, with the 2023 and 2024 thresholds read from those years' instructions.
- Its Tax Table method reproduces five rows copied from the official IRS Tax Tables, including the 2024 row, so the 2024 brackets are now confirmed.

### Chain on both engines

| Year | Carried in (short, long) | AGI | Taxable income | tenforty tax | Independent script | PolicyEngine tax | Carried out (short, long) |
|---|---|---|---|---|---|---|---|
| 2023 | 0, 0 | 93,200 | 79,350 | 12,770 | 12,770 | 12,764.50 | 3,000, 14,000 |
| 2024 | 3,000, 14,000 | 96,300 | 81,700 | 13,033 | 13,033 | 13,027.00 | 0, 9,000 |
| 2025 | 0, 9,000 | 110,400 | 94,650 | 15,533 | 15,533 | 15,527.00 | 0, 0 |

- AGI, taxable income and the carryovers are identical on both engines and the independent script.
- tenforty and the independent script agree on tax to the dollar, including 2025, where $5,000 of short-term gain is taxed at ordinary rates and $3,000 of long-term gain at 15%.
- PolicyEngine is $5.50 to $6.00 lower each year, the same Tax Table rounding as before.

### Year-1 mistake variants

| Variant | Year | tenforty tax | Independent script | PolicyEngine tax | Change from correct |
|---|---|---|---|---|---|
| Nothing carried forward | 2024 | 14,513 | 14,513 | 14,507 | +1,480 |
| Nothing carried forward | 2025 | 16,883 | 16,883 | 16,877 | +1,350 |
| Carryover not reduced by the $3,000 used | 2024 | 13,033 | 13,033 | 13,027 | 0 |
| Carryover not reduced by the $3,000 used | 2025 | 14,943 | 14,943 | 14,937 | -590 |

- With this household a wrong carryover amount now changes tax, in 2025.
- In 2024 it still changes only the carryover figure (2,000 and 10,000 carried out, where 0 and 9,000 is correct).
- The independent script now covers the net-gain years too, and agrees with tenforty to the dollar on all nine variant-years.

### Not checked

- The variant "the $3,000 taken from long-term first" was not run; my hand estimate is about $140 of 2025 tax.
- The carryover has no fully independent execution: all three versions were written or ported by me, from two different official texts and one independent author's code.
- Everything is one single filer with wages, interest and capital gains; no state return, dividends or other carried item.

## Sources

- Schedule D instructions (2025), Capital Loss Carryover Worksheet: https://www.irs.gov/instructions/i1040sd
- Publication 550 (2025), "Figuring your carryover": https://www.irs.gov/pub/irs-pdf/p550.pdf
- Rev. Proc. 2022-38 (2023 amounts): https://www.irs.gov/pub/irs-drop/rp-22-38.pdf
- Rev. Proc. 2023-34 (2024 amounts): https://www.irs.gov/pub/irs-drop/rp-23-34.pdf
- Rev. Proc. 2024-40 (2025 amounts): https://www.irs.gov/pub/irs-drop/rp-24-40.pdf
- 2025 standard deduction: https://www.irs.gov/publications/p17
- Virginia 2025 Form 760 instructions: https://www.tax.virginia.gov/sites/default/files/vatax-pdf/2025-760-instructions.pdf
- 26 U.S.C. 1212(b) and 1211(b): https://www.law.cornell.edu/uscode/text/26/1212 and https://www.law.cornell.edu/uscode/text/26/1211
- Form 1040 instructions with the capital gains worksheet and Tax Tables: https://www.irs.gov/pub/irs-pdf/i1040gi.pdf (2025), https://www.irs.gov/pub/irs-prior/i1040gi--2024.pdf, https://www.irs.gov/pub/irs-prior/i1040gi--2023.pdf
- OpenTaxSolver carryover function: `CapitalLossCarryOverWorksheet` in its 2023 US_1040 program, as bundled with tenforty 2025.14
