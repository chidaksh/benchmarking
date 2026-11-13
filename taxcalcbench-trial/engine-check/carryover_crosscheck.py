"""Check the worksheet carryover against two other formulations on many generated inputs."""

import itertools
import random

from carryover_worksheet import capital_loss_carryover


def carryover_from_statute(taxable_income, net_short, net_long, limit=3000):
    """26 U.S.C. 1212(b): treat the allowed loss as a short-term gain, then net the two buckets."""
    if net_short + net_long >= 0:
        return 0, 0
    # 1211(b): the lower of the limit or the excess of losses over gains.
    allowed = min(limit, -(net_short + net_long))
    # 1212(b)(2)(B): taxable income plus the allowed loss; personal exemptions are zero in these years.
    adjusted_taxable_income = max(taxable_income + allowed, 0)
    deemed_short_term_gain = min(allowed, adjusted_taxable_income)
    short = net_short + deemed_short_term_gain
    short_loss, short_gain = max(-short, 0), max(short, 0)
    long_loss, long_gain = max(-net_long, 0), max(net_long, 0)
    return max(short_loss - long_gain, 0), max(long_loss - short_gain, 0)


def carryover_as_opentaxsolver(taxable_income, net_short, net_long, limit=3000):
    """Port of CapitalLossCarryOverWorksheet in OpenTaxSolver's 2023 US_1040 program."""
    line16 = net_short + net_long
    line21 = -min(limit, -line16) if line16 < 0 else 0.0
    if line21 == 0.0:
        return 0, 0
    if abs(line21) >= abs(line16) and taxable_income >= 0.0:
        return 0, 0
    ws = [0.0] * 14
    ws[1] = taxable_income
    ws[2] = abs(line21)
    ws[3] = max(ws[1] + ws[2], 0)
    ws[4] = min(ws[2], ws[3])
    short = long = 0
    if net_short < 0.0:
        ws[5] = -net_short
        ws[6] = max(net_long, 0)
        ws[7] = ws[4] + ws[6]
        ws[8] = max(ws[5] - ws[7], 0)
        short = ws[8]
    if net_long < 0.0:
        ws[9] = abs(net_long)
        ws[10] = max(net_short, 0)
        ws[11] = max(ws[4] - ws[5], 0)
        ws[12] = ws[10] + ws[11]
        ws[13] = max(ws[9] - ws[12], 0)
        long = ws[13]
    return short, long


def generated_inputs(count, seed=20261112):
    """Edge values on a grid, then random whole-dollar cases, for both loss limits."""
    edges = [-30000, -9000, -3001, -3000, -2999, -2200, -1500, -1, 0, 1, 1500, 3000, 9000, 30000]
    incomes = [-20000, -3001, -3000, -2999, -1500, -1, 0, 1, 1499, 1500, 2999, 3000, 3001, 26000, 80000]
    for income, short, long, limit in itertools.product(incomes, edges, edges, (3000, 1500)):
        yield income, short, long, limit
    rng = random.Random(seed)
    for _ in range(count):
        yield rng.randint(-20000, 200000), rng.randint(-40000, 40000), rng.randint(-40000, 40000), rng.choice((3000, 1500))


def main():
    total, with_carryover, low_income = 0, 0, 0
    disagreements = []
    for income, short, long, limit in generated_inputs(300000):
        worksheet = capital_loss_carryover(income, short, long, limit)
        statute = carryover_from_statute(income, short, long, limit)
        opentaxsolver = carryover_as_opentaxsolver(income, short, long, limit)
        total += 1
        with_carryover += worksheet != (0, 0)
        low_income += short + long < 0 and income + min(limit, -(short + long)) < min(limit, -(short + long))
        if not (worksheet == statute == opentaxsolver):
            disagreements.append((income, short, long, limit, worksheet, statute, opentaxsolver))
    print(f"cases: {total}; with a carryover: {with_carryover}; in the low-income branch: {low_income}")
    print(f"disagreements: {len(disagreements)}")
    for row in disagreements[:10]:
        print("  income, short, long, limit, worksheet, statute, opentaxsolver:", row)
    return 1 if disagreements else 0


if __name__ == "__main__":
    raise SystemExit(main())
