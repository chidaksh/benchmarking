"""The simulated catch cell. The robot service and the verifier both run this file, so a replay gives the same result.

The try is stepped: robot time moves only when a step is taken, 0.1 s at a time, and it lasts a fixed 6 s."""
import struct
import zlib

import mujoco
import numpy as np

import cell
import sensing

DT = 0.002             # one physics step, seconds
STEP_ANGLE = 0.0012    # radians the fastest joint target moves per physics step (0.6 rad/s)
SETTLE = 200           # physics steps after each action outside a pass
GRIP_STEPS = 400
LAG = 0.05
LAG_STEPS = 50
SHORT = 0.002
TOUCH_FORCE = 5.0      # newtons from a fixed thing, or from another part of the arm, that stop a move
PINCH_FORCE = 20.0     # net newtons from loose things that stop a move
TOUCH_STEPS = 3
MAX_POINTS = 200
TICK_STEPS = 5         # physics steps in one tick of the try (0.01 s)
TICK = TICK_STEPS * DT
STEP_TICKS = 20        # ticks in one step of the try (0.2 s)
TRY_STEPS = 20         # steps in the try: it lasts 4 s whatever happens
TRY_TICKS = STEP_TICKS * TRY_STEPS
STEP_ACTIONS = 3       # most actions that may be sent with one step
STOP_TICKS = 20        # ticks the arm stays at rest after a stop before a new move can start (0.2 s)
GRACE = 0.05           # seconds the arm may touch a moving part without a two-finger grip, in all and from its first touch
CLEAR_SECONDS = 0.2    # seconds a gripped part must touch nothing but the fingers to count as caught
CLEAR_LIFT = 0.020     # and it must be this far above the track
REST_SPEED = 0.02      # a part slower than this, in the basket and released, is delivered
LET_GO = 0.02          # seconds without a finger on it after which a caught part counts as let go
SQUEEZE = 0.002        # the commanded finger gap must be this much smaller than the gap reached for a hold to count
IMAGE = {"wrist": (480, 480)}                 # cameras the robot serves
DEV_IMAGE = {"overview": (640, 480)}          # for our own viewing tools only


