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
```

## Data

- Population: [GHSL GHS-POP R2023A](https://human-settlement.emergency.copernicus.eu/download.php?ds=pop)
  (European Commission, Joint Research Centre), CC BY 4.0. Global grids at
  30 arc-seconds (~1 km) and 3 arc-seconds (~100 m), stitched into one
  multi-resolution pyramid.
- Place names: [GeoNames](https://www.geonames.org/), CC BY 4.0.

## Licence

MIT. See [LICENSE](LICENSE).
