You are preparing U.S. federal income tax returns for one taxpayer for three consecutive tax years: 2023, 2024 and 2025.

Taxpayer: Morgan T. Avery, single, born in 1985, not blind, no dependents, and cannot be claimed as a dependent by anyone. They were a U.S. resident for all three years. They take the standard deduction. The documents listed below are their only income; they have no other income, adjustments or credits to consider, and no digital asset transactions.

All files are in `/app/documents/`, one folder per tax year. Each folder holds that year's taxpayer documents together with the official IRS forms and instructions for that year:
- `/app/documents/2023/`: `w2.pdf`, `1099-int.pdf`, `1099-b_1.pdf`, `1099-b_2.pdf`, `form-1040.pdf`, `form-1040-instructions.pdf`, `schedule-d.pdf`, `schedule-d-instructions.pdf`
- `/app/documents/2024/`: the same eight files for 2024
- `/app/documents/2025/`: the same eight files for 2025

Prepare Form 1040 and Schedule D for each year, as the taxpayer should have filed them. Round amounts to whole dollars as the forms do.

Write your answer to `/app/output/returns.json`. Only that file is graded. Use exactly this structure, with one entry per year and a loss written as a negative number:

```json
{
  "2023": {
    "schedule_d_net_short_term": 0,
    "schedule_d_net_long_term": 0,
    "form_1040_capital_gain_or_loss": 0,
    "adjusted_gross_income": 0,
    "taxable_income": 0,
    "tax": 0
  },
  "2024": { "...": "the same six fields" },
  "2025": { "...": "the same six fields" }
}
```

Field meanings:
- `schedule_d_net_short_term`: Schedule D, line 7
- `schedule_d_net_long_term`: Schedule D, line 15
- `form_1040_capital_gain_or_loss`: the capital gain or loss line of Form 1040
- `adjusted_gross_income`: the adjusted gross income line of Form 1040
- `taxable_income`: Form 1040, line 15
- `tax`: Form 1040, line 16
