"""Export individual dead-end assets and a manifest for a future frontend grid."""

import json
from pathlib import Path

import cv2
import numpy as np

COLORS = np.array(
    [[255, 255, 0], [0, 0, 255], [255, 0, 0], [0, 255, 0]], dtype=np.uint8
)


def export_deadend_crops(image_rgb, aligned_mask, analysis, output_dir):
    """Resize the original RGB image to the analysis grid and crop exact boxes.

    Paths in manifest.json are relative to its directory, ready to serve under
    an API static-assets base URL. IDs preserve the source detection IDs.
    Only entries in the manifest belong to this export (old files are ignored).
    """
    width, height = analysis["analysis_size_wh"]
    if image_rgb.ndim != 3 or image_rgb.shape[2] != 3 or image_rgb.dtype != np.uint8:
        raise ValueError("Expected an RGB uint8 image")
    if aligned_mask.shape != (height, width) or not np.issubdtype(
        aligned_mask.dtype, np.integer
    ):
        raise ValueError("Mask must already match the analysis grid")
    if not np.isin(aligned_mask, [0, 1, 2, 3]).all():
        raise ValueError("Mask contains invalid class IDs")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    image = cv2.resize(image_rgb, (width, height), interpolation=cv2.INTER_LINEAR)
    items = []
    preview_tiles = []
    for region in analysis["regions"]:
        x1, y1, x2, y2 = region["pixel_bounds_xyxy"]
        if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
            raise ValueError("Invalid crop bounds")
        item_id = f"deadend_{int(region['detection_id']):04d}"
        folder = output_dir / item_id
        folder.mkdir(exist_ok=True)
        original = image[y1:y2, x1:x2].copy()
        ids = aligned_mask[y1:y2, x1:x2].astype(np.uint8)
        segmentation = COLORS[ids]
        overlay = cv2.addWeighted(original, 0.5, segmentation, 0.5, 0)
        assets = {
            "original": original,
            "segmentation": segmentation,
            "overlay": overlay,
        }
        paths = {}
        for name, rgb in assets.items():
            path = folder / f"{name}.png"
            if not cv2.imwrite(str(path), cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)):
                raise OSError(f"Could not save {path}")
            paths[name] = path.relative_to(output_dir).as_posix()
        path = folder / "class_ids.png"
        if not cv2.imwrite(str(path), ids):
            raise OSError(f"Could not save {path}")
        paths["class_ids"] = path.relative_to(output_dir).as_posix()
        items.append(
            {**region, "id": item_id, "size_wh": [x2 - x1, y2 - y1], "assets": paths}
        )
        if len(preview_tiles) < 24:
            # Preserve aspect ratio; nearest-neighbor enlargement avoids blurred tiny crops.
            tile = np.full((180, 180, 3), 245, dtype=np.uint8)
            scale = min(160 / original.shape[1], 140 / original.shape[0])
            thumb = cv2.resize(
                original,
                (
                    max(1, round(original.shape[1] * scale)),
                    max(1, round(original.shape[0] * scale)),
                ),
                interpolation=cv2.INTER_NEAREST,
            )
            left, top = (180 - thumb.shape[1]) // 2, 25 + (145 - thumb.shape[0]) // 2
            tile[top : top + thumb.shape[0], left : left + thumb.shape[1]] = thumb
            cv2.putText(
                tile, item_id, (8, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (30, 30, 30), 1
            )
            preview_tiles.append(tile)
    manifest = {
        "schema_version": 1,
        "count": len(items),
        "analysis_size_wh": [width, height],
        "color_map_rgb": dict(zip(["Wall", "Water", "Oil", "Gas"], COLORS.tolist())),
        "composition_denominator": analysis["composition_denominator"],
        "coordinate_system": "Analysis-grid pixels; xyxy half-open bounds",
        "items": items,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    if preview_tiles:
        columns = 6
        while len(preview_tiles) % columns:
            preview_tiles.append(np.full((180, 180, 3), 245, dtype=np.uint8))
        sheet = np.vstack(
            [
                np.hstack(preview_tiles[i : i + columns])
                for i in range(0, len(preview_tiles), columns)
            ]
        )
        if not cv2.imwrite(
            str(output_dir / "preview.png"), cv2.cvtColor(sheet, cv2.COLOR_RGB2BGR)
        ):
            raise OSError("Could not save crop preview")
        manifest["preview"] = "preview.png"
        (output_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
    return manifest
