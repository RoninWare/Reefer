"""Model the store edition's fish and bake the views the app turns them through.

    blender -b --factory-startup --python-exit-code 1 -P market/authoring/create_fish.py -- [--only <name>] [--look]

Six species, each built here from a few curves (the outline of the body from the side and
from above), fins laid on as sheets, and a paint function that colours every vertex:

  tang       regal blue tang: royal blue, a black palette on the flank, yellow tail
  surgeon    lined surgeonfish: yellow and blue stripes over a pale belly, lyre tail
  mandarin   mandarinfish: blue-green scrawled with orange, big fan fins
  lionfish   red and white bands, a mane of dorsal spines, great banded pectoral fans
  damsel     leopard damsel: blue with a black net over the back
  dottyback  dusky purple in front running to yellow behind

The app draws a fish from sprites: for each of 26 headings (-60 degrees, swimming away, to 90,
head on; it mirrors them for the rest) a body and a tail, the tail squashed toward its hinge
as it beats. For headings from 0 up there are two more sets with the body bent, tail toward
the near flank ("p2") or the far one ("m2"), shown while the fish turns. This script renders
all of them, one unit to 100 px at the front of the tank, and writes for each species
market/art/fish/<name>_atlas0.png and <name>.json (the "views" block of the scene).

--look renders a few headings of each fish, three times the size, to <name>_look.png instead.
"""
import json
import math
import sys
from math import cos, sin
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector, noise

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "authoring/christmas"))
import rig  # noqa: E402
from rig import TAU  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "art/fish"
OUT.mkdir(parents=True, exist_ok=True)
ARGS = rig.script_args()
ONLY = ARGS[ARGS.index("--only") + 1] if "--only" in ARGS else None
LOOK = "--look" in ARGS
DEG = [-60, -50, -40, -30, -20, -10, 0, 8, 16, 24, 31, 38, 44, 50, 55, 60, 64, 68, 72, 75, 78, 81, 84, 86, 88, 90]
BEND_FROM = DEG.index(0)
BEND = math.radians(34)         # how far the tail swings round in the bent sets: two thirds of a full bend
CENTRE = 0.42                   # where along the body the fish's centre lies: it turns and tilts about this


# ---- small helpers ---------------------------------------------------------------------

def spline(points):
    """A smooth curve through (x, y) points with x increasing, as a function of x."""
    pts = np.array(points, dtype=float)
    ends = np.vstack([2 * pts[0] - pts[1], pts, 2 * pts[-1] - pts[-2]])
    t = np.linspace(0, 1, 24, endpoint=False)[:, None]
    parts = []
    for i in range(1, len(ends) - 2):
        p0, p1, p2, p3 = ends[i - 1:i + 3]
        parts.append(0.5 * (2 * p1 + (p2 - p0) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (3 * p1 - p0 - 3 * p2 + p3) * t ** 3))
    dense = np.vstack(parts + [pts[-1:]])
    return lambda x: float(np.interp(x, dense[:, 0], dense[:, 1]))


def smooth(a, b, x):
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def mix(a, b, t):
    return tuple(p + (q - p) * t for p, q in zip(a, b))


def grain(x, y, z=0.0):
    return noise.noise(Vector((x, y, z)))


def cells(x, y):
    """Distance to the nearest cell wall of a honeycomb of irregular cells: 0 on a wall."""
    d = noise.voronoi(Vector((x, y, 0.0)))[0]
    return d[1] - d[0]


def dots(x, y, size=0.3):
    """1 inside a scatter of round dots, 0 between them."""
    return 1.0 - smooth(size * 0.7, size, noise.voronoi(Vector((x, y, 0.0)))[0][0])


class Mesh:
    """Vertices, faces and a colour for every vertex."""

    def __init__(self):
        self.verts, self.faces, self.tint = [], [], []

    def grid(self, rows, closed=False):
        """rows of (position, colour), all the same length; closed joins each row's ends."""
        n, m = len(self.verts), len(rows[0])
        for row in rows:
            for position, colour in row:
                self.verts.append(tuple(position))
                self.tint.append(colour)
        for i in range(1, len(rows)):
            for k in range(m if closed else m - 1):
                j = (k + 1) % m
                self.faces.append((n + (i - 1) * m + k, n + (i - 1) * m + j, n + i * m + j, n + i * m + k))

    def build(self, scene, name, mat):
        obj = rig.add_mesh(scene, name, self.verts, self.faces, [mat], smooth=True)
        layer = obj.data.attributes.new("tint", "FLOAT_COLOR", "POINT")
        layer.data.foreach_set("color", [c for t in self.tint for c in (t[0], t[1], t[2], 1.0)])
        return obj


