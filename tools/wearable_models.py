#!/usr/bin/env python3
"""
Builds the box models for the four fishing catches worn on the head, and
rewrites their item definitions to use them.

Worn model space is one whole block, 0-16 on each axis. The player's head
occupies 4-12 in all three and faces -Z, so anything inside 4-12 hugs the
skull and anything outside it is overhang. That is the only measurement
these models need, and every number below is placed against it.

Only the `head` display context gets the model. In the inventory, in the
hand and on the ground the catch keeps the flat sprite it has always had,
which is deliberate: the 3D piece is a thing you WEAR, and a bulky model
in the hotbar would make nine fishing catches look like armour.

The item definition becomes a select on display_context with one case, a
pattern this pack already uses for the fishing rod.

Usage:  python wearable_models.py <pack-root>
"""

import json
import math
import os
import sys

NS = "monkeygames"


# A 16x16 tile of a 64x64 atlas, as model uv (always 0-16 over the image).
def tile(col, row):
    return [col * 4, row * 4, col * 4 + 4, row * 4 + 4]


# How much bigger a worn model has to be drawn than it looks on paper.
#
# CustomHeadLayer.translateToHead scales a worn model by 0.625, so a
# 16-unit model box is 0.625 blocks - only 1.25x the width of the 0.5-block
# head, not the 2x it would be at 1:1. The head therefore occupies units
# 1.6 to 14.4 of the model, not 4 to 12.
#
# Everything below is authored against head = 4..12, because that is the
# readable way to think about it, and scaled on the way out. The first
# build shipped unscaled and every head piece came out smaller than the
# skull it was meant to cover.
WORN_SCALE = 6.4 / 4.0          # 1.6
WORN_MID = 8.0

# Carried pieces are authored at true size and get no head correction, so
# the scale is switched off while they are built.
CUR_SCALE = [WORN_SCALE]


def _s(c):
    return round(WORN_MID + (c - WORN_MID) * CUR_SCALE[0], 4)


def el(frm, to, faces, rotation=None):
    e = {"from": [_s(c) for c in frm], "to": [_s(c) for c in to], "faces": faces}
    if rotation:
        r = dict(rotation)
        r["origin"] = [_s(c) for c in r["origin"]]
        e["rotation"] = r
    return e


def faces(spec):
    """spec: {dir: (texture_ref, uv)} -> model face objects."""
    return {d: {"uv": [round(v, 4) for v in uv], "texture": tex}
            for d, (tex, uv) in spec.items()}


def allsides(tex, uv, up=None, down=None):
    s = {d: (tex, uv) for d in ("north", "south", "east", "west")}
    if up:
        s["up"] = up
    if down:
        s["down"] = down
    return s


# ======================================================= deep-sea diving helmet

