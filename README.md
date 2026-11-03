# MicroFlow · LabMEMS / UFRJ

A local workspace for micromodel segmentation, dead-end detection and fluid
composition analysis. The React interface uses the LabMEMS and UFRJ logos,
background `#1c1530`, and accent `#bd3e42`.

## Agradecimentos

Agradecimentos à Shell. A interface exibe essa homenagem
de forma discreta no rodapé, com a logo fornecida sem fundo.

## Start the app

From `C:\labmems\wag-app`, open two PowerShell terminals.

Backend:

```powershell
$env:UV_CACHE_DIR = "$PWD\.uv-cache"
$env:UV_PYTHON_INSTALL_DIR = "$PWD\.uv-python"
uv sync
uv run uvicorn API.FASTAPI.app.main:app --host 127.0.0.1 --port 8000
```

Frontend, in a second terminal:

```powershell
cd C:\labmems\wag-app\FRONTEND
npm install
npm run dev
```

Open the local URL printed by Vite (normally http://127.0.0.1:5173).
The frontend proxies `/api` to port 8000. Both servers must be running.
Use one backend worker: inference jobs run serially to limit memory use.

## Workflow

1. Drop or browse for a PNG, JPG, TIFF or WebP image, up to 25 MB / 40 MP.
2. Select **Analyze image**. The progress screen tracks real processing stages.
3. Switch between original, segmentation, detection and overlay images.
4. Compare full-image fluid composition with the union of detected boxes.
5. Search, filter and sort individual dead ends in a table or image grid.
6. Open a region for enlarged original/mask images and download its class-ID mask.
7. Export composition measurements as CSV, or download the current viewer image.

The **Explore sample** button opens the existing `train.png` results, when the
inference/analysis output files are present. These are real saved results.
New uploads always run both models. A browser refresh preserves an analysis via
its URL; a backend restart interrupts running jobs and the UI asks for reupload.

## Models and outputs

- `MODELS/unet/dcaunet_ema_combined_loss_weighted.pt`
- `MODELS/yolo/best.pt`
- New analyses: `ALGORITHMS/data/results/web/<job-id>/analysis/`
- Each run has independent outputs, a composition JSON/CSV and per-region crops.
- U-Net input is RGB, CHW `3 × 768 × 576`, float32 scaled by 255.
  This normalization remains an assumption to confirm against training.
- YOLOv5 v7.0 runs on a `1792 × 1344` image using `224 × 224` tiles and
  25% overlap. Global class-aware NMS uses IoU 0.45; displayed confidence ≥ 0.70.
  The first detector load downloads the pinned YOLOv5 source if absent.
- Segmentation aligns to the YOLO grid using nearest-neighbor interpolation.
- Fluid composition excludes wall pixels; oil + water + gas fractions sum to 1.
  Regions containing no fluid pixels report unavailable fractions.
- Box coverage measures rectangles, including their wall pixels, and counts
  overlapping pixels once. It is not exact anatomical dead-end area.

The UI adapts the logo backgrounds with CSS filters/blending. Uploaded image
processing stays local; optional web fonts are requested from Google Fonts,
with system-font fallbacks. This development server has no authentication;
keep it bound to loopback for the local research workflow.

## Verify

```powershell
uv run pytest ALGORITHMS/tests API/FASTAPI/tests -q
cd FRONTEND
npm run build
```
