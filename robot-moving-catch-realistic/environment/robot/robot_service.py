"""The catch cell served over HTTP from its own container. Everything the agent does is written to the record.

One thread owns the cell and carries out one request at a time. The cell moves only inside a request: an ordinary action
outside the try, or a step of the try. No reply says how the try stands; that is kept in the record for the verifier.
"""
import json
import math
import os
import queue
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import world as W
from world import World, png

SEED, RECORD, PORT = int(sys.argv[1]), sys.argv[2], int(sys.argv[3])
BEFORE, AFTER = 10, 30        # arm actions allowed before the try is started, and after it is over
world = World(SEED)
actions, finished = [], False
events, began = [], time.time()
jobs = queue.Queue()
J = "application/json"
IN_TRY = "the try is running: only step, skip, look and state work until it is over"
SECONDS_PER_PHYSICS_STEP = 0.0005     # every reply is held to this much time per physics step it ran, well above what the physics needs
overruns = 0                          # replies that took longer than that; kept in the record, never served


def note(kind, **more):
    events.append(dict(t=round(time.time() - began, 2), kind=kind, after_action=len(actions), **more))


def save():
    os.makedirs(os.path.dirname(RECORD), exist_ok=True)
    done = list(actions)
    if world.pass_ is not None:
        # a try that is still running is recorded up to the tick it has reached
        done.append({"kind": "pass", "commands": world.pass_["log"], "ticks": world.pass_["tick"]})
    body = {"seed": SEED, "actions": done, "finished": finished, "start": world.start, "truth": world.truth(), "sense": world.sense(), "events": events, "overruns": overruns}
    with open(RECORD + ".tmp", "w") as fh:
        json.dump(body, fh)
    os.replace(RECORD + ".tmp", RECORD)


def used():
    """Arm actions taken before the try and after it."""
    kinds = [a["kind"] for a in actions]
    cut = kinds.index("pass") if "pass" in kinds else len(kinds)
    return cut, len(kinds) - cut - ("pass" in kinds)


def allowance():
    before, after = used()
    return BEFORE - before if world.tries_used == 0 else AFTER - after


def status(more=None):
    return dict(world.sense(), **(more or {}), actions_left=allowance(), finished=finished)


def take_steps(first, everything):
    """One step of the try with the given actions, or every remaining step. Closes the try in the record when it ends."""
    running = world.step(first)
    while everything and running:
        running = world.step([])
    if not running:
        last = world.last_pass
        actions.append({"kind": "pass", "commands": last["commands"]})
        note("try ended", result=last["result"], seconds=last["seconds"], commands=len(last["commands"]))


def handle(method, path, query, payload):
    """One request. Returns (code, body, content type)."""
    global finished
    running = world.pass_ is not None
    if method == "GET":
        if path == "/state":
            note("state")
            save()
            return 200, status(), J
        if path == "/observe":
            camera = query.get("camera", ["wrist"])[0]
            if camera not in world.cameras():
                return 400, {"error": f"no camera {camera!r}", "cameras": world.cameras()}, J
            note("look", camera=camera)
            save()
            return 200, png(world.render(camera)), "image/png"
        return 404, {"error": "unknown path"}, J
    name = path.strip("/")
    if finished:
        return 409, {"error": "the session is finished"}, J
    if name in ("step", "skip"):
        if not running:
            return 409, {"error": "no try is running"}, J
        given = payload.get("actions", []) if name == "step" else []
        try:
            W.check_actions(given)
        except ValueError as e:
            return 400, {"error": str(e)}, J
        step = world.pass_["tick"] // W.STEP_TICKS + 1
        take_steps(given, name == "skip")
        note(name, step=step, actions=given)
        save()
        return 200, status(), J
    if running:
        return 409, {"error": IN_TRY}, J
    if name == "finish":
        finished = True
        note("finish")
        save()
        return 200, status(), J
    if name == "try":
        try:
            world.start_pass()
        except ValueError as e:
            return 409, {"error": str(e)}, J
        note("try")
        save()
        return 200, status(), J
    if name not in ("path", "grip"):
        return 404, {"error": "unknown action"}, J
    if allowance() <= 0:
        return 429, {"error": "no actions left"}, J
    try:
        if name == "grip":
            action = {"kind": "grip", "width": float(payload["width"])}
            numbers = [action["width"]]
        else:
            points = [[float(v) for v in p] for p in payload["points"]]
            if not 1 <= len(points) <= W.MAX_POINTS or any(len(p) != 7 for p in points):
                raise ValueError("points")
            action = {"kind": "path", "points": points}
            numbers = [v for p in points for v in p]
        if not all(math.isfinite(v) for v in numbers):
            raise ValueError("not finite")
    except (KeyError, TypeError, ValueError):
        return 400, {"error": f"path needs points: 1 to {W.MAX_POINTS} lists of seven joint angles in radians; grip needs width in metres; all must be ordinary numbers"}, J
    actions.append(action)
    result = world.apply(action)
    more = {k: result[k] for k in ("blocked", "points_reached") if k in result}
    note(name, action=action, reply=dict(world.sense(), **more))
    save()
    return 200, status(more), J


class Handler(BaseHTTPRequestHandler):
    timeout = 10

    def reply(self, code, body, kind=J):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def ask(self, method, path, query, payload):
        box, done = {}, threading.Event()
        jobs.put((method, path, query, payload, box, done))
        done.wait()
        self.reply(*box["out"])

    def do_GET(self):
        url = urlparse(self.path)
        self.ask("GET", url.path, parse_qs(url.query), None)

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            if not 0 <= length <= 100_000:
                raise ValueError(length)
            payload = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(payload, dict):
                raise ValueError("not an object")
        except ValueError:
            return self.reply(400, {"error": "the body is not a JSON object, or is longer than 100,000 bytes"})
        self.ask("POST", urlparse(self.path).path, {}, payload)

    def log_message(self, *args):
        pass


save()
server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
server.daemon_threads = True
threading.Thread(target=server.serve_forever, daemon=True).start()
while True:
    method, path, query, payload, box, done = jobs.get()
    began_at, steps_before = time.monotonic(), world.steps_run
    try:
        box["out"] = handle(method, path, query, payload)
    except Exception:
        # never leave a request hanging, and never show the agent what went wrong inside
        traceback.print_exc()
        box["out"] = (500, {"error": "the robot could not carry out the request"}, J)
    # a reply that moved the cell takes a fixed time for the motion it made, so its timing says nothing about how the try stands
    left = began_at + (world.steps_run - steps_before) * SECONDS_PER_PHYSICS_STEP - time.monotonic()
    if left > 0:
        time.sleep(left)
    elif world.steps_run > steps_before:
        overruns += 1
    done.set()