def diving_helmet():
    T = "#0"
    side, front, back, top = tile(0, 0), tile(1, 0), tile(2, 0), tile(3, 0)
    collar, dome, rim, glass = tile(0, 1), tile(1, 1), tile(2, 1), tile(3, 1)
    port, hose, knob, inner = tile(0, 2), tile(1, 2), tile(2, 2), tile(3, 2)

    els = []
    # The shell. One unit of clearance round the head on every side.
    els.append(el([3, 4, 3], [13, 13.5, 13], faces({
        "north": (T, front), "south": (T, back),
        "east": (T, side), "west": (T, side),
        "up": (T, top), "down": (T, inner)})))
    # The bulge at eye level, which is what makes it a diving helmet rather
    # than a bucket: real ones are widest across the face plate.
    els.append(el([2.2, 5.5, 2.2], [13.8, 10.5, 13.8], faces({
        "north": (T, side), "south": (T, side),
        "east": (T, side), "west": (T, side),
        "up": (T, top), "down": (T, top)})))
    # Crown and finial.
    els.append(el([4, 13.5, 4], [12, 15, 12],
                  faces(allsides(T, dome, up=(T, top)))))
    els.append(el([6.5, 15, 6.5], [9.5, 16, 9.5],
                  faces(allsides(T, knob, up=(T, knob)))))
    # The collar, sitting on the shoulders.
    els.append(el([1.5, 2.5, 1.5], [14.5, 4.2, 14.5],
                  faces(allsides(T, collar, up=(T, collar), down=(T, inner)))))
    # The face plate: a brass ring with the glass standing proud of it, so
    # the ring reads as a frame rather than as a painted circle. Pulled in
    # far enough to leave the bolt ring painted on the shell visible.
    els.append(el([4.8, 5.8, 1.4], [11.2, 12.2, 3.3], faces({
        "north": (T, rim), "east": (T, rim), "west": (T, rim),
        "up": (T, rim), "down": (T, rim)})))
    els.append(el([5.7, 6.7, 0.7], [10.3, 11.3, 1.5], faces({
        "north": (T, glass), "east": (T, rim), "west": (T, rim),
        "up": (T, rim), "down": (T, rim)})))
    # Two side ports.
    els.append(el([12.9, 7.5, 6.2], [14.3, 10.5, 9.8], faces({
        "east": (T, port), "north": (T, rim), "south": (T, rim),
        "up": (T, rim), "down": (T, rim)})))
    els.append(el([1.7, 7.5, 6.2], [3.1, 10.5, 9.8], faces({
        "west": (T, port), "north": (T, rim), "south": (T, rim),
        "up": (T, rim), "down": (T, rim)})))
    # Air hose, out of the back of the neck.
    els.append(el([6.2, 9.5, 12.9], [9.8, 12.5, 14.6],
                  faces(allsides(T, collar, up=(T, collar), down=(T, collar)))))
    els.append(el([7, 10.4, 14.4], [9, 12, 16.4],
                  faces(allsides(T, hose, up=(T, hose), down=(T, hose))),
                  {"angle": 22.5, "axis": "x", "origin": [8, 11.2, 14.4]}))
    return {"textures": {"0": NS + ":item/catch/worn/deep_sea_diving_helmet",
                         "particle": NS + ":item/catch/worn/deep_sea_diving_helmet"},
            "elements": els}


# ============================================================= eternal ice cube

def eternal_ice_cube():
    T = "#0"
    side, front, top = tile(0, 0), tile(1, 0), tile(2, 0)
    bottom, frost, icic = tile(3, 0), tile(0, 1), tile(1, 1)
    cryst, back = tile(2, 1), tile(3, 1)

    els = []
    # The block itself, two units clear of the head on every side so the
    # player is plainly INSIDE it rather than wearing it.
    els.append(el([2, 2.5, 2], [14, 14.5, 14], faces({
        "north": (T, front), "south": (T, back),
        "east": (T, side), "west": (T, side),
        "up": (T, top), "down": (T, bottom)})))
    # A crust of rime over the top.
    els.append(el([1.4, 14.5, 1.4], [14.6, 15.6, 14.6],
                  faces(allsides(T, frost, up=(T, frost)))))
    # Icicles. Different lengths, and one hanging past the face, because a
    # matched set round the rim reads as a machined object.
    for frm, to in (([3.0, 0.4, 3.0], [4.4, 2.6, 4.4]),
                    ([11.2, -0.8, 3.4], [12.6, 2.6, 4.8]),
                    ([3.4, 0.9, 11.4], [4.8, 2.6, 12.8]),
                    ([11.0, -0.2, 11.0], [12.4, 2.6, 12.4]),
                    ([7.2, -1.4, 2.2], [8.6, 2.6, 3.6])):
        els.append(el(frm, to, faces(allsides(T, icic, down=(T, icic)))))
    # Shards growing out of the crust and the sides.
    els.append(el([4.6, 15.4, 4.6], [6.2, 18.2, 6.2],
                  faces(allsides(T, cryst, up=(T, cryst))),
                  {"angle": 22.5, "axis": "z", "origin": [5.4, 15.4, 5.4]}))
    els.append(el([9.6, 15.4, 8.4], [11.0, 19.0, 9.8],
                  faces(allsides(T, cryst, up=(T, cryst))),
                  {"angle": -22.5, "axis": "x", "origin": [10.3, 15.4, 9.1]}))
    els.append(el([7.0, 15.4, 11.0], [8.2, 17.4, 12.2],
                  faces(allsides(T, cryst, up=(T, cryst)))))
    els.append(el([13.6, 6.0, 6.2], [15.6, 8.4, 8.0],
                  faces(allsides(T, cryst, up=(T, cryst), down=(T, cryst))),
                  {"angle": 22.5, "axis": "z", "origin": [13.6, 7.2, 7.1]}))
    els.append(el([0.4, 9.0, 8.4], [2.4, 10.8, 10.2],
                  faces(allsides(T, cryst, up=(T, cryst), down=(T, cryst))),
                  {"angle": -22.5, "axis": "z", "origin": [2.4, 9.9, 9.3]}))
    return {"textures": {"0": NS + ":item/catch/worn/eternal_ice_cube",
                         "particle": NS + ":item/catch/worn/eternal_ice_cube"},
            "elements": els}


