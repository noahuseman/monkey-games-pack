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
    A boot that stops at the ankle.

    It used to paint rows 2 to 11 of the leg cube - ten of its twelve
    rows - which is not a boot, it is a legging in leather, and that is
    exactly what it looked like in game: both legs brown from the hip
    down. Vanilla's own humanoid layer was the thing to read, and iron
    boots occupy rows 6 to 11 and nothing above, so this does too. The
    six rows left are the whole boot: a cuff, two of upper, the welt and
    the sole, which is as much boot as a 16-pixel leg can hold.
    """
    im = blank()
    lea = (107, 74, 47, 255)
    lea_d = (74, 50, 31, 255)
    lea_dd = (48, 32, 19, 255)
    lea_l = (138, 102, 66, 255)
    lea_ll = (166, 128, 88, 255)
    sole = (53, 48, 43, 255)
    sole_d = (34, 31, 28, 255)
    welt = (122, 108, 92, 255)
    lace = (216, 203, 168, 255)
    lace_d = (150, 138, 108, 255)
    algae = (79, 122, 62, 255)
    algae_l = (112, 156, 86, 255)
    rust = (126, 76, 42, 255)
    dark = (22, 15, 9, 255)

    rng = random.Random(0xB007)

    TOP, CUFF, UPPER, WELT_ROW, SOLE_ROW = 6, 7, (8, 9), 10, 11

    for key in ("right", "front", "left", "back"):
        f = LEG[key]
        w = f[2] - f[0]
        for ry in range(TOP, 12):
            for rx in range(0, w + 1):
                if ry == TOP:
                    c = lea_ll                       # the cuff, catching light
                elif ry == CUFF:
                    c = lea_d                        # the fold under it
                elif ry <= UPPER[1]:
                    c = lea
                elif ry == WELT_ROW:
                    c = welt
                else:
                    c = sole
                put(im, f[0] + rx, f[1] + ry, c)

        # Lighting: the outer faces catch the light, the inner ones do not.
        tint = {"right": 1.14, "front": 1.04, "left": 0.84, "back": 0.90}[key]
        for ry in range(TOP, 12):
            for rx in range(0, w + 1):
                p = im.getpixel((f[0] + rx, f[1] + ry))
                if p[3]:
                    put(im, f[0] + rx, f[1] + ry, shade(p, tint))

        # The welt, where the sole is stitched on, with the stitches showing.
        for rx in range(0, w + 1, 2):
            put(im, f[0] + rx, f[1] + WELT_ROW, shade(lea_dd, tint))
        # The sole's lower edge is darkest.
        for rx in range(0, w + 1):
            put(im, f[0] + rx, f[1] + SOLE_ROW, sole_d)

        # Scuffing and water blotches, dense near the bottom.
        for ry in range(TOP, WELT_ROW + 1):
            for rx in range(0, w + 1):
                if ry <= CUFF and rng.random() < 0.20:
                    over(im, f[0] + rx, f[1] + ry,
                         (lea_dd[0], lea_dd[1], lea_dd[2], 90))
                elif rng.random() < 0.16:
                    over(im, f[0] + rx, f[1] + ry, (rust[0], rust[1], rust[2], 80))
                elif rng.random() < 0.12:
                    over(im, f[0] + rx, f[1] + ry,
                         (lea_ll[0], lea_ll[1], lea_ll[2], 70))
        # Weed caught in the welt.
        for rx in range(0, w + 1):
            if rng.random() < 0.45:
                over(im, f[0] + rx, f[1] + WELT_ROW - 1,
                     (algae[0], algae[1], algae[2], 150))
            if rng.random() < 0.30:
                over(im, f[0] + rx, f[1] + WELT_ROW,
                     (algae_l[0], algae_l[1], algae_l[2], 120))

    # --- the laces, across the instep
    f = LEG["front"]
    face_box(im, f, 1, CUFF, 2, UPPER[1], shade(lea_dd, 1.05))   # the tongue
    put(im, f[0] + 1, f[1] + CUFF, lace)
    put(im, f[0] + 2, f[1] + CUFF, lace_d)
    put(im, f[0] + 1, f[1] + UPPER[0], lace_d)
    put(im, f[0] + 2, f[1] + UPPER[0], lace)
    put(im, f[0] + 1, f[1] + UPPER[1], lace)
    put(im, f[0] + 2, f[1] + UPPER[1], lace_d)
    put(im, f[0] + 0, f[1] + TOP, (168, 150, 120, 255))          # eyelets
    put(im, f[0] + 3, f[1] + TOP, (168, 150, 120, 255))
    # a loose lace end flopping over the welt
    put(im, f[0] + 3, f[1] + WELT_ROW, lace_d)

    # --- a split on the outside, showing the dark inside of the boot
    f = LEG["right"]
    put(im, f[0] + 1, f[1] + UPPER[0], dark)
    put(im, f[0] + 2, f[1] + UPPER[0], dark)
    put(im, f[0] + 2, f[1] + UPPER[1], dark)
    put(im, f[0] + 1, f[1] + CUFF, shade(lea_ll, 1.1))           # lip of the tear
    put(im, f[0] + 3, f[1] + UPPER[1], shade(lea_ll, 1.1))

    # --- the heel seam up the back
    f = LEG["back"]
    for ry in range(TOP, WELT_ROW):
        put(im, f[0] + 1, f[1] + ry, lea_dd)
        put(im, f[0] + 2, f[1] + ry, shade(lea_l, 0.95))

    # --- the sole, seen from below: a worn tread
    #
    # Lifted well above the colour of the sole's SIDES. A sole lit the same
    # as the shaft disappears into it, and this face is only ever seen
    # against the ground, so it wants to be the lightest thing on the boot.
    tread = (118, 104, 90, 255)
    f = LEG["bottom"]
    face_box(im, f, 0, 0, 3, 3, tread)
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
            # Halved and doubled back, so a texel is a 2x2 block and these
            # match the grain of everything else.
            im = fn()
            w, h = im.size
            im = im.resize((w // 2, h // 2), Image.NEAREST)                    .resize((w, h), Image.NEAREST)
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
