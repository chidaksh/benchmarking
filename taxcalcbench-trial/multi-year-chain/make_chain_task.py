"""Build the multi-year chain households as Harbor tasks: filled IRS forms, official references, verifier and oracle."""

import json
import shutil
import subprocess
from pathlib import Path

from form_stamp import stamp_page

HERE = Path(__file__).parent
FORMS = HERE / "irs-forms"
ENGINE_CHECK = HERE.parent / "engine-check"
YEARS = (2023, 2024, 2025)

TAXPAYER = {
    "first": "Morgan T.",
    "last": "Avery",
    "tin": "XXX-XX-4821",
    "street": "418 Alder Street",
    "city": "Austin, TX 78704",
}
EMPLOYER = {"name": "Lakeshore Analytics LLC, 2200 Congress Ave, Austin, TX 78701", "ein": "12-3456789"}
BANK = {"name": "First Prairie Bank, 90 Main St, Austin, TX 78701", "tin": "12-3456790"}
BROKER = {"name": "Ridgeline Brokerage Services, 15 Market St, Dallas, TX 75201", "tin": "12-3456791"}

# Facts shared by both household versions.
WAGES = {2023: 95000, 2024: 98000, 2025: 101000}
WITHHELD = {2023: 13400, 2024: 13800, 2025: 14300}
INTEREST = {2023: 1200, 2024: 1300, 2025: 1400}
SALE_DATES = {
    2023: {"short": ("03/10/2023", "09/15/2023"), "long": ("05/02/2020", "11/20/2023")},
    2024: {"short": ("02/05/2024", "08/12/2024"), "long": ("06/15/2021", "10/03/2024")},
    2025: {"short": ("01/21/2025", "07/30/2025"), "long": ("04/11/2022", "09/18/2025")},
}
SECURITIES = {"short": "200 sh. Corvane Tech Inc.", "long": "500 sh. Meridian Index Fund"}

# Each sale is (proceeds, cost basis); the versions differ only here.
HOUSEHOLDS = {
    "household-1": {
        "engine_results": "chain_results_household1.json",
        "sales": {
            2023: {"short": (14000, 20000), "long": (20000, 40000)},
            2024: {"short": (9000, 8000), "long": (19000, 15000)},
            2025: {"short": (12000, 10000), "long": (20000, 15000)},
        },
    },
    "household-2": {
        "engine_results": "chain_results.json",
        "sales": {
            2023: {"short": (14000, 20000), "long": (26000, 40000)},
            2024: {"short": (9000, 8000), "long": (19000, 15000)},
            2025: {"short": (25000, 20000), "long": (42000, 30000)},
        },
    },
}

# Blank form used for each tax year.
INT_FORM = {2023: "f1099int--2022.pdf", 2024: "f1099int--2024.pdf", 2025: "f1099int--2024.pdf"}
REFERENCE_FILES = {
    "form-1040.pdf": "f1040--{year}.pdf",
    "form-1040-instructions.pdf": "i1040gi--{year}.pdf",
    "schedule-d.pdf": "f1040sd--{year}.pdf",
    "schedule-d-instructions.pdf": "i1040sd--{year}.pdf",
}
RECIPIENT_COPY_PAGE = 4

FIELDS = (
    "schedule_d_net_short_term",
    "schedule_d_net_long_term",
    "form_1040_capital_gain_or_loss",
    "adjusted_gross_income",
    "taxable_income",
    "tax",
)

