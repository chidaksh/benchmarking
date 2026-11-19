"""Rule checks for the park-start version, with true positions: the park rule, the tricks, and how exact the grip must be."""
import json, sys
from sim_helpers import *
import world as W

seed = int(sys.argv[1]) if len(sys.argv) > 1 else 20261119
plan = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "recorded_oracle_plan.json")))["actions"][0]["commands"]
go, close, lift = plan
print("the reference try:", [(c["tick"], sorted(k for k in c if k != "tick")) for c in plan])
CUT = lift["tick"] + 80                  # by this tick a catch has been decided; cutting the try here keeps the sweeps short

def fresh():
    return World(seed)

def refused(w):
    try:
        w.start_pass()
        return False
    except ValueError as e:
        return str(e)

w = fresh(); w.apply({"kind": "path", "points": [go["joints"]]})
print("try with the arm over the track:", refused(w), "| tries used", w.tries_used, w.status)
w = fresh(); q = list(cell.PARK); q[1] += 0.03; w.apply({"kind": "path", "points": [q]})
print("try with one joint 0.03 from park:", refused(w), "| tries used", w.tries_used)
w = fresh(); q = list(cell.PARK); q[1] += 0.015; w.apply({"kind": "path", "points": [q]})
print("try with one joint 0.015 from park:", refused(w) or "started")
w = fresh(); w.apply({"kind": "grip", "width": 0.048})
print("try at park with the fingers at 0.048:", refused(w), "| tries used", w.tries_used)
w = fresh(); w.apply({"kind": "path", "points": [go["joints"]]}); w.apply({"kind": "path", "points": [cell.PARK]})
print("try after going to the track and back to park:", refused(w) or "started")
w = fresh(); w.apply({"kind": "pass", "commands": []})
print("try with no action:", w.status[0])
w = fresh(); w.apply({"kind": "pass", "commands": [dict(go, grip=0.0)]})
print("closed hand brought into the lane ahead of the part:", w.status[0])
for g in (0.040, 0.0405, 0.041):
    w = fresh(); w.apply({"kind": "pass", "commands": [dict(go, grip=g)]})
    print(f"fingers standing still at {g}:", w.status[0])
# a tap: a closed hand meets the part and lifts away at once, then comes back for a slow part
w = fresh(); w.apply({"kind": "pass", "commands": [dict(go, grip=0.0), {"tick": close["tick"] - 11, "joints": lift["joints"]}, {"tick": close["tick"] - 6, "grip": 0.048},
                                                   {"tick": close["tick"] + 19, "joints": go["joints"]}, {"tick": close["tick"] + 65, "grip": 0.0}, {"tick": close["tick"] + 74, "joints": lift["joints"]}]})
print("a tap that stops the part, then a grip:", w.status[0], "| the arm touched it without a hold for", round(w._w[0]["touch"], 3), "s")
# gripped in time but never lifted clear during the try, then lifted at leisure afterwards
w = fresh(); w.apply({"kind": "pass", "commands": [go, close]})
s1 = w.status[0]
w.apply({"kind": "path", "points": [lift["joints"]]})
print("gripped but not lifted when the try ends:", s1, "| after lifting it once the try is over:", w.status[0])
w = fresh(); w.apply({"kind": "pass", "commands": plan})
print("the reference try run to its end:", w.status[0], "| a second try:", refused(w))
out = []
for ms in range(-120, 121, 10):
    w = fresh()
    k = ms // 10
    w.apply({"kind": "pass", "ticks": CUT, "commands": [go, dict(close, tick=close["tick"] + k), dict(lift, tick=lift["tick"] + k)]})
    out.append((ms, w.status[0]))
print("fingers closed this many ms from the reference moment:", ", ".join(f"{ms:+d}: {s}" for ms, s in out))
good = [ms for ms, s in out if s == "caught"]
print(f"caught from {min(good):+d} to {max(good):+d} ms" if good else "never caught")