# ---- the fish --------------------------------------------------------------------------

class Fish:
    """Builds one species from its spec: a body, fins and eyes in `skin` and `eyes`, and the
    tail fin on its own in `tail`. Everything is in units of 100 px, nose toward +x."""

    def __init__(self, spec):
        self.spec = spec
        self.top, self.bottom, self.width = (spline(spec[key]) for key in ("top", "bottom", "width"))
        tail = spec["tail"]
        self.lb = spec["length"] / 100 / (1 + tail["length"] * 0.92)        # body length, nose to tail joint
        self.skin, self.eyes, self.tail = Mesh(), Mesh(), Mesh()
        self.body()
        for fin in spec["fins"]:
            getattr(self, fin["kind"])(fin)
        self.caudal(tail)
        self.eye(spec["eye"])
        self.hinge = Vector((self.x(1.0), 0.0, self.mid(1.0)))
        self.rear = (1 - CENTRE) * self.lb + tail["length"] * self.lb

    def x(self, s):
        return self.lb * (CENTRE - s)

    def mid(self, s):
        return self.lb * (self.top(s) + self.bottom(s)) / 2

    def at(self, s, h, out=1.0):
        """A point on the body's skin: s along it from the nose, h from -1 (belly) to 1 (back)."""
        half = self.lb * (self.top(s) - self.bottom(s)) / 2
        a = math.asin(max(-1.0, min(1.0, h)))
        return Vector((self.x(s), self.lb * self.width(s) * cos(a) * out, self.mid(s) + half * h))

    def body(self):
        paint, rings, levels = self.spec["paint"], 240, 88
        # Round each flank from belly to back in even steps of height, so a pattern is as fine
        # there as it is along the body.
        loop = [(-1 + 2 * j / levels, 1) for j in range(levels)] + [(1 - 2 * j / levels, -1) for j in range(levels)]
        around = len(loop)
        rows = []
        for i in range(rings + 1):
            s = 0.003 + 0.997 * i / rings
            half, wide = self.lb * (self.top(s) - self.bottom(s)) / 2, self.lb * self.width(s)
            row = []
            for h, flank in loop:
                z = self.mid(s) + half * h
                row.append(((self.x(s), flank * wide * math.sqrt(1 - h * h), z), paint(s, h, z / self.lb)))
            rows.append(row)
        self.skin.grid(rows, closed=True)
        n = len(self.skin.verts)
        self.skin.faces.append(tuple(range(around)))
        self.skin.faces.append(tuple(range(n - around, n)))

    def median(self, fin):
        """A dorsal or anal fin: a sheet standing on the back (side 1) or hanging from the belly (-1)."""
        side, edge = fin.get("side", 1), self.top if fin.get("side", 1) > 0 else self.bottom
        s0, s1, height, sweep, paint = fin["from"], fin["to"], spline(fin["height"]), fin.get("sweep", 0.5), fin["paint"]
        along, up = 60, 10
        rows = []
        for j in range(up + 1):
            r = j / up
            row = []
            for i in range(along + 1):
                t = i / along
                s = s0 + (s1 - s0) * t
                tall = height(t) * self.lb
                base = Vector((self.x(s), 0.0, self.lb * edge(s) - side * 0.012 * self.lb))
                row.append((base + Vector((-sweep * tall * r, 0.0, side * tall * r)), paint(t, r)))
            rows.append(row)
        self.skin.grid(rows)

    def spines(self, fin):
        """A row of separate spines, each trailing a narrow flag of skin (the lionfish's mane)."""
        side, edge = fin.get("side", 1), self.top if fin.get("side", 1) > 0 else self.bottom
        height, paint, count = spline(fin["height"]), fin["paint"], fin["count"]
        for j in range(count):
            t = j / (count - 1)
            s = fin["from"] + (fin["to"] - fin["from"]) * t
            tall, wide = height(t) * self.lb, fin.get("flag", 0.03) * self.lb
            base = Vector((self.x(s), 0.0, self.lb * edge(s) - side * 0.01 * self.lb))
            lean = fin.get("sweep", 0.25) + 0.25 * t
            rows = []
            for i in range(13):
                r = i / 12
                spine = base + Vector((-lean * tall * r, 0.0, side * tall * r))
                flag = wide * (0.25 + 0.75 * sin(math.pi * min(1.0, r * 1.15)) ** 0.7) * (1 - r ** 6)
                rows.append([(spine + Vector((0.004, 0, 0)), paint(t, r)), (spine - Vector((flag * 0.5, 0, 0)), paint(t, r)),
                             (spine - Vector((flag, 0, 0.3 * flag * side)), paint(t, r))])
            self.skin.grid(rows)

    def fan(self, mesh, root, axis, spread_axis, fin, base=0.0):
        """A fan of rays from `root` along `axis`, opening along `spread_axis`."""
        half, length, shape, paint = math.radians(fin["spread"]), fin["length"] * self.lb, fin.get("shape", lambda a: 1.0), fin["paint"]
        across, out = 48, 36
        rows = []
        for i in range(out + 1):
            r = i / out
            row = []
            for j in range(across + 1):
                a = -1 + 2 * j / across
                ray = axis * cos(a * half) + spread_axis * sin(a * half)
                start = root + spread_axis * (base * a)
                row.append((start + ray * (length * shape(a) * r), paint(a, r)))
            rows.append(row)
        mesh.grid(rows)

    def paired(self, fin):
        """A pectoral or pelvic fin on each flank."""
        out, down = math.radians(fin.get("out", 35)), math.radians(fin.get("down", 25))
        for flank in (-1, 1):
            root = self.at(fin["at"][0], fin["at"][1], out=0.92)
            root.y *= flank
            axis = Vector((-cos(out) * cos(down), flank * sin(out), -sin(down))).normalized()
            spread = Vector((-sin(down) * 0.6, flank * 0.25, cos(down))).normalized()
            spread = (spread - axis * spread.dot(axis)).normalized()
            self.fan(self.skin, root, axis, spread, fin, base=fin.get("base", 0.02) * self.lb)

    def caudal(self, fin):
        root = Vector((self.x(1.0) + 0.02 * self.lb, 0.0, self.mid(1.0)))
        base = self.lb * (self.top(1.0) - self.bottom(1.0)) / 2 * 0.95
        self.fan(self.tail, root, Vector((-1, 0, 0)), Vector((0, 0, 1)), fin, base=base)

    def eye(self, eye):
        radius = eye["r"] * self.lb
        for flank in (-1, 1):
            centre = self.at(eye["at"][0], eye["at"][1], out=0.82)
            centre.y *= flank
            rows = []
            for depth, wide in ((-0.5, 1.0), (0.1, 0.97), (0.36, 0.78), (0.5, 0.5), (0.56, 0.22), (0.58, 0.0)):
                colour = eye["pupil"] if wide < 0.6 else eye["iris"]
                rows.append([((centre.x + radius * wide * cos(TAU * k / 20), centre.y + flank * radius * depth, centre.z + radius * wide * sin(TAU * k / 20)), colour)
                             for k in range(20)])
            self.eyes.grid(rows, closed=True)