INSTRUCTION = """You are preparing U.S. federal income tax returns for one taxpayer for three consecutive tax years: 2023, 2024 and 2025.

Taxpayer: {first} {last}, single, born in 1985, not blind, no dependents, and cannot be claimed as a dependent by anyone. They were a U.S. resident for all three years. They take the standard deduction. The documents listed below are their only income; they have no other income, adjustments or credits to consider, and no digital asset transactions.

All files are in `/app/documents/`, one folder per tax year. Each folder holds that year's taxpayer documents together with the official IRS forms and instructions for that year:
- `/app/documents/2023/`: `w2.pdf`, `1099-int.pdf`, `1099-b_1.pdf`, `1099-b_2.pdf`, `form-1040.pdf`, `form-1040-instructions.pdf`, `schedule-d.pdf`, `schedule-d-instructions.pdf`
- `/app/documents/2024/`: the same eight files for 2024
- `/app/documents/2025/`: the same eight files for 2025

Prepare Form 1040 and Schedule D for each year, as the taxpayer should have filed them. Round amounts to whole dollars as the forms do.

Write your answer to `/app/output/returns.json`. Only that file is graded. Use exactly this structure, with one entry per year and a loss written as a negative number:

```json
{{
  "2023": {{
    "schedule_d_net_short_term": 0,
    "schedule_d_net_long_term": 0,
    "form_1040_capital_gain_or_loss": 0,
    "adjusted_gross_income": 0,
    "taxable_income": 0,
    "tax": 0
  }},
  "2024": {{ "...": "the same six fields" }},
  "2025": {{ "...": "the same six fields" }}
}}
```

Field meanings:
- `schedule_d_net_short_term`: Schedule D, line 7
- `schedule_d_net_long_term`: Schedule D, line 15
- `form_1040_capital_gain_or_loss`: the capital gain or loss line of Form 1040
- `adjusted_gross_income`: the adjusted gross income line of Form 1040
- `taxable_income`: Form 1040, line 15
- `tax`: Form 1040, line 16
"""

TASK_TOML = """schema_version = "1.4"
artifacts = ["/app/output/returns.json"]

[task]
name = "multi-year-chain/{name}"
version = "1.0.0"
description = "Three consecutive federal returns for one taxpayer, {name}"
keywords = []

[metadata]

[verifier]
timeout_sec = 600.0
environment_mode = "separate"

[agent]
timeout_sec = 1200.0
network_mode = "allowlist"
allowed_hosts = ["api.anthropic.com"]

[environment]
network_mode = "public"
build_timeout_sec = 900.0
os = "linux"
"""

ENVIRONMENT_DOCKERFILE = """FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends poppler-utils \\
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir pypdf==7.0.1

WORKDIR /app
COPY documents/ /app/documents/
RUN mkdir -p /app/output
"""

TESTS_DOCKERFILE = """FROM python:3.12-slim

WORKDIR /app
COPY . /tests/
"""

TEST_SH = """#!/bin/bash
mkdir -p /logs/verifier
python /tests/grade.py
"""

SOLVE_SH = """#!/bin/bash
set -euo pipefail
mkdir -p /app/output
cp /solution/returns.json /app/output/returns.json
"""


def money(amount):
    """Format a whole-dollar amount the way it is printed on a form."""
    return f"{amount:,.2f}"


# W-2 and 1099-INT fields by position in page order on the recipient copy; the checks below confirm each year.
W2 = {"ssn": 0, "ein": 1, "employer": 2, "first": 4, "last": 5, "address": 7, "box1": 8, "box2": 9, "box3": 10, "box4": 11, "box5": 12, "box6": 13}
INT = {"year": 0, "payer": 1, "payer_tin": 2, "recipient_tin": 3, "name": 4, "street": 5, "city": 6, "box1": 9}
# The 1099-B is addressed by field name: its names keep their meaning across years, its page order does not.
B = {
    "payer": "f2_1[0]",
    "payer_tin": "f2_2[0]",
    "recipient_tin": "f2_3[0]",
    "name": "f2_4[0]",
    "street": "f2_5[0]",
    "city": "f2_6[0]",
    "form_8949_box": "f2_15[0]",
    "description": "f2_16[0]",
    "acquired": "f2_17[0]",
    "sold": "f2_18[0]",
    "proceeds": "f2_19[0]",
    "basis": "f2_20[0]",
}
B_BOXES = {"short": "c2_4[0]", "long": "c2_4[1]", "gross_proceeds": "c2_7[0]", "basis_reported": "c2_9[0]"}


