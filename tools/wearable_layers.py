#!/usr/bin/env python3
"""
Paints the armour-layer textures for the equipable fishing catches.

Five catches are worn on the body rather than the head, and the body slots
have no 3D option in vanilla: the chest, legs and feet are drawn as a skin
over the humanoid model, so what goes there is a decal. (The one 3D chest
layer is the elytra's `wings`, and the client only draws it for an item
carrying the glider component - which would let a player fly, so it is out.)

The decals are therefore painted to read as volume: every shape gets a dark
outline, a lit side, a shadowed side and a cast shadow where it meets the
body, which is the whole trick for making a flat overlay look attached.

Usage:  python wearable_layers.py <pack-root>
        <pack-root> is the directory holding pack.mcmeta.

The layout below is not guesswork - it was read off vanilla's own
iron.png by dumping its alpha channel, so the regions are exactly the
ones the client samples.

  humanoid (64x32)                 humanoid_leggings (64x32)
    head   x 0-31  y 0-15            same cube regions; the model is the
    leg    x 0-15  y16-31            full humanoid body, so anything may
    body   x16-39  y16-31            be painted - vanilla just restricts
    arm    x40-55  y16-31            itself to the hips and thighs.

Each cube unwraps as: top, bottom, right, front, left, back.
Arms and legs are MIRRORED by the humanoid model, so anything painted on
them appears on both sides; only the body cube can carry an asymmetry.
"""

import json
import os
import sys
import math
import random

from PIL import Image

# --------------------------------------------------------------- face regions

# (x0, y0, x1, y1) inclusive, in the 64x32 layer.
BODY = {
    "top":    (20, 16, 27, 19),
    "bottom": (28, 16, 35, 19),
    "right":  (16, 20, 19, 31),
    "front":  (20, 20, 27, 31),
    "left":   (28, 20, 31, 31),
    "back":   (32, 20, 39, 31),
}
ARM = {
    "top":    (44, 16, 47, 19),
    "bottom": (48, 16, 51, 19),
    "right":  (40, 20, 43, 31),
    "front":  (44, 20, 47, 31),
    "left":   (48, 20, 51, 31),
    "back":   (52, 20, 55, 31),
}
LEG = {
    "top":    (4, 16, 7, 19),
    "bottom": (8, 16, 11, 19),
    "right":  (0, 20, 3, 31),
    "front":  (4, 20, 7, 31),
    "left":   (8, 20, 11, 31),
    "back":   (12, 20, 15, 31),
}


def blank():
    return Image.new("RGBA", (64, 32), (0, 0, 0, 0))


def put(im, x, y, c):
    """One pixel, ignored if it falls outside the sheet."""
    if 0 <= x < im.size[0] and 0 <= y < im.size[1]:
        im.putpixel((int(x), int(y)), c)


def over(im, x, y, c):
    """One pixel alpha-composited onto what is already there."""
    if not (0 <= x < im.size[0] and 0 <= y < im.size[1]):
        return
    x, y = int(x), int(y)
    r, g, b, a = c
    if a >= 255:
        im.putpixel((x, y), c)
        return
    br, bg, bb, ba = im.getpixel((x, y))
    f = a / 255.0
    nr = round(r * f + br * (1 - f))
    ng = round(g * f + bg * (1 - f))
    nb = round(b * f + bb * (1 - f))
    na = max(ba, a)
    im.putpixel((x, y), (nr, ng, nb, na))


def box(im, x0, y0, x1, y1, c):
    for y in range(int(y0), int(y1) + 1):
        for x in range(int(x0), int(x1) + 1):
            put(im, x, y, c)


def face_box(im, face, dx0, dy0, dx1, dy1, c):
    """A rectangle in face-local coordinates."""
    x0, y0, x1, y1 = face
    for y in range(int(dy0), int(dy1) + 1):
        for x in range(int(dx0), int(dx1) + 1):
            if x0 + x <= x1 and y0 + y <= y1:
                put(im, x0 + x, y0 + y, c)


def mix(a, b, t):
    t = max(0.0, min(1.0, t))
    return (round(a[0] + (b[0] - a[0]) * t),
            round(a[1] + (b[1] - a[1]) * t),
            round(a[2] + (b[2] - a[2]) * t),
            round(a[3] + (b[3] - a[3]) * t))


