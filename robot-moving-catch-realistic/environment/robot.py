#!/usr/bin/env python3
"""robot: command-line access to the robot cell."""
import json
import os
import sys
import time
import urllib.error
import urllib.request

URL = os.environ.get("ROBOT_URL", "http://robot:8000")

HELP = """robot: the robot cell for this job.

At any time:
  robot state                 joint angles in radians, the gap between the fingers, where the try's clock is, actions left
  robot look FILE             save what the wrist camera sees now as a PNG file

Outside the try (the cell does not move between commands; 10 arm actions before the try, 30 after it):
  robot joints Q1 Q2 Q3 Q4 Q5 Q6 Q7   move all seven joints to these angles in radians
  robot path FILE             move through a list of joint settings without stopping; FILE holds JSON such as [[q1, ..., q7], [q1, ..., q7]]
  robot grip WIDTH            set the gap between the fingers in metres, from 0 to 0.06
  robot finish                declare the job finished; nothing can be done after this

The try (20 steps of 0.2 second; the cell moves only when you take a step):
  robot try                   start the try, from the park pose only: the part is released
  robot step [FILE]           take one step. FILE may hold a JSON list of up to three actions, such as
                              [{"at": 0.03, "joints": [q1, ..., q7]}, {"at": 0.07, "grip": 0.0}]
                              "joints" is a move that cannot be changed once sent; a move waits for the moves before it to end
                              {"at": 0.00, "stop": true} stops the arm and drops its unfinished moves; no move starts for 0.2 after
                              They are carried out during the NEXT step, each at its offset "at" (0.00 to 0.19) from the start of that step
  robot skip                  take all the remaining steps of the try with no new actions

"blocked": true in a reply means the arm did not complete the move: something stopped it, or it ended off its last point.
The robot never says how the try went. Every reply except a picture is JSON.
/app/docs/MANUAL.md describes the robot, the try, the rules and when the job counts as done.
"""


def call(path, payload=None, raw=False):
    data = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(URL + path, data=data, headers={"Content-Type": "application/json"}, method="GET" if data is None else "POST")
    deadline = time.monotonic() + 20
    while True:
        try:
            with urllib.request.urlopen(request, timeout=600) as reply:
                body = reply.read()
                return (body if raw else json.loads(body)), 0
        except urllib.error.HTTPError as error:
            return json.loads(error.read()), 1
        except (urllib.error.URLError, OSError) as error:
            # only a connection that was never made is tried again
            if time.monotonic() > deadline or not isinstance(getattr(error, "reason", error), ConnectionRefusedError):
                return {"error": f"cannot reach the robot: {error}"}, 2
            time.sleep(0.5)


def load(path):
    with open(path) as fh:
        return json.load(fh)


def main(argv):
    if not argv or argv[0] in ("help", "-h", "--help"):
        print(HELP)
        return 0
    name, args = argv[0], argv[1:]
    try:
        if name == "state" and not args:
            body, code = call("/state")
        elif name == "look" and len(args) == 1:
            body, code = call("/observe?camera=wrist", raw=True)
            if code == 0:
                with open(args[0], "wb") as fh:
                    fh.write(body)
                body = {"saved": args[0], "bytes": len(body)}
        elif name == "joints" and len(args) == 7:
            body, code = call("/path", {"points": [[float(v) for v in args]]})
        elif name == "path" and len(args) == 1:
            body, code = call("/path", {"points": load(args[0])})
        elif name == "grip" and len(args) == 1:
            body, code = call("/grip", {"width": float(args[0])})
        elif name == "finish" and not args:
            body, code = call("/finish", {})
        elif name == "try" and not args:
            body, code = call("/try", {})
        elif name == "step" and len(args) <= 1:
            body, code = call("/step", {"actions": load(args[0]) if args else []})
        elif name == "skip" and not args:
            body, code = call("/skip", {})
        else:
            print(HELP)
            return 2
    except (ValueError, OSError) as error:
        print(json.dumps({"error": f"bad input: {error}"}))
        return 2
    print(json.dumps(body))
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
