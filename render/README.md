# INI Austin imagery pipeline

Renders isometric brain imagery from sub-test3's own MRI, for the INI Austin
site. No GPU and no 3D library: the renderers are NumPy rasterisers.

## Source data

Everything comes from `$INI_BIDS_ROOT`, a BIDS dataset.

- Diffusion: `derivatives/qsiprep-ABCD/sub-test3/dwi/` - preprocessed,
  ACPC-aligned, multi-shell (b = 0/500/1000/2000/3000, 96 directions, 103
  volumes, 1.7 mm isotropic).
- Surfaces: `derivatives/fmriprep/sub-test3/anat/` - FreeSurfer pial surfaces
  plus sulcal depth, 298,775 vertices over both hemispheres.

sub-test3 had no tractography reconstruction; only sub-test1 and sub-test2 did.
This pipeline builds one.

## Pipeline

    # 1. DWI -> DSI Studio source -> GQI reconstruction
    dsi_studio --action=src --source=dwi.nii.gz --bval=dwi.bval --bvec=dwi.bvec \
               --output=sub-test3.sz
    dsi_studio --action=rec --source=sub-test3.sz --method=4 --mask=mask.nii.gz \
               --check_btable=0

    # 2a. Whole-brain tractography
    dsi_studio --action=trk --source=sub-test3.gqi.fz --tract_count=600000 \
               --turning_angle=45 --step_size=0.4 --smoothing=0.8 \
               --min_length=20 --max_length=280 --otsu_threshold=0.45 \
               --check_ending=1 --output=tracts_v2.trk.gz

    # 2b. Named bundles by atlas recognition (HCP842), 55 bundles recovered
    dsi_studio --action=atk --source=sub-test3.gqi.fz --output=atk

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
