"""Bake the anemone's current cycle and a small golden star glow."""
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import map_coordinates

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "authoring"


def write_anemone():
    x, y, width, height = 1000, 500, 480, 380
    bg = Image.open(ROOT / "app/images/wide_bg0.jpg").convert("RGBA")
    reef = Image.open(ROOT / "app/images/reef_left.png").convert("RGBA")
    bg.alpha_composite(reef, (499, 62))
    rgba = np.asarray(bg.crop((x, y, x+width, y+height)), dtype=float)
    yy, xx = np.mgrid[:height, :width]
    cx, cy = xx-250, yy-176
    radius = np.hypot(cx/224, cy/164)
    edge = np.minimum.reduce((xx, width-1-xx, yy, height-1-yy))
    fade = np.clip(edge/19, 0, 1) * np.clip((1.16-radius)/0.12, 0, 1)
    rgba[..., 3] = 255 * fade
    # Keep the oral disc pinned. Increase displacement toward the tips and
    # vary the phase around the crown so adjacent tentacles fan at different rates.
    tips = np.clip((radius-0.28)/0.54, 0, 1) * fade
    frame_width, frame_height = 336, 266
    atlas = Image.new("RGBA", (frame_width*4, frame_height*3))
    for index in range(12):
        phase = 2*np.pi*index/12
        wave = np.sin(phase + cy/116 + cx/220)
        secondary = np.sin(2*phase - cx/110 + cy/190)
        coords = (yy + tips*(2.0*wave + 2.4*secondary),
                  xx + tips*(8.0*wave + 2.0*secondary))
        warped = rgba.copy()
        for channel in range(3):
            warped[..., channel] = map_coordinates(rgba[..., channel], coords, order=1, mode="nearest")
        frame = Image.fromarray(warped.round().astype("uint8")).resize(
            (frame_width, frame_height), Image.Resampling.LANCZOS)
        atlas.paste(frame, (index % 4 * frame_width, index // 4 * frame_height))
    atlas.quantize(colors=256, method=Image.Quantize.FASTOCTREE).save(ART / "anemone_current.png", optimize=True)


def write_glow():
    y, x = np.mgrid[-64:65, -64:65]
    halo = 0.48*np.exp(-(x*x+y*y)/(2*16**2))
    core = 0.55*np.exp(-(x*x+y*y)/(2*5**2))
    rays = 0.34 * (np.exp(-abs(x)/13-y*y/5) + np.exp(-abs(y)/14-x*x/5))
    pixels = np.empty((129,129,4), dtype="uint8")
    pixels[..., :3] = (255, 222, 143)
    pixels[..., 3] = (255*np.clip(halo+core+rays, 0, 1)).astype("uint8")
    Image.fromarray(pixels).save(ART / "star_glow.png")


if __name__ == "__main__":
    write_anemone()
    write_glow()
