# Credits

## Rellie Reef additions

Made for Rellie Reef, which this store edition began as. The sources and the scripts that make
them are in the repository's `authoring/` folder, or in `market/` where noted.

| Shipped image(s) | Source | Processing |
|---|---|---|
| `custom_holiday_quartz.png` | original procedural Blender model; the stone is engraved in DejaVu Serif Bold and its source is `market/art/holiday_quartz.blend` | `authoring/create_*.py`, rendered by `authoring/export_sprite.py` |
| `custom_tree.png` | original procedural Blender model: a spire of corals with lights, pearls, baubles and a sea star | `authoring/christmas/create_tree.py` |
| `custom_fireplace.png`, `xmas_fire.png` | original procedural Blender model; the flames are an animated shader | `authoring/christmas/create_fireplace.py` |
| `custom_gifts_hearth.png`, `custom_gifts_tree.png` | original procedural Blender models | `authoring/christmas/create_gifts.py` |
| `xmas_lights.png` | original procedural Blender model, draped along anchor points on the reef | `market/authoring/create_lights.py` |
| `santa_moray.png` | original procedural Blender model, rebuilt and rendered for every pose | `authoring/christmas/create_santa_moray.py` |
| `shrimp.png` | original procedural Blender model of a peppermint shrimp, rebuilt and rendered for every frame of its walk and cleaning cycles | `authoring/shrimp/create_shrimp.py` |
| `xmas_glows.png`, `xmas_bubbles.png`, `star_glow.png` | procedural | `authoring/christmas/create_effects.py`, `authoring/create_reef_motion.py` |
| `wide_bg*.jpg`, `reef_arch.png`, `reef_bommie.png`, `reef_grotto.png` | original procedural Blender scene: sand, water, rock and corals | `market/authoring/create_reefscape.py`, `market/authoring/reef_kit.py`, laid in by `market/reef.py` |
| `surface_ripple.jpg` | that scene mirrored in the water's surface and rippled | `market/authoring/create_surface.py` |
| `tang_atlas0.png`, `surgeon_atlas0.png`, `mandarin_atlas0.png`, `lionfish_atlas0.png`, `damsel_atlas0.png`, `dottyback_atlas0.png` | original procedural Blender models of six reef fish, rendered at 26 headings | `market/authoring/create_fish.py` |
| `reef_*_glow_a.png`, `reef_*_glow_b.png`, `*_glow0.png`, `shrimp_glow.png` | the same models rendered showing only what they give off in the dark | `market/authoring/create_reefscape.py`, `market/authoring/create_fish.py`, `authoring/shrimp/create_shrimp.py`, `market/reef.py` |
| `ray.png`, `mote.png`, `puff.png` | drawn from formulas | `market/light.py` |
| `xmas_embers.png` | the glowing parts of the fireplace's own picture: the cracks in the logs and the bed under the grate | `market/reef.py` |
| `santa_cave.png` | the cave's darkness, cut from our own rendered reef and faded out toward the cave mouth | `market/reef.py` |
| `splash_*.jpg`, `icon_*.jpg` | title in Georgia; the icons carry a capture of the running tank at night | `market/branding.py` |

## Reef Glass

None of Reef Glass's images ship in this edition; every picture in the package is listed above.
The code is adapted from Reef Glass v1.1.3 under Apache-2.0: see [NOTICE.md](NOTICE.md) and
[LICENSE](LICENSE). Reef Glass's own image credits are kept with Rellie Reef, in the repository's
`app/CREDITS.md`.
