import type { ExpressionSpecification } from "maplibre-gl";

export const SEA = "#1e3f66";
/** Land with nobody on it; also the first step of the ramp so the two meet seamlessly. */
export const LAND = "#e9edf0";

/**
 * Thermal tint of density, people per km² -> colour: cold pale blue for near
 * empty land, through teal, green and yellow to red and crimson at the
 * densest cores. Stops are spaced roughly logarithmically.
 */
export const RELIEF_STOPS: [number, string][] = [
  // Below half a person per km² nothing is painted: the land and water
  // polygons underneath decide what shows.
  [0, "rgba(0,0,0,0)"],
  [0.5, "rgba(0,0,0,0)"],
  [1, LAND],
  [25, "#c4d9e8"],
  [100, "#8ec6c5"],
  [400, "#7dc36f"],
  [1500, "#e0d24a"],
  [5000, "#f0952f"],
  [15000, "#d63a22"],
  [50000, "#7a0c1a"],
];

export function reliefColor(): ExpressionSpecification {
  const stops = RELIEF_STOPS.flatMap(([v, c]) => [v, c]);
  return [
    "interpolate",
    ["linear"],
    ["elevation"],
    ...stops,
  ] as ExpressionSpecification;
}

/** Sea level at or below this shows no flood: the terrain's own ocean is enough. */
export const FLOOD_MIN_LEVEL = 1.5;

/**
 * Everything below `level` is flooded. color-relief only honours `interpolate`
 * ramps, so a step is drawn as two stops a hair apart.
 */
export function floodColor(level: number): ExpressionSpecification {
  const edge = Math.max(level, 1);
  return [
    "interpolate",
    ["linear"],
    ["elevation"],
    edge * 0.98,
    FLOOD,
    edge,
    "rgba(0,0,0,0)",
  ];
}

export const FLOOD = "rgba(30, 63, 102, 0.6)";

/** Contour intervals [minor, major] by zoom, in people per km². */
export const CONTOUR_THRESHOLDS: Record<number, [number, number]> = {
  0: [5000, 20000],
  3: [2000, 10000],
  5: [1000, 5000],
  7: [500, 2500],
  9: [250, 1000],
  11: [100, 500],
};

export const INK = "#2b1d14";
export const CONTOUR = "rgba(40, 40, 48, 0.45)";
export const CONTOUR_MAJOR = "rgba(40, 40, 48, 0.8)";
export const HILLSHADE = {
  shadow: "#243040",
  highlight: "#ffffff",
  accent: "#2b3a4c",
};
export const ACCENT = "#c8361f";
export const ACCENT_B = "#1f6f8b";
