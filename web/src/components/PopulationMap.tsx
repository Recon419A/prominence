"use client";

import { useEffect, useRef, useState } from "react";
import {
  addProtocol,
  removeProtocol,
  type ExpressionSpecification,
  type FilterSpecification,
  type GeoJSONSource,
  Map as MapLibreMap,
  type MapLayerMouseEvent,
  NavigationControl,
  ScaleControl,
  setWorkerUrl,
  type StyleSpecification,
} from "maplibre-gl";
import { PMTiles, Protocol } from "pmtiles";
import mlcontour from "maplibre-contour";
import "maplibre-gl/dist/maplibre-gl.css";

import {
  ATTRIBUTION,
  DEM_ENCODING,
  DEM_MAX_ZOOM,
  GLYPHS_URL,
  TILES_URL,
  decodeDensity,
} from "@/lib/config";
import type { MergeResult, Peak } from "@/lib/peaks";
import { peakLabel } from "@/lib/peaks";
import {
  ACCENT,
  ACCENT_B,
  CONTOUR,
  CONTOUR_MAJOR,
  CONTOUR_THRESHOLDS,
  FLOOD_MIN_LEVEL,
  HILLSHADE,
  INK,
  SEA,
  SHORE,
  floodColor,
  reliefColor,
} from "@/lib/style";

export interface Selection {
  a: Peak | null;
  b: Peak | null;
  merge: MergeResult | null;
}

export interface CameraTarget {
  lat: number;
  lon: number;
  zoom?: number;
  /** Changes on every request so the same place can be flown to twice. */
  nonce: number;
}

interface Props {
  peaks: Peak[];
  minProminence: number;
  seaLevel: number;
  exaggeration: number;
  selection: Selection;
  flyTo: CameraTarget | null;
  /** A peak on the map was clicked; `additive` means shift was held. */
  onSelect: (id: number, additive: boolean) => void;
  onClear: () => void;
}

const DEM_PATTERN = "dem://{z}/{x}/{y}";

// Copied into public/ by scripts/copy-maplibre-worker.mjs.
setWorkerUrl("/maplibre/maplibre-gl-worker.mjs");
const SEL_LINE_LAYER = "selection-lines";

/** A Terrain-RGB PNG encoding 0 everywhere, handed out for tiles the archive lacks. */
let emptyTile: Promise<Blob> | null = null;
function emptyDemTile(): Promise<Blob> {
  if (!emptyTile) {
    emptyTile = new Promise((resolve, reject) => {
      const canvas = document.createElement("canvas");
      canvas.width = canvas.height = 256;
      const ctx = canvas.getContext("2d")!;
      ctx.fillStyle = "rgb(0,0,0)"; // density 0
      ctx.fillRect(0, 0, 256, 256);
      canvas.toBlob(
        (b) => (b ? resolve(b) : reject(new Error("toBlob failed"))),
        "image/png",
      );
    });
  }
  return emptyTile;
}

/** Decode one of our Terrain-RGB tiles into elevations for maplibre-contour. */
async function decodeDemTile(
  blob: Blob,
): Promise<{ width: number; height: number; data: Float32Array }> {
  const bitmap = await createImageBitmap(blob);
  const canvas = new OffscreenCanvas(bitmap.width, bitmap.height);
  const ctx = canvas.getContext("2d")!;
  ctx.drawImage(bitmap, 0, 0);
  const { data: rgba } = ctx.getImageData(0, 0, bitmap.width, bitmap.height);
  const data = new Float32Array(bitmap.width * bitmap.height);
  for (let i = 0; i < data.length; i++) {
    data[i] = decodeDensity(rgba[i * 4], rgba[i * 4 + 1], rgba[i * 4 + 2]);
  }
  return { width: bitmap.width, height: bitmap.height, data };
}