def shade(c, f):
    """Lighten (f>1) or darken (f<1) without touching alpha."""
    return (max(0, min(255, round(c[0] * f))),
            max(0, min(255, round(c[1] * f))),
            max(0, min(255, round(c[2] * f))),
            c[3])


# ============================================================ 1. the starfish
#
# Worn on the chest: a starfish clamped to the player's back.
#
# A starfish is already flat, which is why it was the easiest of the three
# chest pieces to make convincing - there is no volume being faked here, only
# a thing lying against a surface. The arms are generated from the standard
# five-lobed polar curve rather than drawn by hand, so the limbs come out
# even and the tapering is smooth, and the tubercles are scattered from a
# fixed seed so the pattern is irregular but identical on every rebuild.

def starfish():
    im = blank()
    base = (214, 94, 43, 255)
    deep = (150, 54, 22, 255)
    edge = (104, 34, 12, 255)
    lit = (243, 143, 82, 255)
    bump = (255, 196, 140, 255)
    core = (126, 42, 16, 255)

    bx0, by0, bx1, by1 = BODY["back"]
    cx = (bx0 + bx1) / 2.0 + 0.5      # 8 wide
    cy = by0 + 5.6                    # sit it high on the back
    rng = random.Random(0x57A4)

    # The silhouette, and a signed distance to the rim for the shading.
    for y in range(by0, by1 + 1):
        for x in range(bx0, bx1 + 1):
            dx = (x + 0.5) - cx
            dy = ((y + 0.5) - cy) * 0.80          # stretch: the back is tall
            r = math.hypot(dx, dy)
            if r < 0.001:
                r = 0.001
            th = math.atan2(dy, dx)
            # The exponent is what makes it a star rather than a blob: it
            # deepens the valleys between the arms, so the arms come to a
            # point instead of merging into a disc.
            lobe = (math.cos(5 * th - math.pi / 2) * 0.5 + 0.5) ** 1.35
            limit = 1.20 + 3.30 * lobe
            if r > limit:
                continue
            k = r / limit                          # 0 centre, 1 rim
            if k > 0.84:
                c = edge
            else:
                # Lit from the upper left, like everything else on the body.
                lam = (-dx - dy) / (limit * 2.2) + 0.5
                c = mix(deep, lit, 0.30 + 0.70 * lam)
                c = mix(c, base, 0.35)
                if k > 0.68:
                    c = mix(c, edge, (k - 0.68) / 0.16 * 0.55)
            if r < 1.35:
                c = mix(c, core, 0.70 - 0.35 * r)
            put(im, x, y, c)

    # Tubercles: the pale knobbly spots down the middle of each arm.
    for y in range(by0, by1 + 1):
        for x in range(bx0, bx1 + 1):
            if im.getpixel((x, y))[3] == 0:
                continue
            dx = (x + 0.5) - cx
            dy = ((y + 0.5) - cy) * 0.80
            r = math.hypot(dx, dy)
            th = math.atan2(dy, dx)
            # Near an arm's spine, and not right at the rim.
            spine = abs(math.sin(2.5 * th - math.pi / 4))
            if r > 1.3 and spine > 0.80 and rng.random() < 0.55:
                over(im, x, y, (bump[0], bump[1], bump[2], 170))

    # The madreporite - the one off-centre pale plate every starfish has.
    over(im, int(cx) + 1, int(cy) - 1, (255, 214, 170, 210))

    # A cast shadow, so it reads as sitting ON the back rather than in it.
    for y in range(by0, by1 + 1):
        for x in range(bx0, bx1 + 1):
            if im.getpixel((x, y))[3] != 0:
                continue
            near = any(
                0 <= x + ox <= 63 and 0 <= y + oy <= 31
                and im.getpixel((x + ox, y + oy))[3] > 0
                for ox, oy in ((0, -1), (-1, 0), (-1, -1))
            )
            if near:
                over(im, x, y, (24, 12, 6, 70))

    # Two arm tips curling round the ribs onto the sides of the torso.
    for y, w in ((by0 + 4, 2), (by0 + 5, 1)):
        for i in range(w):
            put(im, BODY["left"][0] + i, y, mix(deep, edge, i / max(1, w)))
            put(im, BODY["right"][2] - i, y, mix(deep, edge, i / max(1, w)))
    return im


