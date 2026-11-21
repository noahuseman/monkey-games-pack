#!/usr/bin/env python3
"""
The worn cosmetics, rebuilt on a single even texel grid.

Every piece here is whole-unit geometry unwrapped with box UV, so one model
unit is one texel on every face of every box - the same density the game's
own blocks are drawn at. See boxuv.py for why that matters and what it
replaced.

Painting is done per FACE, into the face's own patch of the net, by a
function that is handed the patch's real size. That is the other half of
the fix: the art is laid out in the same units as the geometry, so a
sixteen-pixel-wide brass plate is sixteen units of brass plate, not
"however wide this face happens to be".

Usage:  python cosmetics.py <pack-root>
"""

import json
import math
import os
import sys

from PIL import Image

import boxuv
from boxuv import Box

NS = "monkeygames"

# Head pieces are authored against head = 4..12 and blown up on the way out,
# because a worn model is scaled 0.625 by the game and the head really spans
# 1.6..14.4. See docs/cosmetics.md.
WORN = 1.6


# ----------------------------------------------------------------- painting

def shade(c, f):
    return (max(0, min(255, int(c[0] * f))), max(0, min(255, int(c[1] * f))),
            max(0, min(255, int(c[2] * f))), c[3])


def flat(colour, top=None, bottom=None, edge=None):
    """
    A plain surface: one colour, a lit top row, a shadowed bottom row.

    Deliberately almost nothing. At one texel per unit a face is only six or
    ten pixels across, and anything busier than this turns to noise - which
    is how the first helmet ended up looking like a photograph of brass.
    """
    def paint(px, w, h, face):
        for y in range(h):
            for x in range(w):
                c = colour
                if top is not None and y == 0:
                    c = top
                elif bottom is not None and y == h - 1 and h > 1:
                    c = bottom
                elif edge is not None and (x == 0 or x == w - 1) and w > 2:
                    c = edge
                px[x, y] = c
        # The up face is lit and the down face is not, as in game.
        if face == "up":
            for y in range(h):
                for x in range(w):
                    px[x, y] = shade(px[x, y], 1.12)
        elif face == "down":
            for y in range(h):
                for x in range(w):
                    px[x, y] = shade(px[x, y], 0.72)
    return paint


def banded(colour, band, every=3, top=None):
    """Plain, with a band every few rows - planks, ribs, that sort of thing."""
    base = flat(colour, top=top)

    def paint(px, w, h, face):
        base(px, w, h, face)
        for y in range(h):
            if y % every == every - 1:
                for x in range(w):
                    px[x, y] = band
    return paint


def framed(glass, frame, hot=None):
    """A lit pane inside a frame: the lantern, the porthole."""
    def paint(px, w, h, face):
        for y in range(h):
            for x in range(w):
                inner = 0 < x < w - 1 and 0 < y < h - 1
                px[x, y] = glass if inner else frame
        if hot is not None and w > 2 and h > 2:
            for y in range(1, h - 1):
                for x in range(1, w - 1):
                    if (x + y) % 2 == 0:
                        px[x, y] = hot
    return paint


def speckled(colour, spot, top=None, bottom=None):
    """Plain, with a fixed scatter - moss, frost, chromatophores."""
    base = flat(colour, top=top, bottom=bottom)

    def paint(px, w, h, face):
        base(px, w, h, face)
        for y in range(h):
            for x in range(w):
                # Hashed, not counted. A plain modulus of x and y lands the
                # marks on a regular diagonal, which reads as polka dots
                # rather than as weathering - obvious the moment it is on a
                # curved-looking surface.
                hsh = ((x + 1) * 73856093) ^ ((y + 1) * 19349663) ^ (w * 83492791)
                if (hsh >> 7) % 9 == 0:
                    px[x, y] = spot
    return paint



# ------------------------------------------- marks that survive at skin scale
#
# A player skin gives a head 8 pixels across, and that is the budget here:
# one texel per model unit, the same grid as the skin. At that size a mark
# is either a whole pixel or it is nothing, so each helper below places
# WHOLE pixels at known spots rather than shading a gradient. The earlier
# art failed in both directions at once - too fine to read as Minecraft, too
# vague to tell a diving helmet from a bucket.

