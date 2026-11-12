from pathlib import Path

ANSWER = Path("/app/answer.txt")


def test_answer_file_exists():
    assert ANSWER.is_file(), f"{ANSWER} was not created"


def test_answer_content():
    assert ANSWER.read_text().strip() == "hello harbor"
