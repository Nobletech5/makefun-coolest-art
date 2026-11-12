#!/usr/bin/env python3
"""coolest-art-01: "The Watching Eye".

A giant cosmic eye floating in deep space: a galaxy swirls in its iris,
thin orbit rings circle it, a small planet rides the outer ring, and a
tiny make.fun wordmark sits at the bottom. Drawn entirely in pure Python
stdlib (struct + zlib PNG writer, math, random). Deterministic: fixed
seed, no time, no network, no bundled image. Writes /output/entry.png
(or $MAKEFUN_OUTPUT_DIR/entry.png), 1024x1024 RGB.
"""

import math
import os
import random
import struct
import zlib

W = H = 1024
OUT_NAME = "entry.png"

# ---------------------------------------------------------------- palette
SPACE_TOP = (13, 8, 38)      # deep indigo
SPACE_BOT = (4, 3, 16)       # near black
SCLERA = (248, 247, 255)     # eye white
SCLERA_SHADE = (196, 190, 238)
PUPIL = (10, 6, 24)
GOLD = (255, 197, 61)
CYAN = (34, 211, 238)
MAGENTA = (255, 46, 136)
VIOLET = (123, 47, 247)
WHITE = (255, 255, 255)

EYE_CX, EYE_CY = 512, 470     # eye centre
EYE_D, EYE_R = 210, 430       # almond: two discs, centres +-D, radius R
IRIS_R = 150
PUPIL_R = 62


def clamp(v):
    return 0 if v < 0 else (255 if v > 255 else v)


class Canvas:
    """1024x1024 RGB image as a list of bytearray rows."""

    def __init__(self, w, h):
        self.w, self.h = w, h
        self.rows = [bytearray(w * 3) for _ in range(h)]

    def px(self, x, y, rgb):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = x * 3
            row = self.rows[y]
            row[i] = rgb[0]
            row[i + 1] = rgb[1]
            row[i + 2] = rgb[2]

    def blend_px(self, x, y, rgb, a):
        """Additive-ish alpha blend of rgb over the pixel at x, y."""
        if 0 <= x < self.w and 0 <= y < self.h and a > 0.0:
            i = x * 3
            row = self.rows[y]
            b = 1.0 - a
            row[i] = clamp(int(row[i] * b + rgb[0] * a))
            row[i + 1] = clamp(int(row[i + 1] * b + rgb[1] * a))
            row[i + 2] = clamp(int(row[i + 2] * b + rgb[2] * a))

    def fill_hspan(self, y, x0, x1, rgb):
        """Fill one row from x0 to x1 (inclusive) with a flat colour."""
        if 0 <= y < self.h:
            x0 = max(0, x0)
            x1 = min(self.w - 1, x1)
            if x0 <= x1:
                self.rows[y][x0 * 3:(x1 + 1) * 3] = bytes(rgb) * (x1 - x0 + 1)

    def glow_disc(self, cx, cy, r, rgb, strength):
        """Soft radial glow: alpha falls off as (1 - d^2/r^2)^2."""
        r2 = float(r * r)
        inv = 1.0 / r2
        y0, y1 = max(0, cy - r), min(self.h - 1, cy + r)
        for y in range(y0, y1 + 1):
            dy = y - cy
            dy2 = dy * dy
            if dy2 >= r2:
                continue
            dx_max = int(math.sqrt(r2 - dy2))
            x0, x1 = max(0, cx - dx_max), min(self.w - 1, cx + dx_max)
            for x in range(x0, x1 + 1):
                dx = x - cx
                t = 1.0 - (dx * dx + dy2) * inv
                if t <= 0.0:
                    continue
                self.blend_px(x, y, rgb, t * t * strength)


def background(cv):
    """Vertical deep-space gradient, indigo at top to near-black at bottom."""
    for y in range(H):
        t = y / (H - 1)
        r = int(SPACE_TOP[0] + (SPACE_BOT[0] - SPACE_TOP[0]) * t)
        g = int(SPACE_TOP[1] + (SPACE_BOT[1] - SPACE_TOP[1]) * t)
        b = int(SPACE_TOP[2] + (SPACE_BOT[2] - SPACE_TOP[2]) * t)
        cv.rows[y][:] = bytes((r, g, b)) * W