class World:
    def __init__(self, seed, shape=None):
        self.xml, self.facts = cell.build(seed, shape)
        m = self.model = mujoco.MjModel.from_xml_string(self.xml)
        self.data = mujoco.MjData(m)
        self.grip = cell.OPEN
        self.on_step = None        # a viewer may set this to redraw while an action is carried out
        self._renderers = {}
        self._qadr = [m.joint(f"j{n}").qposadr[0] for n in range(1, 8)]
        root = m.body("link1").id
        arm_bodies = {b for b in range(m.nbody) if m.body_rootid[b] == root}
        solid = [g for g in range(m.ngeom) if m.geom_contype[g]]
        self._arm = {g for g in solid if m.geom_bodyid[g] in arm_bodies}
        self._fixed = {g for g in solid if m.body_weldid[m.geom_bodyid[g]] == 0}
        name = lambda g: m.geom(g).name
        self._fingers = (m.geom("finger_left").id, m.geom("finger_right").id)
        self._track = {g for g in solid if name(g).startswith("track_") or name(g).startswith("feeder_")}
        self._basket = {g for g in solid if name(g).startswith("basket_")}
        self._blocks = [m.body(f"block{i}").id for i in range(3)]
        self._block_geoms = {m.geom(f"block{i}").id for i in range(3)}
        self._parts = [m.body(f"part{k}").id for k in range(cell.TRIES)]
        self._part_geoms = [m.geom(f"part{k}").id for k in range(cell.TRIES)]
        self.status = ["waiting"] * cell.TRIES     # waiting, live, foul, lost, caught, dropped, delivered
        self.tries_used = 0
        # readings and commands share the joints' own zeros, which are slightly off: true angle = commanded angle - zero
        self.zero = np.array(self.facts["senses"]["joint_zero"])
        self.pictures = 0
        self.target = np.array(cell.PARK, dtype=float) - self.zero
        self.goal = self.target.copy()
        self.data.qpos[self._qadr] = self.target
        self.pass_ = None
        self.clock = 0.0           # robot time in seconds since the cell started
        self.steps_run = 0         # physics steps taken, so the service can give every reply a fixed time per step
        self._lagging = self._touching = 0
        self._step(SETTLE * 2)
        self.start = self.truth()

    # ---- physics stepping and what the arm feels

    def _step(self, n):
        half = (cell.OPEN - self.grip) / 2
        self.data.ctrl[:7] = self.target
        self.data.ctrl[7:] = [-half, half]
        for _ in range(n):
            mujoco.mj_step(self.model, self.data)
            self.clock += DT
            self.steps_run += 1
            self._watch_parts()
            if self.on_step:
                self.on_step()

    def _touch(self):
        """Newtons on the arm right now: summed pushes from fixed things or the arm itself, and the net push from loose things."""
        hard, net = 0.0, np.zeros(3)
        force = np.zeros(6)
        for i in range(self.data.ncon):
            c = self.data.contact[i]
            a, b = c.geom1 in self._arm, c.geom2 in self._arm
            if not (a or b):
                continue
            mujoco.mj_contactForce(self.model, self.data, i, force)
            other = c.geom2 if a else c.geom1
            if (a and b) or other in self._fixed:
                hard += abs(float(force[0]))
            else:
                net += (-1.0 if a else 1.0) * (c.frame.reshape(3, 3).T @ force[:3])
        return hard, float(np.linalg.norm(net))

    def _joints(self):
        return self.data.qpos[self._qadr].copy()

    def _hold(self):
        self.target = self._joints()
        self.goal = self.target.copy()

    # ---- the rules of a try, applied at every physics step

    def _watch_parts(self):
        for k, state in enumerate(self.status):
            # the same scan is made however the try stands, so the time a reply takes does not give the outcome away
            g = self._part_geoms[k]
            left = right = arm = track = other = False
            for i in range(self.data.ncon):
                c = self.data.contact[i]
                if c.geom1 != g and c.geom2 != g:
                    continue
                o = c.geom2 if c.geom1 == g else c.geom1
                if o == self._fingers[0]:
                    left = True
                elif o == self._fingers[1]:
                    right = True
                elif o in self._arm:
                    arm = True
                elif o in self._track:
                    track = True
                elif state == "caught" and (o in self._basket or o in self._block_geoms):
                    pass
                else:
                    other = True
            # held by both fingers: both touch it and they are being driven closed onto it, not standing still as a gate
            gap = cell.OPEN - float(self.data.joint("finger_left").qpos[0] - self.data.joint("finger_right").qpos[0])
            gripped = left and right and gap - self.grip >= SQUEEZE
            pos = self.data.xpos[self._parts[k]]
            if state not in ("live", "caught"):
                continue
            w = self._w[k]
            if state == "live":
                f = self.facts
                if (left or right or arm) and not gripped:
                    w["touch"] += DT
                if (left or right or arm) and w["first_touch"] is None:
                    w["first_touch"] = self.clock
                # a touch that does not become a hold in time is a tap: it stops or slows the part
                tapped = w["first_touch"] is not None and not w["was_gripped"] and not gripped and self.clock - w["first_touch"] > GRACE
                if gripped:
                    w["was_gripped"] = True
                clear = gripped and not (arm or track or other)
                w["clear"] = w["clear"] + DT if clear and pos[2] - cell.surface(f, pos[1]) >= cell.ROLLER_RADIUS + CLEAR_LIFT else 0.0
                gone = (pos[1] > f["y_end"] or pos[2] < cell.surface(f, min(pos[1], f["y_end"])) - 0.005
                        or abs(pos[0] - f["track_x"]) > f["lane"] / 2 + cell.RAIL[0])
                if w["clear"] >= CLEAR_SECONDS:
                    self.status[k] = "caught"
                elif not gripped and gone:
                    self.status[k] = "lost"
                elif w["touch"] > GRACE or tapped or (w["was_gripped"] and not (left or right)) or other:
                    self.status[k] = "foul"            # stopped, pushed, met by something put in its way, or let go of
            else:
                # caught: the part stays in the hand until it is let go, and the only place to let it go is the basket
                bx, by = self.facts["basket"]
                over = abs(pos[0] - bx) <= cell.BASKET_INNER[0] / 2 and abs(pos[1] - by) <= cell.BASKET_INNER[1] / 2
                w["free"] = 0.0 if (left or right) else w["free"] + DT
                if w["free"] < LET_GO:
                    w["rest"] = 0.0
                    continue
                if not over:
                    self.status[k] = "dropped"         # let go, or lost from the fingers, anywhere but in the basket
                    continue
                adr = self.model.body_dofadr[self._parts[k]]
                slow = float(np.linalg.norm(self.data.qvel[adr:adr + 3])) < REST_SPEED
                w["rest"] = w["rest"] + DT if slow else 0.0
                if w["rest"] >= CLEAR_SECONDS:
                    self.status[k] = "delivered" if pos[2] <= cell.BASKET_HEIGHT + cell.ROLLER_RADIUS else "dropped"

    # ---- the try: the scene moves in ticks of 0.01 s, ten to a step, and only when a step is taken

    def start_pass(self):
        """Start the try: the part is released. Only from the park pose, and only once."""
        if self.pass_ is not None:
            raise ValueError("the try is already running")
        if self.tries_used >= cell.TRIES:
            raise ValueError("the try has already been used")
        if not self.parked():
            raise ValueError("the try starts from the park pose: park the arm and open the fingers first. Nothing was used up")
        part = self.tries_used
        self.tries_used += 1
        self._release(part)
        self.goal = self.target.copy()
        self._lagging = self._touching = 0
        self.pass_ = {"part": part, "tick": 0, "queue": [], "log": [], "held": [], "blocked": False, "moves": [], "rest_until": 0}
        return part

    def step(self, actions):
        """Take one step of the try. The actions given with the last step are carried out in this one; these are held for the next."""
        p = self.pass_
        if p is None:
            raise ValueError("no try is running")
        held = check_actions(actions)
        p["blocked"] = False
        for e in p["held"]:
            entry = {k: v for k, v in e.items() if k != "offset"}
            entry["tick"] = p["tick"] + e["offset"]
            p["queue"].append(entry)
            p["log"].append(entry)
        p["held"] = held
        for _ in range(STEP_TICKS):
            if not self.tick():
                return False
        return True

    def _release(self, k):
        m, d, f = self.model, self.data, self.facts
        tr = f["tries"][k]
        j = m.joint(m.body(f"part{k}").jntadr[0])
        x, y, z = f["release"]
        yaw = tr["yaw"]
        # the roller lies across the track: its own axis (body z) points along the cell's x, turned by a small yaw
        qy, qz = np.array([np.cos(np.pi / 4), 0, np.sin(np.pi / 4), 0]), np.array([np.cos(yaw / 2), 0, 0, np.sin(yaw / 2)])
        quat = np.zeros(4)
        mujoco.mju_mulQuat(quat, qz, qy)
        d.qpos[j.qposadr[0]:j.qposadr[0] + 7] = [x + tr["offset"], y, z, *quat]
        v = tr["speed"]
        c, s = np.cos(f["slope"]), np.sin(f["slope"])
        R = np.zeros(9)
        mujoco.mju_quat2Mat(R, quat)
        spin_world = np.array([-v / cell.ROLLER_RADIUS, 0.0, 0.0])        # rolling without slipping toward +y
        d.qvel[j.dofadr[0]:j.dofadr[0] + 3] = [0.0, v * c, -v * s]
        d.qvel[j.dofadr[0] + 3:j.dofadr[0] + 6] = R.reshape(3, 3).T @ spin_world
        mujoco.mj_forward(m, d)
        if not hasattr(self, "_w"):
            self._w = {}
        self._w[k] = {"first_touch": None, "touch": 0.0, "clear": 0.0, "rest": 0.0, "free": 0.0, "was_gripped": False, "released": self.clock}
        self.status[k] = "live"

    def tick(self):
        """Advance a running pass by one tick. Returns False when the pass has ended."""
        p = self.pass_
        low, high = np.array(cell.LIMITS).T
        due = [e for e in p["queue"] if e["tick"] <= p["tick"]]
        p["queue"] = [e for e in p["queue"] if e["tick"] > p["tick"]]
        for e in due:
            if e.get("stop"):
                # the arm comes to rest where it is, and the moves it had not finished are dropped
                self._hold()
                p["moves"] = []
                p["rest_until"] = p["tick"] + STOP_TICKS
            if "joints" in e:
                p["moves"].append(np.clip(np.array(e["joints"]), low, high) - self.zero)
            if "grip" in e:
                self.grip = float(np.clip(e["grip"], 0.0, cell.OPEN))
        # a move cannot be changed once sent: the next one starts only when the one before has run its course
        if p["moves"] and p["tick"] >= p["rest_until"] and float(np.abs(self.goal - self.target).max()) <= 1e-9:
            self.goal = p["moves"].pop(0)
        for _ in range(TICK_STEPS):
            gap = self.goal - self.target
            far = float(np.abs(gap).max())
            if far > 1e-9:
                self.target = self.target + gap * min(1.0, STEP_ANGLE / far)
            self._step(1)
            hard, soft = self._touch()
            self._lagging = self._lagging + 1 if float(np.abs(self.target - self._joints()).max()) > LAG else 0
            self._touching = self._touching + 1 if hard > TOUCH_FORCE or soft > PINCH_FORCE else 0
            if self._lagging >= LAG_STEPS or self._touching >= TOUCH_STEPS:
                # something stopped the arm: the same as a stop, and reported for the step in which it happened
                self._hold()
                p["blocked"] = True
                p["moves"] = []
                p["rest_until"] = p["tick"] + STOP_TICKS
                self._lagging = self._touching = 0
        p["tick"] += 1
        k = p["part"]
        over = p["tick"] >= TRY_TICKS
        if over:
            if self.status[k] == "live":
                self.status[k] = "lost"                # not caught by the end of the try
            self.last_pass = {"part": k, "seconds": round(p["tick"] * TICK, 2), "result": self.status[k], "commands": p["log"]}
            self._hold()
            self.pass_ = None
        return not over

    # ---- actions outside a pass

    def apply(self, action):
        """Carry out one recorded action. Returns what the robot can sense afterwards."""
        if self.pass_ is not None:
            raise ValueError("the try is running")
        kind = action["kind"]
        blocked, done = False, 0
        if kind == "path":
            points = np.array(action["points"], dtype=float).reshape(-1, 7)
            if not np.isfinite(points).all() or not 1 <= len(points) <= MAX_POINTS:
                raise ValueError("a path needs 1 to 200 points of seven finite numbers")
            low, high = np.array(cell.LIMITS).T
            lagging = touching = 0
            for goal in np.clip(points, low, high) - self.zero:
                while not blocked:
                    gap = goal - self.target
                    far = float(np.abs(gap).max())
                    if far < 1e-9:
                        break
                    self.target = self.target + gap * min(1.0, STEP_ANGLE / far)
                    self._step(1)
                    hard, soft = self._touch()
                    lagging = lagging + 1 if float(np.abs(self.target - self._joints()).max()) > LAG else 0
                    touching = touching + 1 if hard > TOUCH_FORCE or soft > PINCH_FORCE else 0
                    blocked = lagging >= LAG_STEPS or touching >= TOUCH_STEPS
                if blocked:
                    break
                done += 1
            if blocked:
                self._hold()
            self._step(SETTLE)
            if blocked or float(np.abs(self.target - self._joints()).max()) > SHORT:
                blocked = True
                self._hold()
                self._step(SETTLE)
            self.goal = self.target.copy()
        elif kind == "grip":
            width = float(action["width"])
            if not np.isfinite(width):
                raise ValueError("a grip needs a finite width")
            self.grip = float(np.clip(width, 0.0, cell.OPEN))
            self._step(GRIP_STEPS)
        elif kind == "pass":
            # the try at once, from its log of commands: used to replay a record. `ticks` stops a try that was left unfinished
            self.start_pass()
            for e in action.get("commands", []):
                self.pass_["queue"].append(dict(e))
                self.pass_["log"].append(dict(e))
            stop = action.get("ticks", TRY_TICKS)
            while self.pass_["tick"] < stop and self.tick():
                pass
            return dict(self.sense(), last_pass=None if self.pass_ else {k: v for k, v in self.last_pass.items() if k != "commands"})
        else:
            raise ValueError(f"unknown action: {kind}")
        out = dict(self.sense(), blocked=blocked)
        if kind == "path":
            out["points_reached"] = done
        return out

    def parked(self):
        """The arm reads as being at the park pose with the fingers open, by the same limits the end check uses."""
        gap = cell.OPEN - float(self.data.joint("finger_left").qpos[0] - self.data.joint("finger_right").qpos[0])
        return bool(np.abs(self._joints() + self.zero - np.array(cell.PARK)).max() <= cell.PARK_TOLERANCE and gap >= cell.PARK_GAP - 1e-4)

    def sense(self):
        """What the robot reports: joint angles, the gap between the fingers, and where the try's clock is. Never how the try stands."""
        gap = cell.OPEN - float(self.data.joint("finger_left").qpos[0] - self.data.joint("finger_right").qpos[0])
        out = {"joints": [round(float(v), sensing.READING) for v in self._joints() + self.zero], "finger_gap": round(gap, sensing.READING)}
        p = self.pass_
        if p is None:
            out["try"] = "over" if self.tries_used else "not started"
        else:
            out.update({"try": "running", "step": p["tick"] // STEP_TICKS, "steps_left": TRY_STEPS - p["tick"] // STEP_TICKS,
                        "time": round(p["tick"] * TICK, 2), "blocked": p["blocked"]})
        return out

    def truth(self):
        """True position and attitude of every loose body, and how each try stands. Only the record and the verifier see this."""
        out = {"status": list(self.status)}
        for i in range(1, self.model.nbody):
            name = self.model.body(i).name
            if name.startswith("block") or name.startswith("part") or name == "hand":
                out[name] = {"pos": [float(v) for v in self.data.xpos[i]], "mat": [float(v) for v in self.data.xmat[i]]}
        return out

    def render(self, camera):
        width, height = dict(IMAGE, **DEV_IMAGE)[camera]
        if camera not in self._renderers:
            self._renderers[camera] = mujoco.Renderer(self.model, height, width)
        self._renderers[camera].update_scene(self.data, camera=camera)
        rgb = self._renderers[camera].render()
        if camera in IMAGE:
            # what the robot's own camera delivers: through its lens, with noise
            self.pictures += 1
            rgb = sensing.picture(rgb, self.facts["senses"]["lens"], self.facts["seed"], self.pictures)
        return rgb

    def cameras(self):
        return list(IMAGE)


