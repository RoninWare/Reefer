"""Render the store edition's splash screens and icons into market/app/images. Requires Pillow.

    python market/branding.py

The splash is the title on the tank's dark blue. An icon is a picture of the running tank at
night under a dark band that carries the title, so the title covers nothing in the picture.
The picture is market/art/branding_scene.jpg, a full-size capture from the local preview
(open it with ?market=1 and run capture("name") in the browser console; see market/README.md).
The title is set in Georgia; pass --font for another TrueType file.
"""
import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
TITLE = "Seasons Reef tank"
NAVY, PALE = (6, 24, 42), (224, 233, 235)      # the title stays under 235: broadcast-safe


def title_layer(size, font_path, height, centre_y, widest):
    """The title centred at centre_y, its capitals about `height` pixels tall, made smaller if
    it would be wider than `widest`."""
    points = height * 1.38
    while True:
        font = ImageFont.truetype(str(font_path), round(points))
        left, top, right, bottom = font.getbbox(TITLE)
        if right - left <= widest or points < 6:
            break
        points *= 0.96
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    at = ((size[0] - (right - left)) / 2 - left, centre_y - (bottom - top) / 2 - top)
    ImageDraw.Draw(layer).text(at, TITLE, font=font, fill=(*PALE, 255))
    return layer


def cover(image, size):
    """Scale and centre-crop to fill size."""
    scale = max(size[0] / image.width, size[1] / image.height)
    image = image.resize((round(image.width * scale), round(image.height * scale)), Image.Resampling.LANCZOS)
    left, top = (image.width - size[0]) // 2, (image.height - size[1]) // 2
    return image.crop((left, top, left + size[0], top + size[1]))


def icon(scene, size, font_path):
    width, height = size
    band = round(height * 0.17)
    picture = cover(scene, (width, height - band))
    # The band runs into the dark water at the top of the picture with no edge between them.
    fade = Image.new("L", picture.size, 255)
    ramp = round(height * 0.10)
    for y in range(ramp):
        ImageDraw.Draw(fade).line([(0, y), (width, y)], fill=round(255 * (y / ramp) ** 1.5))
    out = Image.new("RGBA", size, (*NAVY, 255))
    out.paste(picture, (0, band), fade)
    out.alpha_composite(title_layer(size, font_path, band * 0.42, band * 0.60, width * 0.90))
    return out.convert("RGB")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font", type=Path, default=Path("C:/Windows/Fonts/georgia.ttf"))
    args = parser.parse_args()
    out = HERE / "app/images"
    for name, size in (("fhd", (1920, 1080)), ("hd", (1280, 720)), ("sd", (720, 480))):
        splash = Image.new("RGBA", size, (*NAVY, 255))
        splash.alpha_composite(title_layer(size, args.font, size[1] * 0.068, size[1] * 0.49, size[0] * 0.8))
        splash.convert("RGB").save(out / f"splash_{name}.jpg", quality=90, optimize=True)
    picture = Image.open(HERE / "art/branding_scene.jpg").convert("RGB")
    for name, size in (("fhd", (540, 405)), ("hd", (290, 218)), ("sd", (246, 140))):
        icon(picture, size, args.font).save(out / f"icon_{name}.jpg", quality=90, optimize=True)
    print("Branding written to", out.relative_to(HERE.parent))


if __name__ == "__main__":
    main()
