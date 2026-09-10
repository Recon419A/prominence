# Prominence

**Human topography.** Population density rendered and analysed as if it were
terrain, so that questions like *"what counts as a city?"* and *"is that a
megalopolis?"* can be answered with the same tools mountaineers use to decide
what counts as a mountain.

## The idea

Take a population density grid and read it as a digital elevation model:
one person per square kilometre is one metre of altitude. Manhattan becomes a
peak tens of kilometres high, the Ganges plain a vast highland, the Sahara an
ocean floor. Once density is elevation, a whole vocabulary of well-defined
topographic measures applies for free:

- **Height** of a peak: its peak density.
- **Prominence**: how far a peak rises above the highest *saddle* (key col)
  connecting it to any higher peak. A suburb of Tokyo is tall but has almost no
  prominence; a small isolated town has low height but may be very prominent.
  Prominence is the standard mountaineering answer to *"is this its own
  mountain or a shoulder of that one?"*, and here it becomes *"is this its own
  city or a district of that one?"*
- **Key col** and **parent peak**: the saddle that defines a peak's prominence
  and the higher peak on the other side of it. Following parents builds the
  **divide tree**, a hierarchy of every peak on the planet.
- **Merge level**: for any two peaks, the highest contour at which they belong
  to the same landmass. New York and Philadelphia are one blob above some
  density and two blobs below it. Whether "BosWash" is a megalopolis is
  exactly a question about that number.

The app lets you set sea level, draw contours, filter peaks by prominence, and
ask the divide tree how any two places relate.

## Layout

```
pipeline/   Python: fetch GHS-POP, build the density pyramid, compute the
            divide tree, export peaks and terrain tiles.
web/        Next.js + MapLibre: the interactive map.
data/       Raw downloads and derived outputs (not committed).
```

## Build it

The pipeline needs [uv](https://docs.astral.sh/uv/); the web app needs Node 24.

```bash
uv run --project pipeline prominence build   # ~1 GB download, ~10 minutes
cd web && npm install && ln -s ../../data/derived public/data && npm run dev
```

`prominence build` runs four steps that can also be run separately:

| step      | does                                                                 | writes                     |
| --------- | -------------------------------------------------------------------- | -------------------------- |
| `fetch`   | downloads GHS-POP and GeoNames                                       | `data/raw/`                |
| `density` | people per cell → people per km² over a 3×3 (~3 km) box, with overviews | `density_<epoch>_30ss.tif` |
| `peaks`   | divide tree, names, `.npz` of every peak with prominence ≥ 100       | `tree_<epoch>.npz`, `peaks_<epoch>.json` |
| `tiles`   | Terrain-RGB tiles, zoom 0–8, quadtree-pruned                          | `density_<epoch>.pmtiles`  |

`prominence export --min-prominence N` re-exports the web JSON from the saved
tree at another threshold in seconds.

## Method notes

- **Height** is GHS-POP population count divided by cell area on the authalic
  sphere, then averaged over a 3×3 window. GHS-POP concentrates some census
  units into one or two 1 km cells (Luxor and Surat carry cells over
  300,000 /km²); the smoothing keeps such spikes from outranking every real
  megacity, at the cost of lowering every peak somewhat. Some artefacts
  remain visible in the rankings.
- **Sea level** for the tree is 1 person per km². Prominence of an island
  summit is measured from there.
- **Names** come from GeoNames cities of 15,000+ people. Each city belongs to
  the peak whose territory (key col contour minus children's contours) it
  stands in; peaks then claim names in descending order of prominence, taking
  the most populous unclaimed city anywhere on their mountain. A peak with no
  city borrows the nearest one within 30 km, shown as "near …".
- **Tiles** encode density as `0.1 × (R·65536 + G·256 + B)` without the usual
  −10,000 m Terrain-RGB offset, so that sea level stays exact in the reduced
  precision of fragment shaders.

## Data

- Population: [GHSL GHS-POP R2023A](https://human-settlement.emergency.copernicus.eu/download.php?ds=pop)
  (European Commission, Joint Research Centre), CC BY 4.0. Global grids at
  30 arc-seconds (~1 km) and 3 arc-seconds (~100 m), stitched into one
  multi-resolution pyramid.
- Place names: [GeoNames](https://www.geonames.org/), CC BY 4.0.

## Licence

MIT. See [LICENSE](LICENSE).
