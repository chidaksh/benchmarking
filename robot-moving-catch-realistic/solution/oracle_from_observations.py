"""Oracle that works from what the agent observes: the robot command, the palm camera, touches, and the manual's arm formula."""
"""Reference solution that works from what the agent is given: the robot command, the palm camera, touches, and the manual's arm formula."""
import json, os, subprocess, sys, tempfile
import numpy as np
from PIL import Image

ROBOT = os.environ.get("ROBOT_CMD", "robot").split()
WORK = tempfile.mkdtemp()
F = 240 / np.tan(np.radians(30))                              # pixels per unit of slope, from the 60 degree field of view
PARK = np.array([0, 0, 0, 1.5708, 0, 1.5708, 0.0])
HIGH = np.array([2.9, 2.0, 2.9, 2.4, 2.9, 2.0, 2.9]); LOW = -HIGH
TIP, CAM, OPEN, SPEED = 0.070, 0.011, 0.060, 0.6              # manual 1.2, 3, 1.3
TILT = np.radians(float(os.environ.get("TILT", "30")))        # how far the hand leans up the track at the grasp pose
RISE = float(os.environ.get("RISE", "0.016"))                 # fingertips above the track surface at the grasp pose
FROM_END = float(os.environ.get("FROM_END", "0.12"))          # the catch point is this far up the track from its lower end
FIT = int(os.environ.get("FIT", "3"))                           # how many of the latest sightings the straight line is fitted through
STOP_AFTER_TRY = os.environ.get("STOP_AFTER_TRY") == "1"


def say(*a):
    print(*a, flush=True)


# ---- the robot command ------------------------------------------------------------------------------------------------
def robot(*args):
    out = subprocess.run([*ROBOT, *args], capture_output=True, text=True)
    try:
        reply = json.loads(out.stdout)
    except ValueError:
        sys.exit(f"robot {args[0]}: {out.stdout[:200]} {out.stderr[:200]}")
    if out.returncode != 0:
        sys.exit(f"robot {args[0]} was refused: {reply}")
    return reply


def send(name, content):
    path = os.path.join(WORK, name + ".json")
    with open(path, "w") as fh:
        json.dump(content, fh)
    return robot(name, path)


def joints():
    return np.array(robot("state")["joints"])


def look():
    path = os.path.join(WORK, "look.png")
    robot("look", path)
    return np.array(Image.open(path).convert("RGB"))


def move(*points):
    return send("path", [[float(v) for v in p] for p in points])


# ---- the arm, from the manual's formula ---------------------------------------------------------------------------------
def rz(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1.0]])


def ry(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, 0, s], [0, 1.0, 0], [-s, 0, c]])


def fk(q):
    """Palm centre and hand attitude for joint angles q."""
    R = rz(q[0]); p = np.array([0, 0, 0.20])
    R = R @ ry(q[1]) @ rz(q[2]); p = p + R[:, 2] * 0.30
    R = R @ ry(q[3]) @ rz(q[4]); p = p + R[:, 2] * 0.30
    R = R @ ry(q[5]) @ rz(q[6]); p = p + R[:, 2] * 0.10
    return p, R


def spin(R):
    return 0.5 * np.array([R[2, 1] - R[1, 2], R[0, 2] - R[2, 0], R[1, 0] - R[0, 1]])


def ik(pos, R, q0, iters=200):
    """Joint angles that put the palm at pos with attitude R, starting the search from q0."""
    q = np.array(q0, dtype=float)
    for _ in range(iters):
        p, Rc = fk(q)
        e = np.concatenate([pos - p, spin(R @ Rc.T)])
        if np.linalg.norm(e[:3]) < 2e-5 and np.linalg.norm(e[3:]) < 2e-5:
            return q, True
        J = np.zeros((6, 7))
        for i in range(7):
            dq = np.zeros(7); dq[i] = 1e-6
            p2, R2 = fk(q + dq)
            J[:3, i] = (p2 - p) / 1e-6
            J[3:, i] = spin(R2 @ Rc.T) / 1e-6
        step = J.T @ np.linalg.solve(J @ J.T + 1e-4 * np.eye(6), e)
        centre = (np.eye(7) - np.linalg.pinv(J) @ J) @ (-0.1 * q / (HIGH - LOW))
        q = np.clip(q + np.clip(step, -0.2, 0.2) + centre, LOW, HIGH)
    return q, False