def check_actions(actions):
    """The actions sent with one step as clean entries, or ValueError saying what is wrong. Nothing moves if any is wrong."""
    if not isinstance(actions, list) or len(actions) > STEP_ACTIONS:
        raise ValueError(f"the actions of a step are a JSON list of at most {STEP_ACTIONS}")
    out = []
    for n, cmd in enumerate(actions):
        try:
            if not isinstance(cmd, dict) or set(cmd) - {"at", "joints", "grip", "stop"}:
                raise ValueError("an action is a JSON object with at, joints, grip and stop only")
            at = cmd.get("at", 0)
            if isinstance(at, bool) or not isinstance(at, (int, float)) or not -1 < at < 1 or abs(at * 100 - round(at * 100)) > 1e-6 or not 0 <= round(at * 100) < STEP_TICKS:
                raise ValueError("at must be one of 0.00, 0.01, ... 0.19")
            entry = check_command(cmd)
        except ValueError as e:
            raise ValueError(f"action {n + 1} is not valid: {e}. The step was not taken")
        entry["offset"] = int(round(at * 100))
        out.append(entry)
    return out


def check_command(cmd):
    """The joints, grip and stop of one action as a clean entry, or ValueError saying what is wrong with it."""
    entry = {}
    if "stop" in cmd:
        if cmd["stop"] is not True:
            raise ValueError("stop must be true")
        if "joints" in cmd:
            raise ValueError("stop and joints cannot be in the same action")
        entry["stop"] = True
    if "joints" in cmd:
        try:
            q = np.array(cmd["joints"], dtype=float)
        except (TypeError, ValueError):
            q = np.array([])
        if q.shape != (7,) or not np.isfinite(q).all():
            raise ValueError("joints must be seven finite numbers")
        entry["joints"] = [float(v) for v in q]
    if "grip" in cmd:
        g = cmd["grip"]
        if isinstance(g, bool) or not isinstance(g, (int, float)) or not np.isfinite(g):
            raise ValueError("grip must be a finite number")
        entry["grip"] = float(g)
    if not entry:
        raise ValueError("an action needs joints, grip or stop")
    return entry


def png(rgb, level=6):
    """Encode an RGB array as a PNG file with the standard library only."""
    height, width, _ = rgb.shape
    raw = b"".join(b"\x00" + rgb[y].tobytes() for y in range(height))

    def chunk(tag, body):
        return struct.pack(">I", len(body)) + tag + body + struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, level)) + chunk(b"IEND", b""))