def rivets(base, stud, inset=1):
    """Studs at the corners of a face. Reads as metal plate at any size."""
    def paint(px, w, h, face):
        base(px, w, h, face)
        if w < 4 or h < 4:
            return
        for x in (inset, w - 1 - inset):
            for y in (inset, h - 1 - inset):
                px[x, y] = stud
    return paint


def seamed(base, seam, rows=(0.5,)):
    """A band straight across a face - a weld, a strap, a waterline."""
    def paint(px, w, h, face):
        base(px, w, h, face)
        for f in rows:
            y = int(h * f)
            if 0 <= y < h:
                for x in range(w):
                    px[x, y] = seam
    return paint


def planks(colour, groove, light):
    """Vertical boards. What makes a wooden box read as a chest."""
    def paint(px, w, h, face):
        for y in range(h):
            for x in range(w):
                px[x, y] = light if y == 0 else colour
        for x in range(w):
            if x % 3 == 2:
                for y in range(h):
                    px[x, y] = groove
    return paint


def cracked(colour, crack, pale):
    """Ice: a pale top, a couple of fractures, nothing else."""
    def paint(px, w, h, face):
        for y in range(h):
            for x in range(w):
                px[x, y] = pale if y < max(1, h // 4) else colour
        # Two fractures, placed from the face size so they never move.
        for i, (sx, sy) in enumerate(((w // 3, h // 3), (2 * w // 3, h // 2))):
            x, y = sx, sy
            for step in range(min(w, h) // 2 + 1):
                if 0 <= x < w and 0 <= y < h:
                    px[x, y] = crack
                x += 1 if (step + i) % 2 else 0
                y += 1
    return paint


def eyed(white, pupil, glint, skin):
    """One big eye: pupil, catchlight, lid. The squid lives or dies on it."""
    def paint(px, w, h, face):
        for y in range(h):
            for x in range(w):
                px[x, y] = skin
        if w < 3 or h < 3:
            return
        for y in range(1, h - 1):
            for x in range(1, w - 1):
                px[x, y] = white
        cx0, cx1 = max(1, w // 2 - 1), min(w - 2, w // 2)
        cy0, cy1 = max(1, h // 2 - 1), min(h - 2, h // 2)
        for y in range(cy0, cy1 + 1):
            for x in range(cx0, cx1 + 1):
                px[x, y] = pupil
        px[cx0, cy0] = glint
    return paint


def glowing(glass, frame, core):
    """A lit pane: bright in the middle, falling off to the frame."""
    def paint(px, w, h, face):
        for y in range(h):
            for x in range(w):
                if x == 0 or x == w - 1 or y == 0 or y == h - 1:
                    px[x, y] = frame
                elif 1 < x < w - 2 and 1 < y < h - 2:
                    px[x, y] = core
                else:
                    px[x, y] = glass
    return paint


# ------------------------------------------------------------------ pieces

def diving_helmet():
    brass = (176, 125, 58, 255)
    brass_l = (214, 166, 92, 255)
    brass_d = (116, 80, 34, 255)
    patina = (92, 142, 112, 255)
    iron = (150, 150, 158, 255)
    glass = (46, 112, 130, 255)
    glass_l = (150, 212, 222, 255)
    rubber = (52, 52, 58, 255)

    shell = rivets(speckled(brass, patina, top=brass_l, bottom=brass_d), iron)
    plate = rivets(flat(brass_l, top=(238, 200, 140, 255), bottom=brass_d), iron)
    return [
        Box((3, 4, 3), (13, 14, 13), shell, "shell"),
        Box((2, 6, 2), (14, 10, 14),
            seamed(flat(brass, top=brass_l, bottom=brass_d), brass_d), "bulge"),
        Box((2, 2, 2), (14, 4, 14), plate, "collar"),
        Box((5, 6, 1), (11, 12, 3), rivets(flat(brass_l), iron, 0), "rim"),
        Box((6, 7, 0), (10, 11, 1), glowing(glass, iron, glass_l), "glass"),
        Box((13, 8, 6), (15, 11, 9), glowing(glass, brass_l, glass_l), "port_l"),
        Box((1, 8, 6), (3, 11, 9), glowing(glass, brass_l, glass_l), "port_r"),
        Box((6, 10, 13), (10, 13, 15), banded(rubber, (28, 28, 32, 255), 2), "hose"),
        Box((6, 14, 6), (10, 16, 10), flat(brass_l, bottom=brass_d), "knob"),
    ]


def eternal_ice_cube():
    ice = (142, 206, 232, 255)
    ice_l = (206, 240, 252, 255)
    ice_d = (70, 150, 186, 255)
    white = (238, 250, 255, 255)
    deep = (46, 108, 142, 255)

    body = cracked(ice, deep, ice_l)
    shard = flat(ice_l, bottom=ice)
    icicle = flat(ice, bottom=deep)
    return [
        Box((2, 2, 2), (14, 15, 14), body, "cube"),
        Box((1, 15, 1), (15, 16, 15), speckled(white, ice_l), "rime"),
        Box((3, 0, 3), (4, 2, 4), icicle, "ic1"),
        Box((11, -1, 3), (12, 2, 4), icicle, "ic2"),
        Box((3, 0, 11), (4, 2, 12), icicle, "ic3"),
        Box((11, 0, 11), (12, 2, 12), icicle, "ic4"),
        Box((7, -2, 2), (8, 2, 3), icicle, "ic5"),
        Box((4, 16, 4), (6, 19, 6), shard, "sh1"),
        Box((10, 16, 9), (12, 20, 11), shard, "sh2"),
        Box((7, 16, 11), (8, 18, 12), shard, "sh3"),
    ]


def pink_squid():
    pink = (226, 98, 156, 255)
    pink_l = (246, 156, 196, 255)
    pink_d = (166, 56, 108, 255)
    pale = (252, 206, 226, 255)
    spot = (140, 42, 88, 255)
    dark = (40, 16, 32, 255)

    mantle = speckled(pink, spot, top=pink_l, bottom=pink_d)
    arm = flat(pink, top=pink_l, bottom=pink_d, edge=pink_d)
    eye = eyed(pale, dark, (255, 255, 255, 255), pink_d)
    boxes = [
        Box((3, 4, 3), (13, 14, 13), mantle, "mantle"),
        Box((4, 14, 4), (12, 17, 12), flat(pink_d, top=pink), "taper"),
        Box((6, 17, 6), (10, 19, 10), flat(pink_d, top=pink), "tip"),
        Box((12, 8, 5), (14, 11, 9), eye, "eye_l"),
        Box((2, 8, 5), (4, 11, 9), eye, "eye_r"),
        Box((13, 11, 5), (15, 13, 11), flat(pale, bottom=pink), "fin_l"),
        Box((1, 11, 5), (3, 13, 11), flat(pale, bottom=pink), "fin_r"),
        Box((7, 3, 2), (9, 5, 4), flat(dark), "beak"),
    ]
    # Eight arms round the rim, at uneven lengths.
    for i, (x, z, drop) in enumerate((
            (4, 2, 0), (7, 2, -2), (10, 2, 1),
            (2, 5, 0), (2, 10, 1), (12, 5, 1), (12, 10, 0), (7, 12, 0))):
        boxes.append(Box((x, drop, z), (x + 2, 5, z + 2), arm, "arm%d" % i))
    return boxes


def held_lantern():
    iron = (78, 90, 98, 255)
    iron_l = (126, 142, 150, 255)
    iron_d = (44, 54, 62, 255)
    glow = (150, 232, 248, 255)
    glow_l = (226, 250, 255, 255)
    cap = flat(iron, top=iron_l, bottom=iron_d)
    return [
        Box((5, 2, 5), (11, 4, 11), cap, "foot"),
        Box((6, 4, 6), (10, 11, 10), glowing(glow, iron, glow_l), "glass"),
        Box((5, 11, 5), (11, 13, 11), cap, "cap"),
        Box((7, 13, 7), (9, 15, 9), flat(iron_l), "hook"),
        Box((7, 15, 7), (9, 16, 9), flat(iron_l), "ring"),
    ]


def held_chest():
    wood = (108, 76, 42, 255)
    wood_l = (140, 102, 60, 255)
    wood_d = (72, 48, 24, 255)
    moss = (70, 110, 62, 255)
    gold = (214, 165, 43, 255)
    leather = (64, 46, 30, 255)
    return [
        # The lid is painted markedly lighter than the base, with a dark
        # seam under it. Planked identically they read as one crate, and a
        # crate is not a chest - the lid line is the whole silhouette.
        Box((3, 2, 4), (13, 9, 12),
            seamed(planks(wood, wood_d, wood_l), wood_d, (0.0,)), "base"),
        Box((3, 9, 4), (13, 13, 12),
            planks((168, 128, 80, 255), (120, 88, 50, 255),
                   (196, 156, 104, 255)), "lid"),
        Box((7, 8, 3), (9, 11, 4), flat(gold, bottom=(150, 110, 20, 255)), "lock"),
        Box((4, 2, 12), (6, 13, 13), flat(leather, top=(96, 72, 48, 255)), "strap_l"),
        Box((10, 2, 12), (12, 13, 13), flat(leather, top=(96, 72, 48, 255)), "strap_r"),
    ]


PIECES = {
    "deep_sea_diving_helmet": (diving_helmet, True),
    "eternal_ice_cube": (eternal_ice_cube, True),
    "pink_squid": (pink_squid, True),
    "held/phantom_lantern": (held_lantern, False),
    "held/sunken_treasure_chest": (held_chest, False),
}


def grow(b):
    """A box at worn size, snapped back onto whole units."""
    def g(c):
        return int(round(8 + (c - 8) * WORN))
    return Box((g(b.x0), g(b.y0), g(b.z0)), (g(b.x1), g(b.y1), g(b.z1)),
               b.paint, b.name)



# ------------------------------------------------------------------ lily pad
#
# The odd one out, and it earns it: the pad is a disc, not a box, so box UV
# has nothing to unwrap. It is cut into slices across z, each one as wide as
# the circle is at its narrow end, and the alpha in the texture rounds off
# what the slices leave square.
#
# The density still has to match everything else. The disc sheet is one
# texel per model unit, and the model is authored at FINAL size - no 1.6x
# afterwards - so a pad texel is a skin texel. The slices' edge faces read a
# single row straight out of the disc at the z they sit at, which is both
# exactly one texel tall on a one-unit slab and, usefully, the leaf's own
# rim colours, so edge and surface cannot drift apart.

LILY_R = 18           # radius, in model units, at worn size
LILY_Y = 15           # rests just above the head, which tops out at 14.4
LILY_SPAN = 64        # the disc sheet covers this many units each way
LILY_LO = 8 - LILY_SPAN // 2
NOTCH = math.radians(13.0)


def _lily_colour(wx, wz, under):
    green = (86, 140, 56, 255)
    green_d = (58, 102, 40, 255)
    green_dd = (38, 70, 28, 255)
    green_l = (120, 174, 78, 255)
    vein = (48, 88, 34, 255)
    under_c = (124, 76, 106, 255)
    under_d = (84, 50, 74, 255)
    under_l = (156, 102, 136, 255)

    dx, dz = wx - 8, wz - 8
    r = math.hypot(dx, dz)
    if r > LILY_R:
        return None
    if abs(math.atan2(dx, -dz)) < NOTCH:
        return None                      # the notch, opening forwards
    k = r / LILY_R
    if under:
        c = under_l if k < 0.5 else under_c
        if k > 0.88:
            c = under_d
        if abs(math.sin(math.atan2(dz, dx) * 9.0)) > 0.85 and r > 2:
            c = under_d
        return c
    # Top: flat green, a darker rim, veins out of the middle.
    c = green_l if (int(wx) + int(wz)) % 7 == 0 else green
    if k > 0.90:
        c = green_dd
    elif k > 0.80:
        c = green_d
    if abs(math.sin(math.atan2(dz, dx) * 7.0)) > 0.90 and r > 3:
        c = vein
    if r < 2:
        c = green_dd
    return c


def lily_pad(root):
    """Builds its own model: slices plus a box-UV flower."""
    n = LILY_SPAN
    disc = Image.new("RGBA", (n * 2, n), (0, 0, 0, 0))
    dpx = disc.load()
    for half, under in ((0, False), (n, True)):
        for py in range(n):
            for px_ in range(n):
                wx = LILY_LO + px_ + 0.5
                wz = (LILY_LO + n - 1 - py + 0.5) if under else (LILY_LO + py + 0.5)
                c = _lily_colour(wx, wz, under)
                if c:
                    dpx[half + px_, py] = c

    # uv is a fraction of the sheet, so these are plain linear maps.
    def u_top(w):  return (w - LILY_LO) / (n * 2.0) * 16.0
    def u_bot(w):  return (w - LILY_LO + n) / (n * 2.0) * 16.0
    def v_top(w):  return (w - LILY_LO) / float(n) * 16.0
    def v_bot(w):  return (LILY_LO + n - w) / float(n) * 16.0
    texel_u = 16.0 / (n * 2.0)
    texel_v = 16.0 / n

    bands = [(-10, -7), (-7, -3), (-3, 1), (1, 5), (5, 11),
             (11, 15), (15, 19), (19, 23), (23, 26)]
    els = []
    for z0, z1 in bands:
        dz = max(abs(z0 - 8), abs(z1 - 8))
        hw = int(math.sqrt(max(0.0, LILY_R ** 2 - dz ** 2)))
        if hw < 1:
            continue
        x0, x1 = 8 - hw, 8 + hw
        els.append({
            "from": [x0, LILY_Y, z0], "to": [x1, LILY_Y + 1, z1],
            "faces": {
                "up":    {"uv": [u_top(x0), v_top(z0), u_top(x1), v_top(z1)],
                          "texture": "#0"},
                "down":  {"uv": [u_bot(x0), v_bot(z1), u_bot(x1), v_bot(z0)],
                          "texture": "#0"},
                "north": {"uv": [u_top(x0), v_top(z0), u_top(x1), v_top(z0) + texel_v],
                          "texture": "#0"},
                "south": {"uv": [u_top(x0), v_top(z1) - texel_v, u_top(x1), v_top(z1)],
                          "texture": "#0"},
                # Turned a quarter, and it has to be.
                #
                # On a north face the texture's u runs along x, which is
                # what that face needs. On an east or west face u runs
                # along Z - so the same column of pixels arrives on its
                # side, one texel wide against a face that is several
                # units wide and one unit tall. The face rotation puts it
                # back the right way round and the density with it.
                "west":  {"uv": [u_top(x0), v_top(z0), u_top(x0) + texel_u, v_top(z1)],
                          "rotation": 90, "texture": "#0"},
                "east":  {"uv": [u_top(x1) - texel_u, v_top(z0), u_top(x1), v_top(z1)],
                          "rotation": 90, "texture": "#0"},
            }})

    # The flower, as ordinary boxes on their own sheet.
    petal = (238, 180, 210, 255)
    petal_l = (255, 226, 240, 255)
    petal_d = (196, 118, 156, 255)
    gold = (240, 200, 74, 255)
    stem = (86, 140, 56, 255)
    fx, fz = 14, 14
    flower = [
        Box((fx - 3, LILY_Y + 1, fz - 3), (fx + 3, LILY_Y + 2, fz + 3),
            flat(stem, top=(120, 174, 78, 255)), "calyx"),
        Box((fx - 5, LILY_Y + 2, fz - 2), (fx + 5, LILY_Y + 3, fz + 2),
            flat(petal, top=petal_l, bottom=petal_d), "petal_x"),
        Box((fx - 2, LILY_Y + 2, fz - 5), (fx + 2, LILY_Y + 3, fz + 5),
            flat(petal, top=petal_l, bottom=petal_d), "petal_z"),
        Box((fx - 1, LILY_Y + 3, fz - 1), (fx + 1, LILY_Y + 4, fz + 1),
            flat(gold, top=(255, 232, 150, 255)), "heart"),
    ]
    sheet = boxuv.pack(flower)
    fim = Image.new("RGBA", sheet, (0, 0, 0, 0))
    fpx = fim.load()
    for b in flower:
        for face, (rx, ry, rw, rh) in b.regions().items():
            patch = Image.new("RGBA", (rw, rh), (0, 0, 0, 0))
            b.paint(patch.load(), rw, rh, face)
            fim.paste(patch, (rx, ry))
    els += [boxuv.element(b, sheet, "#1") for b in flower]

    base = NS + ":item/catch/worn/lily_pad"
    model = {"textures": {"0": base, "1": base + "_flower", "particle": base},
             "elements": els}
    return disc, fim, model


# ------------------------------------------------------------------- build

def build(name, boxes, worn):
    # Blow head pieces up to the size they are actually worn at BEFORE
    # unwrapping them, and round to whole units.
    #
    # Scaling afterwards would be uniform and therefore even, but it would
    # be even at 0.625 texels per unit while the carried pieces sat at 1.0 -
    # consistent within each piece and inconsistent between them, which is
    # the same complaint one level up. Scaling first makes one texel mean
    # the same thing on every cosmetic on the server.
    if worn:
        boxes = [grow(b) for b in boxes]
    sheet = boxuv.pack(boxes)
    im = Image.new("RGBA", sheet, (0, 0, 0, 0))
    px = im.load()

    for b in boxes:
        for face, (rx, ry, rw, rh) in b.regions().items():
            patch = Image.new("RGBA", (rw, rh), (0, 0, 0, 0))
            b.paint(patch.load(), rw, rh, face)
            im.paste(patch, (rx, ry))

    tex = NS + ":item/catch/worn/" + name
    elements = [boxuv.element(b, sheet) for b in boxes]
    model = {"textures": {"0": tex, "particle": tex}, "elements": elements}
    return im, model, sheet


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        return 1
    root = sys.argv[1]
    if not os.path.isfile(os.path.join(root, "pack.mcmeta")):
        print("not a pack root: " + root)
        return 1
    a = os.path.join(root, "assets", NS)

    for name, (fn, worn) in PIECES.items():
        boxes = fn()
        im, model, sheet = build(name, boxes, worn)
        parts = name.split("/")

        tp = os.path.join(a, "textures", "item", "catch", "worn", *parts) + ".png"
        mp = os.path.join(a, "models", "item", "catch", "worn", *parts) + ".json"
        os.makedirs(os.path.dirname(tp), exist_ok=True)
        os.makedirs(os.path.dirname(mp), exist_ok=True)
        im.save(tp)
        with open(mp, "w", newline="\n") as f:
            json.dump(model, f, indent=2)
            f.write("\n")
        print("%-30s %2d boxes  %dx%d" % (name, len(boxes), sheet[0], sheet[1]))

    disc, fim, model = lily_pad(root)
    tdir = os.path.join(a, "textures", "item", "catch", "worn")
    disc.save(os.path.join(tdir, "lily_pad.png"))
    fim.save(os.path.join(tdir, "lily_pad_flower.png"))
    with open(os.path.join(a, "models", "item", "catch", "worn",
                           "lily_pad.json"), "w", newline="\n") as f:
        json.dump(model, f, indent=2)
        f.write("\n")
    print("%-30s %2d elements  %dx%d + %dx%d" % (
        "lily_pad", len(model["elements"]), disc.size[0], disc.size[1],
        fim.size[0], fim.size[1]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
