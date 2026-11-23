"""Paint the small effect sprites: chimney bubbles and the coloured glows for bulbs and firelight.

    blender -b --factory-startup --python-exit-code 1 -P authoring/christmas/create_effects.py

Blender is used only for its bundled NumPy and PNG writer. Writes bubbles.png (two 40 px
bubbles side by side) and glows.png (64 px cells: red, green, blue, amber, pink, then firelight).
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rig

GLOW_COLORS = [(255, 70, 60), (70, 255, 110), (80, 150, 255), (255, 196, 70), (255, 105, 205), (255, 150, 60)]


def bubble(size, seed):
    """A thin-walled bubble: bright rim, a window highlight up-left and a faint glint opposite."""
    y, x = np.mgrid[:size, :size]
    c = (size - 1) / 2
    u, v = (x - c) / (c - 1), (y - c) / (c - 1)
    r = np.hypot(u, v)
    angle = np.arctan2(v, u)
    rim = np.exp(-((r - 0.90) / 0.075) ** 2) * (0.50 + 0.30 * np.cos(angle - (2.2 + seed)))
    film = 0.10 * (r < 0.92)
    window = 0.95 * np.exp(-(((u + 0.36) / 0.20) ** 2 + ((v + 0.40) / 0.13) ** 2))
    glint = 0.55 * np.exp(-(((u - 0.42) / 0.10) ** 2 + ((v - 0.46) / 0.16) ** 2))
    alpha = np.clip(rim + film + window + glint, 0, 1) * np.clip((1.0 - r) / 0.06, 0, 1)
    rgba = np.empty((size, size, 4), dtype=np.float32)
    shade = np.clip(0.80 + 0.20 * (window + glint + rim), 0, 1)
    rgba[..., 0], rgba[..., 1], rgba[..., 2] = 0.86 * shade, 0.96 * shade, 1.0 * shade
    rgba[..., 3] = alpha
    return rgba


def glow(size, color, core=0.16, halo=0.42):
    y, x = np.mgrid[:size, :size]
    c = (size - 1) / 2
    r = np.hypot(x - c, y - c) / c
    falloff = np.clip(1 - r, 0, 1) ** 2
    alpha = (0.85 * np.exp(-(r / core) ** 2) + 0.55 * np.exp(-(r / halo) ** 2)) * np.clip((1 - r) / 0.25, 0, 1)
    rgba = np.empty((size, size, 4), dtype=np.float32)
    # White-hot at the centre, the bulb's own colour through the halo.
    heat = np.exp(-(r / (core * 0.8)) ** 2)[..., None]
    rgba[..., :3] = (np.array(color) / 255.0) * (1 - 0.75 * heat) + 0.75 * heat
    rgba[..., 3] = np.clip(alpha, 0, 1) * (0.25 + 0.75 * falloff ** 0.25)
    return rgba


rig.write_pixels(rig.HERE / "bubbles.png", np.concatenate([bubble(40, 0.0), bubble(40, 0.9)], axis=1))
rig.write_pixels(rig.HERE / "glows.png", np.concatenate(
    [glow(64, color) for color in GLOW_COLORS[:5]] + [glow(64, GLOW_COLORS[5], core=0.30, halo=0.62)], axis=1))
print("EFFECTS written")