def frame(x, z):
    """Hand attitude from the direction the fingers open along and the direction they point."""
    x, z = np.array(x, dtype=float), np.array(z, dtype=float)
    z /= np.linalg.norm(z)
    x = x - z * (x @ z); x /= np.linalg.norm(x)
    return np.column_stack([x, np.cross(z, x), z])


def tip(q):
    p, R = fk(q)
    return p + TIP * R[:, 2]


def camera(q):
    p, R = fk(q)
    return p + CAM * R[:, 2], R


def on_level(us, vs, q, h):
    """Where the rays through these pixels meet the level z = h."""
    cam, R = camera(q)
    rays = (R @ np.vstack([(us - 239.5) / F, (vs - 239.5) / F, np.ones(len(us))])).T
    return cam + rays * ((h - cam[2]) / rays[:, 2])[:, None]


# ---- colours ------------------------------------------------------------------------------------------------------------
def channels(rgb):
    return (rgb[..., i].astype(int) for i in range(3))


def strip_pixels(rgb):
    r, g, b = channels(rgb)
    return (b > r + 30) & (g > 90)                            # the track: blue and bright


def finger_pixels(rgb):
    r, g, b = channels(rgb)
    return (b > r + 40) & (g < 60)                            # the fingers: blue and dark


def other_pixels(rgb):
    r, g, b = channels(rgb)
    top, low = np.maximum(np.maximum(r, g), b), np.minimum(np.minimum(r, g), b)
    return (top - low > 60) & (b < r + 10)                    # coloured, and not blue: neither track, fingers nor the grey table


def thing_pixels(rgb):
    """Anything that is not the grey table, the track or the fingers."""
    r, g, b = channels(rgb)
    top, low = np.maximum(np.maximum(r, g), b), np.minimum(np.minimum(r, g), b)
    return ~((top - low < 30) & (top > 150)) & ~strip_pixels(rgb) & ~finger_pixels(rgb)


def regions(mask):
    """Connected regions of a mask, on a grid of 4 by 4 pixel cells. Returns a list of arrays of cell coordinates."""
    cells = mask[:480, :480].reshape(120, 4, 120, 4).mean((1, 3)) > 0.5
    seen, out = np.zeros_like(cells), []
    for i, j in zip(*np.nonzero(cells)):
        if seen[i, j]:
            continue
        stack, member = [(i, j)], []
        seen[i, j] = True
        while stack:
            a, b = stack.pop()
            member.append((a, b))
            for c, e in ((a + 1, b), (a - 1, b), (a, b + 1), (a, b - 1)):
                if 0 <= c < 120 and 0 <= e < 120 and cells[c, e] and not seen[c, e]:
                    seen[c, e] = True
                    stack.append((c, e))
        out.append(np.array(member))
    return out


