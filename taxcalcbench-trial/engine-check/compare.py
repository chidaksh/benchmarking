"""Run each calibration case through tenforty on both backends and compare with the benchmark's expected amounts."""

import json
import sys
from pathlib import Path

import tenforty

CASES_DIR = Path(__file__).parent / "cases"
BACKENDS = ("ots", "graph")
TOLERANCE = 5

# The engine has one state tax output, so it is compared with both expected state tax lines.
ENGINE_FIELD = {"state_tax_before_credits": "state_total_tax"}


def run_case(case, backend):
    """Return the engine's outputs as a dict, or an error string."""
    kwargs = {name: entry["value"] for name, entry in case["inputs"].items()}
    try:
        result = tenforty.evaluate_return(year=2025, state=case["state"], backend=backend, **kwargs)
    except Exception as error:
        return f"{type(error).__name__}: {str(error).splitlines()[0][:160]}"
    return result.model_dump()


def verdict(expected, actual):
    """Classify one amount as exact, within tolerance, or off."""
    if actual is None:
        return "not computed"
    difference = round(actual - expected, 2)
    if difference == 0:
        return "exact"
    if abs(difference) <= TOLERANCE:
        return f"within ${TOLERANCE} ({difference:+g})"
    return f"OFF ({difference:+g})"


def main():
    rows = []
    for path in sorted(CASES_DIR.glob("*.json")):
        case = json.loads(path.read_text())
        outputs = {backend: run_case(case, backend) for backend in BACKENDS}
        for backend, output in outputs.items():
            if isinstance(output, str):
                print(f"{case['case']} [{backend}] did not run: {output}")
        for name, entry in case["expected"].items():
            row = {"case": case["case"], "fully_represented": case["fully_represented"], "amount": name, "expected": entry["value"]}
            for backend, output in outputs.items():
                if isinstance(output, str):
                    row[backend] = None
                    row[f"{backend}_verdict"] = "did not run"
                else:
                    actual = output[ENGINE_FIELD.get(name, name)]
                    row[backend] = actual
                    row[f"{backend}_verdict"] = verdict(entry["value"], actual)
            rows.append(row)

    print("\n| Case | Amount | Expected | OTS | OTS result | Graph | Graph result |")
    print("|---|---|---|---|---|---|---|")
    for row in rows:
        print(
            f"| {row['case']} | {row['amount']} | {row['expected']} | {row['ots']} | {row['ots_verdict']} "
            f"| {row['graph']} | {row['graph_verdict']} |"
        )
    Path(__file__).with_name("calibration_results.json").write_text(json.dumps(rows, indent=2))


if __name__ == "__main__":
    sys.exit(main())
