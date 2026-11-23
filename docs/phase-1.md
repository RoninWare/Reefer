# Native Roku aquarium evaluation · 21 November 2026

## Decision

Start from Reef Glass v1.1.3. Its native BrightScript renderer already updates fish independently of the scenery, draws at 1080p coordinates, and exposes the counters needed to test it. Use Tranquil Reef as an offline art and texture-loading reference. The first engineering decision after device testing is which asset or draw pass to reduce on the weakest device. The current evidence gives no reason to port the renderer.

## Technical comparison

| Area | Reef Glass | Tranquil Reef |
|---|---|---|
| Drawing and pacing | Double-buffered 1920×1080 roScreen, roBitmap/roRegion atlases, elapsed-time simulation and scheduled swaps capped at 30 FPS. SceneGraph handles the settings screen. | roSGScreen with a TankScene, Groups, clipped Poster sheets and a repeating 33 ms timer. Timer cadence alone does not establish delivered FPS. |
| Reef and movement | tank.json describes a 3400-pixel tank, 158-second camera cycle, tiled backdrop and four reef pieces. Near/far drawing gives occlusion. The shipped background band scrolls at camera speed. | A Blender-lit panoramic reef split into depth layers, with caustics, a clam, moray, near/far fish and rising bubbles. Camera and animal animation run locally. |
| Fish | Six species, 18 configured individuals, 26 headings and three bends, randomized destinations, follower behavior and separation. Scratch bitmaps support tilted left-facing fish. Body bends approximate a swim stroke. | Photo-derived meshes and glTF fish rendered into swim and turn sheets, a chromis school and rotating visitors. The visitor cycle trades simultaneous variety for texture headroom. |
| Resource pressure | Loads reef before fish, retries failed bitmap allocation after collection, skips missing species or reef pieces. On a 720p UI, large textures shrink to about 4/9 of their original pixels **after** full-size decode. Full and reduced textures can coexist during loading. | Stages load groups, monitors Poster loadStatus, withdraws optional layers, releases visitor/eel textures and explicitly clears textures at shutdown. The author's roughly 71 MB peak is specific to that project and workload. |
| Configuration and launch | Registry-backed day/dusk/night/clock settings. Upstream sideload script transforms a dual-purpose development tree into a standalone release. | Standalone RunScreenSaver with no settings entry in the template. The template retains title alongside screensaver_title, and build.py injects a time-derived build number. Review manifest before any store submission. |
| Rebuild and install | All runtime images available as Git LFS objects. Local ZIP needs no model inference, graphics toolchain, signing key or device. Upstream distinguishes dev launch, release sideload and device-signed store package. | Python assembles a ZIP after external scans, textures and rendered frames are supplied. Upstream also offers a Windows installer, PowerShell deploy script and release ZIP. A clone alone lacks the full art inputs. |

