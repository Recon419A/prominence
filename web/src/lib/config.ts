/** Where the pipeline's outputs are served from. Defaults to `web/public/data`. */
export const DATA_URL = process.env.NEXT_PUBLIC_DATA_URL ?? "/data";

export const EPOCH = 2025;
export const TILES_URL = `${DATA_URL}/density_${EPOCH}.pmtiles`;
export const PEAKS_URL = `${DATA_URL}/peaks_${EPOCH}.json`;

/** Deepest zoom rendered by the pipeline; MapLibre overzooms beyond it. */
export const DEM_MAX_ZOOM = 8;

/**
 * How the tiles encode density: `0.1 * (R*65536 + G*256 + B)`, with no offset
 * so that sea level survives the reduced float precision of fragment shaders.
 */
export const DEM_ENCODING = {
  encoding: "custom",
  redFactor: 6553.6,
  greenFactor: 25.6,
  blueFactor: 0.1,
  baseShift: 0,
} as const;

/** Decode one Terrain-RGB pixel of ours. */
export function decodeDensity(r: number, g: number, b: number): number {
  return (r * 65536 + g * 256 + b) * 0.1;
}

export const GLYPHS_URL =
  "https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf";

export const ATTRIBUTION =
  'Population <a href="https://human-settlement.emergency.copernicus.eu/">GHS-POP R2023A</a> © European Commission JRC, CC BY 4.0 · ' +
  'Names <a href="https://www.geonames.org/">GeoNames</a>, CC BY 4.0 · ' +
  'Coastlines <a href="https://www.naturalearthdata.com/">Natural Earth</a>';
