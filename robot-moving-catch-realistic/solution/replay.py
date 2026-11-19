"""Reference run: sends a recorded list of robot actions through the robot command, then finishes.

The list was planned against the cell's true state, which no agent can see. It shows the job can be done; it is not a method.
The try is sent step by step. Each action is sent one step ahead of the step it is carried out in, as the delay requires.
"""
import json, os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
actions = json.load(open(os.path.join(HERE, "actions.json")))["actions"]


def robot(*args):
    out = subprocess.run(["robot", *args], capture_output=True, text=True)
    reply = json.loads(out.stdout)
    if out.returncode != 0:
        sys.exit(f"robot {args[0]} failed: {reply}")
    return reply


def with_file(content, *command):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump(content, fh)
    try:
        return robot(*command, fh.name)
    finally:
        os.unlink(fh.name)


for n, action in enumerate(actions, 1):
    if action["kind"] == "grip":
        reply = robot("grip", str(action["width"]))
    elif action["kind"] == "path":
        reply = with_file(action["points"], "path")
    else:
        # a step is 20 ticks: an action at tick T is carried out in step T // 20 + 1, so it is sent with step T // 20
        by_step = {}
        for c in action["commands"]:
            by_step.setdefault(c["tick"] // 20, []).append(dict({k: v for k, v in c.items() if k != "tick"}, at=(c["tick"] % 20) / 100))
        robot("try")
        for step in range(1, max(by_step) + 1):
            reply = with_file(by_step[step], "step") if step in by_step else robot("step")
        reply = robot("skip")
    print(n, action["kind"], "blocked" if reply.get("blocked") else "ok", flush=True)
print(json.dumps(robot("finish")))
