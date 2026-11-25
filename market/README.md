# Seasons Reef tank: the store edition

This folder is the channel we list on the Roku store. It began on 2026-11-24 as a copy of Rellie Reef as packaged that day, and it is now its own source: change it freely. Nothing here is read by the Rellie Reef build, and nothing in `app/` or `authoring/` is read by this one.

| Path | Contents |
|---|---|
| `app/` | The channel as it runs: manifest, BrightScript, the settings screen, the scene and every picture, at full quality. |
| `authoring/` | Blender scripts that build and render this edition's reef. |
| `art/` | What those scripts make, and the other sources for this edition's pictures: the rendered reef, the layout, the light strings, the "Holiday Reef" stone and the capture the icons are cut from. |
| `reef.py` | Lays the rendered reef and the fish into `app/`. |
| `light.py` | Draws the light shaft, marine snow and shadow sprites. |
| `build.py` | Packs `app/` into `build/seasons-reef-tank.zip` and fails if it is over Roku's limit. |
| `branding.py` | Renders the splash screens and icons into `app/images`. |

## Build and preview

```sh
pip install pillow imagequant zopfli
python market/build.py
python tools/check_scene.py build/seasons-reef-tank.zip
```

The first build takes about a minute while the pictures are packed; later builds reuse `build/market-cache`. `python market/build.py --list` shows the size of every file in the package.

To see it running, start the preview (`python preview/run.py`) and open `http://127.0.0.1:8765/?market=1`. The other preview options work with it: `cam`, `hour`, `christmas=0`, `nightlite=1`, `resolution=720`.

## The size limit

Roku lists an app only if its file is 4 MB or less (certification criterion 3.7). The build is about 3.4 MB. What keeps it there:

- **Fish.** Each fish sheet has 26 headings and one strength of body bend toward each flank, where Rellie Reef's have three. `fish.brs` shows that bend from a third of a full turn up. The lionfish's sheet is the largest picture in the package, because of its fins.
- **Water surface.** `surface_ripple.jpg` is stored at a quarter of the tank's scale and `surface.brs` draws it four times as large.
- **Packing.** `build.py` reduces full-colour PNGs to 256-colour palettes, repacks every PNG with zopfli, and saves the backgrounds and the water surface again as smaller JPEGs. `PICTURES` in `build.py` holds the settings.

Pictures in `app/images` stay at full quality, so a setting can be changed and the build run again. New art has to fit in what is left under the limit: check with `--list`.

## What differs from Rellie Reef

- The title is "Seasons Reef tank" (manifest, settings screen, splash screens, icons).
- The floor stone reads "Holiday Reef" (`images/custom_holiday_quartz.png`).
- The size measures above.

To remake the stone or the icons:

```sh
blender -b --factory-startup --python-exit-code 1 -P authoring/create_quartz.py -- market/art/new_stone.blend "Holiday Reef"
blender -b market/art/new_stone.blend -P authoring/export_sprite.py
python market/branding.py
```

`create_quartz.py` will not overwrite an existing `.blend`. For the icons, open the preview with `?market=1&cam=285&hour=23`, run `capture("name")` in the browser console, and save the frame from `build/captures/` as `art/branding_scene.jpg`.

## The reef

The tank and its reef are our own, rendered in Blender:

```sh
blender -b --factory-startup --python-exit-code 1 -P market/authoring/create_reefscape.py
blender -b --factory-startup --python-exit-code 1 -P market/authoring/create_surface.py
python market/strings.py
blender -b --factory-startup --python-exit-code 1 -P market/authoring/create_lights.py
python market/reef.py
python market/build.py
```

- `authoring/create_reefscape.py` builds the empty tank and three structures (an arch, a low mound of large corals, and a cave rock for the moray) and renders each on its own into `art/reefscape/`. `-- --draft` is quick and rough; `-- --only <name>` renders one structure. `authoring/reef_kit.py` holds the corals, the rock and their materials.
- `authoring/create_surface.py` mirrors the reef in the underside of the water and bakes the ripple.
- `strings.py` seats the light strings on the reef: `art/string_guides.json` holds a rough line for each string, and it moves every anchor onto coral or rock and adds anchors wherever the wire would sag over open water. It writes `art/strings.json`. Run it again whenever a structure is re-rendered.
- `authoring/create_lights.py` strings Christmas lights along the anchor points in `art/strings.json`.
- `reef.py` lays all of it into `app/`: background tiles, reef pieces, the coral maps the fish steer by, the moray mirrored into the cave, the Christmas set at its places, the bulbs, the embers that glow in the hearth in Night Lite, the shrimp's routes and the fish's haunts. Positions that are ours to choose are in `art/layout.json`.

`art/reefscape/preview.jpg` is the tank with its structures and nothing else. The moray's frames in `art/moray/` are as rendered for Rellie Reef, facing left; `reef.py` mirrors them.

Not yet in this reef: an everyday moray (the cave is empty when the Christmas reef is off), feather dusters, a starfish and an anemone.

## The fish

Six species, modelled and painted in `authoring/create_fish.py`: a regal tang, a lined surgeonfish, a mandarinfish, a lionfish, a leopard damsel and a dottyback.

```sh
blender -b --factory-startup --python-exit-code 1 -P market/authoring/create_fish.py -- --look
blender -b --factory-startup --python-exit-code 1 -P market/authoring/create_fish.py
python market/reef.py
```

`--look` renders a few headings of each fish at three times the size into `art/fish/<name>_look.png`, for a close look while changing a model; `--only <name>` does one species. The full run bakes, for each species, a body and a tail sprite at 26 headings plus two sets with the body bent for turns, into `art/fish/<name>_atlas0.png` with the positions in `<name>.json`. It takes about five minutes.

How each species behaves (how many, how fast, whether it schools or pairs, where it likes to hover) is under `fish` in `art/layout.json`. The app's fish code is unchanged: it turns a fish through its headings, bends it in a turn and beats its tail by squashing the tail sprite toward its hinge.

## Reef Glass

Reef Glass is itself listed on the Roku store, and Roku's distribution agreement does not allow apps that are substantially similar to one another. No picture in `app/images` is Reef Glass's any longer: the tank, reef, fish and light sprites (`light.py`) are all made here.

The code is still Reef Glass's, adapted, under Apache-2.0, with its notices in `app/NOTICE.md` and `app/LICENSE`. They must stay in the package. The way the tank behaves (a wide tank the view glides along, fish that turn and school, a day and night cycle) comes from that code.
