"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useState } from "react";

import { PEAKS_URL } from "@/lib/config";
import { DivideTree, type Peak, type PeaksFile } from "@/lib/peaks";
import type { CameraTarget, Selection } from "./PopulationMap";
import Panel from "./Panel";

const PopulationMap = dynamic(() => import("./PopulationMap"), {
  ssr: false,
  loading: () => <div className="absolute inset-0 bg-sea" />,
});

export interface Controls {
  seaLevel: number;
  minProminence: number;
  exaggeration: number;
}

const EMPTY: Peak[] = [];
const DEFAULT_CONTROLS: Controls = {
  seaLevel: 1,
  minProminence: 1000,
  exaggeration: 0.02,
};

type LoadState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready" };

export default function Explorer() {
  const [tree, setTree] = useState<DivideTree | null>(null);
  const [load, setLoad] = useState<LoadState>({ status: "loading" });
  const [controls, setControls] = useState<Controls>(DEFAULT_CONTROLS);
  const [selectedA, setSelectedA] = useState<number | null>(null);
  const [selectedB, setSelectedB] = useState<number | null>(null);
  const [comparing, setComparing] = useState(false);
  const [flyTo, setFlyTo] = useState<CameraTarget | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    fetch(PEAKS_URL, { signal: controller.signal })
      .then((r) => {
        if (!r.ok)
          throw new Error(`${r.status} ${r.statusText} fetching peaks`);
        return r.json() as Promise<PeaksFile>;
      })
      .then((file) => {
        setTree(DivideTree.fromFile(file));
        setLoad({ status: "ready" });
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setLoad({
          status: "error",
          message: err instanceof Error ? err.message : String(err),
        });
      });
    return () => controller.abort();
  }, []);

  const selection = useMemo<Selection>(() => {
    if (!tree || selectedA === null) return { a: null, b: null, merge: null };
    const a = tree.get(selectedA);
    if (selectedB === null) return { a, b: null, merge: null };
    const b = tree.get(selectedB);
    return { a, b, merge: tree.mergeLevel(a.id, b.id) };
  }, [tree, selectedA, selectedB]);

  const select = useCallback(
    (id: number, additive: boolean) => {
      if ((additive || comparing) && selectedA !== null && id !== selectedA) {
        setSelectedB(id);
      } else {
        setSelectedA(id);
        setSelectedB(null);
      }
      setComparing(false);
    },
    [comparing, selectedA],
  );

  const clear = useCallback(() => {
    setSelectedA(null);
    setSelectedB(null);
    setComparing(false);
  }, []);

  const goTo = useCallback((peak: Peak, zoom?: number) => {
    setFlyTo((prev) => ({
      lat: peak.lat,
      lon: peak.lon,
      zoom,
      nonce: (prev?.nonce ?? 0) + 1,
    }));
  }, []);

  return (
    <div className="relative h-dvh w-full overflow-hidden bg-sea">
      <PopulationMap
        peaks={tree?.peaks ?? EMPTY}
        minProminence={controls.minProminence}
        seaLevel={controls.seaLevel}
        exaggeration={controls.exaggeration}
        selection={selection}
        flyTo={flyTo}
        onSelect={select}
        onClear={clear}
      />
      <Panel
        tree={tree}
        load={load}
        controls={controls}
        onControls={setControls}
        selection={selection}
        comparing={comparing}
        onCompare={() => setComparing((c) => !c)}
        onSelect={(peak) => {
          select(peak.id, false);
          goTo(peak);
        }}
        onSelectB={(peak) => {
          setSelectedB(peak.id);
          setComparing(false);
        }}
        onGoTo={goTo}
        onClear={clear}
      />
    </div>
  );
}
