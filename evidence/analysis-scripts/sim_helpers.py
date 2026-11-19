"""Dev helpers that use the simulator's true state. Never shipped to the agent."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "robot-moving-catch-realistic", "environment", "robot"))
import numpy as np, mujoco
import cell
from world import World

LOW, HIGH = np.array(cell.LIMITS).T


class Dev:
    def __init__(self, seed):
        self.w = World(seed)
        self.m = self.w.model
        self.scratch = mujoco.MjData(self.m)
        self.hand = self.m.body("hand").id
        self.log = []
        self.actions = []
        self.holding = None

    def fk(self, q):
        d = self.scratch
        d.qpos[:] = self.w.data.qpos
        d.qpos[self.w._qadr] = q
        mujoco.mj_kinematics(self.m, d)
        mujoco.mj_comPos(self.m, d)
        return d.xpos[self.hand].copy(), d.xmat[self.hand].reshape(3, 3).copy()

    def ik(self, pos, R, q0, iters=200):
        """Damped least squares to a hand pose (palm centre and attitude)."""
        q = np.array(q0, dtype=float)
        d = self.scratch
        jp, jr = np.zeros((3, self.m.nv)), np.zeros((3, self.m.nv))
        dof = [self.m.joint(f"j{n}").dofadr[0] for n in range(1, 8)]
        for _ in range(iters):
            p, Rc = self.fk(q)
            ep = pos - p
            Re = R @ Rc.T
            er = 0.5 * np.array([Re[2, 1] - Re[1, 2], Re[0, 2] - Re[2, 0], Re[1, 0] - Re[0, 1]])
            if np.linalg.norm(ep) < 2e-5 and np.linalg.norm(er) < 2e-5:
                return q, True
            mujoco.mj_jacBody(self.m, d, jp, jr, self.hand)
            J = np.vstack([jp[:, dof], jr[:, dof]])
            e = np.concatenate([ep, er])
            dq = J.T @ np.linalg.solve(J @ J.T + 1e-4 * np.eye(6), e)
            # the spare joint is used to stay near the middle of the joint ranges
            null = (np.eye(7) - np.linalg.pinv(J) @ J) @ (-0.1 * q / (HIGH - LOW))
            q = np.clip(q + np.clip(dq, -0.2, 0.2) + null, LOW, HIGH)
        return q, False

    def joints(self):
        return self.w._joints()

    def touching(self):
        """What the arm touches in the live cell right now, with the push in newtons."""
        out, force = [], np.zeros(6)
        dd = self.w.data
        for i in range(dd.ncon):
            c = dd.contact[i]
            if c.geom1 in self.w._arm or c.geom2 in self.w._arm:
                mujoco.mj_contactForce(self.m, dd, i, force)
                out.append((self.m.geom(c.geom1).name, self.m.geom(c.geom2).name, round(float(force[0]), 2)))
        return out

    def solve(self, pos, R, gap=None, first=(), quick=False, margin=0.0):
        """A joint setting for a hand pose, tried from the current joints and from a few fixed starts."""
        best = None
        for seed in list(first) + [self.joints(), cell.PARK, [0.5, 0.3, 0, 1.6, 0, 1.2, 0], [-0.5, 0.3, 0, 1.6, 0, 1.2, 0], [0, 0.6, 0.8, 1.4, -0.8, 1.0, 0], [0, 0.6, -0.8, 1.4, 0.8, 1.0, 0]]:
            q, ok = self.ik(pos, R, seed)
            if ok and (q - LOW).min() >= margin and (HIGH - q).min() >= margin and not self.hits(q, gap) and (best is None or np.abs(q - self.joints()).max() < np.abs(best - self.joints()).max()):
                best = q
                if first or quick:
                    break
        return best

    def hits(self, q, gap=None):
        """Names of the things the arm would touch at joint setting q, by the simulator's own collision check."""
        d = self.scratch
        d.qpos[:] = self.w.data.qpos
        d.qpos[self.w._qadr] = q
        if gap is not None:
            d.qpos[self.m.joint("finger_right").qposadr[0]] = -(cell.OPEN - gap) / 2
            d.qpos[self.m.joint("finger_left").qposadr[0]] = (cell.OPEN - gap) / 2
        mujoco.mj_forward(self.m, d)
        out = set()
        for i in range(d.ncon):
            c = d.contact[i]
            if c.dist < 0 and ((c.geom1 in self.w._arm) != (c.geom2 in self.w._arm)):
                out.add(self.m.geom(c.geom2 if c.geom1 in self.w._arm else c.geom1).name)
        # a block in the hand moves with the hand, so its old place is not an obstacle
        out.discard(f"block{self.holding}")
        return out

    def depths(self, q, gap=None):
        """How deep the arm would sink into each thing it touches at joint setting q (metres, by name)."""
        d = self.scratch
        d.qpos[:] = self.w.data.qpos
        d.qpos[self.w._qadr] = q
        if gap is not None:
            d.qpos[self.m.joint("finger_right").qposadr[0]] = -(cell.OPEN - gap) / 2
            d.qpos[self.m.joint("finger_left").qposadr[0]] = (cell.OPEN - gap) / 2
        mujoco.mj_forward(self.m, d)
        out = {}
        for i in range(d.ncon):
            c = d.contact[i]
            if c.dist < 0 and ((c.geom1 in self.w._arm) != (c.geom2 in self.w._arm)):
                name = self.m.geom(c.geom2 if c.geom1 in self.w._arm else c.geom1).name
                out[name] = max(out.get(name, 0.0), -c.dist)
        out.pop(f"block{self.holding}", None)
        return out

    def path_clear(self, q0, q1, n=14):
        """True when the arm touches nothing on the straight joint-space move from q0 to q1 (checked at n points)."""
        q0, q1 = np.array(q0, dtype=float), np.array(q1, dtype=float)
        return not any(self.hits(q0 + s * (q1 - q0)) for s in np.linspace(0.15, 1.0, n))

    def goto(self, pos, R, label="", gap=None, first=(), margin=0.0):
        """Joint-space move to a hand pose, by way of the park pose when the direct move would hit something."""
        q = self.solve(pos, R, gap, first, margin=margin)
        if q is None:
            print("  no joint setting for", label, "| target", np.round(pos, 3), "hand z axis", np.round(R[:, 2], 2))
            for seed in [self.joints(), cell.PARK, [0.5, 0.3, 0, 1.6, 0, 1.2, 0]]:
                qq, ok = self.ik(pos, R, seed)
                print("     seed", np.round(seed, 2), "ik", ok, "q", qq.round(2), "hits", sorted(self.hits(qq, gap)) if ok else "")
            return None
        q0, park = self.joints(), np.array(cell.PARK)
        points = [q.tolist()]
        if not self.path_clear(q0, q) and self.path_clear(q0, park) and self.path_clear(park, q):
            points = [cell.PARK, q.tolist()]
        r = self.do({"kind": "path", "points": points}, label)
        if r["blocked"]:
            print(f"  BLOCKED in {label}")
        return r

    def cmd(self, q):
        """A true joint setting as the command that takes the arm there."""
        return (np.array(q, dtype=float) + self.w.zero).tolist()

    def do(self, action, label=""):
        if action["kind"] == "path":
            action = {"kind": "path", "points": [self.cmd(p) for p in action["points"]]}
        self.actions.append(action)
        r = self.w.apply(action)
        self.log.append((label, action["kind"], r["blocked"]))
        return r

    def line(self, pos, R, steps=None, label=""):
        """Move the hand in a straight line to a pose, as one path of small joint steps."""
        p0, R0 = self.fk(self.joints())
        dist = np.linalg.norm(pos - p0)
        ang = np.arccos(np.clip((np.trace(R0.T @ R) - 1) / 2, -1, 1))
        n = steps or int(max(2, dist / 0.01, ang / 0.05))
        q, pts = self.joints(), []
        from_to = _slerp(R0, R)
        for k in range(1, n + 1):
            s = k / n
            q, ok = self.ik(p0 + s * (pos - p0), from_to(s), q)
            if not ok:
                if pos[2] < p0[2] - 1e-6:
                    print("  IK failed at", label, s)
                    return None
                # a move that goes up may finish as a joint-space move
                if pts:
                    r = self.do({"kind": "path", "points": pts}, label)
                    if r["blocked"]:
                        print(f"  BLOCKED in {label}")
                        return r
                return self.goto(pos, R, label + " (joint move)")
            pts.append(q.tolist())
        r = self.do({"kind": "path", "points": pts}, label)
        if r["blocked"]:
            print(f"  BLOCKED in {label}: reached {r['points_reached']}/{n}")
        return r

    def grip(self, width, label=""):
        return self.do({"kind": "grip", "width": width}, label)

    def block(self, n):
        b = self.w._blocks[n]
        return self.w.data.xpos[b].copy(), self.w.data.xmat[b].reshape(3, 3).copy()


