"""Verifier. Applies the end-state rules to the robot's own record, and replays the record as a cross-check."""
import json
import os
import sys
import time

TESTS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TESTS)
RECORD = sys.argv[1] if len(sys.argv) > 1 else "/srv/data/robot-record.json"
OUT = sys.argv[2] if len(sys.argv) > 2 else "/logs/verifier"
REPLAY_SECONDS = float(os.environ.get("REPLAY_SECONDS", "300"))

d = {"record": "", "actions": 0, "finished": False}
keys = ("delivered_enough", "basket_blocks_in_place", "parked", "finished", "within_budget")
verdict = dict({k: False for k in keys}, overall=0, notes="")
record = None
try:
    record = json.load(open(RECORD))
    import cell
    from judge import judge, within_budget
    # the facts of the scene come from the seed alone, so judging does not depend on rebuilding the physics here
    facts = cell.build(int(record["seed"]))[1]
    kinds = [a["kind"] for a in record["actions"]]
    cut = kinds.index("pass") if "pass" in kinds else len(kinds)
    d["actions_before_the_try"], d["actions_after_the_try"] = cut, len(kinds) - cut - ("pass" in kinds)
    d["actions"], d["finished"] = d["actions_before_the_try"] + d["actions_after_the_try"], bool(record["finished"])
    d["passes"] = kinds.count("pass")
    verdict = judge(facts, record["truth"], record["sense"], d["finished"], within_budget(record["actions"]))
    d["record"] = "read"
except Exception as e:
    d["record"] = f"{type(e).__name__}: {e}"
d["verdict"] = verdict

# The record is written by the robot's container, which the agent cannot reach, so it is what is judged.
# The replay only reports whether this machine reproduces it, and stops after a fixed time.
try:
    from world import World
    world = World(int(record["seed"]))
    began, done = time.time(), 0
    for action in record["actions"]:
        if time.time() - began > REPLAY_SECONDS:
            break
        world.apply(action)
        done += 1
    d["replayed_actions"] = done
    if done == len(record["actions"]):
        truth = world.truth()
        d["replay_largest_difference"] = max(abs(a - b) for name in truth if name != "status" for a, b in zip(truth[name]["pos"], record["truth"][name]["pos"]))
        d["replay_tries"] = truth["status"]
except Exception as e:
    d["replay_largest_difference"] = f"not replayed: {type(e).__name__}: {e}"

reward = {
    "functional_correctness": float(verdict["delivered_enough"]),
    "robustness": float(verdict["basket_blocks_in_place"]),
    "constraint_satisfaction": float(verdict["parked"] and verdict["finished"] and verdict["within_budget"]),
    "artifact_quality": float(d["record"] == "read"),
}
reward["overall"] = float(all(v == 1.0 for v in reward.values()))
reward["reward"] = reward["overall"]
os.makedirs(OUT, exist_ok=True)
json.dump(reward, open(os.path.join(OUT, "reward.json"), "w"))
json.dump(d, open(os.path.join(OUT, "details.json"), "w"), indent=1)
print(json.dumps(reward))
print(json.dumps(d, indent=1))
