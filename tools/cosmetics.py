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



def grain(base, amount=8, alpha=0, seed=0):
    """
    Dozens of nearly identical shades over a face that was one colour.

    The pieces were built out of a handful of flat tones, and a handful of
    flat tones reads as plastic: a brass plate is one brass, repeated.
    Minecraft's own art almost never does that - nearly every pixel sits a
    point or two off its neighbour and the eye averages them into a
    surface. This jitters each channel by a hashed few points, so a face
    carries a lot of colours without any single mark large enough to count
    as DETAIL, which is the thing to avoid: the helmet has been too busy
    once already, and the answer to that was never fewer colours, it was
    fewer marks.
    """
    def paint(px, w, h, face):
        base(px, w, h, face)
        key = (w * 2654435761) ^ (h * 40503) ^ (seed * 2246822519)
        n = 2 * amount + 1
        na = 2 * alpha + 1
        for y in range(h):
            for x in range(w):
                c = px[x, y]
                if c[3] == 0:
                    continue
                hsh = ((x + 1) * 374761393) ^ ((y + 1) * 668265263) ^ key
                hsh = ((hsh ^ (hsh >> 13)) * 1274126177) & 0x7FFFFFFF
                a = c[3]
                if alpha and a < 255:
                    a = max(150, min(250, a + (hsh >> 25) % na - alpha))
                px[x, y] = (max(0, min(255, c[0] + (hsh >> 3) % n - amount)),
                            max(0, min(255, c[1] + (hsh >> 11) % n - amount)),
                            max(0, min(255, c[2] + (hsh >> 19) % n - amount)),
                            a)
    return paint


def flecked(base, spot, mod=11, seed=1):
    """A second, sparser scatter, so weathering is not all one colour."""
    def paint(px, w, h, face):
        base(px, w, h, face)
        for y in range(h):
            for x in range(w):
                if px[x, y][3] == 0:
                    continue
                hsh = (((x + 3) * 2246822519) ^ ((y + 5) * 3266489917)
                       ^ ((seed * 374761393) ^ w))
                if ((hsh ^ (hsh >> 15)) & 0x7FFFFFFF) % mod == 0:
                    px[x, y] = spot
    return paint