def bender(rear, angle):
    """A function that bends points behind the fish's centre round to one side: the spine
    turns through `angle` by the tip of the tail, rear units back."""
    steps = 240
    turn = [angle * smooth(0, 1, i / steps) for i in range(steps * 2)]
    spine = [Vector((0.0, 0.0))]
    for psi in turn[:-1]:
        spine.append(spine[-1] + Vector((-cos(psi), -sin(psi))) * (rear / steps))

    def bend(p):
        if p.x >= 0:
            return p
        k = min(len(spine) - 1, int(-p.x / rear * steps))
        psi, at = turn[k], spine[k]
        left = -p.x - k * rear / steps
        return Vector((at.x - cos(psi) * left - sin(psi) * p.y, at.y - sin(psi) * left + cos(psi) * p.y, p.z))

    return bend


# ---- the six species -------------------------------------------------------------------

def rays(colour, a, count, depth=0.16):
    """A fin colour with its rays shaded in."""
    return tuple(c * (1 - depth * (0.5 - 0.5 * cos(a * count * math.pi))) for c in colour)


def tang():
    blue, deep, black, yellow = (0.02, 0.15, 0.80), (0.01, 0.06, 0.45), (0.008, 0.01, 0.03), (1.0, 0.76, 0.02)

    def paint(s, h, z):
        ring = math.hypot((s - 0.56) / 0.2, (h - 0.06) / 0.44)
        palette = smooth(1.0, 1.08, ring) * smooth(1.5, 1.42, ring) * smooth(0.3, 0.34, s)
        low = 0.42 - 0.3 * smooth(0.7, 1.0, s)
        back = smooth(0.15, 0.19, s) * smooth(low, low + 0.06, h) * smooth(0.86, 0.8, h)
        colour = mix(blue, (0.04, 0.26, 0.92), smooth(-0.3, -0.9, h))
        colour = mix(colour, black, max(palette, back))
        return mix(colour, deep, 0.5 * smooth(0.9, 1.0, abs(h)))

    def fin(a, r):
        return black if r > 0.82 else rays(blue, a, 30)

    def tail(a, r):
        return black if abs(a) > 0.66 + 0.1 * r else rays(yellow, a, 16, 0.1)

    return dict(length=190,
                top=[(0, 0.0), (0.03, 0.06), (0.1, 0.15), (0.22, 0.23), (0.42, 0.27), (0.62, 0.25), (0.8, 0.17), (0.93, 0.075), (1, 0.045)],
                bottom=[(0, -0.02), (0.04, -0.075), (0.12, -0.16), (0.25, -0.235), (0.45, -0.265), (0.65, -0.23), (0.82, -0.15), (0.93, -0.07), (1, -0.045)],
                width=[(0, 0.012), (0.08, 0.055), (0.25, 0.10), (0.45, 0.11), (0.7, 0.08), (0.9, 0.035), (1, 0.022)],
                paint=paint, eye=dict(at=(0.115, 0.5), r=0.036, pupil=(0.005, 0.005, 0.01), iris=(0.03, 0.05, 0.12)),
                tail=dict(length=0.27, spread=40, shape=lambda a: 0.9 + 0.1 * abs(a) ** 2, paint=tail),
                fins=[dict(kind="median", **{"from": 0.17}, to=0.93, height=[(0, 0.03), (0.15, 0.085), (0.7, 0.10), (0.92, 0.08), (1, 0.01)], sweep=0.6, paint=fin),
                      dict(kind="median", side=-1, **{"from": 0.46}, to=0.93, height=[(0, 0.02), (0.2, 0.08), (0.7, 0.09), (0.92, 0.07), (1, 0.01)], sweep=0.6, paint=fin),
                      dict(kind="paired", at=(0.27, -0.12), length=0.16, spread=24, out=20, down=20, shape=lambda a: 1 - 0.3 * a * a,
                           paint=lambda a, r: rays(mix(deep, yellow, smooth(0.78, 1.0, r)), a, 12)),
                      dict(kind="paired", at=(0.3, -0.97), length=0.1, spread=16, out=10, down=58, paint=lambda a, r: rays(deep, a, 8))])


