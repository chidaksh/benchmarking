"""Builds the catch cell: a seven-joint arm, a sloped roller track with a step, a feeder, a reject tray and a basket.

`build(seed)` returns the MuJoCo scene as text and the facts only the robot's record and the verifier may see.
Lengths are metres, angles radians. Nothing but gravity moves a part down the track.
"""
import math
import random

import sensing

# arm (the same arm as the kitting cell)
SHOULDER_Z = 0.20
UPPER = 0.30
FOREARM = 0.30
WRIST_TO_PALM = 0.10
LIMITS = [(-2.9, 2.9), (-2.0, 2.0), (-2.9, 2.9), (-2.4, 2.4), (-2.9, 2.9), (-2.0, 2.0), (-2.9, 2.9)]
PARK = [0.0, 0.0, 0.0, 1.5708, 0.0, 1.5708, 0.0]
PARK_TOLERANCE = 0.02                 # radians each joint may be from the park pose and still count as parked
PARK_GAP = 0.055                      # smallest finger gap that counts as open
GAINS = [(3000, 100, 60)] * 4 + [(600, 20, 15)] * 3     # stiffness, damping and largest torque of each joint drive
OPEN = 0.060
FINGER = (0.008, 0.024, 0.060)       # thickness along hand x, width along hand y, length along hand z
PALM = (0.060, 0.040, 0.020)
TIP_FROM_PALM = PALM[2] / 2 + FINGER[2]
GRIP_FORCE = 15.0
# the part: a roller that lies across the track
ROLLER_RADIUS = 0.012
ROLLER_LENGTH = 0.040
TRIES = 1                             # one try: one part is released, once
# track
SHAPE = "roller"                      # the part: a roller lying across the track, or a ball
LANES = {"roller": 0.044, "ball": 0.030}   # clear width between the rails
RAIL = (0.006, 0.006)                 # thickness and height of a rail
FLOOR_THICK = 0.006
STEP = 0.005                          # height of the step part-way down
TRACK_ABOVE = 0.070                   # height of the track's surface at its lower end
SLOPE_DEGREES = (2.2, 2.6)            # steep enough that the part is quick, shallow enough that the arm can arrive from park
TRACK_UP = 0.62                       # how far the top of the track is up the slope from the middle of the cell
PUSH = (0.05, 0.15)                   # speed a part is released at, metres a second
SLIP = 0.05                           # friction of the track floor, the rails and the roller
# basket
BASKET_INNER = (0.12, 0.12)
BASKET_WALL = 0.006
BASKET_HEIGHT = 0.050
BASKET_FLOOR = 0.004
BLOCK = (0.024, 0.024, 0.050)
# overview camera: not served to the agent, kept for our own viewing tools
VIEW_POS = (0.95, 0.0, 0.55)
VIEW_AT = (0.32, 0.0, 0.03)
VIEW_FOVY = 50


def box(name, pos, half, rgba, extra=""):
    alpha = rgba[3] if len(rgba) > 3 else 1
    return (f'<geom name="{name}" type="box" pos="{pos[0]:.5f} {pos[1]:.5f} {pos[2]:.5f}" '
            f'size="{half[0]:.5f} {half[1]:.5f} {half[2]:.5f}" rgba="{rgba[0]} {rgba[1]} {rgba[2]} {alpha}" {extra}/>')


PAINT = 'contype="0" conaffinity="0" mass="0"'    # a painted mark: seen by the cameras, touched by nothing, weighs nothing


def capsule(name, length, radius, mass, rgba="0.80 0.80 0.84 1"):
    return f'<geom name="{name}" type="capsule" fromto="0 0 0 0 0 {length}" size="{radius}" mass="{mass}" rgba="{rgba}"/>'


def joint(n, axis):
    lo, hi = LIMITS[n - 1]
    return f'<joint name="j{n}" axis="{axis}" range="{lo} {hi}" armature="0.1" damping="0.5"/>'


