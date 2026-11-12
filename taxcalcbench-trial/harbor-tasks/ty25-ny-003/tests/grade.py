"""Grade /app/output/return.md with the TaxCalcBench evaluator."""

import json
import sys
from pathlib import Path

sys.path.insert(0, "/tests")
from tax_calc_bench.tax_return_evaluator import TaxReturnEvaluator

JURISDICTION = "ny"
answer = Path("/app/output/return.md")
generated = answer.read_text() if answer.is_file() else ""
result = TaxReturnEvaluator().evaluate(
    generated, Path("/tests/output.xml").read_text(), tax_year="ty25", jurisdiction=JURISDICTION
)
Path("/logs/verifier/evaluation.md").write_text(result.report)
print(result.report)
Path("/logs/verifier/reward.json").write_text(
    json.dumps(
        {
            "reward": int(result.strictly_correct_return),
            "lenient": int(result.lenient_correct_return),
            "by_line": result.correct_by_line_score,
            "by_line_lenient": result.lenient_correct_by_line_score,
        }
    )
)