def surgeon():
    gold, blue, black, pale = (1.0, 0.60, 0.04), (0.10, 0.52, 1.0), (0.015, 0.015, 0.05), (0.80, 0.80, 0.93)

    def paint(s, h, z):
        wave = sin(TAU * (z * 23 + 0.1 * sin(s * 9)))
        stripes = mix(mix(black, gold, smooth(0.05, 0.3, wave)), blue, smooth(-0.4, -0.62, wave))
        return mix(stripes, pale, smooth(-0.34, -0.5, h))

    def fin(a, r):
        return blue if r > 0.86 else black if r > 0.78 else rays(gold, a, 34)

    def tail(a, r):
        edge = abs(a) > 0.84
        return blue if edge else mix((0.9, 0.5, 0.05), (0.03, 0.04, 0.12), smooth(0.05, 0.35, r))

    return dict(length=185,
                top=[(0, 0.0), (0.03, 0.055), (0.1, 0.13), (0.25, 0.19), (0.45, 0.205), (0.7, 0.165), (0.9, 0.07), (1, 0.04)],
                bottom=[(0, -0.02), (0.05, -0.07), (0.15, -0.15), (0.3, -0.195), (0.5, -0.2), (0.72, -0.15), (0.9, -0.06), (1, -0.04)],
                width=[(0, 0.012), (0.08, 0.055), (0.25, 0.095), (0.45, 0.10), (0.7, 0.075), (0.9, 0.032), (1, 0.02)],
                paint=paint, eye=dict(at=(0.1, 0.55), r=0.03, pupil=(0.005, 0.005, 0.01), iris=(0.75, 0.45, 0.05)),
                tail=dict(length=0.4, spread=36, shape=lambda a: 0.42 + 0.58 * abs(a) ** 2.6, paint=tail),
                fins=[dict(kind="median", **{"from": 0.15}, to=0.94, height=[(0, 0.03), (0.12, 0.075), (0.7, 0.09), (0.93, 0.08), (1, 0.01)], sweep=0.6, paint=fin),
                      dict(kind="median", side=-1, **{"from": 0.44}, to=0.94, height=[(0, 0.02), (0.2, 0.07), (0.7, 0.08), (0.93, 0.07), (1, 0.01)], sweep=0.6, paint=fin),
                      dict(kind="paired", at=(0.25, -0.1), length=0.16, spread=24, out=20, down=18, shape=lambda a: 1 - 0.3 * a * a,
                           paint=lambda a, r: rays((0.85, 0.55, 0.1), a, 12)),
                      dict(kind="paired", at=(0.3, -0.97), length=0.11, spread=16, out=10, down=58, paint=lambda a, r: rays((0.9, 0.5, 0.03), a, 8))])