def find_basket(rgb):
    """The box with other colours inside it: its outline, its two colours, and its most open floor spot as fractions of the outline."""
    best = None
    table = ~thing_pixels(rgb) | strip_pixels(rgb) | finger_pixels(rgb)
    for member in regions(thing_pixels(rgb)):
        if len(member) < 300:
            continue
        v0, u0 = member.min(0) * 4
        v1, u1 = member.max(0) * 4 + 4
        box = rgb[v0:v1, u0:u1].astype(int)
        colour = np.median(box.reshape(-1, 3), 0)
        differs = (np.abs(box - colour).sum(2) > 110) & ~table[v0:v1, u0:u1]
        if best is None or differs.sum() > best[0]:
            best = (int(differs.sum()), (u0, u1, v0, v1), colour, differs)
    if best is None or best[0] < 400:
        return None
    _, (u0, u1, v0, v1), colour, differs = best
    box = rgb[v0:v1, u0:u1].astype(int)
    floor = np.abs(box - colour).sum(2) < 60
    h, w = floor.shape
    ring = np.ones((h, w), bool); ring[int(0.06 * h):int(0.94 * h), int(0.06 * w):int(0.94 * w)] = False
    edge = np.median(box[ring & ~table[v0:v1, u0:u1]], 0)
    # most open spot: the floor point furthest from anything that is not floor
    vv, uu = np.nonzero(~floor[::3, ::3])
    blocked = np.column_stack([uu * 3, vv * 3])
    spot, room = None, -1.0
    for v in range(int(0.14 * h), int(0.86 * h), 4):
        for u in range(int(0.14 * w), int(0.86 * w), 4):
            if not floor[v, u]:
                continue
            d = min(np.sqrt(((blocked - (u, v)) ** 2).sum(1)).min(), u - 0.12 * w, 0.88 * w - u, v - 0.12 * h, 0.88 * h - v)
            if d > room:
                spot, room = (u / w, v / h), d
    return (u0, u1, v0, v1), colour, edge, spot, room / w


def down_pose(xy, tip_z, across, near):
    """Joint setting with the hand straight down, fingers opening across the track, fingertips at this point."""
    R = frame([across[0], across[1], 0], [0, 0, -1])
    for start in (near, PARK):
        q, ok = ik(np.array([xy[0], xy[1], tip_z + TIP]), R, start)
        if ok and (q > LOW + 1e-6).all() and (q < HIGH - 1e-6).all():
            return q
    sys.exit(f"no joint setting above {np.round(xy, 3)} at height {tip_z:.3f}")


def touch(xy, across, from_z):
    """Lower the closed fingers until the arm is stopped. The fingertips' height then is the surface's height."""
    q = joints()
    here = tip(q)
    lift = down_pose(here[:2], max(here[2], from_z), across, q)
    over = down_pose(xy, from_z, across, lift)
    below = down_pose(xy, from_z - 0.14, across, over)
    reply = move(lift, over, below)
    if not reply["blocked"]:
        sys.exit("a touch met nothing")
    return float(tip(np.array(reply["joints"]))[2])