def write_w2(year, target):
    wages = WAGES[year]
    values = {
        W2["ssn"]: TAXPAYER["tin"],
        W2["ein"]: EMPLOYER["ein"],
        W2["employer"]: EMPLOYER["name"],
        W2["first"]: TAXPAYER["first"],
        W2["last"]: TAXPAYER["last"],
        W2["address"]: f"{TAXPAYER['street']}, {TAXPAYER['city']}",
        W2["box1"]: money(wages),
        W2["box2"]: money(WITHHELD[year]),
        W2["box3"]: money(wages),
        W2["box4"]: money(wages * 0.062),
        W2["box5"]: money(wages),
        W2["box6"]: money(wages * 0.0145),
    }
    stamp_page(FORMS / f"fw2--{year}.pdf", RECIPIENT_COPY_PAGE, values, target, font_size=8)


def write_1099_int(year, target):
    values = {
        # The 2022 revision prints "20" before the blank; the 2024 revision leaves the whole year blank.
        INT["year"]: str(year)[2:] if INT_FORM[year] == "f1099int--2022.pdf" else str(year),
        INT["payer"]: BANK["name"],
        INT["payer_tin"]: BANK["tin"],
        INT["recipient_tin"]: TAXPAYER["tin"],
        INT["name"]: f"{TAXPAYER['first']} {TAXPAYER['last']}",
        INT["street"]: TAXPAYER["street"],
        INT["city"]: TAXPAYER["city"],
        INT["box1"]: money(INTEREST[year]),
    }
    stamp_page(FORMS / INT_FORM[year], RECIPIENT_COPY_PAGE, values, target, font_size=8)


def write_1099_b(year, term, sale, target):
    proceeds, basis = sale
    acquired, sold = SALE_DATES[year][term]
    values = {
        B["payer"]: BROKER["name"],
        B["payer_tin"]: BROKER["tin"],
        B["recipient_tin"]: TAXPAYER["tin"],
        B["name"]: f"{TAXPAYER['first']} {TAXPAYER['last']}",
        B["street"]: TAXPAYER["street"],
        B["city"]: TAXPAYER["city"],
        # Form 8949 box: A is short-term and D is long-term, both with basis reported to the IRS.
        B["form_8949_box"]: "A" if term == "short" else "D",
        B["description"]: SECURITIES[term],
        B["acquired"]: acquired,
        B["sold"]: sold,
        B["proceeds"]: money(proceeds),
        B["basis"]: money(basis),
    }
    boxes = (B_BOXES[term], B_BOXES["gross_proceeds"], B_BOXES["basis_reported"])
    stamp_page(FORMS / f"f1099b--{year}.pdf", RECIPIENT_COPY_PAGE, values, target, checked_boxes=boxes, font_size=8)


def expected_answers(household):
    """Take the answer key from tenforty's saved chain and check it against the household's sales."""
    rows = json.loads((ENGINE_CHECK / household["engine_results"]).read_text())["correct"]
    expected = {}
    for row in rows:
        year = row["year"]
        sales = household["sales"][year]
        own_short = sales["short"][0] - sales["short"][1]
        own_long = sales["long"][0] - sales["long"][1]
        assert own_short - row["carry_in_short"] == row["net_short"], (year, "short")
        assert own_long - row["carry_in_long"] == row["net_long"], (year, "long")
        net = row["net_short"] + row["net_long"]
        expected[str(year)] = {
            "schedule_d_net_short_term": row["net_short"],
            "schedule_d_net_long_term": row["net_long"],
            "form_1040_capital_gain_or_loss": net if net >= 0 else -min(3000, -net),
            "adjusted_gross_income": round(row["engine_agi"]),
            "taxable_income": round(row["engine_taxable_income"]),
            "tax": round(row["engine_total_tax"]),
        }
        assert expected[str(year)]["adjusted_gross_income"] == WAGES[year] + INTEREST[year] + expected[str(year)]["form_1040_capital_gain_or_loss"]
    return expected


def pdf_text(path):
    return subprocess.run(["pdftotext", "-layout", str(path), "-"], capture_output=True, text=True, check=True).stdout


def line_after(text, label, offset_limit=2):
    """Return the lines right after the one containing a box label."""
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if label in line:
            return " ".join(lines[index : index + 1 + offset_limit])
    raise AssertionError(f"label not found: {label}")


