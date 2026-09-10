import type { ExpressionSpecification } from "maplibre-gl";

export const SEA = "#9fb3bc";

/**
 * Thermal tint of density, people per km² -> colour: cold pale blue for near
 * empty land, through teal, green and yellow to red and crimson at the
 * densest cores. Stops are spaced roughly logarithmically.
 */
export const RELIEF_STOPS: [number, string][] = [
  // color-relief paints opaquely, so the sea is painted rather than left clear.
  [0, SEA],
  [0.5, SEA],
  [1, "#e9edf0"],
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

export const FLOOD = "rgba(24, 58, 92, 0.55)";

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
export const SHORE = "#1c4a72";
export const ACCENT = "#c8361f";
export const ACCENT_B = "#1f6f8b";