# ================================================== 2. sunken treasure chest
#
# Worn on the chest: a small waterlogged chest slung on the back, with
# straps over the shoulders.
#
# The straps are what sell it. A chest painted on the back alone looks
# printed on; two bands running over the top of the arms and down the front
# of the torso make the player read as carrying something. The arm cube is
# mirrored by the model, so one strap drawn there becomes a matching pair.

def treasure_chest():
    im = blank()
    plank = (104, 72, 40, 255)
    plank_d = (74, 48, 24, 255)
    plank_l = (134, 98, 58, 255)
    iron = (138, 140, 150, 255)
    iron_d = (84, 86, 96, 255)
    iron_l = (186, 189, 198, 255)
    gold = (214, 165, 43, 255)
    gold_d = (150, 110, 20, 255)
    outline = (34, 22, 10, 255)
    moss = (62, 104, 58, 255)
    moss_l = (92, 140, 80, 255)
    barn = (196, 194, 170, 255)
    leather = (62, 44, 30, 255)
    leather_l = (94, 70, 48, 255)
    leather_d = (38, 26, 16, 255)
    stitch = (150, 128, 96, 255)

    back = BODY["back"]
    bx0, by0 = back[0], back[1]

    # --- the chest itself, rows 1-9 of an 8x12 face.
    #
    # Eight pixels across is not much, so the chest is built out of as few
    # marks as will still say "chest": a lid, a seam, three boards, two iron
    # bands and a lock. An earlier version had plank grain on every row and
    # rivets along the bands, and at this size all of it collapsed into
    # noise - the detail has to be in the SHADING, not in more marks.
    face_box(im, back, 0, 1, 7, 9, plank)
    face_box(im, back, 0, 1, 7, 1, shade(plank_l, 1.10))   # lit top of the lid
    face_box(im, back, 0, 2, 7, 3, plank)                  # lid face
    face_box(im, back, 0, 4, 7, 4, outline)                # the lid/base gap
    face_box(im, back, 0, 5, 7, 9, shade(plank, 0.92))     # base, in shadow
    face_box(im, back, 0, 9, 7, 9, plank_d)                # dark at the foot
    for rx in (2, 5):                                      # three boards
        for ry in range(1, 10):
            if ry != 4:
                put(im, bx0 + rx, by0 + ry, plank_d)
    # two iron bands, solid so they read as metal at a glance
    for rx in (1, 6):
        for ry in range(1, 10):
            put(im, bx0 + rx, by0 + ry, iron if ry < 5 else shade(iron, 0.82))
        put(im, bx0 + rx, by0 + 1, iron_l)     # one highlight, not a column
        put(im, bx0 + rx, by0 + 4, iron_d)
        put(im, bx0 + rx, by0 + 9, iron_d)
    # lock plate and keyhole, straddling the seam the way a hasp does
    face_box(im, back, 3, 3, 4, 6, gold)
    face_box(im, back, 3, 3, 4, 3, shade(gold, 1.20))
    face_box(im, back, 3, 6, 4, 6, gold_d)
    put(im, bx0 + 3, by0 + 5, (58, 40, 10, 255))
    put(im, bx0 + 4, by0 + 5, (58, 40, 10, 255))
    # outline, and a cast shadow below so it sits ON the back
    face_box(im, back, 0, 0, 7, 0, outline)
    face_box(im, back, 0, 10, 7, 10, outline)
    for ry in range(1, 10):
        put(im, bx0 + 0, by0 + ry, mix(im.getpixel((bx0, by0 + ry)), outline, 0.55))
        put(im, bx0 + 7, by0 + ry, mix(im.getpixel((bx0 + 7, by0 + ry)), outline, 0.55))
    face_box(im, back, 1, 11, 6, 11, (20, 12, 6, 110))

    # --- it came out of the sea: weed in one corner, two barnacles, a sheen
    for rx, ry in ((0, 8), (0, 9), (1, 9), (7, 2)):
        over(im, bx0 + rx, by0 + ry, (moss[0], moss[1], moss[2], 225))
    over(im, bx0 + 1, by0 + 8, (moss_l[0], moss_l[1], moss_l[2], 160))
    put(im, bx0 + 6, by0 + 2, barn)
    put(im, bx0 + 2, by0 + 8, barn)
    over(im, bx0 + 4, by0 + 2, (235, 245, 250, 80))

    # --- straps: body front, and over the top of the arms
    front = BODY["front"]
    for rx in (1, 2, 5, 6):
        for ry in range(0, 10):
            put(im, front[0] + rx, front[1] + ry,
                leather_l if rx in (1, 5) else leather)
        put(im, front[0] + rx, front[1] + 10, leather_d)
    for ry in range(0, 10, 3):                       # stitching
        put(im, front[0] + 1, front[1] + ry, stitch)
        put(im, front[0] + 6, front[1] + ry, stitch)
    # buckles at chest height
    for rx in (1, 2, 5, 6):
        put(im, front[0] + rx, front[1] + 5, iron_l)
        put(im, front[0] + rx, front[1] + 6, iron_d)

    arm = ARM
    for rx in range(1, 3):                           # over the shoulder
        for ry in range(0, 4):
            put(im, arm["top"][0] + rx, arm["top"][1] + ry,
                leather_l if rx == 1 else leather)
    for ry in range(0, 4):                           # down the arm front
        put(im, arm["front"][0] + 1, arm["front"][1] + ry, leather_l)
        put(im, arm["front"][0] + 2, arm["front"][1] + ry, leather)
    for ry in range(0, 5):                           # and the inner side
        put(im, arm["left"][0] + 1, arm["left"][1] + ry, leather)
        put(im, arm["left"][0] + 2, arm["left"][1] + ry, leather_d)
    # the straps continue round the ribs to reach the chest
    for ry in range(0, 3):
        put(im, BODY["left"][0] + 1, BODY["left"][1] + ry, leather)
        put(im, BODY["right"][2] - 1, BODY["right"][1] + ry, leather)
    return im