def arm(senses):
    fx0 = OPEN / 2 + FINGER[0] / 2
    fz = PALM[2] / 2 + FINGER[2] / 2
    finger = (FINGER[0] / 2, FINGER[1] / 2, FINGER[2] / 2)
    blue = (0.15, 0.15, 0.60)
    return [
        '<geom name="pedestal" type="cylinder" fromto="0 0 0 0 0 0.12" size="0.05" rgba="0.3 0.3 0.33 1"/>',
        '<body name="link1" gravcomp="1">', joint(1, "0 0 1"),
        f'<geom name="arm_shoulder" type="sphere" pos="0 0 {SHOULDER_Z}" size="0.055" mass="2" rgba="0.80 0.80 0.84 1"/>',
        f'<body name="link2" pos="0 0 {SHOULDER_Z}" gravcomp="1">', joint(2, "0 1 0"), capsule("arm_upper_a", UPPER / 2, 0.040, 1.5),
        f'<body name="link3" pos="0 0 {UPPER / 2}" gravcomp="1">', joint(3, "0 0 1"), capsule("arm_upper_b", UPPER / 2, 0.040, 1.5),
        f'<body name="link4" pos="0 0 {UPPER / 2}" gravcomp="1">', joint(4, "0 1 0"), capsule("arm_fore_a", FOREARM / 2, 0.033, 1.0),
        f'<body name="link5" pos="0 0 {FOREARM / 2}" gravcomp="1">', joint(5, "0 0 1"), capsule("arm_fore_b", FOREARM / 2, 0.033, 1.0),
        f'<body name="link6" pos="0 0 {FOREARM / 2}" gravcomp="1">', joint(6, "0 1 0"), capsule("arm_wrist", 0.06, 0.028, 0.5),
        f'<body name="hand" pos="0 0 {WRIST_TO_PALM}" gravcomp="1">', joint(7, "0 0 1"),
        box("palm", (0, 0, 0), (PALM[0] / 2, PALM[1] / 2, PALM[2] / 2), (0.20, 0.20, 0.24), 'mass="0.4"'),
        '<camera name="wrist" pos="{:.6f} {:.6f} {:.6f}" xyaxes="{:.7f} {:.7f} {:.7f} {:.7f} {:.7f} {:.7f}" fovy="60"/>'.format(
            *[c + s for c, s in zip((0, 0, PALM[2] / 2 + 0.001), senses["camera_shift"])],
            *sensing.turned(senses["camera_turn"], (1, 0, 0)), *sensing.turned(senses["camera_turn"], (0, -1, 0))),
        f'<body name="finger_right" pos="{fx0:.4f} 0 {fz:.4f}" gravcomp="1"><joint name="finger_right" type="slide" axis="1 0 0" range="{-OPEN / 2:.4f} 0"/>',
        box("finger_right", (0, 0, 0), finger, blue, 'mass="0.05" friction="1.5 0.005 0.0001"'), '</body>',
        f'<body name="finger_left" pos="{-fx0:.4f} 0 {fz:.4f}" gravcomp="1"><joint name="finger_left" type="slide" axis="1 0 0" range="0 {OPEN / 2:.4f}"/>',
        box("finger_left", (0, 0, 0), finger, blue, 'mass="0.05" friction="1.5 0.005 0.0001"'), '</body>',
        '</body></body></body></body></body></body></body>']


def actuators():
    out = ['<actuator>']
    for n, (kp, kv, top) in enumerate(GAINS, 1):
        lo, hi = LIMITS[n - 1]
        out.append(f'<position name="j{n}" joint="j{n}" kp="{kp}" kv="{kv}" ctrlrange="{lo} {hi}" forcerange="-{top} {top}"/>')
    out.append(f'<position name="finger_right" joint="finger_right" kp="600" kv="20" ctrlrange="{-OPEN / 2:.4f} 0" forcerange="-{GRIP_FORCE} {GRIP_FORCE}"/>')
    out.append(f'<position name="finger_left" joint="finger_left" kp="600" kv="20" ctrlrange="0 {OPEN / 2:.4f}" forcerange="-{GRIP_FORCE} {GRIP_FORCE}"/>')
    out.append('</actuator>')
    return out


