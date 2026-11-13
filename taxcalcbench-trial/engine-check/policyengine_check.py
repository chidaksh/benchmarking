"""Run the federal case, the three-year chain and the Virginia cases on PolicyEngine-US and compare with tenforty."""

import json
from pathlib import Path

from policyengine_us import Simulation

from carryover_worksheet import capital_loss_carryover
from household import FILING_STATUS, HOUSEHOLD, VARIANTS
from independent_tax import federal_return

HERE = Path(__file__).parent
INCOME_TOLERANCE = 1
TAX_TOLERANCE = 10

# Our input name -> PolicyEngine person variable.
PERSON_INPUTS = {
    "w2_income": "employment_income",
    "taxable_interest": "taxable_interest_income",
    "qualified_dividends": "qualified_dividend_income",
    "non_qualified_dividends": "non_qualified_dividend_income",
    "short_term_capital_gains": "short_term_capital_gains",
    "long_term_capital_gains": "long_term_capital_gains",
    "self_employment_income": "self_employment_income",
    "other_income": "miscellaneous_income",
}

FILING_STATUS_MAP = {
    "Single": "SINGLE",
    "Married/Sep": "SEPARATE",
    "Head_of_House": "HEAD_OF_HOUSEHOLD",
}

# Our output name -> PolicyEngine variables to add up.
OUTPUTS = {
    "federal_adjusted_gross_income": ["adjusted_gross_income"],
    "federal_qbi_deduction": ["qualified_business_income_deduction"],
    "federal_taxable_income": ["taxable_income"],
    "federal_income_tax": ["income_tax_before_credits"],
    "federal_se_tax": ["self_employment_tax"],
    "federal_niit": ["net_investment_income_tax"],
    "federal_additional_medicare_tax": ["additional_medicare_tax"],
    # Form 1040 line 24 has no single variable: PolicyEngine keeps these two taxes outside its income tax.
    "federal_total_tax": ["income_tax_before_refundable_credits", "self_employment_tax", "additional_medicare_tax"],
    "state_adjusted_gross_income": ["va_agi"],
    "state_taxable_income": ["va_taxable_income"],
    "state_tax_before_credits": ["va_income_tax_before_non_refundable_credits"],
    "state_total_tax": ["va_income_tax_before_refundable_credits"],
}


def run(year, state, filing_status, filer_age, incomes, dependent_ages=(), outputs=OUTPUTS):
    """Build one household, run it, and return the requested outputs as plain floats."""
    y = str(year)
    filer = {"age": {y: filer_age}}
    for name, value in incomes.items():
        filer[PERSON_INPUTS[name]] = {y: value}
    people = {"filer": filer}
    for index, age in enumerate(dependent_ages):
        people[f"dependent_{index + 1}"] = {"age": {y: age}}
    members = list(people)
    situation = {
        "people": people,
        "tax_units": {"tax_unit": {"members": members, "filing_status": {y: FILING_STATUS_MAP[filing_status]}}},
        "families": {"family": {"members": members}},
        "spm_units": {"spm_unit": {"members": members}},
        "households": {"household": {"members": members, "state_name": {y: state}}},
    }
    simulation = Simulation(situation=situation)
    result = {}
    for name, variables in outputs.items():
        result[name] = round(sum(float(simulation.calculate(v, year).sum()) for v in variables), 2)
    # Read the inputs back to confirm PolicyEngine kept them as entered.
    for name, value in incomes.items():
        kept = float(simulation.calculate(PERSON_INPUTS[name], year).sum())
        if abs(kept - value) > 0.01:
            raise ValueError(f"{PERSON_INPUTS[name]} was entered as {value} but reads back as {kept}")
    return result


def verdict(name, difference):
    """Classify a difference under the agreement rule."""
    limit = INCOME_TOLERANCE if name.endswith(("adjusted_gross_income", "taxable_income")) else TAX_TOLERANCE
    if abs(difference) < 0.005:
        return "exact"
    return f"within ${limit}" if abs(difference) <= limit else "ABOVE TOLERANCE"


