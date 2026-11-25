"""Check packaged fish atlas geometry and estimate image storage. Requires Pillow."""
import argparse
import json
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from PIL import Image


def texture_size(size, scale):
    return tuple(int(side / scale + 0.5) for side in size)


def check_views(name, config, images):
    pages = [images[f"images/{name}_atlas{i}.png"] for i in range(config["pages"])]
    angles = config["deg"]
    if len(config["v"]) != len(angles) or angles != sorted(set(angles)):
        raise ValueError(f"{name}: inconsistent headings")

    poses = list(config["v"])
    if "bend" in config:
        bend = config["bend"]
        for key, rows in bend["sets"].items():
            if len(rows) != len(angles[bend["from"]:]):
                raise ValueError(f"{name}/{key}: inconsistent bend pose count")
            poses.extend(rows)

    for pose in poses:
        for offset in (6, 11):
            page, x, y, w, h = pose[offset:offset + 5]
            if not 0 <= page < len(pages):
                raise ValueError(f"{name}: invalid page {page}")
            width, height = pages[page]
            if not (0 <= x < x + w <= width and 0 <= y < y + h <= height):
                raise ValueError(f"{name}: rectangle outside page {page}: {x,y,w,h}")
            # AtlasRegion rounds each edge independently after LoadTexture shrinks a page.
            sw, sh = texture_size(pages[page], 1.5)
            for start, end, full, small in ((x, x+w, width, sw), (y, y+h, height, sh)):
                if int(start * small / full + 0.5) >= int(end * small / full + 0.5):
                    raise ValueError(f"{name}: empty reduced-resolution sprite")
    return len(poses) * 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("zip", type=Path)
    with ZipFile(parser.parse_args().zip) as archive:
        scene = json.loads(archive.read("scenes/tank.json"))
        images = {}
        for path in archive.namelist():
            if path.startswith("images/") and not path.endswith("/"):
                with Image.open(BytesIO(archive.read(path))) as image:
                    image.load()
                    images[path] = image.size
    count = 0
    for name, species in scene["species"].items():
        count += check_views(name, species["views"], images)
        if "ball" in species:
            count += check_views(name + "_ball", species["ball"], images)
    print(f"{count} body and tail regions pass at both texture scales.")
    # Only pages, background tiles and reef pieces use LoadTexture in this baseline.
    scaled = {p.removeprefix("pkg:/") for p in scene["pan"]["bg"]}
    scaled.update(piece["img"].removeprefix("pkg:/") for piece in scene["pan"]["pieces"])
    scaled.update(path for path in images if "_atlas" in path)
    # The shrimp's frames and the Christmas set's two big sheets go through LoadTexture as well.
    scaled.update(path for path in ("images/shrimp.png", "images/santa_moray.png", "images/xmas_lights.png") if path in images)
    # So do the store edition's glow pictures.
    scaled.update(path for path in images if "_glow" in path)
    for scale in (1, 1.5):
        total = 0
        for path, size in images.items():
            if path.startswith(("images/icon_", "images/splash_")):
                continue
            w, h = texture_size(size, scale if path in scaled else 1)
            total += w * h * 4
        print(f"Scale {scale}: {total / 2**20:.2f} MiB of scene image pixels at 4 bytes/pixel.")


if __name__ == "__main__":
    main()