def check_documents(documents_dir, household):
    """Read each generated form back as text and confirm each amount sits next to its own box label."""
    for year in YEARS:
        folder = documents_dir / str(year)
        w2 = pdf_text(folder / "w2.pdf")
        assert money(WAGES[year]) in line_after(w2, "1 Wages, tips, other compensation", 1), (year, "w2 box 1")
        assert money(WITHHELD[year]) in line_after(w2, "2 Federal income tax withheld", 1), (year, "w2 box 2")
        assert str(year) in w2
        interest = pdf_text(folder / "1099-int.pdf")
        box1 = interest[interest.index("1 Interest income") : interest.index("2 Early withdrawal penalty")]
        assert money(INTEREST[year]) in box1, (year, "1099-INT box 1")
        assert str(year)[2:] in line_after(interest, "For calendar year"), (year, "1099-INT year")
        for index, term in enumerate(("short", "long"), start=1):
            text = pdf_text(folder / f"1099-b_{index}.pdf")
            proceeds, basis = household["sales"][year][term]
            acquired, sold = SALE_DATES[year][term]
            amounts = line_after(text, "1d Proceeds", 1)
            assert money(proceeds) in amounts and money(basis) in amounts, (year, term, "amounts")
            assert amounts.index(money(proceeds)) < amounts.rindex(money(basis)), (year, term, "amount order")
            dates = line_after(text, "1b Date acquired", 1)
            assert acquired in dates and sold in dates and dates.index(acquired) < dates.index(sold), (year, term, "dates")
            assert SECURITIES[term] in line_after(text, "1a Description of property", 2), (year, term, "description")
            marked = "2 Short-term gain or loss X" if term == "short" else "Long-term gain or loss X"
            assert " ".join(text.split()).count(" ".join(marked.split())) == 1, (year, term, "holding period box")
            other = "Long-term gain or loss X" if term == "short" else "2 Short-term gain or loss X"
            assert " ".join(other.split()) not in " ".join(text.split()), (year, term, "other box unmarked")
            assert f" {year} " in text, (year, term, "form year")


def build(name, household):
    task = HERE / "harbor-tasks" / f"chain-{name}"
    if task.exists():
        shutil.rmtree(task)
    for year in YEARS:
        folder = task / "environment" / "documents" / str(year)
        folder.mkdir(parents=True)
        write_w2(year, folder / "w2.pdf")
        write_1099_int(year, folder / "1099-int.pdf")
        write_1099_b(year, "short", household["sales"][year]["short"], folder / "1099-b_1.pdf")
        write_1099_b(year, "long", household["sales"][year]["long"], folder / "1099-b_2.pdf")
        for target, source in REFERENCE_FILES.items():
            shutil.copy(FORMS / source.format(year=year), folder / target)
    check_documents(task / "environment" / "documents", household)

    expected = expected_answers(household)
    (task / "instruction.md").write_text(INSTRUCTION.format(**TAXPAYER))
    (task / "task.toml").write_text(TASK_TOML.format(name=name))
    (task / "environment" / "Dockerfile").write_text(ENVIRONMENT_DOCKERFILE)
    (task / "tests").mkdir()
    (task / "tests" / "Dockerfile").write_text(TESTS_DOCKERFILE)
    (task / "tests" / "test.sh").write_text(TEST_SH)
    shutil.copy(HERE / "grade.py", task / "tests" / "grade.py")
    (task / "tests" / "expected.json").write_text(json.dumps(expected, indent=2) + "\n")
    (task / "solution").mkdir()
    (task / "solution" / "solve.sh").write_text(SOLVE_SH)
    (task / "solution" / "returns.json").write_text(json.dumps(expected, indent=2) + "\n")
    for script in (task / "tests" / "test.sh", task / "solution" / "solve.sh"):
        script.chmod(0o755)
    print(f"built {task.relative_to(HERE)}: {json.dumps(expected)}")


if __name__ == "__main__":
    for household_name, household_facts in HOUSEHOLDS.items():
        build(household_name, household_facts)
