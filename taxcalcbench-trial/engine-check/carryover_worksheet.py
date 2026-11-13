"""IRS Capital Loss Carryover Worksheet (Schedule D instructions, lines 6 and 14), line by line."""

LOSS_LIMIT = 3000


def allowed_loss(line7, line15, limit=LOSS_LIMIT):
    """Schedule D line 21 as a positive amount: the deductible part of a net capital loss."""
    net = line7 + line15
    return min(limit, -net) if net < 0 else 0


def capital_loss_carryover(taxable_income, line7, line15, limit=LOSS_LIMIT):
    """Return (short_term, long_term) carryover to the next year.

    taxable_income is Form 1040 line 15, negative if deductions exceed income.
    line7 and line15 are the prior year's Schedule D net short-term and long-term results.
    """
    line2 = allowed_loss(line7, line15, limit)
    if line2 == 0:
        return 0, 0
    line1 = taxable_income
    line3 = max(line1 + line2, 0)
    line4 = min(line2, line3)

    line5 = -line7 if line7 < 0 else 0
    short_term = 0
    if line7 < 0:
        line6 = max(line15, 0)
        line7_sum = line4 + line6
        short_term = max(line5 - line7_sum, 0)

    long_term = 0
    if line15 < 0:
        line9 = -line15
        line10 = max(line7, 0)
        line11 = max(line4 - line5, 0)
        line12 = line10 + line11
        long_term = max(line9 - line12, 0)
    return short_term, long_term


def check_against_publication_550():
    """Reproduce the example in IRS Publication 550 (2025), "Figuring your carryover"."""
    # Bob and Shelly: capital loss 7,000, taxable income 26,000, deduct 3,000, carry over 4,000.
    assert allowed_loss(-7000, 0) == 3000
    assert capital_loss_carryover(26000, -7000, 0) == (4000, 0)
    assert capital_loss_carryover(26000, 0, -7000) == (0, 4000)
    # Same couple with a 2,000 loss: deduct 2,000, no carryover.
    assert allowed_loss(-2000, 0) == 2000
    assert capital_loss_carryover(26000, -2000, 0) == (0, 0)
    assert capital_loss_carryover(26000, 0, -2000) == (0, 0)
    # Own numbers for the publication's "use short-term losses first" rule, not a published example.
    assert capital_loss_carryover(26000, -2000, -5000) == (0, 4000)


if __name__ == "__main__":
    check_against_publication_550()
    print("Publication 550 example reproduced: loss 7,000 -> deduct 3,000, carry over 4,000; loss 2,000 -> no carryover.")
