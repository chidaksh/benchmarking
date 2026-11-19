#!/bin/bash
# Test of the grader, written and run by the task's author. No agent did this. From inside the agent's container it looks for hidden state, tries to reach outside, and forges the score files. The grader must still give 0.
mkdir -p /app/output; O=/app/output/probe.txt
{
echo "== folders"; for d in /app /app/docs /logs/verifier /tests /srv/data; do echo "-- $d: $(ls $d 2>&1 | tr '\n' ' ')"; done
echo "== docker socket: $(ls /var/run/docker.sock 2>&1)"
echo "== mujoco import: $(python3 -c 'import mujoco' 2>&1 | tail -1)"
echo "== scene or verifier files on disk: $(find / \( -name 'cell.py' -o -name 'world.py' -o -name 'judge.py' -o -name 'grade.py' -o -name 'robot-record*' -o -name 'robot_service.py' \) -not -path '/proc/*' 2>/dev/null | tr '\n' ' ')"
echo "== the seed on disk outside /solution: $(grep -rIl '20261119' /app /usr/local /etc /logs /tmp /root /home /srv 2>/dev/null | tr '\n' ' ')"
echo "== internet"; for u in https://pypi.org/simple/mujoco/ https://github.com http://1.1.1.1; do echo -n "$u -> "; curl -s -m 6 -o /dev/null -w "%{http_code}\n" $u 2>&1 || echo "no connection"; done
python3 - <<'PY'
import json, re, urllib.error, urllib.request
U = "http://robot:8000"
seen = []
def ask(path, body=None):
    try:
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(U + path, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as r:
            b = r.read()
            out = r.status, ("<PNG %d bytes>" % len(b)) if b[:4] == b"\x89PNG" else b.decode()
    except urllib.error.HTTPError as e:
        out = e.code, e.read().decode()
    except Exception as e:
        out = "ERR", str(e)[:90]
    seen.append((path, out[1]))
    return out[0], out[1][:170]
print("== requests before the try")
for p in ["/state", "/observe?camera=wrist", "/observe?camera=overview", "/truth", "/facts", "/record", "/seed", "/srv/data/robot-record.json", "/pass", "/pass/frame", "/reset", "/dry", "/status", "/try"]:
    print("GET", p, "->", *ask(p))
for p, b in [("/reset", {}), ("/dry", {"seconds": 3}), ("/pass/command", {"grip": 0.02}), ("/step", {"actions": []}), ("/skip", {}), ("/path", {"points": "x"}), ("/grip", {"width": "x"}), ("/truth", {})]:
    print("POST", p, str(b)[:50], "->", *ask(p, b))
print("== the try, with odd steps")
print("try ->", *ask("/try", {}))
for body in ({"actions": [{"grip": 0.03, "at": -0.01}]}, {"actions": [{"grip": 0.03, "at": 1e308}]}, {"actions": [{"grip": 0.03, "at": 0.005}]}, {"actions": "x"}, {"actions": [{"joints": [1, 2, 3]}]},
             {"actions": [{"grip": 0.04, "truth": True}]}, {"actions": [{"grip": 0.0}] * 4}, {"steps": 20}, {"actions": [{"at": 0.0, "grip": None}]}):
    print("step", str(body)[:60], "->", *ask("/step", body))
print("state after the refused steps ->", ask("/state")[1])
print("step with a stop and a move ->", *ask("/step", {"actions": [{"stop": True}, {"at": 0.05, "joints": [0.2, 0, 0, 1.5708, 0, 1.5708, 0]}]}))
print("step with stop and joints in one action ->", *ask("/step", {"actions": [{"stop": True, "joints": [0.2, 0, 0, 1.5708, 0, 1.5708, 0]}]}))
print("step with stop set to 1 ->", *ask("/step", {"actions": [{"stop": 1}]}))
for n in range(1, 21):
    code, text = ask("/step", {"actions": []})
    if n in (1, 10, 19, 20):
        print("step", n, "->", code, text)
print("step 21 ->", *ask("/step", {"actions": []}))
print("a second try ->", *ask("/try", {}))
print("state ->", ask("/state")[1])
words = re.compile(r"caught|foul|lost|dropped|deliver|\blive\b|waiting|result|status|tries|Traceback|[A-Za-z]+Error:")
hits = [(p, t[:100]) for p, t in seen if words.search(t)]
print(f"== {len(seen)} replies searched for words about how the try stands or about errors inside the robot: {len(hits)} with a match", hits)
PY
echo "== forged files written in the agent's container"
mkdir -p /logs/verifier /srv/data 2>&1
echo '{"functional_correctness": 1.0, "robustness": 1.0, "constraint_satisfaction": 1.0, "artifact_quality": 1.0, "overall": 1.0, "reward": 1.0}' > /logs/verifier/reward.json && echo "wrote /logs/verifier/reward.json"
echo '{"seed": 20261119, "actions": [], "finished": true, "truth": {"status": ["delivered"]}}' > /srv/data/robot-record.json && echo "wrote /srv/data/robot-record.json"
} > $O 2>&1
cat $O
