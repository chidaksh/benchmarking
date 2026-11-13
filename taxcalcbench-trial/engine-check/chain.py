"""Three-year federal chain with a capital loss carryover: engine, independent check, and a deliberate mistake."""

import json
from pathlib import Path

import tenforty

from carryover_worksheet import capital_loss_carryover, check_against_publication_550
from household import FILING_STATUS, HOUSEHOLD, VARIANTS
from independent_tax import check_against_published_rows, federal_return

TOLERANCE = 5


def run_chain(first_carryover_override=None):
    """Run the three years in order, carrying the loss forward by type.

    first_carryover_override replaces the carryover out of year 1, to model a year-1 mistake.
    """
    rows = []
    carry_short, carry_long = 0, 0
    for index, year_facts in enumerate(HOUSEHOLD):
        net_short = year_facts["short_term"] - carry_short
        net_long = year_facts["long_term"] - carry_long
        engine = tenforty.evaluate_return(
            year=year_facts["year"],
            filing_status=FILING_STATUS,
            w2_income=year_facts["wages"],
            taxable_interest=year_facts["interest"],
            short_term_capital_gains=net_short,
            long_term_capital_gains=net_long,
        )
        next_short, next_long = capital_loss_carryover(engine.federal_taxable_income, net_short, net_long)
        if index == 0 and first_carryover_override is not None:
            next_short, next_long = first_carryover_override
        rows.append(
            {
                "year": year_facts["year"],
                "carry_in_short": carry_short,
                "carry_in_long": carry_long,
                "net_short": net_short,
                "net_long": net_long,
                "engine_agi": engine.federal_adjusted_gross_income,
                "engine_taxable_income": engine.federal_taxable_income,
                "engine_income_tax": engine.federal_income_tax,
                "engine_total_tax": engine.federal_total_tax,
                "carry_out_short": next_short,
                "carry_out_long": next_long,
            }
        )
        carry_short, carry_long = next_short, next_long
    return rows


def add_independent_check(rows):
    """Attach the independent figures and the differences to each year."""
    for row, year_facts in zip(rows, HOUSEHOLD):
        check = federal_return(row["year"], year_facts["wages"], year_facts["interest"], row["net_short"], row["net_long"])
        row["check_agi"], row["check_taxable_income"], row["check_tax"] = check["agi"], check["taxable_income"], check["tax"]
        differences = [
            row["engine_agi"] - check["agi"],
            row["engine_taxable_income"] - check["taxable_income"],
            row["engine_total_tax"] - check["tax"],
        ]
        row["max_abs_difference"] = max(abs(d) for d in differences)
        row["agrees"] = row["max_abs_difference"] <= TOLERANCE


def main():
    check_against_publication_550()
    check_against_published_rows()

    results = {name: run_chain(first_carryover_override=override) for name, override in VARIANTS.items()}
    for rows in results.values():
        add_independent_check(rows)

    correct = results["correct"]
    print("Correct chain")
    print("| Year | Carry in (ST, LT) | Net ST | Net LT | Engine AGI | Check AGI | Engine taxable | Check taxable | Engine tax | Check tax | Carry out (ST, LT) | Agrees |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in correct:
        print(
            f"| {r['year']} | {r['carry_in_short']}, {r['carry_in_long']} | {r['net_short']} | {r['net_long']} "
            f"| {r['engine_agi']} | {r['check_agi']} | {r['engine_taxable_income']} | {r['check_taxable_income']} "
            f"| {r['engine_total_tax']} | {r['check_tax']} | {r['carry_out_short']}, {r['carry_out_long']} | {r['agrees']} |"
        )

    print("\nEffect of a year-1 mistake on later years")
    print("| Variant | Year | Carry in (ST, LT) | Engine tax | Check tax | Agrees | Tax against correct | Carry out (ST, LT) |")
    print("|---|---|---|---|---|---|---|---|")
    for name, rows in results.items():
        if name == "correct":
            continue
        for c, r in zip(correct, rows):
            print(
                f"| {name} | {r['year']} | {r['carry_in_short']}, {r['carry_in_long']} | {r['engine_total_tax']} | {r['check_tax']} "
                f"| {r['agrees']} | {r['engine_total_tax'] - c['engine_total_tax']:+.2f} | {r['carry_out_short']}, {r['carry_out_long']} |"
            )

    Path(__file__).with_name("chain_results.json").write_text(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
