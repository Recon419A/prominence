import type { ExpressionSpecification } from "maplibre-gl";

export const SEA = "#b9c9cf";

/** Hypsometric tint of density, people per km² -> colour. */
export const RELIEF_STOPS: [number, string][] = [
  // color-relief paints opaquely, so the sea is painted rather than left clear.
  [0, SEA],
  [0.5, SEA],
  [1, "#e6dcbf"],
  [25, "#d9c98f"],
  [100, "#cbb46a"],
  [400, "#c28e42"],
  [1500, "#a9552c"],
  [5000, "#7e2b28"],
  [15000, "#4e1b31"],
  [50000, "#1e1126"],
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
export const CONTOUR = "rgba(120, 66, 28, 0.55)";
export const CONTOUR_MAJOR = "rgba(120, 66, 28, 0.9)";
export const SHORE = "#1c4a72";
export const ACCENT = "#c8361f";
export const ACCENT_B = "#1f6f8b";
