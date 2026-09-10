# Prominence — web

The interactive map. Next.js (App Router) and MapLibre GL JS.

## How it draws

The pipeline encodes population density as Terrain-RGB tiles, so MapLibre
treats it as elevation:

- `color-relief` tints density on a hypsometric ramp,
- `hillshade` lights it and `terrain` lets you tilt it into 3-D; both read a
  log-density copy of each tile, re-encoded in the browser (10 /km² is 1 km
  up, 40,000 /km² is 4.6 km), because density-as-metres makes every city a
  cliff that saturates the shading,
- `maplibre-contour` draws density contours client-side from the same tiles,
- a second `color-relief` layer floods everything below the chosen sea level.

Peaks come from `peaks_<epoch>.json` (see `src/lib/peaks.ts`), which carries
the divide tree: every peak's key col, island parent and prominence. The
merge level of any two peaks is computed in the browser by walking the tree.

Tiles are read straight from a PMTiles archive with HTTP range requests; no
tile server is involved.

## Run it

```bash
npm install
ln -s ../../data/derived public/data   # or copy the pipeline outputs there
npm run dev
```

Set `NEXT_PUBLIC_DATA_URL` (see `.env.example`) to serve the archive and peaks
file from elsewhere in production.

`npm run lint`, `npm run typecheck`, `npm run format:check` and `npm run build`
are what CI runs.
