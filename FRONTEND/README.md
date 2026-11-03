# MicroFlow frontend · LabMEMS / UFRJ

React interface for uploading micromodel images and exploring their analysis.
See the [project README](../README.md) for the backend and full setup.

```powershell
npm install
npm run dev
```

The backend must run at `127.0.0.1:8000`. Vite proxies `/api` there.

## Pages

- `/`: file selection, preview and upload.
- `/analysis/sample`: existing real sample results.
- `/analysis/<id>`: live progress and results for a new upload.

The result page includes original/segmentation/detection/overlay tabs, phase
charts, searchable and sortable dead-end table/grid views, expandable crops,
and CSV and segmentation-mask downloads. Fractions exclude wall pixels.

Build with `npm run build`. The source logos are in `public/brand/`; their
backgrounds and colors are adapted using CSS filters and blending.