# ================================================================== pink squid

def pink_squid():
    T = "#0"
    side, front, top, back = tile(0, 0), tile(1, 0), tile(2, 0), tile(3, 0)
    eye, arm, fin, tip = tile(0, 1), tile(1, 1), tile(2, 1), tile(3, 1)
    beak = tile(0, 2)

    els = []
    # The mantle, pulled down to just above the chin.
    els.append(el([3, 4.5, 3], [13, 14, 13], faces({
        "north": (T, front), "south": (T, back),
        "east": (T, side), "west": (T, side),
        "up": (T, top), "down": (T, beak)})))
    # Tapering to a point, in three steps.
    els.append(el([4.2, 14, 4.2], [11.8, 16.2, 11.8],
                  faces(allsides(T, tip, up=(T, tip)))))
    els.append(el([6, 16.2, 6], [10, 18.4, 10],
                  faces(allsides(T, tip, up=(T, tip)))))
    els.append(el([7, 18.4, 7], [9, 19.6, 9],
                  faces(allsides(T, tip, up=(T, tip)))))
    # Fins, angled off the upper mantle.
    els.append(el([12.8, 10.5, 5.2], [14.8, 13.2, 11.2],
                  faces(allsides(T, fin, up=(T, fin), down=(T, fin))),
                  {"angle": 22.5, "axis": "z", "origin": [12.8, 12, 8]}))
    els.append(el([1.2, 10.5, 5.2], [3.2, 13.2, 11.2],
                  faces(allsides(T, fin, up=(T, fin), down=(T, fin))),
                  {"angle": -22.5, "axis": "z", "origin": [3.2, 12, 8]}))
    # The eyes, bulging out of the sides where a squid's actually are.
    els.append(el([12.6, 7.2, 5.6], [14.4, 10.8, 9.4], faces({
        "east": (T, eye), "north": (T, side), "south": (T, side),
        "up": (T, side), "down": (T, side)})))
    els.append(el([1.6, 7.2, 5.6], [3.4, 10.8, 9.4], faces({
        "west": (T, eye), "north": (T, side), "south": (T, side),
        "up": (T, side), "down": (T, side)})))
    # The beak, under the mantle at the front.
    els.append(el([7, 3.4, 2.6], [9, 4.8, 4.2],
                  faces(allsides(T, beak, down=(T, beak)))))
    # Eight arms round the rim. Uneven lengths and a few of them hanging
    # crooked; a ring of identical straight ones looks like a lampshade.
    arms = (
        ([4.4, 0.8, 2.9], [5.8, 4.8, 4.3], None),
        ([7.3, -0.6, 2.9], [8.7, 4.8, 4.3],
         {"angle": -22.5, "axis": "x", "origin": [8, 4.8, 3.6]}),
        ([10.2, 1.2, 2.9], [11.6, 4.8, 4.3], None),
        ([2.9, 0.4, 4.6], [4.3, 4.8, 6.0],
         {"angle": 22.5, "axis": "z", "origin": [3.6, 4.8, 5.3]}),
        ([2.9, 1.6, 9.8], [4.3, 4.8, 11.2], None),
        ([11.7, 0.9, 4.6], [13.1, 4.8, 6.0], None),
        ([11.7, 1.9, 9.8], [13.1, 4.8, 11.2],
         {"angle": -22.5, "axis": "z", "origin": [12.4, 4.8, 10.5]}),
        ([7.3, 1.4, 11.6], [8.7, 4.8, 13.0], None),
    )
    for frm, to, rot in arms:
        els.append(el(frm, to, faces(allsides(T, arm, down=(T, arm))), rot))
    return {"textures": {"0": NS + ":item/catch/worn/pink_squid",
                         "particle": NS + ":item/catch/worn/pink_squid"},
            "elements": els}