def tilted(name, top_mid, half, theta, rgba, extra="", local=(0.0, 0.0, 0.0)):
    """A box whose long side runs down the slope. `top_mid` is a point on the track surface; `local` is the box centre
    measured from it across the track, down the slope and out of the surface."""
    x, s, n = local
    c, sn = math.cos(theta), math.sin(theta)
    pos = (top_mid[0] + x, top_mid[1] + s * c + n * sn, top_mid[2] - s * sn + n * c)
    alpha = rgba[3] if len(rgba) > 3 else 1
    return (f'<geom name="{name}" type="box" pos="{pos[0]:.5f} {pos[1]:.5f} {pos[2]:.5f}" euler="{-theta:.6f} 0 0" '
            f'size="{half[0]:.5f} {half[1]:.5f} {half[2]:.5f}" rgba="{rgba[0]} {rgba[1]} {rgba[2]} {alpha}" {extra}/>')


def view_axes():
    f = [VIEW_AT[i] - VIEW_POS[i] for i in range(3)]
    n = math.sqrt(sum(v * v for v in f))
    f = [v / n for v in f]
    return (0.0, 1.0, 0.0), (f[2], 0.0, -f[0])


def build(seed, shape=None):
    shape = shape or SHAPE
    LANE = LANES[shape]
    rng = random.Random(seed)
    tx = rng.uniform(0.40, 0.44)                       # the track runs along y at this x, downhill toward +y
    y0 = rng.uniform(-0.02, 0.02)
    theta = math.radians(rng.uniform(*SLOPE_DEGREES))
    y_top, y_end = y0 - TRACK_UP, y0 + 0.28
    y_step = y0 + rng.uniform(-0.13, -0.07)
    basket = (rng.uniform(0.19, 0.23), rng.uniform(0.32, 0.36))
    grams = [rng.randint(80, 140) for _ in range(TRIES)]
    tries = [{"speed": rng.uniform(*PUSH), "offset": rng.uniform(-0.001, 0.001), "yaw": rng.uniform(-0.05, 0.05)} for _ in range(TRIES)]
    t = math.tan(theta)
    z_step_low = TRACK_ABOVE + (y_end - y_step) * t    # surface of the lower part just below the step
    z_step_high = z_step_low + STEP

    def surface(y):
        """Height of the track surface under a point at y."""
        return z_step_high + (y_step - y) * t if y < y_step else z_step_low - (y - y_step) * t

    slip = f'friction="{SLIP} 0.005 0.0001"'
    floor_rgb, rail_rgb, steel = (0.55, 0.75, 0.90), (0.30, 0.45, 0.65), (0.45, 0.45, 0.48)
    out = ['<mujoco model="catch_cell">',
           '<compiler angle="radian"/>',
           '<option timestep="0.002" cone="elliptic" impratio="10" integrator="implicitfast" noslip_iterations="5"/>',
           '<visual><global offwidth="640" offheight="480"/><headlight ambient="0.45 0.45 0.45" diffuse="0.5 0.5 0.5" specular="0 0 0"/></visual>',
           '<default><geom solref="0.004 1" condim="4"/></default>',
           '<worldbody>',
           '<geom name="table" type="plane" size="0.9 0.9 0.1" rgba="0.82 0.82 0.80 1" friction="0.8 0.005 0.0001"/>']
    senses = sensing.draw(seed)
    out += arm(senses)
    # track: an upper and a lower part with a step between them, each a floor and two low rails
    for name, a, b in (("upper", y_top, y_step), ("lower", y_step, y_end)):
        mid = (tx, (a + b) / 2, surface((a + b) / 2) if name == "upper" else z_step_low - ((a + b) / 2 - y_step) * t)
        half = (b - a) / 2 / math.cos(theta)
        out.append(tilted(f"track_{name}_floor", mid, (LANE / 2 + RAIL[0], half, FLOOR_THICK / 2), theta, floor_rgb, slip, (0, 0, -FLOOR_THICK / 2)))
        for side, sign in (("a", -1), ("b", 1)):
            out.append(tilted(f"track_{name}_rail_{side}", mid, (RAIL[0] / 2, half, RAIL[1] / 2), theta, rail_rgb, slip,
                              (sign * (LANE / 2 + RAIL[0] / 2), 0, RAIL[1] / 2)))
    for i, y in enumerate((y_top + 0.04, y_step - 0.02, y_end - 0.04)):
        h = surface(y) - FLOOR_THICK - 0.001
        out.append(box(f"post{i}", (tx, y, h / 2), (0.018, 0.010, h / 2), steel))
    # feeder: a covered box over the top of the track; a part comes out of it at each try
    cover, wall = 0.085, 0.004
    mid = (tx, y_top + cover / 2, surface(y_top + cover / 2))
    dark = (0.20, 0.20, 0.23)
    half = cover / 2 / math.cos(theta)
    for side, sign in (("a", -1), ("b", 1)):
        out.append(tilted(f"feeder_wall_{side}", mid, (wall / 2, half, 0.020), theta, dark, "", (sign * (LANE / 2 + RAIL[0] + wall / 2), 0, 0.020)))
    out.append(tilted("feeder_roof", mid, (LANE / 2 + RAIL[0] + wall, half, wall / 2), theta, dark, "", (0, 0, 0.040 + wall / 2)))
    out.append(tilted("feeder_back", mid, (LANE / 2 + RAIL[0] + wall, wall / 2, 0.022), theta, dark, "", (0, -half - wall / 2, 0.022)))
    # magazine: a closed box behind the feeder where the parts wait, out of sight and out of reach
    mag = (tx, y_top - 0.075)
    pocket = 2 * ROLLER_RADIUS + 0.003
    out.append(box("magazine_roof", (mag[0], mag[1], 0.034), (0.034, pocket * TRIES / 2 + 0.008, 0.003), dark))
    for side, sign in (("a", -1), ("b", 1)):
        out.append(box(f"magazine_wall_{side}", (mag[0] + sign * 0.031, mag[1], 0.0155), (0.003, pocket * TRIES / 2 + 0.008, 0.0155), dark))
    for k in range(TRIES + 1):
        out.append(box(f"magazine_div{k}", (mag[0], mag[1] + (k - TRIES / 2) * pocket, 0.0155), (0.028, 0.0012, 0.0155), dark))
    rest = [(mag[0], mag[1] + (k - TRIES / 2 + 0.5) * pocket, ROLLER_RADIUS + 0.0005) for k in range(TRIES)]
    red = (0.90, 0.30, 0.10)
    for k in range(TRIES):
        x, y, z = rest[k]
        out.append("".join([
            f'<body name="part{k}" pos="{x:.5f} {y:.5f} {z:.5f}" quat="0.7071068 0 0.7071068 0"><freejoint/>',
            (f'<geom name="part{k}" type="cylinder" size="{ROLLER_RADIUS} {ROLLER_LENGTH / 2}" mass="{grams[k] / 1000}" rgba="{red[0]} {red[1]} {red[2]} 1" {slip}/>'
             if shape == "roller" else
             f'<geom name="part{k}" type="sphere" size="{ROLLER_RADIUS}" mass="{grams[k] / 1000}" rgba="{red[0]} {red[1]} {red[2]} 1" {slip}/>'),
            # white marks, so the part's turning can be seen
            (f'<geom name="part{k}_line" type="box" pos="{ROLLER_RADIUS:.4f} 0 0" size="0.0004 0.003 {ROLLER_LENGTH / 2 - 0.002:.4f}" rgba="0.97 0.97 0.97 1" {PAINT}/>'
             if shape == "roller" else
             f'<geom name="part{k}_line" type="cylinder" pos="{ROLLER_RADIUS:.4f} 0 0" euler="0 1.5708 0" size="0.004 0.0003" rgba="0.97 0.97 0.97 1" {PAINT}/>'),
            f'<geom name="part{k}_dot_a" type="cylinder" pos="0.006 0 {(ROLLER_LENGTH / 2 if shape == "roller" else ROLLER_RADIUS * 0.866) + 0.0002:.4f}" size="0.003 0.0003" rgba="0.97 0.97 0.97 1" {PAINT}/>',
            f'<geom name="part{k}_dot_b" type="cylinder" pos="0.006 0 {-(ROLLER_LENGTH / 2 if shape == "roller" else ROLLER_RADIUS * 0.866) - 0.0002:.4f}" size="0.003 0.0003" rgba="0.97 0.97 0.97 1" {PAINT}/>',
            '</body>']))
    # reject tray: where a part that was not caught ends up
    ty = y_end + 0.075
    out.append(box("reject_floor", (tx, ty, 0.002), (0.066, 0.076, 0.002), (0.35, 0.20, 0.20)))
    for name, c, h in (("xm", (tx - 0.063, ty), (0.003, 0.076)), ("xp", (tx + 0.063, ty), (0.003, 0.076)), ("yp", (tx, ty + 0.073), (0.060, 0.003))):
        out.append(box(f"reject_wall_{name}", (c[0], c[1], 0.022), (h[0], h[1], 0.022), (0.35, 0.20, 0.20)))
    # basket with three blocks already in it
    bx, by = basket
    hx, hy = BASKET_INNER[0] / 2, BASKET_INNER[1] / 2
    wood = (0.60, 0.45, 0.28)
    out.append(box("basket_floor", (bx, by, BASKET_FLOOR / 2), (hx + BASKET_WALL, hy + BASKET_WALL, BASKET_FLOOR / 2), wood))
    for name, c, h in (("xm", (bx - hx - BASKET_WALL / 2, by), (BASKET_WALL / 2, hy + BASKET_WALL)), ("xp", (bx + hx + BASKET_WALL / 2, by), (BASKET_WALL / 2, hy + BASKET_WALL)),
                       ("ym", (bx, by - hy - BASKET_WALL / 2), (hx, BASKET_WALL / 2)), ("yp", (bx, by + hy + BASKET_WALL / 2), (hx, BASKET_WALL / 2))):
        out.append(box(f"basket_wall_{name}", (c[0], c[1], BASKET_HEIGHT / 2), (h[0], h[1], BASKET_HEIGHT / 2), wood))
    paints = [(0.95, 0.50, 0.10), (0.10, 0.60, 0.60), (0.55, 0.25, 0.75)]
    lay = [((-0.032, -0.030, BLOCK[2] / 2), "1 0 0 0"), ((0.030, -0.020, BLOCK[0] / 2), "0.7071068 0.7071068 0 0"), ((-0.005, 0.038, BLOCK[0] / 2), "0.7071068 0 0.7071068 0")]
    for i, ((dx, dy, dz), quat) in enumerate(lay):
        out.append(f'<body name="block{i}" pos="{bx + dx + rng.uniform(-0.004, 0.004):.5f} {by + dy + rng.uniform(-0.004, 0.004):.5f} {BASKET_FLOOR + dz + 0.001:.5f}" quat="{quat}"><freejoint/>'
                   + box(f"block{i}", (0, 0, 0), (BLOCK[0] / 2, BLOCK[1] / 2, BLOCK[2] / 2), paints[i], f'mass="{rng.randint(60, 160) / 1000}" friction="0.8 0.005 0.0001"') + '</body>')
    right, up = view_axes()
    out += [f'<camera name="overview" pos="{VIEW_POS[0]} {VIEW_POS[1]} {VIEW_POS[2]}" '
            f'xyaxes="{right[0]} {right[1]} {right[2]} {up[0]:.6f} {up[1]:.6f} {up[2]:.6f}" fovy="{VIEW_FOVY}"/>',
            '</worldbody>',
            '<contact><exclude body1="finger_left" body2="finger_right"/></contact>']
    out += actuators()
    out.append('</mujoco>')
    release_y = y_top + 0.040
    facts = {"seed": seed, "track_x": tx, "y_top": y_top, "y_step": y_step, "y_end": y_end, "slope": theta, "step": STEP,
             "z_step_high": z_step_high, "z_step_low": z_step_low, "release": [tx, release_y, surface(release_y) + ROLLER_RADIUS + 0.0005],
             "tries": tries, "grams": grams, "basket": basket, "rest": rest, "shape": shape, "lane": LANE, "senses": senses}
    return "\n".join(out), facts


def surface(facts, y):
    """Height of the track surface under a point at y, from the facts."""
    t = math.tan(facts["slope"])
    return facts["z_step_high"] + (facts["y_step"] - y) * t if y < facts["y_step"] else facts["z_step_low"] - (y - facts["y_step"]) * t
