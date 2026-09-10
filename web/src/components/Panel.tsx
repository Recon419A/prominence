"use client";

import { useMemo, useState } from "react";

import {
  area,
  density,
  logPosition,
  logScale,
  people,
  tidy,
} from "@/lib/format";
import { type DivideTree, type Peak, peakLabel } from "@/lib/peaks";
import type { Controls } from "./Explorer";
import type { Selection } from "./PopulationMap";

const SEA_RANGE: [number, number] = [1, 30_000];
/** Lower bound falls back to this until the peaks file says what it contains. */
const PROM_FLOOR_DEFAULT = 1000;
const PROM_MAX = 30_000;

interface Props {
  tree: DivideTree | null;
  load:
    | { status: "loading" }
    | { status: "error"; message: string }
    | { status: "ready" };
  controls: Controls;
  onControls: (c: Controls) => void;
  selection: Selection;
  comparing: boolean;
  onCompare: () => void;
  onSelect: (peak: Peak) => void;
  onSelectB: (peak: Peak) => void;
  onGoTo: (peak: Peak, zoom?: number) => void;
  onClear: () => void;
}

export default function Panel(props: Props) {
  const { tree, load, controls, onControls, selection } = props;
  const [query, setQuery] = useState("");
  const [showMethod, setShowMethod] = useState(false);

  const ranked = useMemo(
    () => tree?.atLeast(controls.minProminence) ?? [],
    [tree, controls.minProminence],
  );
  const listed = useMemo(() => {
    const q = query.trim().toLowerCase();
    const pool = q
      ? ranked.filter((p) => (p.name ?? "").toLowerCase().includes(q))
      : ranked;
    return pool.slice(0, 60);
  }, [ranked, query]);

  return (
    <aside className="sheet">
      <header className="sheet-head">
        <p className="eyebrow">Survey sheet · GHS-POP 2025</p>
        <h1 className="display">Prominence</h1>
        <p className="lede">
          Population density read as terrain. One person per square kilometre is
          one metre of altitude; cities are mountains, and the
          mountaineer&rsquo;s rules decide which ones count.
        </p>
      </header>

      <section className="block">
        <h2 className="block-title">Instruments</h2>
        <Slider
          label="Sea level"
          hint="Flood everything below this density"
          value={controls.seaLevel}
          range={SEA_RANGE}
          format={(v) => `${density(v)} /km²`}
          onChange={(seaLevel) => onControls({ ...controls, seaLevel })}
        />
        <Slider
          label="What counts as a city"
          hint="Minimum prominence to show a peak"
          value={controls.minProminence}
          range={[tree?.minProminence ?? PROM_FLOOR_DEFAULT, PROM_MAX]}
          format={(v) => `${density(v)} /km²`}
          onChange={(minProminence) =>
            onControls({ ...controls, minProminence })
          }
        />
        <Slider
          label="Relief"
          hint="Vertical exaggeration of the 3-D terrain (tilt the map)"
          value={controls.exaggeration}
          range={[0, 0.08]}
          linear
          format={(v) => (v === 0 ? "flat" : `×${v.toFixed(3)}`)}
          onChange={(exaggeration) => onControls({ ...controls, exaggeration })}
        />
        {tree && (
          <p className="readout">
            <span className="figure">{ranked.length.toLocaleString()}</span>{" "}
            peaks clear the bar
          </p>
        )}
      </section>

      {load.status === "loading" && (
        <p className="block muted">Surveying the planet…</p>
      )}
      {load.status === "error" && (
        <p className="block error">
          Could not load the peaks file: {load.message}
        </p>
      )}

      {tree && selection.a && (
        <PeakCard
          tree={tree}
          peak={selection.a}
          selection={selection}
          comparing={props.comparing}
          onCompare={props.onCompare}
          onGoTo={props.onGoTo}
          onSelect={props.onSelect}
          onSelectB={props.onSelectB}
          onClear={props.onClear}
        />
      )}

      {tree && (
        <section className="block">
          <h2 className="block-title">Ranked by prominence</h2>
          <input
            className="search"
            type="search"
            placeholder="Find a peak…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-label="Find a peak by name"
          />
          <ol className="ranked">
            {listed.map((p) => (
              <li key={p.id}>
                <button
                  type="button"
                  className={`rank-row${selection.a?.id === p.id ? " is-selected" : ""}`}
                  onClick={() => props.onSelect(p)}
                >
                  <span className="rank-no">{ranked.indexOf(p) + 1}</span>
                  <span className="rank-name">
                    {peakLabel(p)}
                    {p.country && (
                      <span className="rank-country"> {p.country}</span>
                    )}
                  </span>
                  <span className="rank-figure">{density(p.prominence)}</span>
                </button>
              </li>
            ))}
          </ol>
        </section>
      )}

      <section className="block">
        <button
          type="button"
          className="link"
          onClick={() => setShowMethod((s) => !s)}
        >
          {showMethod ? "Hide" : "How to read this map"}
        </button>
        {showMethod && <Method />}
      </section>

      <footer className="sheet-foot">
        Population: GHS-POP R2023A, European Commission JRC (CC BY 4.0). Names:
        GeoNames (CC BY 4.0). Coastlines: Natural Earth. Source on{" "}
        <a href="https://github.com/Recon419A/prominence">GitHub</a>.
      </footer>
    </aside>
  );
}

