"""Build the store edition, "Seasons Reef tank", from market/app. Requires Pillow, imagequant
and zopfli (pip install pillow imagequant zopfli).

    python market/build.py                      writes build/seasons-reef-tank.zip
    python tools/check_scene.py build/seasons-reef-tank.zip

market/app is the channel as it runs, with its pictures at full quality. Roku lists an app
only if its file is 4 MB or less (certification criterion 3.7), so the build packs it tight:

  * a full-colour PNG is reduced to a palette of up to 256 colours with alpha, dithered
    (libimagequant, as Reef Glass's own pictures were)
  * every PNG is then packed again with zopfli, which is slow but loses nothing
  * the JPEGs named in PICTURES are saved again at the quality given there; the rest go in
    as they are. PICTURES also gives some PNGs a smaller palette
  * the scene is written without spaces

The build fails if the package comes out over the limit. Packed pictures are kept in
build/market-cache, keyed by the picture and its settings, so only the first build is slow.
"""
import argparse
import fnmatch
import hashlib
import json
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

import imagequant
import zopfli.png
from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
APP = HERE / "app"
CACHE = ROOT / "build/market-cache"
LIMIT = 4_000_000       # bytes; Roku says "4 MB"
# Per picture: "quality" for a JPEG; for a PNG, "colors" in its palette and "dither" (0 to 1).
# The first pattern a picture's name matches is used.
PICTURES = {
    "wide_bg*.jpg": {"quality": 75},
    "surface_ripple.jpg": {"quality": 86},
    # Glow pictures are a few pure colours fading out: a small palette holds them, undithered.
    "floor_glow.png": {"colors": 128, "dither": 1.0},        # soft light: it needs the steps between
    "reef_*_glow_?.png": {"colors": 64, "dither": 0.0},
    "*_glow*.png": {"colors": 32, "dither": 0.0},
    # The lionfish's sheet is the largest picture, and is only reds, browns and creams.
    "lionfish_atlas0.png": {"colors": 128, "dither": 0.5},
}


def settings_for(name):
    return next((settings for pattern, settings in PICTURES.items() if fnmatch.fnmatch(name, pattern)), {})


def cached(data, settings, suffix, make):
    """make(data), remembered in build/market-cache for this picture and these settings."""
    key = hashlib.sha256(data + json.dumps(settings, sort_keys=True).encode()).hexdigest()[:24]
    path = CACHE / f"{key}{suffix}"
    if not path.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        path.write_bytes(make(data))
    return path.read_bytes()


def pack_png(data, colors=256, dither=1.0):
    """A PNG as small as it goes: a palette if it has none, then zopfli."""
    with Image.open(BytesIO(data)) as image:
        if image.mode == "RGBA":
            out = BytesIO()
            imagequant.quantize_pil_image(image, dithering_level=dither, max_colors=colors).save(out, "PNG")
            data = out.getvalue()
    return zopfli.png.optimize(data, num_iterations=15, num_iterations_large=5)


def pack_jpeg(data, quality):
    out = BytesIO()
    with Image.open(BytesIO(data)) as image:
        image.save(out, "JPEG", quality=quality, optimize=True)
    return out.getvalue()


def contents():
    """Every file of the package, by its path inside it."""
    files = {}
    for path in sorted(APP.rglob("*")):
        if not path.is_file():
            continue
        name, data = path.relative_to(APP).as_posix(), path.read_bytes()
        settings = settings_for(path.name)
        if name.endswith(".png"):
            data = cached(data, settings, ".png", lambda source: pack_png(source, **settings))
        elif name.endswith(".jpg") and settings:
            data = cached(data, settings, ".jpg", lambda source: pack_jpeg(source, **settings))
        elif name.endswith(".json"):
            data = json.dumps(json.loads(data), separators=(",", ":")).encode()
        files[name] = data
    return files


def archive(files):
    out = BytesIO()
    with ZipFile(out, "w", ZIP_DEFLATED, compresslevel=9) as package:
        for name, data in files.items():
            package.writestr(ZipInfo(name), data, compress_type=ZIP_DEFLATED)
    return out.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "build/seasons-reef-tank.zip")
    parser.add_argument("--list", action="store_true", help="show the size of every file in the package")
    args = parser.parse_args()
    data = archive(contents())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(data)
    if args.list:
        with ZipFile(BytesIO(data)) as package:
            for info in sorted(package.infolist(), key=lambda item: -item.compress_size):
                print(f"{info.compress_size:9d}  {info.filename}")
    over = len(data) - LIMIT
    print(f"{args.out.relative_to(ROOT).as_posix()}: {len(data) / 1e6:.2f} MB,",
          f"{-over / 1e3:.0f} KB under Roku's 4 MB limit." if over <= 0 else f"{over / 1e3:.0f} KB OVER Roku's 4 MB limit.")
    raise SystemExit(over > 0)


if __name__ == "__main__":
    main()