Evidence is from the pinned runtime, scene descriptions, scripts and credit files. Both render local pictures and animate them with BrightScript. Neither runtime showed a network fetcher or video player. Upstream Reef Glass mentions Ultra testing without identifying a model and publishing corresponding benchmark logs. [Reef Glass source](https://github.com/timsaucer/reef_glass_roku_screensaver/tree/270f1b06c4b5e5f4279dc12815e16121388659c6) · [Tranquil Reef source](https://github.com/ferrellsl/Tranquil-Reef/tree/f1e9697e2e948f9e51cbe4a70082fc092164e0cc) · [Roku screensaver entry points and manifests](https://developer.roku.com/dev/docs/screensavers)

## Dependency and license inventory

| Scope | Dependencies and rights |
|---|---|
| Baseline deployment | Roku OS BrightScript 2D APIs, registry, SceneGraph settings, local JSON and images. Host rebuild uses Git, Git LFS for initial asset retrieval, and Python 3 with zlib. A browser handles sideloading over the LAN. No bundled third-party runtime library was identified. |
| Reef Glass code and art | Apache-2.0 code and CC0-1.0 shipped images according to upstream. The baseline ZIP includes both license texts and the upstream credits. Preserve applicable notices and identify later changes in modified upstream files. Screenshot/icon titles use rendered Georgia lettering. Source font files are not in the runtime. |
| Optional primary art generation | mflux drives Z-Image-Turbo and FLUX.2 klein 4B. Credits identify both models and Depth Anything V2 Small as Apache-2.0, TripoSR as MIT. Upstream uses uv, Python 3.11, PyTorch, OmegaConf, einops, transformers 4.44.2, trimesh, huggingface-hub, scikit-image, Pillow, ModernGL/OpenGL, NumPy, imageio, imagequant and OpenCV. TripoSR needs upstream-described local patches. Drafts, PLY meshes, prompts, seeds, masks and scene specs support rebuilding individual assets. The complete generation environment is not locked. |
| Primary device tools | Bash, zip, curl with Digest auth and Python console helper. run.sh expects .venv/bin/python. ECP is used for launching development builds. package.sh asks a Roku with a signing key to make a store .pkg and uses macOS-style stat. These are optional for the local baseline ZIP. |
| Secondary code and tooling | MIT code. Preserve copyright and license if importing it. Python 3, Pillow, NumPy, SciPy, OpenCV for some photo preparation, Blender 4.2+ and a render-capable GPU per upstream. Shell scripts orchestrate renders. Tkinter/PyInstaller and PowerShell/curl.exe are Windows installer/deployment tools. External scans, glTF assets, textures and reference photos are host inputs. |
| Secondary art | Credits list Smithsonian corals, Poly Haven rocks/textures, and parrotfish/puffer as CC0. Reference photos are marked public domain or CC0. Lionfish, dark angelfish and copperband butterflyfish are CC BY 4.0. Retain creator, source, license and modification details for any reused render. The Vienna giant clam is CC BY-NC 4.0 and is composited into tank imagery. For unrestricted distribution, replace it and re-render every affected layer or frame. Credits describe a separate attribution-required fallback scan. |

The inventory records upstream declarations. Future imports should carry the exact source, revision, license and credit alongside their derivatives. No secondary or Aquatic Life art was imported into the ZIP. [Primary credits](https://github.com/timsaucer/reef_glass_roku_screensaver/blob/270f1b06c4b5e5f4279dc12815e16121388659c6/CREDITS.md) · [Secondary credits](https://github.com/ferrellsl/Tranquil-Reef/blob/f1e9697e2e948f9e51cbe4a70082fc092164e0cc/CREDITS.md) · [Coral photos](https://github.com/ferrellsl/Tranquil-Reef/blob/f1e9697e2e948f9e51cbe4a70082fc092164e0cc/CORAL-CREDITS.md)

## Proposed repository structure

This section records the plan at the time of the evaluation. The repository has since taken Reef Glass v1.1.3 in as its own source under `app/`. The current layout is in [local-preview.md](local-preview.md).

The workspace currently holds upstream checkouts, baseline artifacts, the packaging helper and this report. Once the measurements are recorded, use a development worktree branched from the pinned primary commit. This preserves history and the upstream paths used by its tools.

```text
upstream/reef_glass_roku_screensaver/    primary clone at v1.1.3
upstream/Tranquil-Reef/                  pinned reference checkout
baseline/                               screensaver ZIP and SHA256SUMS
tools/build_baseline.py                  offline release build from pinned Git objects
docs/phase-1.md                          evaluation and device runbook
measurements/<model>/<os>/<run>/         proposed raw logs and run metadata
development/                            proposed primary development worktree
  roku/reefglass/{source,components,images,scenes}/
  gen/                                  upstream authoring sources and specifications
  tools/                                upstream art and device scripts
  LICENSE, LICENSE-ART, CREDITS.md
```

Keep future Blender sources, seeds, attribution and export recipes under development/gen. Export final tiles and atlases into the existing package. Keep fish logic separate from the camera clock. Prototype fin frames, parallax, bubbles, density settings and resolution-specific asset packs individually after measuring the baseline. The current release exposes lighting only. A 720p display setting is a useful test condition but cannot stand in for an older soundbar's CPU and memory limits.

## Reproduce the baseline

The repository includes the frozen baseline ZIP. To regenerate it from upstream, install Git LFS and run the commands below. The Tranquil Reef checkout is an optional reference. Fetch other Reef Glass LFS paths separately for art authoring.

```sh
GIT_LFS_SKIP_SMUDGE=1 git clone https://github.com/timsaucer/reef_glass_roku_screensaver.git upstream/reef_glass_roku_screensaver
git -C upstream/reef_glass_roku_screensaver checkout --detach 270f1b06c4b5e5f4279dc12815e16121388659c6
git -C upstream/reef_glass_roku_screensaver lfs pull --include='roku/reefglass/images/**'
git clone https://github.com/ferrellsl/Tranquil-Reef.git upstream/Tranquil-Reef
git -C upstream/Tranquil-Reef checkout --detach f1e9697e2e948f9e51cbe4a70082fc092164e0cc
python3 tools/build_baseline.py
sha256sum -c baseline/SHA256SUMS
unzip -tq baseline/reefglass-1.1.3.zip
```

The helper packages tracked content at the pinned commit, checks image bytes against each Git LFS SHA-256, applies upstream's release manifest transformation and omits the dev Main entry. It adds upstream attribution files and fixes ZIP ordering, timestamps and permissions. Two independent invocations with Python 3.11.14 and zlib 1.3 produced the same 3,964,041-byte archive. All 28 images decoded and literal package references in the manifest and tank JSON resolved. This verifies the build locally. Device compilation, first display and idle activation still require hardware.

## Installation and measurement plan

1. **Identify targets.** Use the oldest available Roku Ultra and an actual Roku soundbar/Streambar. Record model number, Roku OS/build, display mode, UI resolution, baseline SHA, lighting setting and prior sideload. Save a reinstallable copy of any development app the owner needs. Each device has one development slot. A second ZIP replaces the current occupant. [Roku developer setup](https://developer.roku.com/dev/docs/developer-setup)
2. **Install one device at a time.** On its remote press Home three times, Up twice, then Right, Left, Right, Left, Right. Enable the development installer, set a password and reboot. Open the shown device IP from a browser on the same LAN, sign in as rokudev, upload baseline/reefglass-1.1.3.zip, and record the install response. Repeat explicitly for the second device. Both can use the identical ZIP. No store signing key is needed.
3. **Exercise the actual screensaver.** Select Reef Glass in Settings → Theme → Screensavers and set an idle wait time. Verify preview, automatic activation from Home after that timeout, and return on remote input. Select dusk through Change screensaver settings and confirm it survives re-entry. Restore daytime for benchmark runs. Repeat after unplugging the WAN while retaining LAN access. Record missing fish, exposed layer edges, black frames or crashes. [Roku screensavers](https://developer.roku.com/dev/docs/screensavers)
4. **Capture timing and memory.** Before activation attach a console, e.g. `telnet DEVICE_IP 8087 | tee screensaver.log`. Capture three runs after device restart and three warm re-entries per model at the same settings. Capture FIRST FRAME (script entry to first swap, including the initial fade), and separately stopwatch activation to first visible reef. Save MEMORY start/loaded and all warning events. Use a second telnet connection to 8080 and issue `r2d2_bitmaps` before activation, just after loading, at 60 seconds, during a busy pan/turn and after exit. Record reported used/free/total bytes, baseline delta and timestamp. Resource Monitor can provide a time series when available. Keep app memory figures, device texture totals and sampled peaks separately labeled. [Roku memory diagnostics](https://developer.roku.com/dev/docs/memory-management)
5. **Measure sustained delivery.** Capture 10 minutes per device at default load, enough for multiple 158-second camera cycles. Summarize median and worst 10-second FPS windows, total late frames and any long stalls. Upstream divides frame count by a nominal ten seconds and calls an interval late above 1.4× the target frame time. These are approximate rates. Keep the raw logs. Inspect smooth turns, occlusion and fin motion at both pan extremes. Run a one-hour soak and repeated exits/re-entries to look for memory growth or dropped layers.
6. **Isolate bottlenecks.** Only after recording release runs, use the separate dev build on a designated device. Upstream tools/run.sh installs that build and logs port 8085. Supply ROKU_IP and ROKU_DEV_PASSWORD in the clone's local .env and provide its expected .venv/bin/python. Run one change at a time using profile=1, fps=0, lowres=1, nofish=1 or failbmp=puffer. Compare update/draw submission time, scratch usage and pressure against the same scene. Dev launch differs from idle launch in available memory. Reinstall the frozen release ZIP for the final idle check.
7. **Record and decide.** Store a row per run with model, OS, SHA, mode (idle/preview/dev), cold/warm, display/UI size, settings, script/visible startup ms, memory start/loaded, peak sampled texture bytes and minimum free bytes, FPS median/worst, late count, warning/omission counts and raw log path. Mark unsupported counters unavailable. Summarize repeatability and the largest observed bottleneck per device. If full-size decode causes a startup spike, trial pre-sized tiles first. If fish draws dominate, trial fewer active fish or smaller atlases. If pacing is already stable with headroom, spend the measured margin on one visual improvement and rerun the same matrix.

| Required physical result | Older Ultra | Soundbar/Streambar |
|---|---|---|
| Model, OS/build, release install and idle activation | Pending device access | Pending device access |
| Cold/warm startup, steady FPS and late frames | Unmeasured | Unmeasured |
| App memory, graphics memory and re-entry behavior | Unmeasured | Unmeasured |

Phase 1 exits when both target classes have raw release logs, lifecycle results and a measured decision for the next change. Record any failed device run as a result with its error and model. Preserve this ZIP for all subsequent comparisons.

### Local preflight before the first device run

Run `python3 tools/check_scene.py baseline/reefglass-1.1.3.zip` with Python 3.9+ and Pillow. The frozen package has 1,770 body and tail region definitions across the straight, bent and inflated poses. All fit their assigned atlas pages, and each still has positive width and height after the renderer's 720p texture rounding.

At four bytes per pixel, the packaged scene images total 49.97 MiB at full size and 22.59 MiB with the baseline's reduced textures. This estimate assumes one copy of each scene image. It excludes icons, splash screens, display buffers, scratch bitmaps, transient decode allocations, alignment and OS overhead. Use the first device run to compare actual texture usage before activation, during loading and after the fish have turned in both directions.