# ============================================================ 3. the shark fin
#
# Worn on the chest: a dorsal fin standing up from the spine.
#
# Seen from behind - which is how anyone else sees a player's back - a
# dorsal fin is a symmetrical triangle, so it is built that way rather than
# swept, with the taper on a power curve so the leading edges are concave
# like the real thing instead of straight.

def shark_fin():
    im = blank()
    grey = (76, 89, 101, 255)
    grey_d = (40, 49, 58, 255)
    grey_l = (126, 141, 155, 255)
    pale = (170, 183, 194, 255)
    outline = (20, 25, 30, 255)

    back = BODY["back"]
    bx0, by0, bx1, by1 = back
    cx = (bx0 + bx1) / 2.0 + 0.5
    base_y = by0 + 10          # the root, low on the back
    apex_y = by0 + 0           # the tip, at the shoulders

    for y in range(apex_y, base_y + 1):
        u = (base_y - y) / float(base_y - apex_y)        # 0 root, 1 tip
        half = 0.55 + 3.65 * (1.0 - u) ** 0.78
        for x in range(bx0, bx1 + 1):
            d = abs((x + 0.5) - cx)
            if d > half:
                continue
            k = d / half
            if k > 0.80:
                c = outline
            else:
                # Lit from above and to one side; the lower third of a fin
                # is always paler where it meets the body.
                lam = 0.30 + 0.70 * (1.0 - u) * 0.6 + 0.35 * (1.0 - k)
                c = mix(grey_d, grey_l, lam)
                c = mix(c, grey, 0.30)
                if u < 0.26:
                    c = mix(c, pale, (0.26 - u) / 0.26 * 0.32)
                if k > 0.62:
                    c = mix(c, outline, (k - 0.62) / 0.18 * 0.5)
            put(im, x, y, c)

    # Two bites out of the trailing edges, taken off the OUTERMOST pixel of
    # a row rather than a fixed coordinate. Punching a hole at a fixed spot
    # put the nicks in the middle of the blade, where they read as damage to
    # the texture instead of damage to the shark.
    for ry, side in ((3, +1), (6, -1), (7, +1)):
        y = apex_y + ry
        run = [x for x in range(bx0, bx1 + 1) if im.getpixel((x, y))[3] > 0]
        if run:
            put(im, max(run) if side > 0 else min(run), y, (0, 0, 0, 0))

    # A bright specular streak just inside the leading edge.
    for y in range(apex_y + 1, base_y - 1):
        u = (base_y - y) / float(base_y - apex_y)
        half = 0.55 + 3.65 * (1.0 - u) ** 0.78
        sx = int(cx - half * 0.55)
        if im.getpixel((sx, y))[3] > 0:
            over(im, sx, y, (225, 236, 244, 110))

    # The root: a low mound of skin where the fin grows out of the back,
    # wider than the fin so the join is not a hard edge.
    for ry, a in ((10, 255), (11, 210)):
        for x in range(bx0 + 1, bx1):
            d = abs((x + 0.5) - cx)
            c = mix(grey_d, grey, 1.0 - d / 4.0)
            over(im, x, by0 + ry, (c[0], c[1], c[2], a))
    for x in range(bx0 + 2, bx1 - 1):
        over(im, x, by0 + 11, (24, 30, 36, 90))

    # Shark skin tone creeping onto the sides of the torso, so the fin is
    # not a decal floating on bare skin.
    for ry in range(9, 12):
        over(im, BODY["left"][0], BODY["left"][1] + ry, (grey_d[0], grey_d[1], grey_d[2], 120))
        over(im, BODY["right"][2], BODY["right"][1] + ry, (grey_d[0], grey_d[1], grey_d[2], 120))
    return im