def locked(base, dark, glint):
    """A keyhole, on the one face anybody ever sees."""
    def paint(px, w, h, face):
        base(px, w, h, face)
        if face != "north" or w < 4 or h < 5:
            return
        cx, cy = w // 2 - 1, h // 2 - 1
        for sx, sy in ((0, 0), (1, 0), (0, 1), (1, 1), (0, 2)):
            px[cx + sx, cy + sy] = dark
        px[cx, cy - 1] = glint
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
    """
    Ice: a pale top and a few fractures that wander.

    The fractures used to step one across for every one down, which makes
    a dashed forty-five degree line - three of them on a face read as
    hatching, not as broken ice. These drift by a hash instead, so they
    lean without ever being straight, and each one lays a paler pixel
    along one side every other step. That highlight is doing two jobs: a
    break in ice catches light on one lip, and it quietly doubles the
    number of tones on a face that would otherwise be two.
    """
    def paint(px, w, h, face):
        for y in range(h):
            for x in range(w):
                px[x, y] = pale if y < max(1, h // 4) else colour
        if w < 3 or h < 3:
            return
        for i, sx in enumerate((w // 4, w // 2, (3 * w) // 4)):
            x, y = sx, (i * h) // 5
            for step in range((2 * h) // 3 + i):
                if not (0 <= x < w and 0 <= y < h):
                    break
                px[x, y] = crack
                if step % 2 and x + 1 < w and px[x + 1, y] != crack:
                    px[x + 1, y] = pale
                hsh = ((x + 11) * 2654435761) ^ ((y + 7) * 2246822519) ^ (i * 97)
                drift = ((hsh ^ (hsh >> 12)) & 0x7FFFFFFF) % 5
                if drift == 0 and x > 0:
                    x -= 1
                elif drift >= 3 and x + 1 < w:
                    x += 1
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
    patina_l = (118, 166, 132, 255)
    copper = (158, 104, 62, 255)
    iron = (150, 150, 158, 255)
    glass = (46, 112, 130, 255)
    glass_l = (150, 212, 222, 255)
    rubber = (52, 52, 58, 255)

    shell = grain(rivets(flecked(
        speckled(brass, patina, top=brass_l, bottom=brass_d),
        patina_l, 17, 3), iron), 10)
    plate = grain(rivets(flecked(
        flat(brass_l, top=(238, 200, 140, 255), bottom=brass_d),
        copper, 19, 7), iron), 10)
    return [
        Box((3, 4, 3), (13, 14, 13), shell, "shell"),
        Box((2, 6, 2), (14, 10, 14), grain(
            seamed(flat(copper, top=brass_l, bottom=brass_d), brass_d), 10),
            "bulge"),
        Box((2, 2, 2), (14, 4, 14), plate, "collar"),
        Box((5, 6, 1), (11, 12, 3),
            grain(rivets(flat(brass_l), iron, 0), 9), "rim"),
        Box((6, 7, 0), (10, 11, 1),
            grain(glowing(glass, iron, glass_l), 11), "glass"),
        Box((13, 8, 6), (15, 11, 9),
            grain(glowing(glass, brass_l, glass_l), 11), "port_l"),
        Box((1, 8, 6), (3, 11, 9),
            grain(glowing(glass, brass_l, glass_l), 11), "port_r"),
        Box((6, 10, 13), (10, 13, 15),
            grain(banded(rubber, (28, 28, 32, 255), 2), 7), "hose"),
        Box((6, 14, 6), (10, 16, 10),
            grain(flat(brass_l, bottom=brass_d), 9), "knob"),
    ]


def eternal_ice_cube():
    # Ice you can see into.
    #
    # An item model is drawn on the translucent item sheet, so alpha below
    # 255 really is alpha - the far side of the cube shows faintly through
    # the near side, which is most of what makes ice read as ice rather
    # than as blue stone. Nothing here drops below 150: an armour LAYER
    # cuts hard at 128 and turns anything fainter into a black hole, and
    # staying well clear of that line means these colours still behave if
    # a piece is ever moved onto one.
    A = 196
    ice = (142, 206, 232, A)
    ice_l = (206, 240, 252, A + 24)
    white = (238, 250, 255, 232)
    deep = (46, 108, 142, 238)

    body = grain(cracked(ice, deep, ice_l), 7, alpha=14)
    shard = grain(flat((206, 240, 252, 214), bottom=(142, 206, 232, 204)),
                  7, alpha=12)
    icicle = grain(flat((160, 214, 238, 208), bottom=(70, 150, 186, 230)),
                   7, alpha=12)
    return [
        Box((2, 2, 2), (14, 15, 14), body, "cube"),
        Box((1, 15, 1), (15, 16, 15),
            grain(speckled(white, ice_l), 6, alpha=8), "rime"),
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

    blush = (238, 128, 174, 255)
    mantle = grain(flecked(
        speckled(pink, spot, top=pink_l, bottom=pink_d), blush, 13, 5), 10)
    arm = grain(flat(pink, top=pink_l, bottom=pink_d, edge=pink_d), 9)
    eye = grain(eyed(pale, dark, (255, 255, 255, 255), pink_d), 6)
    boxes = [
        Box((3, 4, 3), (13, 14, 13), mantle, "mantle"),
        Box((4, 14, 4), (12, 17, 12),
            grain(flat(pink_d, top=pink), 9), "taper"),
        Box((6, 17, 6), (10, 19, 10),
            grain(flat(pink_d, top=pink), 9), "tip"),
        Box((12, 8, 5), (14, 11, 9), eye, "eye_l"),
        Box((2, 8, 5), (4, 11, 9), eye, "eye_r"),
        Box((13, 11, 5), (15, 13, 11),
            grain(flat(pale, bottom=pink), 8), "fin_l"),
        Box((1, 11, 5), (3, 13, 11),
            grain(flat(pale, bottom=pink), 8), "fin_r"),
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
    cap = grain(flat(iron, top=iron_l, bottom=iron_d), 8)
    # Two units wider all round than it was. A lantern six units across
    # and eleven tall reads as a bottle at hip size; eight across is
    # squat enough to read as a lantern from across an arena, which is
    # the only distance it is ever seen from.
    return [
        Box((4, 2, 4), (12, 4, 12), cap, "foot"),
        Box((5, 4, 5), (11, 11, 11),
            grain(glowing(glow, iron, glow_l), 9), "glass"),
        Box((4, 11, 4), (12, 13, 12), cap, "cap"),
        Box((7, 13, 7), (9, 15, 9), grain(flat(iron_l), 8), "hook"),
        Box((7, 15, 7), (9, 16, 9), grain(flat(iron_l), 8), "ring"),
    ]


def held_chest():
    wood = (108, 76, 42, 255)
    wood_l = (140, 102, 60, 255)
    wood_d = (72, 48, 24, 255)
    gold = (214, 165, 43, 255)
    gold_d = (150, 110, 20, 255)
    gold_l = (248, 214, 112, 255)
    iron = (124, 130, 138, 255)
    iron_l = (170, 176, 184, 255)
    iron_d = (68, 74, 82, 255)
    leather = (64, 46, 30, 255)
    dark = (26, 20, 14, 255)

    band = grain(flat(iron, top=iron_l, bottom=iron_d), 9)
    # Banding, and why it is geometry rather than paint.
    #
    # Painted on, a strap is a stripe: it lies in the same plane as the
    # boards and the eye reads it as a stain. Standing a unit proud of
    # the lid it catches a different face shade on every side and throws
    # a silhouette, which is the difference between a crate with lines on
    # it and a chest with iron round it.
    #
    # The straps stand 1 unit out and the waist band 2, so the band
    # passes OVER them with no two faces sharing a plane. Coplanar faces
    # are what z-fighting is, and the way to not have it is to not write
    # it, not to nudge things by a hundredth afterwards.
    out = [
        # The lid is painted markedly lighter than the base, with a dark
        # seam under it. Planked identically they read as one crate, and a
        # crate is not a chest - the lid line is the whole silhouette.
        Box((3, 2, 4), (13, 9, 12), grain(
            seamed(planks(wood, wood_d, wood_l), wood_d, (0.0,)), 8), "base"),
        Box((3, 9, 4), (13, 13, 12), grain(
            planks((168, 128, 80, 255), (120, 88, 50, 255),
                   (196, 156, 104, 255)), 8), "lid"),
    ]
    for tag, x0 in (("l", 4), ("r", 10)):
        out += [
            Box((x0, 2, 3), (x0 + 2, 13, 4), band, "strap_f_" + tag),
            Box((x0, 13, 3), (x0 + 2, 14, 13), band, "strap_t_" + tag),
            Box((x0, 2, 12), (x0 + 2, 13, 13), band, "strap_b_" + tag),
        ]
    out += [
        Box((3, 8, 2), (13, 10, 4), band, "waist_f"),
        Box((3, 8, 12), (13, 10, 14), band, "waist_b"),
        Box((2, 8, 4), (3, 10, 12), band, "waist_l"),
        Box((13, 8, 4), (14, 10, 12), band, "waist_r"),
        # The lock sits in the waist band, not on it, for the same reason.
        Box((6, 6, 1), (10, 11, 3),
            grain(locked(flat(gold, top=gold_l, bottom=gold_d), dark, gold_l),
                  7), "lock"),
        Box((4, 2, 13), (6, 13, 14),
            grain(flat(leather, top=(96, 72, 48, 255)), 7), "sling_l"),
        Box((10, 2, 13), (12, 13, 14),
            grain(flat(leather, top=(96, 72, 48, 255)), 7), "sling_r"),
    ]
    return out


def held_shark_fin():
    """
    A fin that grows out of a back, built rather than extruded.

    It used to be the inventory sprite, which `item/generated` extrudes
    one unit thick - about half a pixel once the display has scaled it,
    so from the side it was a razor blade, and nothing about its weight
    on the back could be controlled because the silhouette came from an
    icon drawn to be looked at face-on.

    Built as boxes it gets a real root four units thick, tapering to two,
    and it is centred on x = 8 by construction, which the sprite never
    was: the fin in that icon leans, so the extrusion's mass sat right of
    the middle however carefully the display was centred.

    Authored with +Z towards the player, so the root plane is the face
    that meets the spine and everything else reaches backwards and up.
    """
    grey = (108, 120, 132, 255)
    grey_l = (146, 158, 170, 255)
    grey_d = (70, 80, 92, 255)
    pale = (176, 186, 196, 255)
    slate = (92, 104, 118, 255)

    def coat(c, t, seed):
        return grain(flecked(flat(c, top=t, bottom=grey_d), slate, 15, seed), 9)

    # Thin slices, and thinner the higher it goes.
    #
    # The first attempt was three fat boxes and it read as a stepped
    # brick, because a shape made of three steps is not a curve, it is
    # three corners. This is the same silhouette cut finer: the bottom
    # edge climbs and the top edge falls over six slices, so the blade
    # sweeps instead of stepping, and the steps that remain are small
    # enough to pass for the stepping the game does everywhere else.
    #
    # It also thins with height. The root is four units thick where it
    # meets the back - three pixels once the display has scaled it, which
    # is what a fin needs to stop being a razor blade - and two above the
    # waist of the blade, because a fin that is equally fat at the tip is
    # a shark-shaped doorstop.
    # Two units thick everywhere, with one thickening in the middle of
    # the root.
    #
    # It used to be four units thick for the three slices nearest the
    # back and two beyond them, which put all the weight at one END of
    # the attachment - a lump under the fin rather than a root. Thickness
    # does belong where a fin meets a body, but along the middle of the
    # join, not piled at the bottom of it, so the blade is an even two
    # units everywhere and the four-unit band sits centred on the back
    # and tapers out over two slices.
    #
    # Each slice is therefore up to three boxes stacked in y: thin, thick,
    # thin. Where two of them meet, the shared plane is interior to the
    # solid they form together, so neither face is ever reachable by a
    # ray and there is nothing to z-fight.
    #
    # Deep against the back, tipping DOWN as it goes away.
    #
    # The bottom edge runs almost level out from the small of the back
    # and the top edge falls steadily, so the point finishes low and
    # behind rather than raked up over the shoulder.
    #
    # Root-first: index 0 is the slice touching the back. The band is
    # written against the root slices rather than against particular
    # numbers, so it stays at the join if the blade is ever turned
    # again.
    slices = [(14, 16, 1, 15, (5, 11)), (12, 14, 1, 14, (6, 10)),
              (10, 12, 2, 13, None), (8, 10, 2, 10, None),
              (6, 8, 3, 8, None), (4, 6, 3, 6, None)]
    out = []
    for n, (z0, z1, y0, y1, thick) in enumerate(slices):
        skin = coat((112 + 7 * n, 124 + 7 * n, 136 + 7 * n, 255),
                    pale if n > 2 else grey_l, 9 + n)
        if thick is None:
            out.append(Box((7, y0, z0), (9, y1, z1), skin, "fin%d" % n))
            continue
        t0, t1 = thick
        if t0 > y0:
            out.append(Box((7, y0, z0), (9, t0, z1), skin, "fin%dl" % n))
        out.append(Box((6, t0, z0), (10, t1, z1),
                       coat((96 + 8 * n, 108 + 8 * n, 120 + 8 * n, 255),
                            grey, 2 + n), "fin%dm" % n))
        if y1 > t1:
            out.append(Box((7, t1, z0), (9, y1, z1), skin, "fin%du" % n))
    return out


PIECES = {
    "deep_sea_diving_helmet": (diving_helmet, True),
    "eternal_ice_cube": (eternal_ice_cube, True),
    "pink_squid": (pink_squid, True),
    "held/phantom_lantern": (held_lantern, False),
    "held/sunken_treasure_chest": (held_chest, False),
    "held/shark_fin": (held_shark_fin, False),
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

        # A carried piece also needs the item definition that points at
        # the model, since nothing else writes one for a piece that was
        # never a head piece. Head pieces keep theirs in wearable_models.
        if parts[0] == "held":
            ip = os.path.join(a, "items", "catch", *parts) + ".json"
            os.makedirs(os.path.dirname(ip), exist_ok=True)
            with open(ip, "w", newline="\n") as f:
                json.dump({"model": {
                    "type": "minecraft:model",
                    "model": NS + ":item/catch/worn/" + name}}, f, indent=2)
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