def main():
    # ---- survey: where the track is, which way is downhill, where it ends, how high it is at the catch point -------------
    h0 = 0.08                                                 # a first guess at the track's height, replaced by the touches
    q = joints()
    vs, us = np.nonzero(strip_pixels(look()))
    if len(us) < 500:
        sys.exit("no track in the picture from park")
    pts = on_level(us, vs, q, h0)[:, :2]
    c0 = pts.mean(0)
    t0 = np.linalg.eigh(np.cov((pts - c0).T))[1][:, 1]        # the long direction of the strip
    n0 = np.array([t0[1], -t0[0]])
    # action 1: a look from straight above the strip, to place its centre line
    q = np.array(move(down_pose(c0, h0 + 0.20 - (TIP - CAM), n0, q))["joints"])
    vs, us = np.nonzero(strip_pixels(look()))
    pts = on_level(us, vs, q, h0)[:, :2]
    c1 = np.median(pts, 0)
    t1 = np.linalg.eigh(np.cov((pts - pts.mean(0)).T))[1][:, 1]
    n1 = np.array([t1[1], -t1[0]])
    c1 = c1 - n1 * ((pts - c1) @ n1).mean()
    say(f"survey: strip centre near {np.round(c1, 3)}, running along {np.round(t1, 3)}")
    # actions 2 to 4: closed fingers, and two touches 0.14 apart along the strip. The lower one is downhill
    robot("grip", "0")
    za = touch(c1 - 0.07 * t1, n1, 0.20)
    zb = touch(c1 + 0.07 * t1, n1, za + 0.05)
    say(f"survey: touches at heights {za:.4f} and {zb:.4f}")
    if abs(za - zb) < 0.002 or min(za, zb) < 0.03:
        sys.exit("the two touches do not show a sloping track")
    if zb > za:
        t1, n1 = -t1, -n1                                     # from here on, +s runs downhill
    sb, zlow = 0.07, min(za, zb)
    line = lambda s, off=0.0: c1 + t1 * s + n1 * off
    # action 5: a look further downhill for the lower end of the strip
    q = joints()
    lift = down_pose(tip(q)[:2], zlow + 0.10, n1, q)
    q = np.array(move(lift, down_pose(line(sb + 0.15), zlow + 0.22 - (TIP - CAM), n1, lift))["joints"])
    vs, us = np.nonzero(strip_pixels(look()))
    pts = on_level(us, vs, q, zlow - 0.005)[:, :2]
    s = ((pts - c1) @ t1)[np.abs((pts - c1) @ n1) < 0.035]
    edge = ((on_level(np.array([239.5, 239.5]), np.array([0.0, 479.0]), q, zlow - 0.005)[:, :2] - c1) @ t1).max()
    s_end = float(np.percentile(s, 99.5))
    if s_end > edge - 0.01:
        sys.exit("the strip runs out of the picture: its lower end was not seen")
    s_c = s_end - FROM_END
    # action 6: a touch at the catch point for its height
    zc = touch(line(s_c), n1, zlow + 0.06)
    slope = float(np.clip((zlow - zc) / max(s_c - sb, 0.02), 0.0, 0.08))
    S = lambda s_: zc + slope * (s_c - s_)                    # height of the track surface along the strip, as measured
    say(f"survey: lower end {s_end:.3f} along the strip, catch point at {np.round(line(s_c), 3)}, height there {zc:.4f}, slope {slope:.3f}")
    # actions 7 and 8: lift, open the fingers, and look closely: the strip should sit midway between the fingers
    q = joints()
    lift = down_pose(tip(q)[:2], zc + 0.06, n1, q)
    move(lift, down_pose(line(s_c), zc + 0.035, n1, lift))
    robot("grip", str(OPEN))
    q = joints()
    rgb = look()
    rows, cols = slice(200, 280), np.arange(480)
    strip = cols[strip_pixels(rgb)[rows].mean(0) > 0.5]
    if len(strip) < 40:
        sys.exit("no strip in the close look")
    u_strip = (strip.min() + strip.max()) / 2
    dark = finger_pixels(rgb)[rows].mean(0) > 0.5
    left, right = cols[dark & (cols < strip.min() - 3)], cols[dark & (cols > strip.max() + 3)]
    half = (OPEN / 2) / (TIP - CAM) * F                       # half the open gap, as the camera sees it at the fingertips
    if len(left) and len(right):
        u_fingers = (left.max() + right.min()) / 2
    elif len(left) or len(right):
        u_fingers = left.max() + half if len(left) else right.min() - half
    else:
        sys.exit("no finger in the close look")
    side = (u_strip - u_fingers) * (camera(q)[0][2] - zc) / F  # the strip's centre from midway between the fingers, along hand x
    off = float((tip(q)[:2] + fk(q)[1][:2, 0] * side - line(s_c)) @ n1)
    say(f"survey: the strip's centre is {1000 * off:+.1f} mm to the side of where the first look put it")
    # action 9: a high look over the ground between the track's lower end and the arm's base, for the basket
    end = line(s_end)
    spot = end - 0.13 * end / np.linalg.norm(end)
    lift = down_pose(tip(q)[:2], zc + 0.10, n1, q)
    qh = np.array(move(lift, down_pose(spot, 0.42 - TIP, n1, lift))["joints"])
    high = look()
    found = find_basket(high)
    if found is None:
        sys.exit("no box with blocks in it in the high look")
    (u0, u1, v0, v1), colour, edge, (fx, fy), room = found
    width_high, cam_high = u1 - u0, camera(qh)[0][2]
    basket0 = on_level(np.array([(u0 + u1) / 2]), np.array([(v0 + v1) / 2]), qh, 0.03)[0, :2]
    say(f"survey: a box with other colours inside near {np.round(basket0, 3)}; most open floor at {fx:.2f}, {fy:.2f} of its outline, room {room:.2f} of its width")
    # action 10: back to park
    reply = move(PARK)
    say(f"survey done, {reply['actions_left']} of 10 actions left")

    # ---- plan: grasp pose, and a watch pose chosen from geometry -----------------------------------------------------------
    zdir = np.array([-np.sin(TILT) * t1[0], -np.sin(TILT) * t1[1], -np.cos(TILT)])
    target = np.array([*line(s_c, off), zc + RISE])

    def seen(q, s_lo, s_hi):
        """How many of ten points along this stretch of the strip the camera would show from this joint setting."""
        cam, R = camera(q)
        count = 0
        for s_ in np.linspace(s_lo, s_hi, 10):
            v = R.T @ (np.array([*line(s_, off), S(s_) + 0.010]) - cam)
            count += bool(v[2] > 0.03 and abs(F * v[0] / v[2]) < 200 and abs(F * v[1] / v[2]) < 200)
        return count

    # watch pose: reachable from park in 0.85 s, and showing the most strip above the catch point on the way down
    steps = np.arange(-0.5, 0.51, 0.125)
    best = None
    for sign in (1, -1):
        R = frame([sign * n1[0], sign * n1[1], 0], zdir)
        g, ok = ik(target - zdir * TIP, R, PARK)
        up, ok2 = ik(target - zdir * TIP + np.array([0, 0, 0.10]), R, g)
        if not ok or not ok2 or (g <= LOW).any() or (g >= HIGH).any():
            continue
        for a1 in steps:
            for a2 in steps:
                for a4 in steps:
                    for a5 in steps:
                        for a6 in steps:
                            wq = PARK + np.array([a1, a2, 0, a4, a5, a6, 0])
                            far = seen(wq, s_c - 0.45, s_c - 0.10)
                            if far < 8:
                                continue
                            score = (far + seen((wq + g) / 2, s_c - 0.30, s_c - 0.03), -float(np.abs(g - wq).max()))
                            if best is None or score > best[0]:
                                best = (score, g, wq, up)
    if best is None:
        sys.exit("no watch pose shows the strip")
    _, G, Wq, UP = best
    due = 0.2 + (np.abs(Wq - PARK).max() + np.abs(G - Wq).max()) / SPEED
    say(f"plan: watch pose is park plus {np.round(Wq - PARK, 3)}, hand due at the grasp pose at {due:.2f} s")

    radius = [0.010]                                          # the part's radius: a first guess, replaced by what the sightings show

    def sight(rgb, q):
        """The part's place along the strip: whatever lies over the strip and is not the strip's colour."""
        vs, us = np.nonzero(other_pixels(rgb))
        if len(us) < 60:
            return None
        rad = float(np.median(radius))
        pts = on_level(us, vs, q, zc + rad)
        s_ = (pts[:, :2] - c1) @ t1
        pts[:, 2] = S(s_) + rad
        keep = (np.abs((pts[:, :2] - c1) @ n1 - off) < 0.03) & (s_ < s_end + 0.02)
        if keep.sum() < 60:
            return None
        us, vs = us[keep], vs[keep]
        if us.min() <= 1 or us.max() >= 478 or vs.min() <= 1 or vs.max() >= 478:
            return None                                       # cut by the edge of the picture: its middle cannot be trusted
        cam, R = camera(q)
        ray = R @ np.array([(us.mean() - 239.5) / F, (vs.mean() - 239.5) / F, 1.0])
        k = 0.3
        for _ in range(12):                                   # where the middle ray meets the height of the part's middle
            pt = cam + k * ray
            k += (S((pt[:2] - c1) @ t1) + rad - pt[2]) / ray[2]
        pt = cam + k * ray
        along = (on_level(us, vs, q, pt[2])[:, :2] - c1) @ t1
        steep = -ray[2] / np.linalg.norm(ray)                 # a roller seen from this steeply shows a length of 2 r / steep along the strip
        radius.append(float(np.clip((np.percentile(along, 98) - np.percentile(along, 2)) * steep / 2, 0.004, 0.025)))
        return float((pt[:2] - c1) @ t1)

    # ---- the try -------------------------------------------------------------------------------------------------------------
    state = robot("try")
    first = [{"at": 0.0, "joints": Wq.tolist(), "grip": OPEN}, {"at": 0.01, "joints": G.tolist()}]
    plan, sights, sent, t_arr, k = {}, [], False, None, 0
    while state["try"] == "running":
        k += 1
        t = int(round(state["time"] * 100))
        y = sight(look(), np.array(state["joints"]))
        if y is not None and (not sights or y > sights[-1][1] - 0.01):
            sights.append((t, y))
        near = [s_ for s_ in sights if s_[1] > s_c - 0.45][-FIT:]
        if len(near) >= 2 and not sent:
            v = np.polyfit([s_[0] for s_ in near], [s_[1] for s_ in near], 1)[0]
            if v > 0.0005:
                t_arr = near[-1][0] + (s_c - near[-1][1]) / v
        lo = 20 * k                                           # the step that carries out what is sent now starts at this tick
        if not sent and t_arr is not None and t_arr < lo + 20:
            at = int(round(max(t_arr, lo)))
            plan[at] = dict(plan.get(at, {}), grip=0.0)
            plan[at + 9] = dict(plan.get(at + 9, {}), joints=UP.tolist())
            sent = True
            say(f"try: {len(sights)} sightings so far, part's radius measured as {1000 * np.median(radius):.1f} mm, fingers to close at {at / 100:.2f} s")
        acts = first if k == 1 else [dict(plan[tk], at=round((tk - lo) / 100, 2)) for tk in sorted(plan) if lo <= tk < lo + 20]
        state = send("step", acts[:3]) if acts else robot("step")
    gap = robot("state")["finger_gap"]
    say(f"try over: sightings {[(s_[0] / 100, round(s_[1], 3)) for s_ in sights]}; finger gap now {gap:.3f}")
    holding = 0.015 < gap < 0.055
    say("the fingers are closed on something" if holding else "the fingers hold nothing")
    if STOP_AFTER_TRY:
        return
    if not holding:
        sys.exit("nothing in the hand: the job cannot be completed")
    # ---- deliver ---------------------------------------------------------------------------------------------------------------
    # look from above the basket: the held part hides the middle, the outline shows round it
    q = joints()
    here = tip(q)
    lift = down_pose(here[:2], 0.26, n1, q)
    qb = np.array(move(lift, down_pose(basket0, 0.20, n1, lift))["joints"])
    rgb = look().astype(int)
    like = (np.abs(rgb - colour).sum(2) < 60) | (np.abs(rgb - edge).sum(2) < 60)
    cols, rows = np.nonzero(like.sum(0) > 12)[0], np.nonzero(like.sum(1) > 12)[0]
    if len(cols) < 50 or len(rows) < 50:
        sys.exit("the basket is not under the hand")
    u0, u1, v0, v1 = cols.min(), cols.max(), rows.min(), rows.max()
    cam_low = camera(qb)[0][2]
    width_low = ((u1 - u0) + (v1 - v0)) / 2
    rim = float(np.clip((width_low * cam_low - width_high * cam_high) / (width_low - width_high), 0.02, 0.10))   # from its size at two heights
    size = width_low * (cam_low - rim) / F
    centre = on_level(np.array([(u0 + u1) / 2]), np.array([(v0 + v1) / 2]), qb, rim)[0, :2]
    Rb = fk(qb)[1]
    drop = centre + Rb[:2, 0] * (fx - 0.5) * size + Rb[:2, 1] * (fy - 0.5) * size
    say(f"deliver: basket centre {np.round(centre, 3)}, {size:.3f} across, rim at {rim:.3f}; letting go over {np.round(drop, 3)}")
    over = down_pose(drop, 0.20, n1, qb)
    reply = move(over, down_pose(drop, rim + 0.02, n1, over))
    if reply["blocked"]:
        say("deliver: the way down was blocked; letting go from where the hand stopped")
    robot("grip", str(OPEN))
    q = joints()
    reply = move(down_pose(tip(q)[:2], 0.26, n1, q), PARK)
    say(f"parked: joints {reply['joints']}, {reply['actions_left']} of 30 actions left")
    say("finish:", robot("finish"))


if __name__ == "__main__":
    main()
