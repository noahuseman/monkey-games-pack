#!/usr/bin/env python3
"""
Box UV: one texel per model unit, everywhere, on everything.

The models this replaces each pointed every face at a 16x16 tile, whatever
size the face was. A ten-unit shell and a two-unit bolt housing both got
sixteen texels across, so the bolt housing was drawn at five times the
resolution of the shell it was bolted to. That is what "different pixel
sizes depending on how much it has been stretched" means, and no amount of
repainting fixes it - the density is decided by the UV, not by the art.

Minecraft's own answer is box UV, and it is the only one worth having: a
cuboid is unwrapped into a cross, and the cross is exactly as many texels
across as the cuboid is units. Every face on every piece then lands on the
same grid as every other, and as the game's own blocks.

Two rules follow from it and both are load-bearing:

  * Geometry is authored in WHOLE units. Half a unit is half a texel, and
    half a texel cannot be drawn.
  * Scaling the finished model is fine, as long as it is uniform. Scaling
    stretches every face by the same amount, so the grid stays even - which
    is why the head pieces can still be built against a readable head of
    4..12 and blown up by 1.6 on the way out.

The net, for a cuboid w x h x d, is 2(w+d) wide and h+d tall:

        +---------+---------+
        |  down   |   up    |        d
    +---+---------+---+-----+---+
    | E |  north  | W |  south  |    h
    +---+---------+---+---------+
      d      w      d      w
"""

import math


class Box:
    """One cuboid, and where its net sits in the atlas."""

    __slots__ = ("x0", "y0", "z0", "x1", "y1", "z1", "u", "v", "paint", "name")

    def __init__(self, frm, to, paint, name=""):
        self.x0, self.y0, self.z0 = frm
        self.x1, self.y1, self.z1 = to
        for a, b in ((self.x0, self.x1), (self.y0, self.y1), (self.z0, self.z1)):
            if int(a) != a or int(b) != b:
                raise ValueError(
                    "%s: box UV needs whole units, got %s..%s" % (name, a, b))
        self.paint = paint
        self.name = name
        self.u = self.v = 0

    @property
    def w(self):
        return int(self.x1 - self.x0)

    @property
    def h(self):
        return int(self.y1 - self.y0)

    @property
    def d(self):
        return int(self.z1 - self.z0)

    @property
    def net_w(self):
        return 2 * (self.w + self.d)

    @property
    def net_h(self):
        return self.h + self.d

    def faces(self, sheet):
        """
        The six faces, as model uv in the 0-16 space over the whole sheet.

        A uv is in sixteenths of the image whatever the image's size, so a
        texel is 16/size uv units. Every number below is a whole texel
        count turned into that space, which is what keeps the density even.
        """
        sw, sh = sheet
        fx, fy = 16.0 / sw, 16.0 / sh
        u, v, w, h, d = self.u, self.v, self.w, self.h, self.d

        def rect(x0, y0, x1, y1):
            return [round(x0 * fx, 5), round(y0 * fy, 5),
                    round(x1 * fx, 5), round(y1 * fy, 5)]

        return {
            "down":  rect(u + d,         v,     u + d + w,      v + d),
            "up":    rect(u + d + w,     v,     u + d + 2 * w,  v + d),
            "east":  rect(u,             v + d, u + d,          v + d + h),
            "north": rect(u + d,         v + d, u + d + w,      v + d + h),
            "west":  rect(u + d + w,     v + d, u + 2 * d + w,  v + d + h),
            "south": rect(u + 2 * d + w, v + d, u + 2 * d + 2 * w, v + d + h),
        }

    def regions(self):
        """Where each face lives in the atlas, in texels: (x, y, w, h)."""
        u, v, w, h, d = self.u, self.v, self.w, self.h, self.d
        return {
            "down":  (u + d,         v,     w, d),
            "up":    (u + d + w,     v,     w, d),
            "east":  (u,             v + d, d, h),
            "north": (u + d,         v + d, w, h),
            "west":  (u + d + w,     v + d, d, h),
            "south": (u + 2 * d + w, v + d, w, h),
        }


def pack(boxes, pad=1):
    """
    Lay the nets out in a square-ish power-of-two sheet.

    A shelf packer, which is plenty: these are a handful of rectangles, not
    a font. One texel of padding stops a face bleeding into its neighbour
    when the texture is sampled.
    """
    order = sorted(boxes, key=lambda b: -b.net_h)
    for size in (32, 64, 128, 256, 512):
        x = y = shelf = 0
        ok = True
        for b in order:
            bw, bh = b.net_w + pad, b.net_h + pad
            if bw > size:
                ok = False
                break
            if x + bw > size:
                x = 0
                y += shelf
                shelf = 0
            if y + bh > size:
                ok = False
                break
            b.u, b.v = x, y
            x += bw
            shelf = max(shelf, bh)
        if ok:
            return size, size
    raise ValueError("cosmetic does not fit in 512x512")


def element(box, sheet, tex="#0", rotation=None):
    """The model element for a box, with its six faces already unwrapped."""
    uv = box.faces(sheet)
    e = {
        "from": [box.x0, box.y0, box.z0],
        "to": [box.x1, box.y1, box.z1],
        "faces": {d: {"uv": uv[d], "texture": tex} for d in uv},
    }
    if rotation:
        e["rotation"] = rotation
    return e


def scaled(e, factor, mid=8.0):
    """
    Blow an element up about a point, uniformly.

    Uniform is the whole point: every face grows by the same amount, so the
    texel grid stays even. Anything per-axis here would reintroduce exactly
    the stretching this module exists to remove.
    """
    def s(c):
        return round(mid + (c - mid) * factor, 4)
    out = dict(e)
    out["from"] = [s(c) for c in e["from"]]
    out["to"] = [s(c) for c in e["to"]]
    if "rotation" in e:
        r = dict(e["rotation"])
        r["origin"] = [s(c) for c in r["origin"]]
        out["rotation"] = r
    return out
