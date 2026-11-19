"""What makes the robot's senses imperfect: the camera's mount, its lens and its noise, and the zero of each joint reading.

Every limit here is stated in the manual. The errors are fixed for a cell, except the picture noise, which differs from picture to picture.
"""
import math
import random

import numpy as np

MOUNT_SHIFT = 0.003               # the camera sits within this distance of where the manual says, metres
MOUNT_TURN = math.radians(1.5)    # and is turned by no more than this from the stated direction
LENS = 0.02                       # a point's image is displaced along its radius by up to this fraction, most at the corners
NOISE = 0.016                     # standard deviation of the picture noise, as a fraction of full scale
FLICKER = 0.03                    # the brightness of a picture varies by up to this fraction
JOINT_ZERO = 0.003                # each joint reading is off by a fixed amount of up to this, radians
READING = 3                       # decimal places of the joint and finger readings


def draw(seed):
    """The fixed errors of one cell."""
    rng = random.Random(f"{seed}-senses")
    v = [rng.gauss(0, 1) for _ in range(3)]
    n = math.sqrt(sum(x * x for x in v))
    shift = [x / n * MOUNT_SHIFT * rng.uniform(0.5, 1.0) for x in v]
    a = [rng.gauss(0, 1) for _ in range(3)]
    n = math.sqrt(sum(x * x for x in a))
    turn = [x / n * MOUNT_TURN * rng.uniform(0.5, 1.0) for x in a]          # axis times angle
    lens = rng.choice((-1, 1)) * LENS * rng.uniform(0.5, 1.0)
    zero = [rng.uniform(-JOINT_ZERO, JOINT_ZERO) for _ in range(7)]
    return {"camera_shift": shift, "camera_turn": turn, "lens": lens, "joint_zero": zero}


def turned(turn, v):
    """Vector v turned by the small rotation `turn` (axis times angle)."""
    t = np.array(turn, dtype=float)
    angle = float(np.linalg.norm(t))
    if angle < 1e-12:
        return np.array(v, dtype=float)
    k = t / angle
    v = np.array(v, dtype=float)
    return v * math.cos(angle) + np.cross(k, v) * math.sin(angle) + k * (k @ v) * (1 - math.cos(angle))


def through_lens(rgb, lens):
    """The picture as the lens gives it: each point moved along its radius by the fraction lens * (r / r_corner)^2."""
    h, w, _ = rgb.shape
    cy, cx = (h - 1) / 2, (w - 1) / 2
    ys, xs = np.mgrid[0:h, 0:w].astype(float)
    dx, dy = xs - cx, ys - cy
    r2 = (dx * dx + dy * dy) / (cx * cx + cy * cy)
    sx = np.clip(cx + dx * (1 - lens * r2), 0, w - 1)
    sy = np.clip(cy + dy * (1 - lens * r2), 0, h - 1)
    x0, y0 = np.floor(sx).astype(int), np.floor(sy).astype(int)
    x1, y1 = np.minimum(x0 + 1, w - 1), np.minimum(y0 + 1, h - 1)
    fx, fy = (sx - x0)[..., None], (sy - y0)[..., None]
    img = rgb.astype(float)
    return (img[y0, x0] * (1 - fx) * (1 - fy) + img[y0, x1] * fx * (1 - fy) + img[y1, x0] * (1 - fx) * fy + img[y1, x1] * fx * fy)


def picture(rgb, lens, seed, count):
    """One picture as the camera delivers it: through the lens, with this picture's brightness and noise."""
    rng = np.random.default_rng([abs(int(seed)), int(count)])
    img = through_lens(rgb, lens) * (1 + rng.uniform(-FLICKER, FLICKER))
    img = img + rng.normal(0, NOISE * 255, img.shape)
    return np.clip(np.rint(img), 0, 255).astype(np.uint8)
