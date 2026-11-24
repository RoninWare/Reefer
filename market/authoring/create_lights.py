"""Drape strings of Christmas lights over the store edition's reef and bake them into tiles.

    blender -b --factory-startup --python-exit-code 1 -P market/authoring/create_lights.py

market/art/strings.json lists each string's anchor points in tank pixels (where the wire
rests on a coral). The wire sags between anchors and carries a bulb every `spacing` pixels.
The whole tank is rendered once, straight on, then cut into tight tiles so empty water costs
no texture memory. Writes market/art/lights.png (the tile atlas) and lights.json (tile and
bulb positions in tank pixels; the app draws a twinkling glow on each bulb).

The method is Rellie Reef's (authoring/christmas/create_lights.py); the strings are this reef's.
"""
import json
import math
import random
import sys
from pathlib import Path

import numpy as np
from mathutils import Vector

ART = Path(__file__).resolve().parents[1] / "art"
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "authoring/christmas"))
import rig  # noqa: E402

TANK_W, TANK_H = 3400, 1080
COLORS = [(1.0, 0.035, 0.03), (0.03, 0.85, 0.12), (0.04, 0.22, 1.0), (1.0, 0.55, 0.04), (1.0, 0.10, 0.55)]
spec = json.loads((ART / "strings.json").read_text())
scene = rig.reset(samples=96)
rng = random.Random(24)


def tank(x, y, depth=0.0):
    return Vector((x / rig.PX, depth, -y / rig.PX))


wire_mat = rig.material("Wire", (0.006, 0.055, 0.02), 0.5)
socket_mat = rig.material("Socket", (0.008, 0.07, 0.025), 0.45)
bulb_mats = []
for i, color in enumerate(COLORS):
    mat = rig.material(f"Bulb {i}", color, 0.12, Coat_Weight=1.0)
    g = rig.Graph(mat)
    g.to("Emission Color", color)
    g.to("Emission Strength", 1.5)
    bulb_mats.append(mat)

# Bulb outline along its axis: (distance from the socket, radius), in units of 100 px.
SCALE = 1.2
PROFILE = [(0.036, 0.020), (0.052, 0.033), (0.078, 0.041), (0.105, 0.038), (0.132, 0.026), (0.150, 0.012), (0.158, 0.003)]

bulbs = []
count = 0
for string in spec["strings"]:
    anchors = string["points"]
    path = []
    for (x0, y0), (x1, y1) in zip(anchors, anchors[1:]):
        span = math.hypot(x1 - x0, y1 - y0)
        sag = min(30.0, max(6.0, span * 0.13)) * rng.uniform(0.8, 1.2)
        steps = max(6, int(span / 6))
        for s in range(steps):
            u = s / steps
            path.append((x0 + (x1 - x0) * u, y0 + (y1 - y0) * u + 4 * sag * u * (1 - u)))
    path.append(tuple(anchors[-1]))
    points = [tank(x, y, 0.012 * math.sin(i * 0.37)) for i, (x, y) in enumerate(path)]
    verts, faces, _ = rig.sweep(points, [(0.0105, 0.0105)] * len(points), 8)
    rig.add_mesh(scene, f"Wire: {string['name']}", verts, faces, [wire_mat], smooth=True)

    travelled, due = 0.0, spec["spacing"] * 0.5
    for (xa, ya), (xb, yb) in zip(path, path[1:]):
        step = math.hypot(xb - xa, yb - ya)
        while travelled + step >= due:
            u = (due - travelled) / step
            x, y = xa + (xb - xa) * u, ya + (yb - ya) * u
            # Most bulbs hang; a few are knocked sideways, as on any real string.
            tilt = math.radians(rng.uniform(-38, 38) if rng.random() < 0.8 else rng.choice((-1, 1)) * rng.uniform(60, 105))
            direction = Vector((math.sin(tilt), -0.25, -math.cos(tilt))).normalized()
            base = tank(x, y, -0.012)
            sv, sf, _ = rig.sweep([base, base + direction * 0.05 * SCALE], [(0.024 * SCALE,) * 2] * 2, 12)
            rig.add_mesh(scene, "Socket", sv, sf, [socket_mat], smooth=True, sharp_angle=40)
            bv, bf, _ = rig.sweep([base + direction * d * SCALE for d, _ in PROFILE], [(r * SCALE,) * 2 for _, r in PROFILE], 14)
            color = count % len(COLORS)
            rig.add_mesh(scene, "Bulb", bv, bf, [bulb_mats[color]], smooth=True)
            centre = base + direction * 0.092 * SCALE
            bulbs.append([round(centre.x * rig.PX, 1), round(-centre.z * rig.PX, 1), color])
            count += 1
            due += spec["spacing"] * rng.uniform(0.9, 1.1)
        travelled += step

# The coral surface just behind the wire, catching a soft shadow that seats the string on it.
w, h = TANK_W / rig.PX, TANK_H / rig.PX
back = rig.add_mesh(scene, "Coral surface", [(-1, 0.07, 1), (w + 1, 0.07, 1), (w + 1, 0.07, -h - 1), (-1, 0.07, -h - 1)], [(0, 1, 2, 3)],
                    [rig.material("Coral", (0.6, 0.5, 0.5), 0.9)])
back.is_shadow_catcher = True

rig.tank_light(scene)
cam = rig.camera(scene, elevation=0)
cam.location = (w / 2, -30, -h / 2)
cam.data.ortho_scale = w
scene.render.resolution_x, scene.render.resolution_y = TANK_W, TANK_H
full = ART / "_lights_full.png"
rig.render(scene, full)
pixels = rig.read_pixels(full)
full.unlink()

# Cut into tiles: 192 px columns, split wherever a column has a clear gap between strings.
solid = pixels[..., 3] > 3 / 255
tiles = []
for x0 in range(0, TANK_W, 192):
    strip = solid[:, x0:x0 + 192]
    rows = np.flatnonzero(strip.any(axis=1))
    if not len(rows):
        continue
    for run in np.split(rows, np.flatnonzero(np.diff(rows) > 20) + 1):
        y0, y1 = int(run[0]), int(run[-1]) + 1
        cols = np.flatnonzero(strip[y0:y1].any(axis=0))
        tiles.append((x0 + int(cols[0]), y0, int(cols[-1]) - int(cols[0]) + 1, y1 - y0))

# Shelf packing, tallest first.
ATLAS_W = 1024
placed, ax, ay, shelf = {}, 0, 0, 0
for i in sorted(range(len(tiles)), key=lambda i: -tiles[i][3]):
    tw, th = tiles[i][2], tiles[i][3]
    if ax + tw > ATLAS_W:
        ax, ay, shelf = 0, ay + shelf + 1, 0
    placed[i] = (ax, ay)
    ax, shelf = ax + tw + 1, max(shelf, th)
atlas = np.zeros((ay + shelf, ATLAS_W, 4), dtype=np.float32)
layout = []
for i, (x, y, tw, th) in enumerate(tiles):
    px, py = placed[i]
    atlas[py:py + th, px:px + tw] = pixels[y:y + th, x:x + tw]
    layout.append([x, y, px, py, tw, th])
rig.write_pixels(ART / "lights.png", atlas)
bulbs.sort()
(ART / "lights.json").write_text(json.dumps({"tiles": sorted(layout), "bulbs": bulbs}, separators=(",", ":")) + "\n")
print("LIGHTS", len(bulbs), "bulbs,", len(tiles), "tiles, atlas", atlas.shape[1], "x", atlas.shape[0])