function buildStyle(
  demTiles: string,
  contourTiles: string,
): StyleSpecification {
  return {
    version: 8,
    glyphs: GLYPHS_URL,
    sources: {
      // MapLibre asks for separate sources for terrain and for the layers draped on it.
      dem: {
        type: "raster-dem",
        tiles: [demTiles],
        ...DEM_ENCODING,
        tileSize: 256,
        maxzoom: DEM_MAX_ZOOM,
        attribution: ATTRIBUTION,
      },
      terrain: {
        type: "raster-dem",
        tiles: [demTiles],
        ...DEM_ENCODING,
        tileSize: 256,
        maxzoom: DEM_MAX_ZOOM,
      },
      contours: {
        type: "vector",
        tiles: [contourTiles],
        maxzoom: DEM_MAX_ZOOM + 4,
      },
      coast: { type: "geojson", data: "/basemap/ne_50m_coastline.geojson" },
      borders: {
        type: "geojson",
        data: "/basemap/ne_50m_admin_0_boundary_lines_land.geojson",
      },
      peaks: {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      },
      selection: {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      },
    },
    layers: [
      { id: "sea", type: "background", paint: { "background-color": SEA } },
      {
        id: "relief",
        type: "color-relief",
        source: "dem",
        paint: { "color-relief-color": reliefColor() },
      },
      {
        id: "hillshade",
        type: "hillshade",
        source: "dem",
        paint: {
          "hillshade-exaggeration": 0.4,
          "hillshade-shadow-color": HILLSHADE.shadow,
          "hillshade-highlight-color": HILLSHADE.highlight,
          "hillshade-accent-color": HILLSHADE.accent,
          "hillshade-illumination-direction": 315,
        },
      },
      {
        id: "flood",
        type: "color-relief",
        source: "dem",
        layout: { visibility: "none" },
        paint: { "color-relief-color": floodColor(1) },
      },
      {
        id: "coast",
        type: "line",
        source: "coast",
        paint: { "line-color": SHORE, "line-width": 0.6, "line-opacity": 0.7 },
      },
      {
        id: "borders",
        type: "line",
        source: "borders",
        paint: {
          "line-color": INK,
          "line-width": 0.5,
          "line-opacity": 0.35,
          "line-dasharray": [4, 2],
        },
      },
      {
        id: "contour-minor",
        type: "line",
        source: "contours",
        "source-layer": "contours",
        minzoom: 4,
        filter: ["==", ["get", "level"], 0],
        paint: { "line-color": CONTOUR, "line-width": 0.5 },
      },
      {
        id: "contour-major",
        type: "line",
        source: "contours",
        "source-layer": "contours",
        filter: [">", ["get", "level"], 0],
        paint: { "line-color": CONTOUR_MAJOR, "line-width": 1 },
      },
      {
        id: "contour-labels",
        type: "symbol",
        source: "contours",
        "source-layer": "contours",
        minzoom: 5,
        filter: [">", ["get", "level"], 0],
        layout: {
          "symbol-placement": "line",
          "text-field": ["number-format", ["get", "ele"], {}],
          "text-font": ["Noto Sans Italic"],
          "text-size": 9,
          "symbol-spacing": 400,
        },
        paint: {
          "text-color": CONTOUR_MAJOR,
          "text-halo-color": "rgba(255,248,230,0.9)",
          "text-halo-width": 1,
        },
      },
      {
        id: SEL_LINE_LAYER,
        type: "line",
        source: "selection",
        filter: ["==", ["geometry-type"], "LineString"],
        paint: {
          "line-color": ACCENT,
          "line-width": 1.5,
          "line-dasharray": [2, 2],
        },
      },
      {
        id: "peaks-circle",
        type: "circle",
        source: "peaks",
        paint: {
          "circle-radius": visibleByZoom(3, 7),
          "circle-color": INK,
          "circle-opacity": 0.85,
          "circle-stroke-color": "#fff8e6",
          "circle-stroke-width": 1,
        },
      },
      {
        id: "peaks-label",
        type: "symbol",
        source: "peaks",
        layout: {
          "text-field": ["get", "name"],
          "text-font": ["Noto Sans Bold"],
          "text-size": visibleByZoom(10, 14),
          "text-anchor": "left",
          "text-offset": [0.7, 0],
          "symbol-sort-key": ["-", 0, ["get", "prominence"]],
          "text-optional": true,
        },
        paint: {
          "text-color": INK,
          "text-halo-color": "rgba(255,248,230,0.92)",
          "text-halo-width": 1.4,
        },
      },
      {
        id: "selection-cols",
        type: "circle",
        source: "selection",
        filter: ["==", ["get", "kind"], "col"],
        paint: {
          "circle-radius": 6,
          "circle-color": "#fff8e6",
          "circle-stroke-color": ACCENT,
          "circle-stroke-width": 2,
        },
      },
      {
        id: "selection-peaks",
        type: "circle",
        source: "selection",
        filter: ["==", ["get", "kind"], "peak"],
        paint: {
          "circle-radius": 9,
          "circle-color": "rgba(0,0,0,0)",
          "circle-stroke-color": [
            "match",
            ["get", "slot"],
            "b",
            ACCENT_B,
            ACCENT,
          ],
          "circle-stroke-width": 2.5,
        },
      },
      {
        id: "selection-labels",
        type: "symbol",
        source: "selection",
        filter: ["==", ["get", "kind"], "col"],
        layout: {
          "text-field": ["get", "label"],
          "text-font": ["Noto Sans Italic"],
          "text-size": 11,
          "text-anchor": "top",
          "text-offset": [0, 0.8],
        },
        paint: {
          "text-color": ACCENT,
          "text-halo-color": "rgba(255,248,230,0.95)",
          "text-halo-width": 1.5,
        },
      },
    ],
  };
}

