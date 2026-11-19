"""Grades the record of a test run with the task's grader, replaying it with the same sensing errors the run used.

usage: grade_test_run.py DRAW RECORD    prints the reward and the largest difference between the record and its replay
"""
import io, json, os, runpy, sys, tempfile, contextlib
HERE = os.path.dirname(os.path.abspath(__file__))
TESTS = os.path.join(HERE, "..", "..", "robot-moving-catch-realistic", "tests")
sys.path.insert(0, os.path.join(HERE, "..", "..", "robot-moving-catch-realistic", "environment", "robot"))
import sensing

draw, record = int(sys.argv[1]), sys.argv[2]
if draw:
    draw0 = sensing.draw
    sensing.draw = lambda seed: draw0(f"{seed}-{draw}")
out = tempfile.mkdtemp()
sys.argv = ["grade.py", record, out]
with contextlib.redirect_stdout(io.StringIO()):
    runpy.run_path(os.path.join(TESTS, "grade.py"), run_name="__main__")
reward = json.load(open(os.path.join(out, "reward.json")))
details = json.load(open(os.path.join(out, "details.json")))
print(f"reward {reward['reward']} | replay difference {details.get('replay_largest_difference')}")
