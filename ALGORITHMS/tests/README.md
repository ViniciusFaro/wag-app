# Real-model inference test

From the project root in PowerShell:

```powershell
uv run python -m ALGORITHMS.tests.run_inference
uv run python -m ALGORITHMS.tests.run_inference --image ALGORITHMS/data/raw/another.png
uv run pytest ALGORITHMS/tests/test_inference.py
```

Defaults use the supplied U-Net and YOLO weights and `train.png`. Outputs are saved
to `ALGORITHMS/data/results/inference_test`: class-ID mask, colored segmentation,
segmentation aligned to YOLO dimensions, detections, combined overlay, and JSON
report. A nonzero exit indicates a loading, inference, or output failure.

The architecture is reproduced from `AGENTS/specification.MD`. U-Net uses
height 768, width 576 (the documented CHW order), RGB float32 scaled by 255,
and strict state-dictionary loading. Normalization must be confirmed against
training before treating the segmentation as validated.

YOLOv5 v7.0 is pinned as a compatibility baseline because the training revision
was not supplied. First use downloads that repository through Torch Hub.
Only trusted weights should be supplied: legacy YOLO checkpoints deserialize
a Python model. The full image is resized to width 1792, height 1344, then
processed in 224x224 tiles with 25% overlap. Per-tile confidence is 0.25,
IoU is 0.45, global class-aware NMS IoU is 0.45, and display confidence is 0.70.
Class masks are aligned using nearest-neighbor interpolation.

This verifies execution and output consistency, not predictive accuracy.
No ground truth or training preprocessing configuration was supplied.

## Dead-end class composition

After inference, run from the project root:

```powershell
uv run python -m ALGORITHMS.analyze_deadends
uv run pytest ALGORITHMS/tests/test_overlay.py
```

`--input` selects a directory containing the inference `report.json` and
`segmentation_ids.png`. `--output` selects the analysis output directory;
the default is `ALGORITHMS/data/results/deadend_analysis`.
`--min-confidence` defaults to 0.70, and `--deadend-class` defaults to `deadend`.
The analysis cannot recover detections discarded by the inference display filter.

The class-ID mask is resized to the report's YOLO width/height using nearest
neighbor interpolation. Each clipped box uses floor for its lower bounds and
ceil for its upper bounds, with half-open pixel slices. Percentages include all
three fluid classes only: water, oil and gas. Wall pixels are excluded from the
composition denominator. `class_fractions` sum to 1 and `class_percentages`
sum to 100 whenever fluid pixels exist. Regions containing only walls have
null fractions/percentages and no dominant fluid class. Full-image and combined box composition
are measured on the same grid. The combined measurement uses the union of
the boxes, so overlapping pixels contribute only once. Individual box rows
may overlap and must not be summed to obtain the union area.

Outputs include `composition.json`, `per_deadend.csv`,
`deadend_box_union.png`, and `composition_comparison.png`.
Coverage means rectangular detected-box area, not exact anatomical dead-end
area. Empty regions have no dominant class; when no detections match, the
JSON reports zero area and null comparison differences. Geometric box coverage
still uses the full rectangular union area, independently of fluid normalization.

## Individual dead-end crops

The analysis command also calls `export_deadend_crops` from
`ALGORITHMS/core/deadend_crops.py`. It saves a `deadends/manifest.json` with one
entry per valid detection, original pixel dimensions, coordinates, confidence,
fluid composition, and relative asset paths. Each `deadend_XXXX/` directory
contains `original.png`, `segmentation.png`, `overlay.png` and `class_ids.png`.
The original image is resized to the common analysis grid before cropping;
the crops use exactly the same half-open bounds as the composition calculation.
Color assets use the four specification colors, while composition excludes walls.

Use `--image PATH` if the original image path stored in the inference report has
changed. `deadends/preview.png` shows up to the first 24 original crops; all
regions remain available through the manifest. The frontend can use asset paths
relative to a future static-assets base URL. No frontend endpoint is added yet.
On reruns, only entries listed in the current manifest are active; older export
files are not deleted automatically. Export to a separate `--output` directory
to keep results from multiple experiments.