# ============================================================== 4. the old boot
#
# Worn on the feet. One boot is painted and the model mirrors it, which is
# why every piece of vanilla armour is symmetrical too.
#
# It is a boot that has been in a lake: the leather is blotched, the sole is
# coming away at the welt, there is a split on the outside, and there is
# weed in the creases. The lace panel goes on the front of the leg, which is
# the shin - the model has no foot box, so that is where the lacing reads.

def old_boot():
    """
    A boot that stops at the ankle, drawn pixel by pixel.

    Two things were wrong with the old one. It painted rows 2 to 11 of
    the leg cube - ten of its twelve - which is not a boot, it is a
    legging in leather, and in game both legs were brown from the hip
    down; vanilla's own humanoid layer puts iron boots on rows 6 to 11
    and nothing above, so this does too. And the sheet was being halved
    on the way out, which left those six rows holding three real pixels.

    What is left is four pixels across and six down per side, and the
    only way to get a boot out of that is to spend every one of them
    deliberately. So each face is written out as a little picture rather
    than built from bands: the instep carries a tongue, eyelets and
    crossed laces, the heel a seam and a pull tab, the outer side a strap
    with a brass buckle, and all four meet at a stitched welt above a
    dark sole. Shading is per face afterwards, outer faces lit and inner
    ones not, which is what keeps it reading as a solid object.
    """
    im = blank()

    # One family of colours and nothing outside it: leather browns,
    # moss greens, and the greys of the sole and the buckle. The cream
    # laces and brass buckle that were here before were the only two
    # hues on the boot and they pulled the eye straight to them, which
    # at four pixels across is the whole boot. Drab laces and an iron
    # buckle sit in the same family, so the boot reads as one object
    # that has been in a pond rather than as a brown shape with two
    # bright marks on it.
    INK = {
        "L": (150, 118, 82, 255),    # leather, lit
        "l": (124, 96, 66, 255),
        "m": (100, 76, 52, 255),
        "d": (76, 56, 38, 255),
        "D": (52, 38, 26, 255),      # leather, deepest
        "c": (118, 104, 76, 255),    # lace
        "C": (88, 76, 54, 255),
        "g": (92, 118, 64, 255),     # moss
        "G": (122, 146, 86, 255),
        "n": (68, 90, 50, 255),
        "i": (138, 142, 142, 255),   # buckle
        "I": (94, 98, 100, 255),
        "w": (108, 100, 86, 255),    # welt
        "s": (72, 70, 66, 255),      # sole
        "S": (48, 46, 44, 255),
    }

    # Six rows, top of the cuff first, laid out at rows 6..11 of the leg.
    # Moss gathers low, where a boot stood in the water.
    ART = {
        # the shin and instep: tongue, and laces crossing it
        "front": ["LlLL",
                  "dDDd",
                  "mcCm",
                  "lCcl",
                  "wgDw",
                  "SsgS"],
        # the heel: a pull tab at the top, the seam below it
        "back":  ["lLll",
                  "dDDd",
                  "mDDm",
                  "mDdm",
                  "gwDw",
                  "sSgS"],
        # the outer side: a strap with an iron buckle, weed at the welt
        "right": ["LlLL",
                  "lllm",
                  "miIm",
                  "mmdm",
                  "wGDw",
                  "ssgS"],
        # the inner side: plainer, and darker for being out of the light
        "left":  ["lmll",
                  "dmmd",
                  "mndm",
                  "mdmm",
                  "wwgD",
                  "sSsg"],
    }
    TINT = {"right": 1.14, "front": 1.04, "left": 0.84, "back": 0.90}
    TOP = 6

    for key, rows in ART.items():
        f = LEG[key]
        for ry, row in enumerate(rows):
            for rx, ch in enumerate(row):
                if ch == ".":
                    continue
                c = INK[ch]
                # The sole reads flat and dark whichever way it faces;
                # everything above it is lit by which way its face points.
                if ch not in ("s", "S"):
                    c = shade(c, TINT[key])
                put(im, f[0] + rx, f[1] + TOP + ry, c)

    # --- the sole, seen from below: a worn tread
    #
    # Lifted well above the colour of the sole's SIDES. A sole lit the same
    # as the upper disappears into it, and this face is only ever seen
    # against the ground, so it wants to be the lightest thing on the boot.
    tread = (96, 92, 86, 255)
    f = LEG["bottom"]
    for ry in range(0, 4):
        for rx in range(0, 4):
            c = shade(tread, 0.70) if (rx + ry) % 2 == 0 else tread
            put(im, f[0] + rx, f[1] + ry, c)
    put(im, f[0] + 0, f[1] + 0, shade(tread, 1.25))       # heel, worn smooth
    put(im, f[0] + 1, f[1] + 0, shade(tread, 1.18))
    put(im, f[0] + 3, f[1] + 3, shade(tread, 1.25))       # and the toe
    put(im, f[0] + 2, f[1] + 3, shade(tread, 1.18))
    return im