def mandarin():
    blue, green, orange, navy, bright = (0.03, 0.28, 0.85), (0.04, 0.55, 0.38), (0.96, 0.36, 0.02), (0.01, 0.05, 0.3), (0.12, 0.55, 1.0)

    def paint(s, h, z):
        scrawl = sin(TAU * (6.2 * s + 0.85 * h + 0.75 * grain(s * 7.5, h * 2.2)))
        base = mix(blue, green, smooth(0.0, 0.9, h))
        return mix(mix(base, navy, smooth(0.08, 0.18, scrawl)), orange, smooth(0.3, 0.42, scrawl))

    def fin(a, r):
        if r > 0.86:
            return bright
        return bright if cos(a * 9 * math.pi) > 0.86 and r > 0.15 else rays(orange, a, 9, 0.2)

    sail = [(0, 0.05), (0.2, 0.3), (0.6, 0.26), (1, 0.03)]
    return dict(length=108,
                top=[(0, 0.02), (0.04, 0.10), (0.12, 0.165), (0.3, 0.17), (0.6, 0.14), (0.85, 0.08), (1, 0.055)],
                bottom=[(0, -0.03), (0.05, -0.10), (0.15, -0.15), (0.35, -0.16), (0.6, -0.13), (0.85, -0.07), (1, -0.05)],
                width=[(0, 0.03), (0.08, 0.12), (0.2, 0.155), (0.4, 0.145), (0.7, 0.09), (1, 0.03)],
                paint=paint, eye=dict(at=(0.1, 0.72), r=0.058, pupil=(0.005, 0.005, 0.01), iris=(0.9, 0.2, 0.03)),
                tail=dict(length=0.4, spread=50, shape=lambda a: 1 - 0.2 * a * a, paint=fin),
                fins=[dict(kind="median", **{"from": 0.2}, to=0.46, height=sail, sweep=0.5, paint=fin),
                      dict(kind="median", **{"from": 0.5}, to=0.9, height=[(0, 0.04), (0.25, 0.2), (0.7, 0.19), (1, 0.02)], sweep=0.7, paint=fin),
                      dict(kind="median", side=-1, **{"from": 0.52}, to=0.9, height=[(0, 0.03), (0.3, 0.16), (0.7, 0.15), (1, 0.02)], sweep=0.7, paint=fin),
                      dict(kind="paired", at=(0.24, -0.25), length=0.3, spread=52, out=50, down=20, shape=lambda a: 1 - 0.25 * a * a, paint=fin),
                      dict(kind="paired", at=(0.2, -0.95), length=0.3, spread=46, out=40, down=58, shape=lambda a: 1 - 0.25 * a * a, paint=fin)])