def _slerp(R0, R1):
    Rd = R0.T @ R1
    ang = np.arccos(np.clip((np.trace(Rd) - 1) / 2, -1, 1))
    if ang < 1e-9:
        return lambda s: R1
    axis = np.array([Rd[2, 1] - Rd[1, 2], Rd[0, 2] - Rd[2, 0], Rd[1, 0] - Rd[0, 1]]) / (2 * np.sin(ang))
    K = np.array([[0, -axis[2], axis[1]], [axis[2], 0, -axis[0]], [-axis[1], axis[0], 0]])
    return lambda s: R0 @ (np.eye(3) + np.sin(s * ang) * K + (1 - np.cos(s * ang)) * K @ K)


def down(yaw):
    """Hand attitude with the fingers pointing straight down and opening along the direction yaw."""
    c, s = np.cos(yaw), np.sin(yaw)
    return np.array([[c, s, 0], [s, -c, 0], [0, 0, -1]], dtype=float)


def frame(x, z):
    """Hand attitude from the direction the fingers open along and the direction they point."""
    x, z = np.array(x, dtype=float), np.array(z, dtype=float)
    z /= np.linalg.norm(z)
    x = x - z * (x @ z)
    x /= np.linalg.norm(x)
    return np.column_stack([x, np.cross(z, x), z])