# ==================================================================== lily pad
#
# The pad is a disc 22 blocks-of-model across, built out of seven bars
# stacked front to back. Bars rather than one square slab because a square
# would need its corners cut by alpha on the top AND bottom AND leave four
# right-angled side faces sticking out of a round leaf; and bars rather than
# crossed boxes at an angle because every bar is axis-aligned, which means
# each one can read its patch of the pad straight out of the texture with no
# rotation to get backwards.
#
# They never overlap - each owns a slice of z - so no two faces are coplanar
# and there is nothing to z-fight. Each bar is cut to the widest point of
# its own slice, and the alpha in the texture rounds off the rest.
#
# The notch is a transparent wedge in the texture, opening towards -Z, which
# is the way the wearer faces.

PAD_LO, PAD_HI = -4.0, 20.0
PAD_Y0, PAD_Y1 = 12.9, 13.8
PAD_R = 11.0


def _u(w):
    return (w - PAD_LO) / (PAD_HI - PAD_LO) * 8.0


def _vt(w):
    return (w - PAD_LO) / (PAD_HI - PAD_LO) * 16.0


def _vb(w):
    # The underside half of the sheet is written with z running upwards, to
    # match the way a `down` face runs its v along -z.
    return (PAD_HI - w) / (PAD_HI - PAD_LO) * 16.0


