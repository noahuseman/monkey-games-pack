#!/usr/bin/env python3
"""
Paints the texture atlases for the four fishing catches worn on the head.

The head slot is the one place a resource pack can put real geometry on a
player. An item equipped to the head with NO equipment asset is drawn as its
own model, which is why a carved pumpkin looks like a pumpkin and not like a
pumpkin-coloured helmet - there is no `carved_pumpkin.json` in vanilla's
equipment folder at all. These four take the same road: a `head` case in the
item definition points at a box model, and that model is what sits on the
player.

Model space for a worn item is one whole block, 0-16 on every axis, with the
player's head occupying 4-12 and facing -Z. So anything from 4 to 12 hugs the
head and anything outside that is overhang.

The atlases are 64x64 with 16x16 tiles, addressed by (column, row). A model's
`uv` is always in a 0-16 space stretched over the whole image, so a tile at
column c, row r is uv [c*4, r*4, c*4+4, r*4+4].

Usage:  python wearable_worn.py <pack-root>
"""

import os
import sys
import math
import random

from PIL import Image

TILE = 16
SHEET = 64


def sheet():
    return Image.new("RGBA", (SHEET, SHEET), (0, 0, 0, 0))


def put(im, x, y, c):
    if 0 <= x < im.size[0] and 0 <= y < im.size[1]:
        im.putpixel((int(x), int(y)), c)


def over(im, x, y, c):
    if not (0 <= x < im.size[0] and 0 <= y < im.size[1]):
        return
    x, y = int(x), int(y)
    r, g, b, a = c
    if a >= 255:
        im.putpixel((x, y), c)
        return
    br, bg, bb, ba = im.getpixel((x, y))
    f = a / 255.0
    im.putpixel((x, y), (round(r * f + br * (1 - f)),
                         round(g * f + bg * (1 - f)),
                         round(b * f + bb * (1 - f)),
                         max(ba, a)))


def mix(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(4))


def shade(c, f):
    return (max(0, min(255, round(c[0] * f))),
            max(0, min(255, round(c[1] * f))),
            max(0, min(255, round(c[2] * f))), c[3])


class Tile:
    """A 16x16 window onto the atlas, with its own local coordinates."""

    def __init__(self, im, col, row):
        self.im = im
        self.ox = col * TILE
        self.oy = row * TILE

    def set(self, x, y, c):
        if 0 <= x < TILE and 0 <= y < TILE:
            put(self.im, self.ox + x, self.oy + y, c)

    def blend(self, x, y, c):
        if 0 <= x < TILE and 0 <= y < TILE:
            over(self.im, self.ox + x, self.oy + y, c)

    def get(self, x, y):
        if 0 <= x < TILE and 0 <= y < TILE:
            return self.im.getpixel((self.ox + x, self.oy + y))
        return (0, 0, 0, 0)

    def fill(self, c):
        for y in range(TILE):
            for x in range(TILE):
                self.set(x, y, c)

    def rect(self, x0, y0, x1, y1, c):
        for y in range(int(y0), int(y1) + 1):
            for x in range(int(x0), int(x1) + 1):
                self.set(x, y, c)

    def vgrad(self, top, bottom):
        for y in range(TILE):
            c = mix(top, bottom, y / (TILE - 1.0))
            for x in range(TILE):
                self.set(x, y, c)

    def radial(self, inner, outer, cx=7.5, cy=7.5, power=1.0):
        mx = math.hypot(cx, cy)
        for y in range(TILE):
            for x in range(TILE):
                t = (math.hypot(x - cx, y - cy) / mx) ** power
                self.set(x, y, mix(inner, outer, t))

    def disc(self, cx, cy, r, c):
        for y in range(TILE):
            for x in range(TILE):
                if math.hypot(x - cx, y - cy) <= r:
                    self.set(x, y, c)

    def ring(self, cx, cy, r0, r1, c):
        for y in range(TILE):
            for x in range(TILE):
                d = math.hypot(x - cx, y - cy)
                if r0 <= d <= r1:
                    self.set(x, y, c)

    def border(self, c, w=1):
        for y in range(TILE):
            for x in range(TILE):
                if x < w or y < w or x >= TILE - w or y >= TILE - w:
                    self.set(x, y, c)

    def speckle(self, rng, c, chance, alpha=255):
        for y in range(TILE):
            for x in range(TILE):
                if self.get(x, y)[3] and rng.random() < chance:
                    self.blend(x, y, (c[0], c[1], c[2], alpha))