def lionfish():
    red, edge, cream, veil = (0.45, 0.07, 0.04), (0.22, 0.035, 0.03), (0.95, 0.88, 0.80), (0.92, 0.86, 0.76)

    def paint(s, h, z):
        band = sin(TAU * (s * 13 + 0.3 * grain(s * 6, h * 3) + 0.12 * h))
        return mix(mix(edge, red, smooth(0.05, 0.22, band)), cream, smooth(-0.2, -0.38, band))

    def spotted(a, r):
        return mix(rays(veil, a, 14, 0.12), (0.12, 0.05, 0.04), dots(a * 5.5, r * 4.0, 0.22))

    def banded(a, r):
        band = sin(TAU * r * 5)
        return mix(mix(edge, red, smooth(0.0, 0.2, band)), cream, smooth(-0.25, -0.45, band))

    def pectoral(a, r):
        return rays(banded(a, r), a, 13, 0.3)

    return dict(length=190,
                top=[(0, 0.0), (0.04, 0.09), (0.12, 0.17), (0.25, 0.21), (0.5, 0.19), (0.75, 0.12), (0.92, 0.06), (1, 0.045)],
                bottom=[(0, -0.03), (0.05, -0.11), (0.15, -0.18), (0.3, -0.2), (0.55, -0.17), (0.8, -0.09), (1, -0.045)],
                width=[(0, 0.02), (0.08, 0.085), (0.2, 0.12), (0.45, 0.11), (0.75, 0.065), (1, 0.025)],
                paint=paint, eye=dict(at=(0.13, 0.5), r=0.03, pupil=(0.005, 0.005, 0.01), iris=(0.55, 0.3, 0.2)),
                tail=dict(length=0.3, spread=44, shape=lambda a: 1 - 0.22 * a * a, paint=spotted),
                fins=[dict(kind="spines", **{"from": 0.2}, to=0.62, count=12, height=[(0, 0.3), (0.3, 0.44), (0.7, 0.4), (1, 0.24)], flag=0.024, paint=banded),
                      dict(kind="median", **{"from": 0.66}, to=0.88, height=[(0, 0.08), (0.3, 0.22), (0.7, 0.2), (1, 0.03)], sweep=0.5, paint=spotted),
                      dict(kind="median", side=-1, **{"from": 0.62}, to=0.86, height=[(0, 0.06), (0.3, 0.18), (0.7, 0.17), (1, 0.03)], sweep=0.5, paint=spotted),
                      dict(kind="paired", at=(0.26, -0.3), length=0.62, spread=58, out=52, down=22, base=0.04,
                           shape=lambda a: (1 - 0.28 * a * a) * (0.9 + 0.1 * abs(cos(a * 6.5 * math.pi))), paint=pectoral),
                      dict(kind="paired", at=(0.3, -0.95), length=0.3, spread=24, out=18, down=66, paint=pectoral)])


def damsel():
    blue, pale, black = (0.08, 0.30, 0.95), (0.55, 0.76, 1.0), (0.01, 0.015, 0.06)

    def paint(s, h, z):
        base = mix(pale, blue, smooth(-0.85, -0.1, h))
        net = smooth(0.09, 0.025, cells(s * 17, z * 17)) * smooth(-0.8, -0.3, h)
        return mix(base, black, net)

    def fin(a, r):
        return mix(rays(blue, a, 20), black, dots(a * 7, r * 3.2, 0.2) * 0.9)

    return dict(length=82,
                top=[(0, 0.0), (0.04, 0.075), (0.13, 0.17), (0.3, 0.25), (0.5, 0.26), (0.75, 0.17), (0.92, 0.085), (1, 0.065)],
                bottom=[(0, -0.03), (0.06, -0.105), (0.18, -0.19), (0.35, -0.235), (0.55, -0.23), (0.78, -0.15), (0.93, -0.075), (1, -0.06)],
                width=[(0, 0.02), (0.08, 0.075), (0.25, 0.125), (0.45, 0.13), (0.7, 0.09), (1, 0.03)],
                paint=paint, eye=dict(at=(0.12, 0.42), r=0.05, pupil=(0.005, 0.005, 0.01), iris=(0.6, 0.8, 1.0)),
                tail=dict(length=0.36, spread=40, shape=lambda a: 0.68 + 0.32 * abs(a) ** 1.6, paint=fin),
                fins=[dict(kind="median", **{"from": 0.2}, to=0.88, height=[(0, 0.03), (0.15, 0.08), (0.6, 0.085), (0.85, 0.11), (1, 0.02)], sweep=0.55, paint=fin),
                      dict(kind="median", side=-1, **{"from": 0.55}, to=0.88, height=[(0, 0.03), (0.3, 0.085), (0.75, 0.1), (1, 0.02)], sweep=0.6, paint=fin),
                      dict(kind="paired", at=(0.27, -0.2), length=0.18, spread=26, out=22, down=18, shape=lambda a: 1 - 0.3 * a * a,
                           paint=lambda a, r: rays((0.3, 0.55, 1.0), a, 10)),
                      dict(kind="paired", at=(0.32, -0.97), length=0.16, spread=16, out=10, down=55, paint=lambda a, r: rays((0.2, 0.6, 1.0), a, 6))])


