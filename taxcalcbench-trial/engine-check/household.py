"""The chain household, shared by the tenforty and PolicyEngine runs."""

FILING_STATUS = "Single"

# Amounts are that year's own sales, before any carryover.
HOUSEHOLD = [
    {"year": 2023, "wages": 95000, "interest": 1200, "short_term": -6000, "long_term": -14000},
    {"year": 2024, "wages": 98000, "interest": 1300, "short_term": 1000, "long_term": 4000},
    {"year": 2025, "wages": 101000, "interest": 1400, "short_term": 5000, "long_term": 12000},
]

# Carryover out of year 1 as (short-term, long-term); None means computed by the worksheet.
VARIANTS = {
    "correct": None,
    "whole_loss_deducted_year1": (0, 0),
    "carryover_not_reduced": (6000, 14000),
}
