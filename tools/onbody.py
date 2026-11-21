"""
The carried pieces where they actually sit, against a player.

Rendering a model on its own says nothing about whether a fin grows off a
back or out of a chest. This puts each one at the offset and scale the
plugin gives it, next to a player built to the real proportions, so the
placement can be looked at before it is deployed rather than after.

Axes are the player's own: +X is their LEFT, +Y up, +Z the way they face -
the same frame the plugin writes offsets in.
"""
import json
import math
import os

from PIL import Image, ImageDraw

SRC = (r"C:\Users\noahu\AppData\Local\Temp\claude\a909b112d5a55ede"
       r"\75d22452-daaf-4697-ba19-8590b5ca7862\scratchpad\packsrc")
A = os.path.join(SRC, "assets", "monkeygames")
OUT = (r"C:\Users\noahu\AppData\Local\Temp\claude\a909b112d5a55ede"
       r"\75d22452-daaf-4697-ba19-8590b5ca7862\scratchpad")

W = H = 380
PPB = 115.0                      # pixels per block
FACE_N = {"north": (0, 0, -1), "south": (0, 0, 1), "west": (-1, 0, 0),
          "east": (1, 0, 0), "up": (0, 1, 0), "down": (0, -1, 0)}

# forward, side, up, scale, model - straight out of CatchCosmetics.loadSpots
SPOTS = {
    "shark_fin": (-0.47, 0.0, 1.15, 0.75, "held/shark_fin"),
    "sunken_treasure_chest": (-0.27, 0.0, 1.08, 0.62, "held/sunken_treasure_chest"),
    "phantom_lantern": (-0.02, 0.31, 0.62, 0.40, "held/phantom_lantern"),
}

# the player, in blocks: (x0,y0,z0, x1,y1,z1, shade)
BODY = [
    (-0.25, 1.50, -0.25, 0.25, 2.00, 0.25, (150, 128, 112)),   # head
    (-0.25, 0.75, -0.125, 0.25, 1.50, 0.125, (86, 108, 150)),  # torso
    (-0.50, 0.75, -0.125, -0.25, 1.50, 0.125, (120, 96, 84)),  # left arm
    (0.25, 0.75, -0.125, 0.50, 1.50, 0.125, (120, 96, 84)),    # right arm
    (-0.25, 0.00, -0.125, 0.00, 0.75, 0.125, (62, 70, 112)),   # leg
    (0.00, 0.00, -0.125, 0.25, 0.75, 0.125, (62, 70, 112)),    # leg
]


def box_quads(b, colour):
    x0, y0, z0, x1, y1, z1 = b
    for d in FACE_N:
        yield corners((x0, y0, z0), (x1, y1, z1), d), None, None, FACE_N[d], colour


def corners(f, t, d):
    x0, y0, z0 = f
    x1, y1, z1 = t
    return {
        "north": [(x1, y1, z0), (x0, y1, z0), (x0, y0, z0), (x1, y0, z0)],
        "south": [(x0, y1, z1), (x1, y1, z1), (x1, y0, z1), (x0, y0, z1)],
        "west":  [(x0, y1, z0), (x0, y1, z1), (x0, y0, z1), (x0, y0, z0)],
        "east":  [(x1, y1, z1), (x1, y1, z0), (x1, y0, z0), (x1, y0, z1)],
        "up":    [(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)],
        "down":  [(x0, y0, z1), (x1, y0, z1), (x1, y0, z0), (x0, y0, z0)],
    }[d]


