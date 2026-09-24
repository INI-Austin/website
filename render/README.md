# INI Austin imagery pipeline

Renders isometric brain imagery for the INI Austin site. No GPU and no 3D
library: the renderers are NumPy rasterisers.

## Source data

The scripts read a BIDS dataset mounted locally. Nothing in that dataset is
committed here, and the paths below are relative to whatever root you point
the scripts at.

- Diffusion: `derivatives/qsiprep-ABCD/<subject>/dwi/` - preprocessed,
  ACPC-aligned, multi-shell (b = 0/500/1000/2000/3000, 96 directions, 103
  volumes, 1.7 mm isotropic).
- Surfaces: `derivatives/fmriprep/<subject>/anat/` - FreeSurfer pial surfaces
  plus sulcal depth, 298,775 vertices over both hemispheres.

The subject used here had no tractography reconstruction on file, so this
pipeline builds one.

## Pipeline

    # 1. DWI -> DSI Studio source -> GQI reconstruction
    dsi_studio --action=src --source=dwi.nii.gz --bval=dwi.bval --bvec=dwi.bvec \
               --output=subject.sz
    dsi_studio --action=rec --source=subject.sz --method=4 --mask=mask.nii.gz \
               --check_btable=0

    # 2a. Whole-brain tractography
    dsi_studio --action=trk --source=subject.gqi.fz --tract_count=600000 \
               --turning_angle=45 --step_size=0.4 --smoothing=0.8 \
               --min_length=20 --max_length=280 --otsu_threshold=0.45 \
               --check_ending=1 --output=tracts_v2.trk.gz

    # 2b. Named bundles by atlas recognition (HCP842), 55 bundles recovered
    dsi_studio --action=atk --source=subject.gqi.fz --output=atk

    # 3. Caches
    uv run python prep_tracts.py work/tracts_v2.trk.gz work/tracts_v2.npz
    uv run python prep_bundles.py
    uv run python to_anat.py work/bundles.npz work/bundles_anat.npz

    # 4. Hero composite
    uv run python hero.py --width 2400 --height 1900 --azim 90 --elev 35.264 \
                          --out out/final/hero-isometric.png

Do not pass `--align_acpc=0` to `rec`; it is parsed as a resolution and fails.
`--param0` and `--fiber_count` are silently ignored, the real names are
`--param` and `--tract_count`.

## Renderers

- `render_iso.py` - direction-coloured tractography. Depth-slab compositing so
  near fibres occlude far ones, and illuminated-streamline shading (Zoeckler)
  so bundles read as tubes rather than flat ribbons.
- `render_bundles.py` - same core, coloured by named anatomical tract.
- `render_surface.py` - cortical surface. Vectorised z-buffer: samples are
  sorted far-to-near so NumPy's last-write-wins on duplicate indices *is* the
  depth test. Blinn-Phong plus a Fresnel rim for the glass edge light.
  `--faces front|back` splits the shell so tracts can sit inside it.
- `hero.py` - composites back shell, tracts, front shell.

Sample density adapts to segment length in pixels (`--auto-samples`); a fixed
value beads the atlas bundles, whose step size is coarser than the whole-brain
track's.

## Registration

Tracts are in qsiprep ACPC space, surfaces in fMRIPrep anat space.
`align_check.py` resolves the ambiguity in BIDS `from-X_to-Y` naming and ITK's
LPS convention by trying all four readings and keeping whichever seats white
matter inside the pial surface. The winner puts 86.5% of streamline points
inside, against 75.5% untransformed. `to_anat.py` applies it.

## The ULM viewer on the research page

Nothing here is related to the tractography above. The research page's
ultrasound section shows Aleph Neuro's own track viewer, vendored under
`web/viewer/ulm` from `ultratrace_ulm/web/track_viewer` in their MIT licensed
repository and fed the track data they published. `ulm_to_viewer.py` does the
conversion the two ends of their pipeline need, and `ulm_figure.py` renders the
still that stands in when WebGL is unavailable.

- `ulm_decode.py` reads the ULMT v6 binary from `alephneuro.com/data/`. Tracks
  are delta encoded: the first point of a track carries absolute quantised
  coordinates and every point after it an int16 step, which is how a whole
  reconstruction fits in about a megabyte. The two scalar planes are easy to
  swap and I had them the wrong way round for a while: the plane at offset 7n,
  scaled by the float at header offset 16, is flow speed, and the plane at 8n
  is a normalised weight. The giveaway is the range, 0 to 0.404 against exactly
  0 to 1. Their figure divides the first by `RAMP_DIVISOR` and labels the top
  of the ramp 38 mm/s.
- `ulm_to_viewer.py` rewrites that into the v3 layout their viewer reads:
  a 64 byte header, an 8 byte per track offset and length table, then 24 byte
  point records of x, y, z, frame, speed and intensity as float32. The result
  is 3.0 MB, which is why the figure is lazily loaded.
- The renderer in `web/viewer/ulm/index.html` is not the reveal animation their
  repo viewer ships, which builds the map up over several seconds, holds,
  blanks and replays. It is the one their own site runs, which is a different
  program: the reveal is switched off there and what you see is a crowd of
  bubbles being advected. Each track carries forty particles at scattered
  starting phases; every frame each particle advances five acquisition frames
  along its own recording, wraps at the end, and is placed by interpolating
  between the two samples that bracket that moment. Nothing appears or
  disappears, so the vascular map is always complete, and every dot in it is
  moving down the vessel the bubble that drew it actually travelled.
- `ulm_figure.py` renders the still the section falls back to without WebGL. It
  splats the points with a sort-then-scatter depth test, the same trick
  `render_surface.py` uses. Compositing picks the brightest
  contributor per pixel rather than a per-channel maximum: taking the max of
  each channel blends a red track crossing a cyan one into white, inventing a
  flow speed that is in neither of them.

Colour is the full spectrum their figure uses, with their exact stops, because
that is the convention in velocity-encoded flow imaging and it keeps our render
readable against theirs.

Their published parameters, read out of the site bundle rather than guessed:
forty particles per track capped by a 350,000 particle budget, five acquisition
frames per second of playback, a colour divisor of 0.18, a ramp labelled 0 to
38 mm/s, a flat point disc with a soft rim, ordinary alpha blending, and a size
boost of 1.3 on the slowest third of tracks so the finest vessels stay visible.

    python3 ulm_to_viewer.py work/ulm-tracks.bin.gz \
        ../web/viewer/ulm/data/tracks.bin
    python3 ulm_figure.py 35 18     # azimuth, elevation, for the still
