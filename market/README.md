# Seasons Reef tank: the store edition

This folder is the channel we list on the Roku store. It began on 2026-11-24 as a copy of Rellie Reef as packaged that day, and it is now its own source: change it freely. Nothing here is read by the Rellie Reef build, and nothing in `app/` or `authoring/` is read by this one.

| Path | Contents |
|---|---|
| `app/` | The channel as it runs: manifest, BrightScript, the settings screen, the scene and every picture, at full quality. |
| `authoring/` | Blender scripts that build and render this edition's reef. |
| `art/` | What those scripts make, and the other sources for this edition's pictures: the rendered reef, the layout, the light strings, the "Seasons Reef" stone and the capture the icons are cut from. |
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
- The floor stone reads "Seasons Reef" (`images/custom_seasons_quartz.png`, made from `art/seasons_quartz.png` by `reef.py`).
- The size measures above.

To remake the stone or the icons:

```sh
blender -b --factory-startup --python-exit-code 1 -P authoring/create_quartz.py -- market/art/new_stone.blend "Seasons Reef"
blender -b market/art/new_stone.blend -P authoring/export_sprite.py
python market/branding.py
```

`create_quartz.py` will not overwrite an existing `.blend`. For the icons, open the preview with `?market=1&cam=285&hour=23`, run `capture("name")` in the browser console, and save the frame from `build/captures/` as `art/branding_scene.jpg`.

## The reef

The tank and its reef are our own, rendered in Blender:

```sh
blender -b --factory-startup --python-exit-code 1 -P market/authoring/create_reefscape.py
blender -b --factory-startup --python-exit-code 1 -P market/authoring/create_reefscape.py -- --glow
blender -b --factory-startup --python-exit-code 1 -P market/authoring/create_surface.py
python market/strings.py
blender -b --factory-startup --python-exit-code 1 -P market/authoring/create_lights.py
python market/reef.py
python market/build.py
```

- `authoring/create_reefscape.py` builds the empty tank and three structures (an arch, a low mound of large corals, and a cave rock for the moray) and renders each on its own into `art/reefscape/`. `-- --draft` is quick and rough; `-- --only <name>` renders one structure; `-- --plate` renders the empty tank alone, for work on the sand. The sand is combed into rows of ripples with darker grains in the troughs, and strewn with coral rubble and grit, so that it keeps some texture when the tank is dim. `authoring/reef_kit.py` holds the corals, the rock and their materials.
- `authoring/create_surface.py` mirrors the reef in the underside of the water and bakes the ripple.
- `strings.py` seats the light strings on the reef: `art/string_guides.json` holds a rough line for each string, and it moves every anchor onto coral or rock and adds anchors wherever the wire would sag over open water. It writes `art/strings.json`. Run it again whenever a structure is re-rendered.
- `authoring/create_lights.py` strings Christmas lights along the anchor points in `art/strings.json`.
- `reef.py` lays all of it into `app/`: background tiles, reef pieces, the coral maps the fish steer by, the moray mirrored into the cave, the Christmas set at its places (the fireplace's picture, its fire and its mantel and wreath lights come from `authoring/christmas/`, which both editions share), the bulbs, the embers that glow in the hearth in Night Lite, the shrimp's routes and the fish's haunts. Positions that are ours to choose are in `art/layout.json`.

`art/reefscape/preview.jpg` is the tank with its structures and nothing else. The moray's frames in `art/moray/` are as rendered for Rellie Reef, facing left; `reef.py` mirrors them.

Not yet in this reef: an everyday moray (the cave is empty when the Christmas reef is off), feather dusters, a starfish and an anemone.

## Glow at night

At night and in Night Lite the reef fluoresces a little, as corals do under a tank's blue light. It is an accent: sparse highlights, well short of full brightness, so the night stays dark and the tree's lights stay the brightest things in it. Everything that glows has a second picture holding only its light, drawn over the night's dark so that it shines out of it:

- **Corals.** `create_reefscape.py -- --glow` renders each structure again with every material swapped for its glow: the very tips of branching corals and sea fans, a thin line round the rims of plates, the mouths of zoanthids and star corals, the grooves of brain corals. Only patches of the reef are lit at all. `reef.py` splits each structure's glow into two half-size pictures in soft patches, and the app brightens one while it dims the other. Its strength is `GLOW_ALPHA` in `glow.brs`.
- **Sand.** The same run renders `floor_glow.png`: the sand lit by the whole reef's glow, at a quarter of the tank's size. `reef.py` cuts the reef itself out of it and the app lays it faintly over the floor, so the sand near the corals takes some of their colour.
- **Fish.** Each fish has a glow paint beside its colours in `create_fish.py` (fin edges, the lines of its pattern, the ring of its eye), baked into `<name>_glow0.png`, a sheet laid out like its sprites.
- **Shrimp.** `authoring/shrimp/create_shrimp.py -- --glow market/art/shrimp_glow.png` renders the shrimp's red lines, leg joints, feelers and eyes.

The glow never shows through anything. A frame is drawn from the back: the water and the fish behind the reef, the reef with its light strings, the night's dark, the reef's glow, and only then what stands or swims in front of the reef (the tree, the fireplace, the gifts, the stone, the lit bulbs, the moray, the shrimp, the fish). Those are solid and are drawn in the night's tint (`s.dim`, set in `reef.brs`), a little lifted so that they read as themselves in the dark, with a fish's glow lines over its body. So a fish is either behind the reef, the tree and all their lights, or in front of all of them. A fish behind the reef shows its glow only in open water. The order is in `PanFrame` (`pan.brs`).

The glow pictures load last, so a Roku short of graphics memory goes without them first. The code is in `app/source/glow.brs`, `fish.brs` and `shrimp.brs`.

## The fish

Six species, modelled and painted in `authoring/create_fish.py`: a regal tang, a lined surgeonfish, a mandarinfish, a lionfish, a leopard damsel and a dottyback.

```sh
blender -b --factory-startup --python-exit-code 1 -P market/authoring/create_fish.py -- --look
blender -b --factory-startup --python-exit-code 1 -P market/authoring/create_fish.py
python market/reef.py
```

`--look` renders a few headings of each fish at three times the size into `art/fish/<name>_look.png`, for a close look while changing a model; `--only <name>` does one species. The full run bakes, for each species, a body and a tail sprite at 26 headings plus two sets with the body bent for turns, the near pectoral fin in each pose of its stroke, and the glow of every one of those sprites. They go into `art/fish/<name>_atlas0.png` and `<name>_glow0.png`, with the positions in `<name>.json`. It takes about a quarter of an hour.

How each species behaves (how many, how fast, whether it schools or pairs, where it likes to hover) is under `fish` in `art/layout.json`. The app turns a fish through its headings, bends it in a turn, beats its tail by squashing the tail sprite toward its hinge, and rows it along by stepping the near pectoral fin through its stroke, out and back. `row` in the layout sets how fast a species rows, in poses a second.

## Reef Glass

Reef Glass is itself listed on the Roku store, and Roku's distribution agreement does not allow apps that are substantially similar to one another. No picture in `app/images` is Reef Glass's any longer: the tank, reef, fish and light sprites (`light.py`) are all made here.

The code is still Reef Glass's, adapted, under Apache-2.0, with its notices in `app/NOTICE.md` and `app/LICENSE`. They must stay in the package. The way the tank behaves (a wide tank the view glides along, fish that turn and school, a day and night cycle) comes from that code.
