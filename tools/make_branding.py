"""Render Rellie Reef's splash screens and screensaver icons into app/images. Requires Pillow.

    python tools/make_branding.py

The splash is the title on the tank's dark blue. The icons are a picture of the running tank
(authoring/branding/scene.jpg, a 16:9 capture from the local preview) with the title over it.
The title is set in Georgia; pass --font for another TrueType file.
"""
import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "app/images"
TITLE = "Rellie Reef"
NAVY, PALE = (6, 24, 42), (230, 242, 245)


def title_layer(size, font_path, height, centre_y, shadow):
    """The title centred at centre_y, its capitals about `height` pixels tall."""
    font = ImageFont.truetype(str(font_path), round(height * 1.38))
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    left, top, right, bottom = draw.textbbox((0, 0), TITLE, font=font)
    at = ((size[0] - (right - left)) / 2 - left, centre_y - (bottom - top) / 2 - top)
    if shadow:
        dark = Image.new("RGBA", size, (0, 0, 0, 0))
        ImageDraw.Draw(dark).text((at[0], at[1] + height * 0.06), TITLE, font=font, fill=(0, 12, 28, 235))
        layer = dark.filter(ImageFilter.GaussianBlur(height * 0.09))
        draw = ImageDraw.Draw(layer)
    draw.text(at, TITLE, font=font, fill=(*PALE, 255))
    return layer


def cover(image, size):
    """Scale and centre-crop to fill size."""
    scale = max(size[0] / image.width, size[1] / image.height)
    image = image.resize((round(image.width * scale), round(image.height * scale)), Image.Resampling.LANCZOS)
    left, top = (image.width - size[0]) // 2, (image.height - size[1]) // 2
    return image.crop((left, top, left + size[0], top + size[1]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font", type=Path, default=Path("C:/Windows/Fonts/georgia.ttf"))
    parser.add_argument("--scene", type=Path, default=ROOT / "authoring/branding/scene.jpg")
    args = parser.parse_args()
    for name, size in (("fhd", (1920, 1080)), ("hd", (1280, 720)), ("sd", (720, 480))):
        splash = Image.new("RGBA", size, (*NAVY, 255))
        splash.alpha_composite(title_layer(size, args.font, size[1] * 0.068, size[1] * 0.49, shadow=False))
        splash.convert("RGB").save(OUT / f"splash_{name}.jpg", quality=92)
    scene = Image.open(args.scene).convert("RGB")
    for name, size in (("fhd", (540, 405)), ("hd", (290, 218)), ("sd", (246, 140))):
        icon = cover(scene, size).convert("RGBA")
        icon.alpha_composite(title_layer(size, args.font, size[1] * 0.118, size[1] * 0.17, shadow=True))
        icon.convert("RGB").save(OUT / f"icon_{name}.jpg", quality=92)
    print("Branding written to", OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