/**
 * Prominence a peak needs to be drawn at each zoom, so the world view shows
 * only the great summits and every village appears once you are close.
 */
const PROMINENCE_BY_ZOOM: [zoom: number, minProminence: number][] = [
  [1, 40000],
  [3, 15000],
  [5, 5000],
  [7, 1500],
  [9, 0],
];

/** A size that grows from `small` to `large` with zoom and prominence, and is 0 for peaks below the bar. */
function visibleByZoom(small: number, large: number): ExpressionSpecification {
  const stops = PROMINENCE_BY_ZOOM.flatMap(([zoom, minProminence], i) => {
    const t = i / (PROMINENCE_BY_ZOOM.length - 1);
    const size: ExpressionSpecification = [
      "interpolate",
      ["linear"],
      ["get", "logProminence"],
      3,
      small + (large - small) * t,
      5.3,
      (small + (large - small) * t) * 2.2,
    ];
    return [
      zoom,
      ["case", [">=", ["get", "prominence"], minProminence], size, 0],
    ];
  });
  return [
    "interpolate",
    ["linear"],
    ["zoom"],
    ...stops,
  ] as ExpressionSpecification;
}

function peaksGeoJson(peaks: Peak[]): GeoJSON.FeatureCollection {
  return {
    type: "FeatureCollection",
    features: peaks.map((p) => ({
      type: "Feature",
      id: p.id,
      geometry: { type: "Point", coordinates: [p.lon, p.lat] },
      properties: {
        id: p.id,
        name: p.name ? peakLabel(p) : "",
        prominence: p.prominence,
        logProminence: Math.log10(Math.max(p.prominence, 1)),
      },
    })),
  };
}

function selectionGeoJson(sel: Selection): GeoJSON.FeatureCollection {
  const features: GeoJSON.Feature[] = [];
  const addPeak = (p: Peak, slot: "a" | "b") =>
    features.push({
      type: "Feature",
      geometry: { type: "Point", coordinates: [p.lon, p.lat] },
      properties: { kind: "peak", slot },
    });
  const addCol = (p: Peak, label: string) => {
    if (!p.col) return;
    features.push({
      type: "Feature",
      geometry: { type: "Point", coordinates: [p.col[1], p.col[0]] },
      properties: { kind: "col", label },
    });
  };
  const addLine = (coords: [number, number][]) =>
    features.push({
      type: "Feature",
      geometry: { type: "LineString", coordinates: coords },
      properties: { kind: "line" },
    });

  if (sel.a) {
    addPeak(sel.a, "a");
    if (sel.merge && sel.b) {
      addPeak(sel.b, "b");
      const pass = sel.merge.pass;
      if (pass?.col) {
        addCol(
          pass,
          `pass · ${Math.round(sel.merge.level).toLocaleString()} /km²`,
        );
        addLine([
          [sel.a.lon, sel.a.lat],
          [pass.col[1], pass.col[0]],
          [sel.b.lon, sel.b.lat],
        ]);
      }
    } else if (sel.a.col) {
      addCol(
        sel.a,
        `key col · ${Math.round(sel.a.colHeight).toLocaleString()} /km²`,
      );
      addLine([
        [sel.a.lon, sel.a.lat],
        [sel.a.col[1], sel.a.col[0]],
      ]);
    }
  }
  return { type: "FeatureCollection", features };
}