# ======================================================= 5. the phantom lantern
#
# Worn on the legs: a belt with a lantern hanging off it.
#
# The leg cube is mirrored, so the lantern itself lands on both thighs - a
# matching pair, the way vanilla armour always is. The belt and buckle sit
# on the body cube, which is NOT mirrored, so the buckle can be a single
# object at the front where a buckle belongs.
#
# The light is painted, not emitted: resource packs cannot make a worn layer
# glow, so the lantern is given a very bright core and a cold rim so it
# reads as lit even though it casts nothing.

def phantom_lantern():
    im = blank()
    belt = (59, 58, 74, 255)
    belt_l = (96, 94, 118, 255)
    belt_d = (34, 33, 44, 255)
    membrane = (138, 136, 164, 255)
    buckle = (195, 207, 210, 255)
    buckle_d = (108, 120, 126, 255)
    iron = (52, 63, 70, 255)
    iron_l = (118, 134, 142, 255)
    iron_d = (32, 40, 45, 255)
    chain = (154, 167, 172, 255)
    glow_hot = (226, 250, 255, 255)
    glow_1 = (166, 238, 252, 255)
    glow_2 = (111, 214, 238, 255)
    glow_3 = (62, 164, 196, 255)

    # --- the belt, round all four faces of the hips (rows 8-10)
    for key in ("right", "front", "left", "back"):
        f = BODY[key]
        w = f[2] - f[0]
        tint = {"right": 1.10, "front": 1.0, "left": 0.86, "back": 0.92}[key]
        for rx in range(0, w + 1):
            put(im, f[0] + rx, f[1] + 8, shade(belt_l, tint))
            put(im, f[0] + rx, f[1] + 9, shade(belt, tint))
            put(im, f[0] + rx, f[1] + 10, shade(belt_d, tint))
        # phantom-membrane veining, which is what the thing is made of
        for rx in range(0, w + 1, 3):
            over(im, f[0] + rx, f[1] + 9,
                 (membrane[0], membrane[1], membrane[2], 150))
        for rx in range(1, w + 1, 4):
            over(im, f[0] + rx, f[1] + 8,
                 (membrane[0], membrane[1], membrane[2], 110))

    # --- the buckle, front and centre
    f = BODY["front"]
    for rx in (3, 4):
        put(im, f[0] + rx, f[1] + 8, buckle)
        put(im, f[0] + rx, f[1] + 9, buckle_d)
        put(im, f[0] + rx, f[1] + 10, buckle)
    put(im, f[0] + 3, f[1] + 9, (40, 46, 50, 255))   # the pin's slot
    put(im, f[0] + 4, f[1] + 9, buckle)

    # --- the hanging rings, on the sides of the hips, below the belt
    put(im, BODY["left"][0] + 1, BODY["left"][1] + 11, chain)
    put(im, BODY["right"][2] - 1, BODY["right"][1] + 11, chain)

    # --- the lantern, on the outer face of the thigh (rows 0-7)
    f = LEG["right"]
    lx = f[0]
    ly = f[1]
    put(im, lx + 1, ly + 0, chain)                    # the ring it hangs by
    put(im, lx + 2, ly + 0, shade(chain, 0.8))
    for rx in range(0, 4):                            # top cap
        put(im, lx + rx, ly + 1, iron if rx in (1, 2) else iron_d)
    put(im, lx + 1, ly + 1, iron_l)
    for ry, c in ((2, glow_1), (3, glow_hot), (4, glow_2), (5, glow_3)):
        put(im, lx + 0, ly + ry, iron_d)              # frame post
        put(im, lx + 1, ly + ry, c)
        put(im, lx + 2, ly + ry, mix(c, glow_3, 0.35))
        put(im, lx + 3, ly + ry, iron_d)
    put(im, lx + 1, ly + 3, glow_hot)                 # the core
    for rx in range(0, 4):                            # bottom cap
        put(im, lx + rx, ly + 6, iron if rx in (1, 2) else iron_d)
    put(im, lx + 1, ly + 7, iron_d)
    put(im, lx + 2, ly + 7, iron_d)

    # The light bleeding onto the leather and the leg around it.
    for ry in range(1, 7):
        over(im, lx + 0, ly + ry, (glow_2[0], glow_2[1], glow_2[2], 70))
        over(im, lx + 3, ly + ry, (glow_2[0], glow_2[1], glow_2[2], 70))
    # and wrapping one pixel onto the neighbouring faces of the thigh
    for ry in range(2, 6):
        over(im, LEG["front"][0], LEG["front"][1] + ry,
             (glow_2[0], glow_2[1], glow_2[2], 110))
        over(im, LEG["back"][2], LEG["back"][1] + ry,
             (glow_2[0], glow_2[1], glow_2[2], 110))
    for ry in (0, 1, 6, 7):
        over(im, LEG["front"][0], LEG["front"][1] + ry, iron_d)
        over(im, LEG["back"][2], LEG["back"][1] + ry, iron_d)
    return im