def case_incomes(case, include_other_income):
    """Translate a tenforty case file's inputs into our PolicyEngine input names."""
    values = {name: entry["value"] for name, entry in case["inputs"].items()}
    incomes = {}
    for name in ("w2_income", "taxable_interest", "qualified_dividends", "short_term_capital_gains", "long_term_capital_gains", "self_employment_income"):
        if name in values:
            incomes[name] = values[name]
    if "ordinary_dividends" in values:
        incomes["non_qualified_dividends"] = values["ordinary_dividends"] - values.get("qualified_dividends", 0)
    if include_other_income and "schedule_1_income" in values:
        incomes["other_income"] = values["schedule_1_income"]
    return values["filing_status"], incomes


def smoke_check():
    """Single filer with 50,000 of wages in 2025."""
    result = run(2025, "TX", "Single", 40, {"w2_income": 50000})
    check = federal_return(2025, 50000, 0, 0, 0)
    assert result["federal_adjusted_gross_income"] == 50000, result
    assert result["federal_taxable_income"] == 34250, result
    assert abs(result["federal_income_tax"] - check["tax"]) <= TAX_TOLERANCE, (result, check)
    print(f"Smoke check passed: AGI 50,000, taxable income 34,250, tax {result['federal_income_tax']} against {check['tax']} from the Tax Table.")


def federal_case(tenforty_rows):
    """ty25-us-006 on PolicyEngine, with and without the gambling income entered as miscellaneous income."""
    case = json.loads((HERE / "cases" / "ty25-us-006.json").read_text())
    names = list(case["expected"])
    federal_outputs = {n: OUTPUTS[n] for n in names}
    results = {}
    for label, include in (("gambling_not_entered", False), ("gambling_as_miscellaneous_income", True)):
        filing_status, incomes = case_incomes(case, include)
        results[label] = run(2025, "FL", filing_status, 24, incomes, outputs=federal_outputs)
    tenforty = {r["amount"]: r["ots"] for r in tenforty_rows if r["case"] == "ty25-us-006"}

    print("\nty25-us-006")
    print("| Amount | Expected | tenforty | PolicyEngine, gambling not entered | PolicyEngine, gambling as miscellaneous income | Against expected | Against tenforty |")
    print("|---|---|---|---|---|---|---|")
    for name in names:
        expected = case["expected"][name]["value"]
        with_income = results["gambling_as_miscellaneous_income"][name]
        print(
            f"| {name} | {expected} | {round(tenforty[name], 2)} | {results['gambling_not_entered'][name]} | {with_income} "
            f"| {verdict(name, with_income - expected)} ({with_income - expected:+.2f}) | {verdict(name, with_income - tenforty[name])} ({with_income - tenforty[name]:+.2f}) |"
        )
    return results


def chain(first_carryover_override):
    """Run the three years on PolicyEngine, carrying its own loss forward by type."""
    rows = []
    carry_short, carry_long = 0, 0
    chain_outputs = {n: OUTPUTS[n] for n in ("federal_adjusted_gross_income", "federal_taxable_income", "federal_total_tax")}
    for index, facts in enumerate(HOUSEHOLD):
        net_short = facts["short_term"] - carry_short
        net_long = facts["long_term"] - carry_long
        incomes = {
            "w2_income": facts["wages"],
            "taxable_interest": facts["interest"],
            "short_term_capital_gains": net_short,
            "long_term_capital_gains": net_long,
        }
        result = run(facts["year"], "TX", FILING_STATUS, 40, incomes, outputs=chain_outputs)
        next_short, next_long = capital_loss_carryover(result["federal_taxable_income"], net_short, net_long)
        if index == 0 and first_carryover_override is not None:
            next_short, next_long = first_carryover_override
        rows.append(
            {
                "year": facts["year"],
                "net_short": net_short,
                "net_long": net_long,
                "agi": result["federal_adjusted_gross_income"],
                "taxable_income": result["federal_taxable_income"],
                "total_tax": result["federal_total_tax"],
                "carry_out_short": next_short,
                "carry_out_long": next_long,
            }
        )
        carry_short, carry_long = next_short, next_long
    return rows