def dottyback():
    dusk, gold, line, slate = (0.26, 0.19, 0.36), (1.0, 0.76, 0.03), (0.80, 0.30, 0.02), (0.20, 0.22, 0.36)

    def paint(s, h, z):
        colour = mix(dusk, gold, smooth(0.3, 0.8, s + 0.1 * h))
        stripes = smooth(0.4, 0.9, sin(TAU * z * 30)) * smooth(0.2, 0.45, s) * smooth(0.95, 0.75, s)
        return mix(colour, line, 0.75 * stripes)

    return dict(length=96,
                top=[(0, 0.0), (0.04, 0.075), (0.12, 0.14), (0.3, 0.17), (0.6, 0.16), (0.85, 0.11), (1, 0.08)],
                bottom=[(0, -0.03), (0.05, -0.09), (0.15, -0.14), (0.35, -0.155), (0.6, -0.14), (0.85, -0.1), (1, -0.075)],
                width=[(0, 0.02), (0.08, 0.06), (0.25, 0.085), (0.5, 0.08), (0.8, 0.05), (1, 0.025)],
                paint=paint, eye=dict(at=(0.1, 0.5), r=0.045, pupil=(0.005, 0.005, 0.01), iris=(0.2, 0.62, 0.95)),
                tail=dict(length=0.27, spread=44, shape=lambda a: 1 - 0.1 * a * a,
                          paint=lambda a, r: rays(mix(gold, (1.0, 0.95, 0.7), smooth(0.6, 1.0, r)), a, 14)),
                fins=[dict(kind="median", **{"from": 0.2}, to=0.96, height=[(0, 0.03), (0.1, 0.09), (0.8, 0.11), (0.95, 0.09), (1, 0.02)], sweep=0.5,
                           paint=lambda a, r: rays(mix(slate, (0.85, 0.85, 0.95), smooth(0.7, 1.0, r)), a, 40)),
                      dict(kind="median", side=-1, **{"from": 0.5}, to=0.96, height=[(0, 0.02), (0.2, 0.08), (0.8, 0.1), (1, 0.02)], sweep=0.5,
                           paint=lambda a, r: rays(gold, a, 24)),
                      dict(kind="paired", at=(0.25, -0.15), length=0.17, spread=26, out=22, down=15, shape=lambda a: 1 - 0.3 * a * a,
                           paint=lambda a, r: rays((0.6, 0.48, 0.5), a, 10)),
                      dict(kind="paired", at=(0.26, -0.97), length=0.16, spread=14, out=10, down=55, paint=lambda a, r: rays(gold, a, 6))])


SPECIES = {"tang": tang, "surgeon": surgeon, "mandarin": mandarin, "lionfish": lionfish, "damsel": damsel, "dottyback": dottyback}

# ---- stage -----------------------------------------------------------------------------
PX = 300 if LOOK else 100
scene = rig.reset(samples=40 if LOOK else 72)
rig.tank_light(scene, key=3.0, sky=0.8, sand=0.6)
cam = rig.camera(scene, elevation=0)
cam.location = (0, -30, 0)

SKIN = rig.material("Fish skin", (0.5, 0.5, 0.5), 0.5, Coat_Weight=0.08, Sheen_Weight=0.2)
g = rig.Graph(SKIN)
g.to("Base Color", g.attribute("tint").outputs["Color"])
g.to("Emission Color", g.attribute("tint").outputs["Color"])
g.to("Emission Strength", 0.08)
g.bump(g.noise(g.coords(), scale=90, detail=2).outputs["Fac"], strength=0.12, distance=0.004)
EYE = rig.material("Fish eye", (0.01, 0.01, 0.01), 0.05, Coat_Weight=1.0)
rig.Graph(EYE).to("Base Color", rig.Graph(EYE).attribute("tint").outputs["Color"])


def pose(objects, shapes, heading):
    """Put every object into one of its shapes (straight or bent) and turn it to a heading."""
    for obj, coords in zip(objects, shapes):
        obj.data.vertices.foreach_set("co", coords)
        obj.data.update()
        obj.rotation_euler.z = -math.radians(heading)


def shot(path, show, hide):
    for obj in show:
        obj.hide_render = False
    for obj in hide:
        obj.hide_render = True
    rig.render(scene, path)
    return rig.read_pixels(path)


def cut(pixels):
    """The picture cropped to what is in it: (crop, left, top)."""
    solid = pixels[..., 3] > 2 / 255
    if not solid.any():
        return pixels[:2, :2] * 0, 0, 0
    ys, xs = np.flatnonzero(solid.any(axis=1)), np.flatnonzero(solid.any(axis=0))
    return pixels[ys[0]:ys[-1] + 1, xs[0]:xs[-1] + 1], int(xs[0]), int(ys[0])


