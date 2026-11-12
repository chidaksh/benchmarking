"""Wrap one TaxCalcBench TY25 case as a Harbor task for pilot runs."""

import shutil
import sys
from pathlib import Path

from lxml import etree

HERE = Path(__file__).resolve().parent
BENCH = HERE / "tax-calc-bench"
sys.path.insert(0, str(BENCH))

from tax_calc_bench.ty25_prompt import build_ty25_tax_return_prompt  # noqa: E402
from tax_calc_bench.ty25_scoring import get_ty25_scoring_fields  # noqa: E402

VENDORED = ["config.py", "data_classes.py", "ty25_scoring.py", "tax_return_evaluator.py"]

PREFACE = """The taxpayer's files are in `/app/input/`. Where the text below says "attached PDFs", it means the PDF files in that folder.
Write your final answer, in the output format described below, to `/app/output/return.md`. Only that file is graded.

"""

TASK_TOML = """schema_version = "1.4"
artifacts = ["/app/output/return.md"]

[task]
name = "taxcalcbench-trial/{case}"
version = "1.0.0"
description = "TaxCalcBench {case} wrapped as a Harbor task"
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

ENV_DOCKERFILE = """FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends poppler-utils \\
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir pypdf==7.0.1

WORKDIR /app
COPY input/ /app/input/
RUN mkdir -p /app/output
"""

TESTS_DOCKERFILE = """FROM python:3.12-slim

RUN pip install --no-cache-dir lxml==6.1.3 numpy==2.5.4

WORKDIR /app
COPY . /tests/
"""

TEST_SH = """#!/bin/bash
mkdir -p /logs/verifier
python /tests/grade.py
"""

GRADE_PY = '''"""Grade /app/output/return.md with the TaxCalcBench evaluator."""

import json
import sys
from pathlib import Path

sys.path.insert(0, "/tests")
from tax_calc_bench.tax_return_evaluator import TaxReturnEvaluator

JURISDICTION = "{jurisdiction}"
answer = Path("/app/output/return.md")
generated = answer.read_text() if answer.is_file() else ""
result = TaxReturnEvaluator().evaluate(
    generated, Path("/tests/output.xml").read_text(), tax_year="ty25", jurisdiction=JURISDICTION
)
Path("/logs/verifier/evaluation.md").write_text(result.report)
print(result.report)
Path("/logs/verifier/reward.json").write_text(
    json.dumps(
        {{
            "reward": int(result.strictly_correct_return),
            "lenient": int(result.lenient_correct_return),
            "by_line": result.correct_by_line_score,
            "by_line_lenient": result.lenient_correct_by_line_score,
        }}
    )
)
'''

SOLVE_SH = """#!/bin/bash
set -euo pipefail
mkdir -p /app/output
cp /solution/return.md /app/output/return.md
"""


def oracle_return(case_dir: Path, jurisdiction: str) -> str:
    tree = etree.fromstring((case_dir / "output.xml").read_bytes())
    lines = []
    for field in get_ty25_scoring_fields(jurisdiction):
        found = tree.xpath(field.xpath)
        value = found[0].text if found and hasattr(found[0], "text") else (found[0] if found else "0")
        lines.append(f"{field.label} | from expected output | {value}")
    return "\n".join(lines) + "\n"


def build(case: str, out_root: Path, task_name: str | None = None, extra_pdfs: tuple[Path, ...] = ()) -> None:
    case_dir = BENCH / "tax_calc_bench" / "ty25" / "test_data" / case
    jurisdiction = case.split("-")[1]
    task_name = task_name or case
    task = out_root / task_name
    if task.exists():
        shutil.rmtree(task)
    (task / "environment").mkdir(parents=True)
    (task / "tests" / "tax_calc_bench").mkdir(parents=True)
    (task / "solution").mkdir()

    shutil.copytree(case_dir / "input", task / "environment" / "input")
    for extra in extra_pdfs:
        shutil.copy(extra, task / "environment" / "input" / extra.name)
    pdfs = sorted(p.name for p in (task / "environment" / "input").glob("*.pdf"))
    remaining = (case_dir / "input" / "remaining_data.json").read_text()
    prompt = build_ty25_tax_return_prompt(jurisdiction, remaining, pdfs, test_name=case)

    (task / "instruction.md").write_text(PREFACE + prompt)
    (task / "task.toml").write_text(TASK_TOML.format(case=task_name))
    (task / "environment" / "Dockerfile").write_text(ENV_DOCKERFILE)
    (task / "tests" / "Dockerfile").write_text(TESTS_DOCKERFILE)
    (task / "tests" / "test.sh").write_text(TEST_SH)
    (task / "tests" / "grade.py").write_text(GRADE_PY.format(jurisdiction=jurisdiction))
    shutil.copy(case_dir / "output.xml", task / "tests" / "output.xml")
    for name in VENDORED:
        shutil.copy(BENCH / "tax_calc_bench" / name, task / "tests" / "tax_calc_bench" / name)
    (task / "tests" / "tax_calc_bench" / "__init__.py").write_text("")
    (task / "solution" / "solve.sh").write_text(SOLVE_SH)
    (task / "solution" / "return.md").write_text(oracle_return(case_dir, jurisdiction))
    for script in (task / "tests" / "test.sh", task / "solution" / "solve.sh"):
        script.chmod(0o755)
    print(f"built {task}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("cases", nargs="+")
    parser.add_argument("--task-name", help="output task name, for a single case")
    parser.add_argument("--add-pdf", type=Path, action="append", default=[], help="extra PDF placed in /app/input")
    args = parser.parse_args()
    out = HERE / "harbor-tasks"
    out.mkdir(exist_ok=True)
    for name in args.cases:
        build(name, out, task_name=args.task_name, extra_pdfs=tuple(args.add_pdf))