def lily_pad():
    PAD, TRIM = "#0", "#1"
    edge = tile(3, 0)
    petal, petal_u, centre, stalk = tile(0, 0), tile(1, 0), tile(2, 0), tile(1, 1)

    def halfwidth(dz):
        return math.sqrt(max(0.0, PAD_R * PAD_R - dz * dz))

    # Slice boundaries, chosen so the disc's half-width drops by a roughly
    # even step each time rather than by an even distance - a circle turns
    # fastest at its ends, so the slices have to get thinner there or the
    # last one is a plank.
    #
    # The frontmost sliver is left out: the notch eats all of it.
    cuts = [-2.04, -0.87, 0.45, 1.67, 3.42, 4.72, 6.5, 9.5,
            11.28, 12.58, 14.33, 15.55, 16.87, 18.04, 18.82]
    slices = list(zip(cuts, cuts[1:]))

    els = []
    for z0, z1 in slices:
        # Cut each slice to its NARROW end - the end further from the middle.
        #
        # Cutting to the wide end instead gives a rounder silhouette on the
        # flat of the leaf, because the alpha then trims the corners. It
        # also leaves the slice's far edge face hanging out past the disc,
        # and an edge face is opaque: the first build had green hairlines
        # sticking out of the back of the leaf. Narrow end it is, and the
        # steps between slices read as the edge of a round thing.
        dz = max(abs(z0 - 8.0), abs(z1 - 8.0))
        hw = halfwidth(dz)
        x0, x1 = round(8.0 - hw, 3), round(8.0 + hw, 3)
        els.append(el(
            [x0, PAD_Y0, z0], [x1, PAD_Y1, z1],
            faces({
                "up":    (PAD, [_u(x0), _vt(z0), _u(x1), _vt(z1)]),
                "down":  (PAD, [_u(x0) + 8, _vb(z1), _u(x1) + 8, _vb(z0)]),
                "north": (TRIM, edge), "south": (TRIM, edge),
                "east":  (TRIM, edge), "west": (TRIM, edge)})))

    # A water lily, off to one side so it does not read as a propeller.
    fx, fz = 11.0, 11.0
    els.append(el([fx - 1.8, PAD_Y1, fz - 1.8], [fx + 1.8, 14.3, fz + 1.8],
                  faces(allsides(TRIM, stalk, up=(TRIM, stalk)))))
    for frm, to, rot in (
            ([fx - 3.6, 14.2, fz - 1.4], [fx + 3.6, 14.75, fz + 1.4], None),
            ([fx - 1.4, 14.2, fz - 3.6], [fx + 1.4, 14.75, fz + 3.6], None),
            ([fx - 2.6, 14.7, fz - 0.9], [fx + 2.6, 15.25, fz + 0.9],
             {"angle": 45, "axis": "y", "origin": [fx, 15.0, fz]}),
            ([fx - 0.9, 14.7, fz - 2.6], [fx + 0.9, 15.25, fz + 2.6],
             {"angle": 45, "axis": "y", "origin": [fx, 15.0, fz]})):
        els.append(el(frm, to, faces(
            allsides(TRIM, petal, up=(TRIM, petal), down=(TRIM, petal_u))), rot))
    els.append(el([fx - 0.9, 15.1, fz - 0.9], [fx + 0.9, 15.9, fz + 0.9],
                  faces(allsides(TRIM, centre, up=(TRIM, centre)))))

    return {"textures": {"0": NS + ":item/catch/worn/lily_pad",
                         "1": NS + ":item/catch/worn/lily_pad_trim",
                         "particle": NS + ":item/catch/worn/lily_pad"},
            "elements": els}



# ================================== the pieces carried as objects on the body
#
# Authored at true size: 16 units is one block, and the plugin scales each
# one down to where it looks right on a player. Four or five boxes apiece -
# enough to have sides, not enough to stop looking like Minecraft.

def held_lantern():
    T = "#0"
    cap, glass, dark, hook = tile(0, 0), tile(1, 0), tile(2, 0), tile(3, 0)
    els = [
        el([5, 2, 5], [11, 4, 11], faces(allsides(T, cap, up=(T, cap), down=(T, dark)))),
        el([5.5, 4, 5.5], [10.5, 11, 10.5], faces(allsides(T, glass))),
        el([4.5, 11, 4.5], [11.5, 13, 11.5],
           faces(allsides(T, cap, up=(T, cap), down=(T, dark)))),
        el([7.25, 13, 7.25], [8.75, 15, 8.75],
           faces(allsides(T, hook, up=(T, hook)))),
        el([6.5, 15, 7.5], [9.5, 16, 8.5],
           faces(allsides(T, hook, up=(T, hook), down=(T, hook)))),
    ]
    return {"textures": {"0": NS + ":item/catch/worn/held/phantom_lantern",
                         "particle": NS + ":item/catch/worn/held/phantom_lantern"},
            "elements": els}


def held_chest():
    T = "#0"
    base, lid, lock, strap = tile(0, 0), tile(1, 0), tile(2, 0), tile(3, 0)
    els = [
        el([3, 2, 4], [13, 9, 12], faces(allsides(T, base, up=(T, base), down=(T, base)))),
        el([3, 9, 4], [13, 13, 12], faces(allsides(T, lid, up=(T, lid), down=(T, lid)))),
        el([7, 7.5, 3.4], [9, 11, 4.2], faces(allsides(T, lock, up=(T, lock), down=(T, lock)))),
        el([4.5, 2, 11.9], [6, 13, 13], faces(allsides(T, strap, up=(T, strap), down=(T, strap)))),
        el([10, 2, 11.9], [11.5, 13, 13], faces(allsides(T, strap, up=(T, strap), down=(T, strap)))),
    ]
    return {"textures": {"0": NS + ":item/catch/worn/held/sunken_treasure_chest",
                         "particle": NS + ":item/catch/worn/held/sunken_treasure_chest"},
            "elements": els}


