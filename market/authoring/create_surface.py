"""Bake the store edition's water surface: the reef mirrored in the underside of the water,
rippling in a seamless cycle.

    blender -b --factory-startup --python-exit-code 1 -P market/authoring/create_surface.py

Run after create_reefscape.py. The top of the plate is plain water, so the surface is made
here: the reef (market/art/reefscape) is mirrored about the waterline and squeezed, as it
looks from below at a shallow angle, then laid faintly over the plate's top band and rippled.
Writes market/art/surface_ripple.png: 24 frames, one above the next, at a quarter of the
tank's scale. The app draws the current frame over the top 96 px of the tank.
"""
import json
import sys
from pathlib import Path

import numpy as np

ART = Path(__file__).resolve().parents[1] / "art"
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "authoring/christmas"))
import rig  # noqa: E402

HEIGHT, FRAMES, SHRINK = 96, 24, 4
MIRRORED = 620          # how many rows of the tank below the band show in it

plate = rig.read_pixels(ART / "reefscape/plate.jpg")[..., :3]
tank = plate.copy()
for info in sorted((ART / "reefscape").glob("*.json")):
    at = json.loads(info.read_text())
    piece = rig.read_pixels(info.with_suffix(".png"))
    region = tank[at["y"]:at["y"] + piece.shape[0], at["x"]:at["x"] + piece.shape[1]]
    piece = piece[:region.shape[0], :region.shape[1]]
    region[:] = region * (1 - piece[..., 3:]) + piece[..., :3] * piece[..., 3:]
width = tank.shape[1]

# The mirror image: the reef's top lies nearest the bottom of the band, deeper rows above it.
rows = np.arange(HEIGHT + 5)
source = np.clip(HEIGHT + (HEIGHT - rows) / HEIGHT * MIRRORED, 0, tank.shape[0] - 1).astype(int)
mirror = tank[source]
# Soften it sideways, as a rippled mirror does, and take it toward the water's own blue.
kernel = np.ones(25) / 25
mirror = np.stack([np.apply_along_axis(lambda line: np.convolve(line, kernel, mode="same"), 1, mirror[..., c]) for c in range(3)], axis=-1)
mirror = mirror * 0.75 + np.array([0.02, 0.10, 0.22]) * 0.25
strength = np.clip((HEIGHT - 14 - rows) / 50, 0, 1)[:, None, None] * 0.6      # nothing of it at the band's lower edge
water = plate[:HEIGHT + 5] * (1 - strength) + mirror * strength
# The band lightens toward the surface.
water = water + np.clip((30 - rows) / 30, 0, 1)[:, None, None] * np.array([0.03, 0.07, 0.10])

y, x = np.mgrid[:HEIGHT, :width]
falloff = np.clip((HEIGHT - 1 - y) / 40, 0, 1)
falloff *= falloff * (3 - 2 * falloff)
small = np.zeros((HEIGHT // SHRINK * FRAMES, width // SHRINK, 4), dtype=np.float32)
small[..., 3] = 1
for i in range(FRAMES):
    phase = 2 * np.pi * i / FRAMES
    wave = x / 107 + y / 7 - phase
    swell = x / 248 - y / 13 + phase
    sx = np.clip(x + falloff * (5.4 * np.sin(wave) + 3 * np.sin(swell)), 0, width - 1)
    sy = np.clip(y + falloff * (2.1 * np.sin(x / 83 + y / 22 - phase) + 1.2 * np.cos(swell * 2)), 0, HEIGHT + 3)
    x0, y0 = sx.astype(int), sy.astype(int)
    x1 = np.minimum(x0 + 1, width - 1)
    fx, fy = (sx - x0)[..., None], (sy - y0)[..., None]
    frame = (1 - fy) * ((1 - fx) * water[y0, x0] + fx * water[y0, x1]) + fy * ((1 - fx) * water[y0 + 1, x0] + fx * water[y0 + 1, x1])
    # Box-shrink each frame on its own, so none bleeds into the next.
    frame = frame[:, :width // SHRINK * SHRINK].reshape(HEIGHT // SHRINK, SHRINK, width // SHRINK, SHRINK, 3).mean(axis=(1, 3))
    small[i * (HEIGHT // SHRINK):(i + 1) * (HEIGHT // SHRINK), :, :3] = frame
rig.write_pixels(ART / "surface_ripple.png", small)
print("SURFACE", small.shape[1], "x", small.shape[0])