def uv_corners(d, uv):
    u0, v0, u1, v1 = uv
    if d == "up":
        return [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
    if d == "down":
        return [(u0, v1), (u1, v1), (u1, v0), (u0, v0)]
    return [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]


def piece_quads(slug, spot):
    """The model's faces, in the player's own frame, in blocks."""
    fwd, side, up, scale, path = spot
    m = json.load(open(os.path.join(A, "models", "item", "catch", "worn",
                                    *path.split("/")) + ".json"))
    tex = {}
    for k, v in m["textures"].items():
        if k == "particle":
            continue
        tex["#" + k] = Image.open(
            os.path.join(A, "textures", *v.split(":")[1].split("/")) + ".png"
        ).convert("RGBA")

    k = scale / 16.0

    def place(p):
        # The display's origin is the model's middle; the model's +X is the
        # player's left and its +Z the way they face, because the entity
        # itself is never turned and the yaw rides in the transformation.
        return (side + (p[0] - 8) * k, up + (p[1] - 8) * k, fwd + (p[2] - 8) * k)

    for e in m["elements"]:
        for d, fc in e["faces"].items():
            pts = [place(p) for p in corners(e["from"], e["to"], d)]
            uvs = uv_corners(d, fc["uv"])
            for _ in range((fc.get("rotation", 0) // 90) % 4):
                uvs = uvs[1:] + uvs[:1]
            yield pts, uvs, tex[fc["texture"]], FACE_N[d], None


def draw(quads, az, el, label):
    ca, sa = math.cos(math.radians(az)), math.sin(math.radians(az))
    ce, se = math.cos(math.radians(el)), math.sin(math.radians(el))

    def proj(p):
        x, y, z = p[0], p[1] - 1.0, p[2]
        x, z = x * ca + z * sa, -x * sa + z * ca
        y, z = y * ce + z * se, -y * se + z * ce
        return (W / 2 + x * PPB, H / 2 - y * PPB, z)

    img = Image.new("RGBA", (W, H), (30, 34, 40, 255))
    zb = [[1e9] * W for _ in range(H)]
    px = img.load()
    L = (-0.45, 0.80, -0.40)

    def tri(a, b, c, ta, tb, tc, im, flat, sh):
        xs, ys = (a[0], b[0], c[0]), (a[1], b[1], c[1])
        x0, x1 = max(0, int(min(xs))), min(W - 1, int(max(xs)) + 1)
        y0, y1 = max(0, int(min(ys))), min(H - 1, int(max(ys)) + 1)
        den = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(den) < 1e-9:
            return
        for yy in range(y0, y1 + 1):
            for xx in range(x0, x1 + 1):
                w0 = ((b[1] - c[1]) * (xx + .5 - c[0])
                      + (c[0] - b[0]) * (yy + .5 - c[1])) / den
                w1 = ((c[1] - a[1]) * (xx + .5 - c[0])
                      + (a[0] - c[0]) * (yy + .5 - c[1])) / den
                w2 = 1 - w0 - w1
                if w0 < -1e-3 or w1 < -1e-3 or w2 < -1e-3:
                    continue
                z = w0 * a[2] + w1 * b[2] + w2 * c[2]
                if z >= zb[yy][xx]:
                    continue
                if im is None:
                    col = flat + (255,)
                else:
                    u = (w0 * ta[0] + w1 * tb[0] + w2 * tc[0]) / 16.0 * im.size[0]
                    v = (w0 * ta[1] + w1 * tb[1] + w2 * tc[1]) / 16.0 * im.size[1]
                    col = im.getpixel((min(im.size[0] - 1, max(0, int(u))),
                                       min(im.size[1] - 1, max(0, int(v)))))
                    if col[3] < 24:
                        continue
                zb[yy][xx] = z
                px[xx, yy] = (min(255, int(col[0] * sh)), min(255, int(col[1] * sh)),
                              min(255, int(col[2] * sh)), 255)

    for pts, uvs, im, n, flat in quads:
        sh = 0.55 + 0.45 * max(0.0, n[0] * L[0] + n[1] * L[1] + n[2] * L[2])
        p = [proj(q) for q in pts]
        t = uvs or [(0, 0)] * 4
        tri(p[0], p[1], p[2], t[0], t[1], t[2], im, flat, sh)
        tri(p[0], p[2], p[3], t[0], t[2], t[3], im, flat, sh)
    ImageDraw.Draw(img).text((6, 6), label, fill=(210, 225, 255, 255))
    return img


def main():
    rows = []
    for slug, spot in SPOTS.items():
        quads = []
        for b in BODY:
            quads += list(box_quads(b[:6], b[6]))
        quads += list(piece_quads(slug, spot))
        # left side (the player faces right), behind, and three-quarter
        rows.append((slug, [draw(quads, az, el, lab) for az, el, lab in (
            (90, 8, "from the player's left - they face right"),
            (180, 8, "from behind"),
            (215, 14, "three quarters behind"))]))

    sheet = Image.new("RGBA", (W * 3 + 16, (H + 20) * len(rows)), (18, 20, 24, 255))
    d = ImageDraw.Draw(sheet)
    for i, (slug, row) in enumerate(rows):
        d.text((6, i * (H + 20) + 4), slug, fill=(255, 210, 120, 255))
        for j, im in enumerate(row):
            sheet.paste(im, (8 + j * W, i * (H + 20) + 18))
    sheet.save(os.path.join(OUT, "proof_onbody.png"))
    print("ok")


main()