def chain_tables(tenforty_chain):
    """Compare the correct chain and the two mistake variants with tenforty and the independent script."""
    results = {name: chain(override) for name, override in VARIANTS.items()}

    print("\nCorrect chain")
    print("| Year | PolicyEngine AGI | tenforty AGI | PolicyEngine taxable | tenforty taxable | PolicyEngine tax | tenforty tax | Independent tax | Tax against tenforty | Carry out, PolicyEngine | Carry out, tenforty |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for pe, tf, facts in zip(results["correct"], tenforty_chain["correct"], HOUSEHOLD):
        independent = federal_return(pe["year"], facts["wages"], facts["interest"], pe["net_short"], pe["net_long"])
        difference = pe["total_tax"] - tf["engine_total_tax"]
        pe["agrees"] = (
            abs(pe["agi"] - tf["engine_agi"]) <= INCOME_TOLERANCE
            and abs(pe["taxable_income"] - tf["engine_taxable_income"]) <= INCOME_TOLERANCE
            and abs(difference) <= TAX_TOLERANCE
            and abs(pe["total_tax"] - independent["tax"]) <= TAX_TOLERANCE
            and (pe["carry_out_short"], pe["carry_out_long"]) == (tf["carry_out_short"], tf["carry_out_long"])
        )
        print(
            f"| {pe['year']} | {pe['agi']} | {tf['engine_agi']} | {pe['taxable_income']} | {tf['engine_taxable_income']} "
            f"| {pe['total_tax']} | {tf['engine_total_tax']} | {independent['tax']} | {verdict('tax', difference)} ({difference:+.2f}) "
            f"| {pe['carry_out_short']}, {pe['carry_out_long']} | {tf['carry_out_short']}, {tf['carry_out_long']} |"
        )
    print("All three years agree:", all(r["agrees"] for r in results["correct"]))

    print("\nYear-1 mistake variants (total tax)")
    print("| Variant | Year | Net short | Net long | PolicyEngine | tenforty | Difference |")
    print("|---|---|---|---|---|---|---|")
    for name in ("whole_loss_deducted_year1", "carryover_not_reduced"):
        for pe, tf in zip(results[name], tenforty_chain[name]):
            difference = pe["total_tax"] - tf["engine_total_tax"]
            print(f"| {name} | {pe['year']} | {pe['net_short']} | {pe['net_long']} | {pe['total_tax']} | {tf['engine_total_tax']} | {verdict('tax', difference)} ({difference:+.2f}) |")
    return results


def virginia_cases():
    """The two Virginia cases tenforty got wrong or refused."""
    people = {"ty25-va-009": (31, ()), "ty25-va-003": (31, (3, 1))}
    names = ("federal_adjusted_gross_income", "state_adjusted_gross_income", "state_taxable_income", "state_tax_before_credits", "state_total_tax")
    results = {}
    print("\nVirginia cases")
    print("| Case | Amount | Expected | PolicyEngine | Result |")
    print("|---|---|---|---|---|")
    for case_name, (filer_age, dependent_ages) in people.items():
        case = json.loads((HERE / "cases" / f"{case_name}.json").read_text())
        filing_status, incomes = case_incomes(case, True)
        result = run(2025, "VA", filing_status, filer_age, incomes, dependent_ages, outputs={n: OUTPUTS[n] for n in names})
        results[case_name] = result
        for name in names:
            expected = case["expected"][name]["value"]
            print(f"| {case_name} | {name} | {expected} | {result[name]} | {verdict(name, result[name] - expected)} ({result[name] - expected:+.2f}) |")
    return results


def main():
    tenforty_rows = json.loads((HERE / "calibration_results.json").read_text())
    tenforty_chain = json.loads((HERE / "chain_results.json").read_text())
    smoke_check()
    results = {
        "ty25-us-006": federal_case(tenforty_rows),
        "chain": chain_tables(tenforty_chain),
        "virginia": virginia_cases(),
    }
    (HERE / "policyengine_results.json").write_text(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