# ---------------------------------------------------------------------- output

LAYER1 = {
    "starfish": starfish,
    "sunken_treasure_chest": treasure_chest,
    "shark_fin": shark_fin,
    "old_boot": old_boot,
}
LAYER2 = {
    "phantom_lantern": phantom_lantern,
}


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        return 1
    root = sys.argv[1]
    if not os.path.isfile(os.path.join(root, "pack.mcmeta")):
        print("not a pack root (no pack.mcmeta): " + root)
        return 1

    assets = os.path.join(root, "assets", "monkeygames")
    eq = os.path.join(assets, "equipment", "catch")
    os.makedirs(eq, exist_ok=True)

    for layer, table in (("humanoid", LAYER1), ("humanoid_leggings", LAYER2)):
        out = os.path.join(assets, "textures", "entity", "equipment",
                           layer, "catch")
        os.makedirs(out, exist_ok=True)
        for name, fn in table.items():
            # Saved at full resolution.
            #
            # These used to be halved and blown straight back up, so that
            # a texel covered a 2x2 block - a "coarser grain" that in
            # practice threw away three pixels in every four. A leg face
            # is four wide and the boot occupies six of its rows, so what
            # reached the game was a boot drawn in two pixels by three.
            # That is the whole of the complaint that the boots looked
            # like sixteen pixels: they very nearly were.
            #
            # 64x32 IS the coarse grain. It is the same grid a player skin
            # is drawn on, which is the rule everywhere else here, and
            # halving it again is not style, it is loss.
            im = fn()
            im.save(os.path.join(out, name + ".png"))
            # The asset the item's equippable component names. One layer
            # each: these are accessories, not armour, so there is no baby
            # variant and nothing for a horse to wear.
            with open(os.path.join(eq, name + ".json"), "w",
                      newline="\n") as f:
                json.dump({"layers": {layer: [
                    {"texture": "monkeygames:catch/" + name}]}}, f, indent=2)
                f.write("\n")
            print("%-24s %s" % (name, layer))
    return 0


if __name__ == "__main__":
    sys.exit(main())
