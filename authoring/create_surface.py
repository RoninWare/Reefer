"""Bake a seamless ripple cycle from the tank's own waterline."""
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
HEIGHT = 96
FRAMES = 24
tiles = []
for i in (0, 1):
    image = Image.open(ROOT / f"app/images/wide_bg{i}.jpg")
    tiles.append(np.array(image.crop((0, 0, image.width, HEIGHT+5))))
water = np.concatenate(tiles, axis=1)
width = water.shape[1]
atlas = Image.new("RGB", (width//2, HEIGHT//2 * FRAMES))
y, x = np.mgrid[:HEIGHT, :width]
falloff = np.clip((HEIGHT-1-y)/40, 0, 1)
falloff *= falloff * (3-2*falloff)
for i in range(FRAMES):
    phase = 2*np.pi*i/FRAMES
    wave = x/107 + y/7 - phase
    swell = x/248 - y/13 + phase
    sx = np.clip(x + falloff*(5.4*np.sin(wave) + 3*np.sin(swell)), 0, width-1)
    sy = np.clip(y + falloff*(2.1*np.sin(x/83+y/22-phase) + 1.2*np.cos(swell*2)), 0, HEIGHT+3)
    # Bilinear sampling retains highlight detail between consecutive poses.
    x0, y0 = sx.astype(int), sy.astype(int)
    x1 = np.minimum(x0+1, width-1)
    fx, fy = (sx-x0)[..., None], (sy-y0)[..., None]
    pixels = ((1-fy)*((1-fx)*water[y0,x0]+fx*water[y0,x1])
              + fy*((1-fx)*water[y0+1,x0]+fx*water[y0+1,x1]))
    frame = Image.fromarray(pixels.round().astype('uint8')).resize(
        (width//2, HEIGHT//2), Image.Resampling.LANCZOS)
    atlas.paste(frame, (0, i*(HEIGHT//2)))
atlas.save(ROOT / "authoring/surface_ripple.jpg", quality=92, subsampling=0)
