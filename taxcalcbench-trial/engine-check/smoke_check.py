"""Reproduce the tenforty README Quick Start household and compare with its printed values."""

import tenforty

# Values printed in the tenforty README Quick Start.
README_VALUES = {
    "total_tax": 4476.0,
    "federal_income_tax": 3346.0,
    "state_total_tax": 1130.0,
    "federal_taxable_income": 68500.0,
    "state_taxable_income": 88588.0,
}

result = tenforty.evaluate_return(
    w2_income=100_000,
    state="CA",
    filing_status="Married/Joint",
    num_dependents=2,
)

failed = False
for name, expected in README_VALUES.items():
    actual = getattr(result, name)
    status = "match" if actual == expected else "DIFFERENT"
    failed = failed or actual != expected
    print(f"{name}: readme {expected}, engine {actual}, {status}")

print("all fields:", result.model_dump())
raise SystemExit(1 if failed else 0)