def stars(cv, rng):
    """Deterministic starfield: small dots plus a few bright sparkles."""
    for _ in range(380):
        x = rng.randrange(0, W)
        y = rng.randrange(0, H)
        v = rng.choice((200, 220, 240, 255))
        warm = rng.random() < 0.25
        col = (v, v, v) if not warm else (255, 230, 180)
        if rng.random() < 0.12:
            cv.px(x, y, col)
            cv.px(x + 1, y, col)
            cv.px(x, y + 1, col)
            cv.px(x + 1, y + 1, col)
        else:
            cv.px(x, y, col)
    for _ in range(16):
        x = rng.randrange(40, W - 40)
        y = rng.randrange(40, H - 40)
        arm = rng.randrange(4, 9)
        col = (255, 255, 255)
        for d in range(-arm, arm + 1):
            f = 1.0 - abs(d) / float(arm)
            cv.blend_px(x + d, y, col, f)
            cv.blend_px(x, y + d, col, f)


def almond_half_width(y):
    """Half-width of the vesica-piscis eye at row y (0 outside the eye)."""
    dy1 = y - (EYE_CY - EYE_D)
    dy2 = y - (EYE_CY + EYE_D)
    r2 = EYE_R * EYE_R
    if dy1 * dy1 > r2 or dy2 * dy2 > r2:
        return 0.0
    dx1 = math.sqrt(r2 - dy1 * dy1)
    dx2 = math.sqrt(r2 - dy2 * dy2)
    return min(dx1, dx2)


def inside_almond(x, y):
    """True when point (x, y) lies inside the eye shape."""
    dy1 = y - (EYE_CY - EYE_D)
    dy2 = y - (EYE_CY + EYE_D)
    r2 = EYE_R * EYE_R
    if dy1 * dy1 > r2 or dy2 * dy2 > r2:
        return False
    dx = x - EYE_CX
    return dx * dx <= (EYE_R * EYE_R - dy1 * dy1) and \
        dx * dx <= (EYE_R * EYE_R - dy2 * dy2)


def draw_eye(cv):
    """Sclera: almond fill, brighter at the top, shadowed toward the lid."""
    for y in range(EYE_CY - 220, EYE_CY + 221):
        hw = almond_half_width(y)
        if hw <= 0.0:
            continue
        t = (y - EYE_CY) / 220.0
        if t < 0:
            shade = 1.0 - 0.05 * (-t)
        else:
            shade = 1.0 - 0.30 * t
        rgb = tuple(clamp(int(SCLERA[i] * shade +
                              SCLERA_SHADE[i] * (1.0 - shade) * 0.35))
                    for i in range(3))
        x0 = int(EYE_CX - hw)
        x1 = int(EYE_CX + hw)
        cv.fill_hspan(y, x0, x1, rgb)


def iris_colour(r, ang):
    """Galaxy iris: concentric colour bands twisted into spiral arms."""
    arms = 0.5 + 0.5 * math.sin(ang * 3.0 + r * 0.12)
    arms = arms * arms  # sharpen the arms so the swirl reads clearly
    if r < PUPIL_R:
        return PUPIL
    if r < 80:
        base = (245, 158, 11)      # gold inner ring
        k = 0.80 + 0.45 * arms
    elif r < 108:
        base = (236, 72, 153)      # magenta
        k = 0.60 + 0.70 * arms
    elif r < 132:
        base = (124, 58, 237)      # violet
        k = 0.60 + 0.70 * arms
    else:
        base = (34, 211, 238)      # cyan rim
        k = 0.90 + 0.10 * arms
    # thin dark separators between the bands sharpen the galaxy rings
    for edge in (80.0, 108.0, 132.0):
        if abs(r - edge) < 2.0:
            k *= 0.65
    return tuple(clamp(int(c * k)) for c in base)


def draw_iris(cv):
    """Spiral galaxy iris, dark pupil, crisp specular highlights."""
    for y in range(EYE_CY - IRIS_R, EYE_CY + IRIS_R + 1):
        dy = y - EYE_CY
        for x in range(EYE_CX - IRIS_R, EYE_CX + IRIS_R + 1):
            dx = x - EYE_CX
            r2 = dx * dx + dy * dy
            if r2 > IRIS_R * IRIS_R:
                continue
            r = math.sqrt(r2)
            ang = math.atan2(dy, dx)
            cv.px(x, y, iris_colour(r, ang))
    # specular highlights on the pupil
    cv.glow_disc(EYE_CX - 52, EYE_CY - 58, 26, WHITE, 0.95)
    cv.glow_disc(EYE_CX + 34, EYE_CY + 38, 10, WHITE, 0.9)