function Slider({
  label,
  hint,
  value,
  range,
  format,
  onChange,
  linear = false,
}: {
  label: string;
  hint: string;
  value: number;
  range: [number, number];
  format: (v: number) => string;
  onChange: (v: number) => void;
  linear?: boolean;
}) {
  const [min, max] = range;
  const position = linear
    ? (value - min) / (max - min)
    : logPosition(value, min, max);
  return (
    <label className="slider">
      <span className="slider-head">
        <span className="slider-label">{label}</span>
        <span className="slider-value">{format(value)}</span>
      </span>
      <input
        type="range"
        min={0}
        max={1000}
        value={Math.round(position * 1000)}
        onChange={(e) => {
          const t = Number(e.target.value) / 1000;
          onChange(
            linear ? min + t * (max - min) : tidy(logScale(t, min, max)),
          );
        }}
      />
      <span className="slider-hint">{hint}</span>
    </label>
  );
}

function PeakCard({
  tree,
  peak,
  selection,
  comparing,
  onCompare,
  onGoTo,
  onSelect,
  onSelectB,
  onClear,
}: {
  tree: DivideTree;
  peak: Peak;
  selection: Selection;
  comparing: boolean;
  onCompare: () => void;
  onGoTo: (peak: Peak, zoom?: number) => void;
  onSelect: (peak: Peak) => void;
  onSelectB: (peak: Peak) => void;
  onClear: () => void;
}) {
  const lineage = tree.lineage(peak.id).slice(1);
  const parent = lineage[0];
  const { b, merge } = selection;

  return (
    <section className="block card">
      <div className="card-head">
        <div>
          <p className="eyebrow">
            {peak.country ?? "Peak"} · #{peak.id}
          </p>
          <h2 className="card-title">{peakLabel(peak)}</h2>
        </div>
        <button
          type="button"
          className="ghost"
          onClick={onClear}
          aria-label="Clear selection"
        >
          ×
        </button>
      </div>

      <dl className="stats">
        <Stat label="Summit" value={density(peak.height)} unit="/km²" />
        <Stat
          label="Prominence"
          value={density(peak.prominence)}
          unit="/km²"
          accent
        />
        <Stat
          label="Key col"
          value={peak.col ? density(peak.colHeight) : "sea level"}
          unit={peak.col ? "/km²" : ""}
        />
        <Stat
          label="Within contour"
          value={people(peak.population)}
          unit="people"
        />
        <Stat label="Area" value={area(peak.areaKm2)} />
        <Stat
          label="Parent"
          value={parent ? peakLabel(parent) : "none — island summit"}
          onClick={parent ? () => onSelect(parent) : undefined}
        />
      </dl>

      {lineage.length > 1 && (
        <p className="lineage">
          <span className="muted">Lineage </span>
          {lineage.map((p, i) => (
            <span key={p.id}>
              {i > 0 && <span className="muted"> › </span>}
              <button
                type="button"
                className="chip"
                onClick={() => onSelect(p)}
              >
                {peakLabel(p)}
              </button>
            </span>
          ))}
        </p>
      )}

      <div className="actions">
        <button type="button" className="btn" onClick={() => onGoTo(peak, 9)}>
          Zoom to summit
        </button>
        {peak.col && (
          <button
            type="button"
            className="btn"
            onClick={() =>
              onGoTo({ ...peak, lat: peak.col![0], lon: peak.col![1] }, 9)
            }
          >
            Zoom to key col
          </button>
        )}
        <button
          type="button"
          className={`btn${comparing ? " is-active" : ""}`}
          onClick={onCompare}
        >
          {comparing ? "Now click a second peak…" : "Compare with…"}
        </button>
      </div>

      {b && merge && (
        <div className="compare">
          <p className="eyebrow">Merge level</p>
          <p className="compare-line">
            <strong>{peakLabel(peak)}</strong> and{" "}
            <strong>{peakLabel(b)}</strong>{" "}
            {merge.level > tree.floor ? (
              <>
                are one landmass above{" "}
                <span className="figure">{density(merge.level)} /km²</span>
                {merge.pass?.col && (
                  <>
                    , joined through the pass at{" "}
                    <button
                      type="button"
                      className="chip"
                      onClick={() =>
                        onGoTo(
                          {
                            ...b,
                            lat: merge.pass!.col![0],
                            lon: merge.pass!.col![1],
                          },
                          8,
                        )
                      }
                    >
                      {merge.pass.col[0].toFixed(2)},{" "}
                      {merge.pass.col[1].toFixed(2)}
                    </button>
                  </>
                )}
                .
              </>
            ) : (
              <>never join above sea level: they sit on different islands.</>
            )}
          </p>
          <p className="slider-hint">
            Set sea level to{" "}
            {merge.level > tree.floor
              ? `just under ${density(merge.level)}`
              : "its minimum"}{" "}
            to see them as a single blob; set it above and they split.
          </p>
          <div className="actions">
            <button type="button" className="btn" onClick={() => onSelectB(b)}>
              Swap focus
            </button>
          </div>
        </div>
      )}
      {comparing && (
        <p className="slider-hint">
          Tip: shift-click any peak on the map to compare it at any time.
        </p>
      )}
    </section>
  );
}

