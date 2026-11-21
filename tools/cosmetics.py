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
                if ((x * 7 + y * 13 + w * 3 + h) % 11) == 0:
                    px[x, y] = spot
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

    shell = speckled(brass, patina, top=brass_l, bottom=brass_d)
    plate = flat(brass_l, top=(238, 200, 140, 255), bottom=brass_d)
    return [
        Box((3, 4, 3), (13, 14, 13), shell, "shell"),
        Box((2, 6, 2), (14, 10, 14), flat(brass, top=brass_l, bottom=brass_d), "bulge"),
        Box((2, 2, 2), (14, 4, 14), plate, "collar"),
        Box((5, 6, 1), (11, 12, 3), flat(brass_l, edge=iron), "rim"),
        Box((6, 7, 0), (10, 11, 1), framed(glass, iron, glass_l), "glass"),
        Box((13, 8, 6), (15, 11, 9), framed(glass, brass_l), "port_l"),
        Box((1, 8, 6), (3, 11, 9), framed(glass, brass_l), "port_r"),
        Box((6, 10, 13), (10, 13, 15), banded(rubber, (28, 28, 32, 255), 2), "hose"),
        Box((6, 14, 6), (10, 16, 10), flat(brass_l, bottom=brass_d), "knob"),
    ]


def eternal_ice_cube():
    ice = (142, 206, 232, 255)
    ice_l = (206, 240, 252, 255)
    ice_d = (70, 150, 186, 255)
    white = (238, 250, 255, 255)
    deep = (46, 108, 142, 255)

    body = speckled(ice, white, top=ice_l, bottom=ice_d)
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
    eye = framed(dark, pale)
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
        Box((6, 4, 6), (10, 11, 10), framed(glow, iron, glow_l), "glass"),
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
        Box((3, 2, 4), (13, 9, 12), speckled(wood, moss, top=wood_l, bottom=wood_d), "base"),
        Box((3, 9, 4), (13, 13, 12), banded(wood_l, wood_d, 3, top=(162, 124, 78, 255)), "lid"),
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