def held_boot():
    T = "#0"
    upper, shaft, sole, tread = tile(0, 0), tile(1, 0), tile(2, 0), tile(3, 0)
    els = [
        el([4, 1, 2], [12, 3, 13], faces(allsides(T, sole, up=(T, sole), down=(T, tread)))),
        el([4, 3, 2], [12, 7, 13], faces(allsides(T, upper, up=(T, upper), down=(T, sole)))),
        el([4.5, 7, 7], [11.5, 13, 13], faces(allsides(T, shaft, up=(T, shaft), down=(T, upper)))),
        el([4.2, 3, 1.4], [11.8, 6, 2.6], faces(allsides(T, upper, up=(T, upper), down=(T, sole)))),
    ]
    return {"textures": {"0": NS + ":item/catch/worn/held/old_boot",
                         "particle": NS + ":item/catch/worn/held/old_boot"},
            "elements": els}


# The boot is not here: it is drawn by its armour layer, which bends with
# the leg. See docs/cosmetics.md.
HELD = {
    "phantom_lantern": held_lantern,
    "sunken_treasure_chest": held_chest,
}

# ---------------------------------------------------------------------- output

MODELS = {
    "deep_sea_diving_helmet": diving_helmet,
    "eternal_ice_cube": eternal_ice_cube,
    "pink_squid": pink_squid,
}


def held_definition(slug):
    return {"model": {"type": "minecraft:model",
                      "model": NS + ":item/catch/worn/held/" + slug}}


def item_definition(slug):
    """Flat sprite everywhere except on a head, where the model takes over."""
    return {
        "model": {
            "type": "minecraft:select",
            "property": "minecraft:display_context",
            "cases": [
                {"when": ["head"],
                 "model": {"type": "minecraft:model",
                           "model": NS + ":item/catch/worn/" + slug}}
            ],
            "fallback": {"type": "minecraft:model",
                         "model": NS + ":item/catch/" + slug}
        }
    }


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        return 1
    root = sys.argv[1]
    if not os.path.isfile(os.path.join(root, "pack.mcmeta")):
        print("not a pack root (no pack.mcmeta): " + root)
        return 1

    mdir = os.path.join(root, "assets", NS, "models", "item", "catch", "worn")
    idir = os.path.join(root, "assets", NS, "items", "catch")
    os.makedirs(mdir, exist_ok=True)
    os.makedirs(idir, exist_ok=True)

    for slug, fn in MODELS.items():
        model = fn()
        with open(os.path.join(mdir, slug + ".json"), "w", newline="\n") as f:
            json.dump(model, f, indent=2)
            f.write("\n")
        with open(os.path.join(idir, slug + ".json"), "w", newline="\n") as f:
            json.dump(item_definition(slug), f, indent=2)
            f.write("\n")
        print("%-24s %2d elements" % (slug, len(model["elements"])))

    # The carried pieces, at true size.
    CUR_SCALE[0] = 1.0
    hmdir = os.path.join(mdir, "held")
    hidir = os.path.join(idir, "held")
    os.makedirs(hmdir, exist_ok=True)
    os.makedirs(hidir, exist_ok=True)
    for slug, fn in HELD.items():
        model = fn()
        with open(os.path.join(hmdir, slug + ".json"), "w", newline="\n") as f:
            json.dump(model, f, indent=2)
            f.write("\n")
        with open(os.path.join(hidir, slug + ".json"), "w", newline="\n") as f:
            json.dump(held_definition(slug), f, indent=2)
            f.write("\n")
        print("%-24s %2d elements (carried)" % (slug, len(model["elements"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
