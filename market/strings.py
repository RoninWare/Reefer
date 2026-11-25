"""Seat the Christmas light strings on the reef. Requires Pillow.

    python market/strings.py

market/art/string_guides.json holds a rough line for each string, in tank pixels. This walks
each line and moves it onto the coral and rock of the rendered reef (market/art/reefscape),
so that no part of a string hangs over open water: every anchor is put on the nearest solid
part of a structure, and where the wire would sag off the reef between two anchors another
is added between them. A string is cut where the reef gives it nothing to rest on.
Writes market/art/strings.json, which authoring/create_lights.py renders.
"""
import json
import math
from pathlib import Path

from PIL import Image, ImageFilter

ART = Path(__file__).resolve().parent / "art"
REEF = ART / "reefscape"
STEP, REACH, INSET = 72, 70, 5      # px between anchors; how far an anchor may move; how far inside the outline it sits


def reef_mask():
    """White where a structure is solid, on the tank's 3400 x 1080 canvas."""
    mask = Image.new("L", Image.open(REEF / "plate.jpg").size, 0)
    for info in sorted(REEF.glob("*.json")):
        at = json.loads(info.read_text())
        solid = Image.open(info.with_suffix(".png")).getchannel("A").point(lambda v: 255 if v > 220 else 0)
        mask.paste(255, (at["x"], at["y"]), solid)
    return mask


def main():
    mask = reef_mask()
    inner = mask.filter(ImageFilter.MinFilter(2 * INSET + 1)).load()
    outer = mask.load()
    width, height = mask.size

    def solid(x, y, pixels=outer):
        x, y = round(x), round(y)
        return 0 <= x < width and 0 <= y < height and pixels[x, y] > 0

    def seat(x, y):
        """The nearest point of the reef above or below (x, y), or None if there is none close."""
        for away in range(REACH + 1):
            for at in (y - away, y + away):
                if solid(x, at, inner):
                    return [round(x), round(at)]
        return None

    def rests(a, b):
        """Whether the wire from a to b, sagging as create_lights.py hangs it, stays on the reef."""
        span = math.dist(a, b)
        sag = min(30.0, max(6.0, span * 0.13)) * 1.2
        return all(solid(a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u + 4 * sag * u * (1 - u)) for u in (0.25, 0.5, 0.75))

    def join(a, b, out):
        """Add the anchors that carry the wire from a to b. False if the reef does not reach."""
        if rests(a, b):
            out.append(b)
            return True
        if math.dist(a, b) < 30:
            return False
        mid = seat((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        return mid is not None and mid not in (a, b) and join(a, mid, out) and join(mid, b, out)

    guides = json.loads((ART / "string_guides.json").read_text())
    strings = []
    for guide in guides["strings"]:
        # Walk the guide in even steps.
        points, walked = [], []
        for a, b in zip(guide["points"], guide["points"][1:]):
            steps = max(1, round(math.dist(a, b) / STEP))
            walked += [(a[0] + (b[0] - a[0]) * i / steps, a[1] + (b[1] - a[1]) * i / steps) for i in range(steps)]
        walked.append(tuple(guide["points"][-1]))
        runs = [[]]
        for x, y in walked:
            at = seat(x, y)
            if at is None:
                runs.append([])
            elif not runs[-1]:
                runs[-1].append(at)
            else:
                trial = []
                if join(runs[-1][-1], at, trial):
                    runs[-1] += trial
                else:
                    runs.append([at])
        runs = [run for run in runs if len(run) > 2]
        for n, run in enumerate(runs):
            strings.append({"name": guide["name"] + (f" {n + 1}" if len(runs) > 1 else ""), "points": run})
        length = sum(math.dist(a, b) for run in runs for a, b in zip(run, run[1:]))
        print(f'{guide["name"]}: {len(runs)} run(s), {sum(map(len, runs))} anchors, {length:.0f} px')
    lines = ",\n".join("  " + json.dumps(string) for string in strings)
    (ART / "strings.json").write_text(f'{{\n "spacing": {guides["spacing"]},\n "strings": [\n{lines}\n ]\n}}\n')


if __name__ == "__main__":
    main()