function createMap(
  host: HTMLDivElement,
  callbacks: React.RefObject<{
    onSelect: Props["onSelect"];
    onClear: Props["onClear"];
  }>,
  onReady: (map: MapLibreMap) => void,
): MapLibreMap {
  const archive = new PMTiles(TILES_URL);
  const protocol = new Protocol();
  protocol.add(archive);
  addProtocol("pmtiles", protocol.tile);

  // maplibre-contour fetches DEM tiles itself, so hand it the archive directly.
  const demSource = new mlcontour.DemSource({
    url: DEM_PATTERN,
    encoding: "mapbox",
    maxzoom: DEM_MAX_ZOOM,
    worker: false,
  });
  demSource.manager = new mlcontour.LocalDemManager({
    demUrlPattern: DEM_PATTERN,
    cacheSize: 200,
    encoding: "mapbox",
    maxzoom: DEM_MAX_ZOOM,
    timeoutMs: 15_000,
    decodeImage: decodeDemTile,
    getTile: async (url) => {
      const [z, x, y] = url.slice("dem://".length).split("/").map(Number);
      const tile = await archive.getZxy(z, x, y);
      const data = tile
        ? new Blob([tile.data], { type: "image/png" })
        : await emptyDemTile();
      return { data };
    },
  });
  // Not demSource.setupMaplibre: the local manager caches contour tiles and
  // returns the same ArrayBuffer for a repeated request, but MapLibre transfers
  // the buffer to its worker, which detaches it. Hand MapLibre a copy each time.
  addProtocol(demSource.contourProtocolId, async (params, abort) => {
    const response = await demSource.contourProtocolV4(params, abort);
    return { ...response, data: response.data.slice(0) };
  });

  const map = new MapLibreMap({
    container: host,
    style: buildStyle(
      `pmtiles://${TILES_URL}/{z}/{x}/{y}`,
      demSource.contourProtocolUrl({
        thresholds: CONTOUR_THRESHOLDS,
        contourLayer: "contours",
        elevationKey: "ele",
        levelKey: "level",
        extent: 4096,
        buffer: 1,
      }),
    ),
    center: [12, 28],
    zoom: 1.9,
    minZoom: 1,
    maxZoom: 13,
    hash: true,
    attributionControl: { compact: false },
    maxPitch: 75,
  });
  map.on("error", (e) => console.error("map error", e.error ?? e));
  if (process.env.NODE_ENV === "development") {
    (window as unknown as { __map?: MapLibreMap }).__map = map;
  }
  map.addControl(new NavigationControl({ visualizePitch: true }), "top-right");
  map.addControl(new ScaleControl({ unit: "metric" }), "bottom-right");

  map.on("load", () => {
    map.on("click", "peaks-circle", (e: MapLayerMouseEvent) => {
      const id = e.features?.[0]?.properties?.id;
      if (typeof id === "number") {
        callbacks.current.onSelect(id, e.originalEvent.shiftKey);
      }
    });
    map.on("click", (e: MapLayerMouseEvent) => {
      const hits = map.queryRenderedFeatures(e.point, {
        layers: ["peaks-circle"],
      });
      if (hits.length === 0) callbacks.current.onClear();
    });
    map.on(
      "mouseenter",
      "peaks-circle",
      () => (map.getCanvas().style.cursor = "pointer"),
    );
    map.on(
      "mouseleave",
      "peaks-circle",
      () => (map.getCanvas().style.cursor = ""),
    );
    onReady(map);
  });
  return map;
}

export default function PopulationMap({
  peaks,
  minProminence,
  seaLevel,
  exaggeration,
  selection,
  flyTo,
  onSelect,
  onClear,
}: Props) {
  const container = useRef<HTMLDivElement>(null);
  /** The map, once its style has loaded and layers can be driven. */
  const [live, setLive] = useState<MapLibreMap | null>(null);
  const callbacks = useRef({ onSelect, onClear });
  useEffect(() => {
    callbacks.current = { onSelect, onClear };
  }, [onSelect, onClear]);

  useEffect(() => {
    const host = container.current;
    if (!host) return;

    // Build the map on the next tick. React's development-mode double mount
    // would otherwise create a map, tear it down (releasing MapLibre's shared
    // worker pool) and create another synchronously, which can leave the
    // survivor with terminated workers. (Not requestAnimationFrame: it never
    // fires in a hidden tab.)
    let map: MapLibreMap | null = null;
    const timer = setTimeout(() => {
      map = createMap(host, callbacks, setLive);
    }, 0);

    return () => {
      clearTimeout(timer);
      setLive(null);
      map?.remove();
      removeProtocol("pmtiles");
    };
    // The map is created once; later prop changes are applied by the effects below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Each effect below re-applies one prop to the live map.
  useEffect(() => {
    if (!live) return;
    (live.getSource("peaks") as GeoJSONSource | undefined)?.setData(
      peaksGeoJson(peaks),
    );
  }, [live, peaks]);

  useEffect(() => {
    if (!live) return;
    const filter: FilterSpecification = [
      ">=",
      ["get", "prominence"],
      minProminence,
    ];
    live.setFilter("peaks-circle", filter);
    live.setFilter("peaks-label", filter);
  }, [live, minProminence]);

  useEffect(() => {
    if (!live) return;
    live.setPaintProperty("flood", "color-relief-color", floodColor(seaLevel));
    live.setLayoutProperty(
      "flood",
      "visibility",
      seaLevel >= FLOOD_MIN_LEVEL ? "visible" : "none",
    );
  }, [live, seaLevel]);

  useEffect(() => {
    if (!live) return;
    live.setTerrain(
      exaggeration > 0 ? { source: "terrain", exaggeration } : null,
    );
  }, [live, exaggeration]);

  useEffect(() => {
    if (!live) return;
    (live.getSource("selection") as GeoJSONSource | undefined)?.setData(
      selectionGeoJson(selection),
    );
  }, [live, selection]);

  useEffect(() => {
    if (!live || !flyTo) return;
    live.flyTo({
      center: [flyTo.lon, flyTo.lat],
      zoom: flyTo.zoom ?? Math.max(live.getZoom(), 7),
      duration: 1400,
      essential: true,
    });
  }, [live, flyTo]);

  return <div ref={container} className="map-stage" />;
}