def draw_rings(cv):
    """Two tilted orbit rings that pass behind the eye (skipped inside it)."""
    for (rx, ry, col, thick) in ((455, 150, GOLD, 3), (495, 190, CYAN, 2)):
        rot = math.radians(-18.0)
        cr, sr = math.cos(rot), math.sin(rot)
        steps = 1800
        for i in range(steps + 1):
            t = 2.0 * math.pi * i / steps
            ex, ey = rx * math.cos(t), ry * math.sin(t)
            x = int(EYE_CX + ex * cr - ey * sr)
            y = int(EYE_CY + ex * sr + ey * cr)
            if inside_almond(x, y):
                continue
            for d in range(-(thick // 2), thick // 2 + 1):
                cv.blend_px(x + d, y, col, 0.9)
                cv.blend_px(x, y + d, col, 0.9)


def draw_planet(cv):
    """Small ringed planet riding the outer orbit ring, upper right."""
    px, py, pr = 848, 318, 20
    cv.glow_disc(px, py, pr + 14, (45, 212, 191), 0.25)
    for y in range(py - pr, py + pr + 1):
        dy = y - py
        dx = int(math.sqrt(max(0, pr * pr - dy * dy)))
        shade = 1.0 - 0.35 * (dy / float(pr))
        rgb = tuple(clamp(int(c * shade)) for c in (45, 212, 191))
        cv.fill_hspan(y, px - dx, px + dx, rgb)
    cv.glow_disc(px - 7, py - 7, 7, (190, 255, 248), 0.8)
    for i in range(361):
        t = math.radians(i)
        x = int(px + 34 * math.cos(t))
        y = int(py + 10 * math.sin(t))
        cv.blend_px(x, y, GOLD, 0.85)


# 5x7 pixel font for the wordmark "MAKE.FUN" (capitals, clean and bold)
GLYPHS = {
    "M": ["10001", "11011", "10101", "10101", "10001", "10001", "10001"],
    "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    "K": ["10001", "10010", "10100", "11000", "10100", "10010", "10001"],
    "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    ".": ["00000", "00000", "00000", "00000", "00000", "01100", "01100"],
    "F": ["11111", "10000", "10000", "11110", "10000", "10000", "10000"],
    "U": ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
    "N": ["10001", "11001", "10101", "10011", "10001", "10001", "10001"],
}


def draw_wordmark(cv, text, cy, scale, rgb):
    """Centre `text` horizontally at vertical centre cy, in the pixel font."""
    cw, ch = 5 * scale, 7 * scale
    gap = scale
    total = len(text) * (cw + gap) - gap
    x0 = (W - total) // 2
    y0 = cy - ch // 2
    for ci, ch in enumerate(text):
        glyph = GLYPHS[ch]
        ox = x0 + ci * (cw + gap)
        for row in range(7):
            for col in range(5):
                if glyph[row][col] == "1":
                    for dy in range(scale):
                        for dx in range(scale):
                            cv.px(ox + col * scale + dx,
                                  y0 + row * scale + dy, rgb)


def _chunk(tag, data):
    return (struct.pack(">I", len(data)) + tag + data +
            struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))


def write_png(path, cv):
    raw = b"".join(b"\x00" + bytes(row) for row in cv.rows)
    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    png = (b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr) +
           _chunk(b"IDAT", zlib.compress(raw, 9)) + _chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


def main():
    rng = random.Random(20261112)
    cv = Canvas(W, H)
    background(cv)
    # nebula clouds, soft and behind the stars
    cv.glow_disc(300, 300, 260, VIOLET, 0.50)
    cv.glow_disc(760, 240, 200, CYAN, 0.42)
    cv.glow_disc(700, 800, 280, MAGENTA, 0.38)
    cv.glow_disc(240, 820, 220, GOLD, 0.30)
    stars(cv, rng)
    # halo behind the eye, then the eye itself
    cv.glow_disc(EYE_CX, EYE_CY, 400, (139, 92, 246), 0.45)
    draw_eye(cv)
    draw_iris(cv)
    draw_rings(cv)
    draw_planet(cv)
    draw_wordmark(cv, "MAKE.FUN", 948, 4, (248, 247, 255))
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, OUT_NAME)
    size = write_png(path, cv)
    print("wrote %s (%d bytes)" % (path, size))


if __name__ == "__main__":
    main()
