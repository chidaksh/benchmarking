"""Judge check: the reference run's end state passes; each way of getting it wrong fails on the rule it breaks."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "robot-moving-catch-realistic", "environment", "robot")); sys.path.insert(0, os.path.join(HERE, "..", "..", "robot-moving-catch-realistic", "tests"))
import numpy as np, mujoco
import cell
from world import World
from judge import judge_world
rec = json.load(open(os.path.join(HERE, "recorded_oracle_plan.json")))
def run(upto=None, drop=()):
    w = World(rec["seed"])
    for n, a in enumerate(rec["actions"]):
        if upto is not None and n >= upto: break
        if n in drop: continue
        w.apply(a)
    return w
show = lambda name, v: print(f"{name:52s} overall {v['overall']}  " + " ".join(k for k in v if v[k] is False) + "  | " + v["notes"])
kinds = [a["kind"] for a in rec["actions"]]
i_pass = kinds.index("pass"); i_release = max(n for n, k in enumerate(kinds) if k == "grip")
w = run(); show("the reference run", judge_world(w, True))
show("the same, but finish was not run", judge_world(w, False))
show("the same, but over the action budget", judge_world(w, True, False))
w = run(upto=len(kinds) - 1); show("delivered, arm not parked", judge_world(w, True))
w = run(upto=i_pass); show("no try was made", judge_world(w, True))
w = run(upto=i_pass); w.apply({"kind": "pass", "commands": []}); show("the try was made with no action (lost)", judge_world(w, True))
w = run(upto=i_pass + 1); w.apply({"kind": "grip", "width": cell.OPEN}); w.apply({"kind": "path", "points": [cell.PARK]}); show("caught, then let go above the track", judge_world(w, True))
w = run(upto=i_release); w.apply({"kind": "path", "points": [cell.PARK]}); show("caught and carried, never let go", judge_world(w, True))
# a basket block knocked out: move one out by hand after the reference run
w = run(); j = w.model.joint(w.model.body("block0").jntadr[0]); w.data.qpos[j.qposadr[0]:j.qposadr[0] + 3] = [0.30, 0.10, 0.03]; w._step(300)
show("delivered, but a basket block is on the table", judge_world(w, True))
# the part taken back out of the basket after delivery
w = run(); j = w.model.joint(w.model.body("part0").jntadr[0]); w.data.qpos[j.qposadr[0]:j.qposadr[0] + 3] = [0.30, 0.10, 0.03]; w._step(300)
show("delivered, then the part ends outside the basket", judge_world(w, True))