function Stat({
  label,
  value,
  unit,
  accent,
  onClick,
}: {
  label: string;
  value: string;
  unit?: string;
  accent?: boolean;
  onClick?: () => void;
}) {
  const body = (
    <>
      <span className={`stat-value${accent ? " is-accent" : ""}`}>{value}</span>
      {unit && <span className="stat-unit"> {unit}</span>}
    </>
  );
  return (
    <div className="stat">
      <dt>{label}</dt>
      <dd>
        {onClick ? (
          <button type="button" className="chip" onClick={onClick}>
            {body}
          </button>
        ) : (
          body
        )}
      </dd>
    </div>
  );
}

function Method() {
  return (
    <div className="method">
      <p>
        <strong>Height</strong> is population density, from the GHS-POP 1 km
        grid. The map shades, lights and contours it exactly as it would a
        mountain range.
      </p>
      <p>
        <strong>Prominence</strong> is how far a peak rises above its{" "}
        <em>key col</em>: the highest saddle on any route to higher ground. A
        dense suburb next to a denser city centre has almost none; an isolated
        town can be very prominent at a fraction of the height. Move the
        &ldquo;what counts as a city&rdquo; slider and watch shoulders vanish
        while true summits stay.
      </p>
      <p>
        <strong>Parent</strong> is the highest peak inside the key col&rsquo;s
        contour, so following parents climbs a single tree that ends at the
        densest cell on each island.
      </p>
      <p>
        <strong>Merge level</strong> answers the megalopolis question. Pick two
        peaks: the lowest col on the tree path between them is the highest
        density at which they are one contiguous blob. Raise sea level past it
        and they become two.
      </p>
      <p>
        <strong>Within contour</strong> counts everyone living inside a
        peak&rsquo;s key col contour: the population of the mountain, rather
        than of an administrative boundary.
      </p>
    </div>
  );
}
