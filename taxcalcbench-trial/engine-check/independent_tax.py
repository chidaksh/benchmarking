"""Federal tax for a single filer with wages, interest and capital gains or losses, from IRS figures only."""

from carryover_worksheet import allowed_loss

# Standard deduction for a single filer, by tax year.
STANDARD_DEDUCTION = {2023: 13850, 2024: 14600, 2025: 15750}

# Single-filer rate schedule: (upper limit of bracket, rate), by tax year.
RATE_SCHEDULE = {
    2023: [(11000, 0.10), (44725, 0.12), (95375, 0.22), (182100, 0.24)],
    2024: [(11600, 0.10), (47150, 0.12), (100525, 0.22), (191950, 0.24)],
    2025: [(11925, 0.10), (48475, 0.12), (103350, 0.22), (197300, 0.24)],
}

# Qualified Dividends and Capital Gain Tax Worksheet, lines 6 and 13, single filer.
CAPITAL_GAIN_THRESHOLDS = {2023: (44625, 492300), 2024: (47025, 518900), 2025: (48350, 533400)}

# Rows copied from the IRS Tax Tables (single column): (year, row start) -> tax.
PUBLISHED_TAX_TABLE_ROWS = {
    (2023, 79350): 12770,
    (2024, 81700): 13033,
    (2025, 83650): 13323,
    (2025, 91650): 15083,
    (2025, 94650): 15743,
}


def schedule_tax(year, taxable_income):
    """Tax from the rate schedule, unrounded."""
    tax, lower = 0.0, 0
    for upper, rate in RATE_SCHEDULE[year]:
        if taxable_income <= lower:
            break
        tax += (min(taxable_income, upper) - lower) * rate
        lower = upper
    if taxable_income > RATE_SCHEDULE[year][-1][0]:
        raise ValueError("taxable income is above the brackets entered here")
    return tax


def income_tax(year, taxable_income):
    """Tax Table below 100,000 (midpoint of the 50-dollar row), rate schedule above."""
    if taxable_income >= 100000:
        return schedule_tax(year, taxable_income)
    if taxable_income < 3000:
        raise ValueError("Tax Table rows below 3,000 are narrower and not entered here")
    row_start = taxable_income // 50 * 50
    return int(schedule_tax(year, row_start + 25) + 0.5)


def capital_gain_worksheet_tax(year, taxable_income, preferential_gain):
    """Qualified Dividends and Capital Gain Tax Worksheet, lines 1 to 25, with no qualified dividends."""
    zero_rate_limit, fifteen_rate_limit = CAPITAL_GAIN_THRESHOLDS[year]
    line1 = taxable_income
    line4 = preferential_gain
    line5 = max(line1 - line4, 0)
    line7 = min(line1, zero_rate_limit)
    line8 = min(line5, line7)
    line9 = line7 - line8
    line10 = min(line1, line4)
    line12 = line10 - line9
    line14 = min(line1, fifteen_rate_limit)
    line15 = line5 + line9
    line16 = max(line14 - line15, 0)
    line17 = min(line12, line16)
    line18 = line17 * 0.15
    line19 = line9 + line17
    line20 = line10 - line19
    line21 = line20 * 0.20
    line22 = income_tax(year, line5)
    line23 = line18 + line21 + line22
    line24 = income_tax(year, line1)
    return min(line23, line24)


def federal_return(year, wages, interest, net_short_term, net_long_term):
    """Return AGI, taxable income and tax (Form 1040 line 16)."""
    net = net_short_term + net_long_term
    capital_line = net if net >= 0 else -allowed_loss(net_short_term, net_long_term)
    agi = wages + interest + capital_line
    taxable_income = max(agi - STANDARD_DEDUCTION[year], 0)
    # Worksheet line 3: the smaller of Schedule D line 15 or 16, zero if either is a loss.
    preferential_gain = min(net_long_term, net) if net_long_term > 0 and net > 0 else 0
    if preferential_gain > 0:
        tax = capital_gain_worksheet_tax(year, taxable_income, preferential_gain)
    else:
        tax = income_tax(year, taxable_income)
    return {"agi": agi, "taxable_income": taxable_income, "tax": tax}


def check_against_published_rows():
    """The Tax Table method must reproduce the rows copied from the IRS instructions."""
    for (year, row_start), published in PUBLISHED_TAX_TABLE_ROWS.items():
        assert income_tax(year, row_start) == published, (year, row_start, income_tax(year, row_start), published)


if __name__ == "__main__":
    check_against_published_rows()
    print(f"Tax Table method reproduces {len(PUBLISHED_TAX_TABLE_ROWS)} published IRS rows.")
