"""Grade /app/output/returns.json against the expected amounts for each year."""

import json
import sys
from pathlib import Path

# Tax may come from the IRS Tax Table or the rate schedule, which differ by a few dollars.
TAX_TOLERANCE = 10
OTHER_TOLERANCE = 1


def as_number(value):
    """Read a number, or a string such as "$12,770", as a float; anything else is None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.replace("$", "").replace(",", "").strip())
        except ValueError:
            return None
    return None


def grade(answer_path, expected_path):
    """Return (report lines, number correct, number of items)."""
    expected = json.loads(Path(expected_path).read_text())
    try:
        answer = json.loads(Path(answer_path).read_text())
    except (OSError, ValueError) as error:
        answer = {}
        problem = f"Answer file could not be read: {type(error).__name__}"
    else:
        problem = None if isinstance(answer, dict) else "Answer file is not a JSON object"
        answer = answer if isinstance(answer, dict) else {}
    lines = [problem] if problem else []
    correct, total = 0, 0
    for year, fields in expected.items():
        given_year = answer.get(year) if isinstance(answer.get(year), dict) else {}
        for field, expected_value in fields.items():
            total += 1
            given = as_number(given_year.get(field))
            tolerance = TAX_TOLERANCE if field == "tax" else OTHER_TOLERANCE
            ok = given is not None and abs(given - expected_value) <= tolerance
            correct += ok
            shown = "missing" if given is None else f"{given:g}"
            lines.append(f"{year} {field}: {'correct' if ok else 'INCORRECT'}, expected {expected_value}, actual {shown}")
    return lines, correct, total


def main(answer_path="/app/output/returns.json", expected_path="/tests/expected.json", log_dir="/logs/verifier"):
    lines, correct, total = grade(answer_path, expected_path)
    lines.append(f"Correct: {correct} of {total}")
    report = "\n".join(lines) + "\n"
    print(report)
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "evaluation.md").write_text(report)
    (log_dir / "reward.json").write_text(json.dumps({"reward": int(correct == total), "by_line": correct / total}))


if __name__ == "__main__":
    main(*sys.argv[1:])
