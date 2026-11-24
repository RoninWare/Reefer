"""Draw the store edition's three light sprites into market/app/images. Requires Pillow.

    python market/light.py

  ray.png    a shaft of light from the surface: bright at the top, fading down and to its sides
  mote.png   a speck of drifting marine snow
  puff.png   a soft round blot, used for shadows on the sand

Each is white (the ray a pale blue) with the shape in its alpha, drawn from a formula.
"""
import math
from pathlib import Path

from PIL import Image

IMAGES = Path(__file__).resolve().parent / "app/images"


def sprite(size, colour, alpha):
    """An image of one colour whose opacity at (x, y) is alpha(x, y), from 0 to 1."""
    w, h = size
    image = Image.new("RGBA", size, (*colour, 0))
    image.putalpha(Image.frombytes("L", size, bytes(round(255 * max(0.0, min(1.0, alpha(x, y)))) for y in range(h) for x in range(w))))
    return image


def bell(distance, reach):
    """1 at the middle falling smoothly to 0 at `reach`."""
    return math.exp(-4.5 * (distance / reach) ** 2) if distance < reach else 0.0


def ray(x, y):
    w, h = 160, 680
    down = y / (h - 1)
    spread = 22 + 26 * down                        # a shaft widens as it goes down
    return 0.98 * (1 - down) ** 1.35 * bell(abs(x - (w - 1) / 2), spread * 1.6)


sprite((160, 680), (228, 244, 255), ray).save(IMAGES / "ray.png")
sprite((8, 8), (255, 255, 255), lambda x, y: 0.68 * bell(math.hypot(x - 3.5, y - 3.5), 5.2)).save(IMAGES / "mote.png")
sprite((24, 24), (255, 255, 255), lambda x, y: 0.88 * bell(math.hypot(x - 11.5, y - 11.5), 13.5)).save(IMAGES / "puff.png")
print("Light sprites written to", IMAGES.relative_to(IMAGES.parents[2]))