def crack(t, rng, c, x, y, steps, bias=(0, 1)):
    """A branching fracture, walked rather than drawn, so it looks split."""
    for _ in range(steps):
        t.blend(int(x), int(y), c)
        if rng.random() < 0.22:
            t.blend(int(x) + 1, int(y), (c[0], c[1], c[2], 110))
        x += bias[0] + rng.uniform(-0.8, 0.8)
        y += bias[1] + rng.uniform(-0.6, 0.6)
        if not (0 <= x < TILE and 0 <= y < TILE):
            return


# ======================================================= deep-sea diving helmet
#
# Copper gone slightly green, because it was on the bottom of a lake. The
# detail that makes it is the bolt ring around the porthole: it is the one
# thing everybody associates with a diving helmet, so it gets the crispest
# pixels on the sheet.

def diving_helmet():
    im = sheet()
    rng = random.Random(0xD1E5)

    brass = (176, 125, 58, 255)
    brass_l = (217, 168, 92, 255)
    brass_ll = (240, 205, 140, 255)
    brass_d = (122, 84, 36, 255)
    brass_dd = (78, 53, 20, 255)
    patina = (78, 138, 107, 255)
    bolt = (201, 194, 168, 255)
    bolt_d = (124, 118, 96, 255)
    glass = (22, 65, 79, 255)
    glass_m = (42, 109, 128, 255)
    glass_l = (159, 224, 232, 255)
    rubber = (58, 58, 62, 255)
    rubber_d = (34, 34, 38, 255)

    def weather(t, heavy=False):
        """Verdigris blotches and scratches - what the lake did to it."""
        for _ in range(5 if heavy else 3):
            cx, cy = rng.randrange(TILE), rng.randrange(TILE)
            r = rng.uniform(1.2, 2.8)
            for y in range(TILE):
                for x in range(TILE):
                    d = math.hypot(x - cx, y - cy)
                    if d <= r and rng.random() < 0.75:
                        t.blend(x, y, (patina[0], patina[1], patina[2],
                                       int(150 * (1 - d / r)) + 40))
        for _ in range(4):
            x, y = rng.randrange(TILE), rng.randrange(TILE)
            for _ in range(rng.randrange(2, 5)):
                t.blend(x, y, (brass_dd[0], brass_dd[1], brass_dd[2], 120))
                x += rng.choice((-1, 0, 1))
                y += rng.choice((-1, 0, 1))

    def plate(t, seams=True):
        t.vgrad(brass_l, brass_d)
        if seams:
            for y in (2, 13):
                t.rect(0, y, 15, y, brass_dd)
                t.rect(0, y - 1, 15, y - 1, brass_ll)
            for x in (2, 13):
                for y in (5, 8, 11):
                    t.set(x, y, bolt)
                    t.set(x, y + 1, bolt_d)
        weather(t)

    # (0,0) shell sides
    plate(Tile(im, 0, 0))

    # (1,0) shell front - a shallow recess where the porthole is seated
    t = Tile(im, 1, 0)
    plate(t, seams=False)
    t.ring(7.5, 7.5, 5.0, 6.4, brass_dd)
    t.ring(7.5, 7.5, 6.4, 7.2, brass_ll)
    t.disc(7.5, 7.5, 4.8, brass_d)
    for i in range(8):
        a = math.pi * 2 * i / 8
        t.set(round(7.5 + math.cos(a) * 5.7), round(7.5 + math.sin(a) * 5.7), bolt)
    weather(t)

    # (2,0) shell back - a welded seam and the hose mounting plate
    t = Tile(im, 2, 0)
    plate(t, seams=False)
    t.rect(7, 0, 8, 15, brass_d)
    t.rect(7, 0, 7, 15, brass_ll)
    for y in range(1, 15, 3):
        t.set(8, y, bolt_d)
    t.rect(5, 1, 10, 4, brass)
    t.rect(5, 1, 10, 1, brass_ll)
    t.rect(5, 4, 10, 4, brass_dd)
    for x in (6, 9):
        t.set(x, 2, bolt)
    weather(t, heavy=True)

    # (3,0) shell top
    t = Tile(im, 3, 0)
    t.radial(brass_ll, brass_d, power=0.85)
    t.ring(7.5, 7.5, 5.2, 5.9, brass_dd)
    t.ring(7.5, 7.5, 2.4, 3.0, brass_l)
    weather(t)

    # (0,1) collar - heavier, bigger bolts, deep shadow underneath
    t = Tile(im, 0, 1)
    t.vgrad(brass_ll, brass_dd)
    t.rect(0, 0, 15, 1, brass_ll)
    t.rect(0, 12, 15, 15, brass_dd)
    for x in range(1, 16, 4):
        t.set(x, 6, bolt)
        t.set(x + 1, 6, bolt)
        t.set(x, 7, bolt_d)
        t.set(x + 1, 7, bolt_d)
    weather(t, heavy=True)

    # (1,1) dome
    t = Tile(im, 1, 1)
    t.radial(brass_ll, brass, cx=5.5, cy=4.5, power=0.9)
    t.ring(7.5, 7.5, 6.6, 7.4, brass_d)
    weather(t)

    # (2,1) porthole rim - polished, with the bolt ring
    t = Tile(im, 2, 1)
    t.vgrad(brass_ll, brass_d)
    t.rect(0, 0, 15, 0, (255, 236, 196, 255))
    t.rect(0, 15, 15, 15, brass_dd)
    for x in range(1, 16, 3):
        t.set(x, 7, bolt)
        t.set(x, 8, bolt_d)

    # (3,1) the glass - deep, with a hard diagonal reflection
    t = Tile(im, 3, 1)
    for y in range(TILE):
        for x in range(TILE):
            d = math.hypot(x - 7.5, y - 7.5) / 10.6
            c = mix(glass_m, glass, d ** 0.7)
            t.set(x, y, c)
    for i in range(-6, 7):                       # the streak
        for w in range(3):
            t.blend(3 + i + w, 11 + i, (glass_l[0], glass_l[1], glass_l[2],
                                        150 - w * 45))
    for i in range(-3, 4):                       # a second, thinner one
        t.blend(9 + i, 4 + i, (glass_l[0], glass_l[1], glass_l[2], 90))
    for y in range(TILE):                        # a face, dim, behind it
        for x in range(TILE):
            d = math.hypot((x - 7.5) / 3.4, (y - 8.6) / 4.0)
            if d < 1.0:
                t.blend(x, y, (10, 28, 36, int(120 * (1 - d))))
    t.border((12, 38, 48, 255))

    # (0,2) side port
    t = Tile(im, 0, 2)
    t.fill(brass_d)
    t.ring(7.5, 7.5, 5.6, 7.4, brass_l)
    t.ring(7.5, 7.5, 7.0, 7.6, brass_dd)
    t.disc(7.5, 7.5, 5.4, glass_m)
    t.disc(5.6, 5.6, 1.8, glass_l)
    for i in range(6):
        a = math.pi * 2 * i / 6
        t.set(round(7.5 + math.cos(a) * 6.4), round(7.5 + math.sin(a) * 6.4), bolt)

    # (1,2) the air hose - ribbed rubber
    t = Tile(im, 1, 2)
    for y in range(TILE):
        c = rubber if (y // 2) % 2 == 0 else rubber_d
        for x in range(TILE):
            t.set(x, y, c)
    for y in range(0, TILE, 4):
        t.rect(1, y, 2, y, (96, 96, 102, 255))

    # (2,2) finial knob
    t = Tile(im, 2, 2)
    t.radial(brass_ll, brass_dd, power=0.7)

    # (3,2) the dark inside
    Tile(im, 3, 2).fill((28, 21, 14, 255))
    return im


# ============================================================= eternal ice cube
#
# A block of ice with a head inside it. The front face carries a dim oval
# where the player's face would be, which is the whole illusion: without it
# the cube reads as a box balanced on someone's shoulders rather than as
# something they are frozen into.

def eternal_ice_cube():
    im = sheet()
    rng = random.Random(0x1CE0)

    pale = (214, 244, 255, 255)
    ice = (168, 226, 245, 255)
    mid = (111, 197, 226, 255)
    deep = (62, 146, 180, 255)
    core = (35, 92, 120, 255)
    white = (242, 252, 255, 255)
    frac = (28, 74, 97, 255)

    def body(t, top, bottom, edge=True):
        t.vgrad(top, bottom)
        # Two short fractures, and faint. Ice is mostly clear; an earlier
        # pass ran four long opaque ones per face and the cube came out
        # looking scribbled on rather than frozen.
        for _ in range(2):
            crack(t, rng, (deep[0], deep[1], deep[2], 130),
                  rng.randrange(3, 13), rng.randrange(1, 5),
                  rng.randrange(4, 8))
        for _ in range(4):                      # trapped bubbles
            bx, by = rng.randrange(2, 14), rng.randrange(2, 14)
            t.blend(bx, by, (255, 255, 255, 190))
            t.blend(bx + 1, by, (255, 255, 255, 110))
            t.blend(bx, by + 1, (255, 255, 255, 110))
            t.blend(bx + 1, by + 1, (core[0], core[1], core[2], 120))
        if edge:                                # a lit rim, so it reads cubic
            for x in range(TILE):
                t.blend(x, 0, (255, 255, 255, 170))
                t.blend(x, 15, (core[0], core[1], core[2], 140))
            for y in range(TILE):
                t.blend(0, y, (255, 255, 255, 120))
                t.blend(15, y, (core[0], core[1], core[2], 110))

    body(Tile(im, 0, 0), pale, deep)            # sides

    t = Tile(im, 1, 0)                          # front, with the face in it
    body(t, pale, deep)
    for y in range(TILE):
        for x in range(TILE):
            d = math.hypot((x - 7.5) / 3.8, (y - 8.2) / 4.6)
            if d < 1.0:
                t.blend(x, y, (28, 70, 92, int(135 * (1 - d * 0.75))))
    for ex in (5, 10):                          # two darker pits for eyes
        t.blend(ex, 7, (18, 48, 64, 150))
        t.blend(ex, 8, (18, 48, 64, 110))
    for i in range(-7, 8):                      # a hard specular streak
        t.blend(4 + i, 12 + i, (255, 255, 255, 120))

    body(Tile(im, 2, 0), white, ice)            # top, frosted
    t = Tile(im, 2, 0)
    t.speckle(rng, white, 0.30, 200)

    body(Tile(im, 3, 0), deep, core)            # bottom, in shadow

    t = Tile(im, 0, 1)                          # rime crust
    t.vgrad(white, ice)
    t.speckle(rng, white, 0.45, 230)
    t.speckle(rng, mid, 0.18, 150)
    for x in range(TILE):
        t.blend(x, 0, (255, 255, 255, 200))

    t = Tile(im, 1, 1)                          # icicle
    t.vgrad(ice, core)
    for y in range(TILE):                       # a bright spine down it
        t.blend(5, y, (255, 255, 255, 150 - y * 6))
        t.blend(6, y, (255, 255, 255, 90 - y * 4))
        t.blend(0, y, (frac[0], frac[1], frac[2], 120))
        t.blend(15, y, (frac[0], frac[1], frac[2], 120))

    t = Tile(im, 2, 1)                          # crystal shard
    t.vgrad(white, mid)
    for y in range(TILE):
        t.blend(4, y, (255, 255, 255, 180))
        t.blend(11, y, (deep[0], deep[1], deep[2], 150))

    body(Tile(im, 3, 1), pale, deep)            # back
    return im


# ================================================================= pink squid
#
# The mantle goes over the head, the eyes bulge out of the sides and the arms
# hang down past the player's chin. The eye is the piece that earns the most
# pixels: a big pupil with a hard specular dot reads as alive, and everything
# else on the model is supporting it.

def pink_squid():
    im = sheet()
    rng = random.Random(0x59D1)

    pink = (232, 96, 156, 255)
    pink_l = (247, 154, 196, 255)
    pink_ll = (255, 200, 222, 255)
    pink_d = (179, 58, 114, 255)
    pink_dd = (125, 37, 80, 255)
    spot = (142, 42, 88, 255)
    pale = (255, 227, 238, 255)
    sclera = (244, 232, 190, 255)
    pupil = (20, 10, 18, 255)

    def skin(t, top, bottom, spots=0.16):
        t.vgrad(top, bottom)
        # chromatophores: the pigment cells, scattered but clustered
        for _ in range(18):
            cx, cy = rng.randrange(TILE), rng.randrange(TILE)
            for _ in range(rng.randrange(1, 4)):
                x = cx + rng.randrange(-1, 2)
                y = cy + rng.randrange(-1, 2)
                if rng.random() < 0.8:
                    t.blend(x, y, (spot[0], spot[1], spot[2], rng.randrange(110, 200)))
        t.speckle(rng, pale, spots * 0.4, 110)

    skin(Tile(im, 0, 0), pink_l, pink_d)        # mantle sides

    t = Tile(im, 1, 0)                          # mantle front, paler belly
    skin(t, pale, pink, spots=0.08)
    for y in range(TILE):                       # a soft sheen down the middle
        t.blend(6, y, (255, 255, 255, 70))
        t.blend(7, y, (255, 255, 255, 110))
        t.blend(8, y, (255, 255, 255, 70))

    t = Tile(im, 2, 0)                          # mantle top
    t.radial(pink_l, pink_dd, cx=6.0, cy=5.0, power=0.9)
    skin_rng = rng
    for _ in range(14):
        cx, cy = skin_rng.randrange(TILE), skin_rng.randrange(TILE)
        t.blend(cx, cy, (spot[0], spot[1], spot[2], skin_rng.randrange(110, 190)))

    skin(Tile(im, 3, 0), pink, pink_dd)         # mantle back

    # (0,1) the eye
    t = Tile(im, 0, 1)
    t.fill(pink_d)
    t.disc(7.5, 7.5, 7.4, pink_l)               # the lid, bulging
    t.ring(7.5, 7.5, 6.4, 7.4, pink_dd)
    t.disc(7.5, 7.5, 6.2, sclera)
    t.disc(7.5, 7.5, 4.4, pupil)
    t.disc(5.4, 5.4, 1.5, (255, 255, 255, 255))  # the catchlight
    t.set(10, 10, (255, 255, 255, 150))          # and a weaker one opposite
    t.ring(7.5, 7.5, 4.4, 5.0, (72, 22, 48, 255))

    # (1,1) an arm, with suckers down one side
    t = Tile(im, 1, 1)
    t.vgrad(pink_l, pink_dd)
    for y in range(TILE):
        t.set(0, y, pink_dd)
        t.set(15, y, pink_dd)
        t.blend(4, y, (255, 255, 255, 60))
    for y in range(1, TILE, 2):
        t.set(11, y, pale)
        t.set(12, y, pink_ll)
        t.set(11, y + 1, pink_d)

    # (2,1) the fin - thin, and lit through
    t = Tile(im, 2, 1)
    t.vgrad(pink_ll, pink)
    # Veins fanning out from the fin's root rather than ruled diagonals -
    # evenly spaced stripes read as a sweet wrapper, not a membrane.
    for y in range(TILE):
        for x in range(TILE):
            a = math.atan2(y - 15.5, x - 7.5)
            if abs(math.sin(a * 6.0)) > 0.93:
                t.blend(x, y, (pink_d[0], pink_d[1], pink_d[2], 95))
    for x in range(TILE):
        t.blend(x, 0, (255, 255, 255, 120))
        t.blend(x, 15, (pink_d[0], pink_d[1], pink_d[2], 130))

    # (3,1) the mantle's point
    t = Tile(im, 3, 1)
    t.vgrad(pink, pink_dd)
    t.speckle(rng, spot, 0.2, 170)

    # (0,2) the beak
    t = Tile(im, 0, 2)
    t.vgrad((58, 30, 48, 255), (18, 8, 16, 255))
    t.rect(6, 0, 9, 3, (92, 52, 74, 255))
    return im


# ================================================================== lily pad
#
# Drawn as a function of world position rather than as a set of tiles,
# because the pad is one continuous disc spread across three overlapping
# boxes - two crossed rectangles and a diamond - and the veins and the notch
# have to line up across all three or the seams show.
#
# Sampling means each box asks the same function what colour its patch of the
# world is, so they agree by construction. The diamond asks in rotated
# coordinates, since the model spins that element 45 degrees.

PAD_LO, PAD_HI = -4.0, 20.0       # world span each 32x32 half covers
PAD_CX = PAD_CY = 8.0
PAD_R = 11.0
NOTCH_HALF = math.radians(13.0)


def _pad_colour(wx, wz, under, rng_cache={}):
    green = (78, 140, 58, 255)
    green_d = (53, 100, 42, 255)
    green_dd = (34, 64, 27, 255)
    green_l = (111, 176, 78, 255)
    green_ll = (150, 204, 106, 255)
    vein = (44, 82, 34, 255)
    under_c = (122, 74, 104, 255)
    under_d = (82, 48, 74, 255)
    under_l = (154, 100, 134, 255)
    under_v = (168, 112, 148, 255)

    dx, dz = wx - PAD_CX, wz - PAD_CY
    r = math.hypot(dx, dz)
    if r > PAD_R:
        return None
    # The notch: a wedge opening towards -Z, which is the way the player faces.
    ang = math.atan2(dx, -dz)
    if abs(ang) < NOTCH_HALF:
        return None

    k = r / PAD_R
    if under:
        c = mix(under_l, under_d, k ** 0.8)
        # the big radiating ribs lily pads have underneath
        spokes = abs(math.sin(math.atan2(dz, dx) * 9.0))
        if spokes > 0.86 and r > 1.5:
            c = mix(c, under_v, 0.75)
        if k > 0.90:
            c = mix(c, under_d, 0.8)
        if r < 1.6:
            c = mix(c, under_c, 0.7)
        return c

    # top: a lit disc, darker at the rim, with veins out of the centre
    lam = 0.5 - (dx + dz) / (PAD_R * 3.4)
    c = mix(green_d, green_ll, 0.35 + 0.65 * lam)
    c = mix(c, green, 0.35)
    # Mottling first, veins over the top of it. The other way round the
    # blotches swallowed the veins and the leaf came out looking like
    # camouflage netting.
    h = (int(wx * 2.1) * 73856093) ^ (int(wz * 2.1) * 19349663)
    m = (h & 1023) / 1023.0
    if m > 0.88:
        c = mix(c, green_ll, 0.30)
    elif m < 0.14:
        c = mix(c, green_dd, 0.22)
    spokes = abs(math.sin(math.atan2(dz, dx) * 7.0))
    if spokes > 0.88 and r > 1.8:
        c = mix(c, vein, 0.60)
    elif spokes > 0.80 and r > 3.0:
        c = mix(c, vein, 0.22)
    if k > 0.88:
        c = mix(c, green_dd, (k - 0.88) / 0.12 * 0.85)
    elif k > 0.80:
        c = mix(c, green_d, (k - 0.80) / 0.08 * 0.5)
    if r < 1.7:
        c = mix(c, green_dd, 0.55)      # where the stem joins
    # a couple of beads of water
    for bx, bz, br in ((3.0, 11.0, 1.5), (12.5, 5.0, 1.2), (10.0, 13.0, 1.0)):
        d = math.hypot(wx - bx, wz - bz)
        if d <= br:
            c = mix(c, (198, 234, 244, 255), 0.55 - 0.25 * (d / br))
            if d <= br * 0.45:
                c = mix(c, (255, 255, 255, 255), 0.55)
    return c


def lily_pad():
    """
    Two 32x32 halves of a 64x32 sheet: the pad seen from above, and from
    below.

    The underside half is written with world z running UPWARDS, which is not
    an aesthetic choice. FaceBakery.defaultFaceUV maps a `down` face with u
    along +x and v along -z, the mirror of an `up` face. Baking that flip
    into the image means every element can quote its uv in the natural
    order, and - the part that actually matters - the transparent notch
    lands on the same side of the pad whether you are looking at the top of
    it or the bottom.
    """
    im = Image.new("RGBA", (SHEET, 32), (0, 0, 0, 0))
    span = PAD_HI - PAD_LO
    for ox, under in ((0, False), (32, True)):
        for py in range(32):
            for px in range(32):
                wx = PAD_LO + (px + 0.5) * span / 32.0
                t = (py + 0.5) * span / 32.0
                wz = (PAD_HI - t) if under else (PAD_LO + t)
                c = _pad_colour(wx, wz, under)
                if c is not None:
                    im.putpixel((ox + px, py), c)
    return im


def lily_trim():
    """The pad's cut edge, and the flower that sits on it."""
    im = sheet()
    rng = random.Random(0x11FA)

    green_d = (53, 100, 42, 255)
    green_dd = (34, 64, 27, 255)
    green_l = (111, 176, 78, 255)
    petal = (242, 184, 212, 255)
    petal_l = (255, 228, 240, 255)
    petal_d = (201, 120, 159, 255)
    petal_dd = (156, 84, 118, 255)
    yellow = (240, 200, 74, 255)
    yellow_d = (186, 146, 32, 255)

    # (0,0) petal, top side
    t = Tile(im, 0, 0)
    t.vgrad(petal_l, petal_d)
    for x in range(TILE):                       # ribs along the petal
        for y in range(TILE):
            if (x + y * 2) % 7 == 0:
                t.blend(x, y, (petal_d[0], petal_d[1], petal_d[2], 110))
    for x in range(TILE):
        t.blend(x, 0, (255, 255, 255, 180))
        t.blend(x, 15, (petal_dd[0], petal_dd[1], petal_dd[2], 170))

    # (1,0) petal, underside
    t = Tile(im, 1, 0)
    t.vgrad(petal, petal_dd)

    # (2,0) the flower's centre - stamens
    t = Tile(im, 2, 0)
    t.radial(yellow, yellow_d, power=0.8)
    for _ in range(26):
        x, y = rng.randrange(TILE), rng.randrange(TILE)
        t.blend(x, y, (255, 240, 170, 200))
    t.ring(7.5, 7.5, 6.6, 7.6, (150, 112, 20, 255))

    # (3,0) the pad's cut edge, solid
    t = Tile(im, 3, 0)
    t.vgrad(green_l, green_dd)
    t.rect(0, 0, 15, 2, green_l)
    t.rect(0, 10, 15, 15, green_dd)
    for x in range(0, TILE, 3):
        t.blend(x, 5, (green_d[0], green_d[1], green_d[2], 160))

    # (1,1) the stalk
    t = Tile(im, 1, 1)
    t.vgrad(green_l, green_dd)
    for y in range(TILE):
        t.blend(5, y, (255, 255, 255, 60))
    return im


# ---------------------------------------------------------------------- output

SHEETS = {
    "deep_sea_diving_helmet": diving_helmet,
    "eternal_ice_cube": eternal_ice_cube,
    "pink_squid": pink_squid,
    "lily_pad": lily_pad,
    "lily_pad_trim": lily_trim,
}


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        return 1
    root = sys.argv[1]
    if not os.path.isfile(os.path.join(root, "pack.mcmeta")):
        print("not a pack root (no pack.mcmeta): " + root)
        return 1
    out = os.path.join(root, "assets", "monkeygames", "textures",
                       "item", "catch", "worn")
    os.makedirs(out, exist_ok=True)
    for name, fn in SHEETS.items():
        path = os.path.join(out, name + ".png")
        fn().save(path)
        print("wrote " + path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
