"""Timing test on a recorded run: its own actions, with only the finger-closing action and the lift after it moved in time.

Everything before the finger-closing action is replayed as recorded. Actions after the lift are left out.
If some shift gives `caught`, the arm was placed well enough and the timing alone decided the try.

usage: catch_timing_sweep.py RECORD GRIP_TICK LIFT_TICK FIRST_MS LAST_MS STEP_MS    a tick is 0.01 s of the try
"""
import copy, json, os, sys
sys.path.insert(0, os.environ.get("SIM", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "robot-moving-catch-realistic", "environment", "robot")))
from world import World

record = json.load(open(sys.argv[1]))
grip, lift, first, last, every = (int(v) for v in sys.argv[2:7])
actions = record["actions"]
k = [a["kind"] for a in actions].index("pass")


def run(shift, keep_later):
    world = World(int(record["seed"]))
    for action in actions[:k]:
        world.apply(action)
    attempt = copy.deepcopy(actions[k])
    kept = []
    for c in attempt["commands"]:
        if c["tick"] in (grip, lift):
            c["tick"] += shift
            kept.append(c)
        elif c["tick"] < grip or keep_later:
            kept.append(c)
    attempt["commands"] = sorted(kept, key=lambda c: c["tick"])
    world.apply(attempt)
    return world.truth()["status"][0]


print("as recorded, every action:", run(0, True))
caught = []
for ms in range(first, last + 1, every):
    result = run(ms // 10, False)
    caught += [ms] if result == "caught" else []
    print(f"fingers close {ms:+4d} ms from the recorded time, at {grip / 100 + ms / 1000:.2f} s: {result}")
print("caught for shifts of", f"{min(caught):+d} to {max(caught):+d} ms" if caught else "none")