for name, make in SPECIES.items():
    if ONLY not in (None, name):
        continue
    fish = Fish(make())
    objects = [fish.skin.build(scene, name, SKIN), fish.eyes.build(scene, name + " eyes", EYE), fish.tail.build(scene, name + " tail", SKIN)]
    body, tail = objects[:2], objects[2:]
    shapes, hinges = {}, {}
    for key, angle in (("", 0.0), ("p2", BEND), ("m2", -BEND)):
        bend = bender(fish.rear, angle) if angle else (lambda p: p)
        shapes[key] = [np.array([c for v in mesh.verts for c in bend(Vector(v))], dtype=np.float32) for mesh in (fish.skin, fish.eyes, fish.tail)]
        hinges[key] = bend(fish.hinge)
    # One frame for every view: wide enough for the fish at any heading and in any shape.
    reach = max(float(np.hypot(c[0::3], c[1::3]).max()) for group in shapes.values() for c in group)
    rise = max(float(np.abs(c[2::3]).max()) for group in shapes.values() for c in group)
    width, tall = 2 * math.ceil(reach * PX) + 8, 2 * math.ceil(rise * PX) + 8
    scene.render.resolution_x, scene.render.resolution_y = width, tall
    cam.data.ortho_scale = max(width, tall) / PX
    frame = OUT / "_view.png"

    if LOOK:
        strip = np.zeros((tall, width * 5, 4), dtype=np.float32)
        for i, (key, heading) in enumerate((("", 0), ("", 44), ("", 90), ("", -50), ("p2", 24))):
            pose(objects, shapes[key], heading)
            strip[:, i * width:(i + 1) * width] = shot(frame, objects, [])
        rig.write_pixels(OUT / f"{name}_look.png", strip)
    else:
        sprites, views = [], {"": [], "p2": [], "m2": []}
        for key in views:
            for heading in (DEG if not key else DEG[BEND_FROM:]):
                pose(objects, shapes[key], heading)
                turn = math.radians(-heading)
                hinge = hinges[key]
                hx, hy = (hinge.x * cos(turn) - hinge.y * sin(turn)) * PX, -hinge.z * PX
                view = []
                for show, hide in ((body, tail), (tail, body)):
                    crop, left, top = cut(shot(frame, show, hide))
                    view.append((len(sprites), width / 2 - left, tall / 2 - top))
                    sprites.append(crop)
                views[key].append((view, hx, hy))
        # Pack the sprites onto shelves, tallest first.
        sheet_w = 2048 if sum(s.shape[0] * s.shape[1] for s in sprites) > 900_000 else 1024
        placed, x, y, shelf = {}, 0, 0, 0
        for i in sorted(range(len(sprites)), key=lambda i: -sprites[i].shape[0]):
            h, w = sprites[i].shape[:2]
            if x + w > sheet_w:
                x, y, shelf = 0, y + shelf + 2, 0
            placed[i] = (x, y)
            x, shelf = x + w + 2, max(shelf, h)
        sheet = np.zeros((y + shelf, sheet_w, 4), dtype=np.float32)
        for i, sprite in enumerate(sprites):
            px, py = placed[i]
            sheet[py:py + sprite.shape[0], px:px + sprite.shape[1]] = sprite
        rig.write_pixels(OUT / f"{name}_atlas0.png", sheet)

        def rows(key):
            out = []
            for ((b, bx, by), (t, tx, ty)), hx, hy in views[key]:
                out.append([round(bx, 1), round(by, 1), round(tx, 1), round(ty, 1), round(hx, 1), round(hy, 1),
                            0, *placed[b], sprites[b].shape[1], sprites[b].shape[0], 0, *placed[t], sprites[t].shape[1], sprites[t].shape[0]])
            return out

        block = {"deg": DEG, "pages": 1, "v": rows(""), "bend": {"from": BEND_FROM, "sets": {"p2": rows("p2"), "m2": rows("m2")}}}
        (OUT / f"{name}.json").write_text(json.dumps(block, separators=(",", ":")) + "\n")
        print("FISH", name, "sheet", sheet.shape[1], "x", sheet.shape[0], "from", len(sprites), "sprites")
    frame.unlink(missing_ok=True)
    for obj in objects:
        bpy.data.meshes.remove(obj.data)
