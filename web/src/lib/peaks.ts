/** The divide tree exported by the pipeline, and queries on it. */

export interface Peak {
  id: number;
  lat: number;
  lon: number;
  /** Peak density, people per km². */
  height: number;
  prominence: number;
  colHeight: number;
  /** Key col as [lat, lon]; null for an island summit. */
  col: [number, number] | null;
  /** Island parent: the highest peak inside the key col's contour. */
  parent: number | null;
  /** People living inside the key col contour. */
  population: number;
  areaKm2: number;
  name: string | null;
  country: string | null;
  /** True if the naming city sits inside this peak's territory, false if merely near it. */
  nameContained: boolean | null;
}

/** Columnar form written by the pipeline; one entry per peak in id order. */
export interface PeaksFile {
  units: { height: string };
  floor: number;
  minProminence: number;
  lat: number[];
  lon: number[];
  height: number[];
  prominence: number[];
  colHeight: number[];
  /** [lat, lon] pairs; null for island summits. */
  col: ([number, number] | null)[];
  /** -1 for island summits. */
  parent: number[];
  population: number[];
  areaKm2: number[];
  /** Empty string when unnamed. */
  name: string[];
  country: string[];
  /** 1 contained, 0 nearby, -1 unnamed. */
  nameContained: number[];
}

export interface MergeResult {
  /** Highest density contour at which both peaks are one landmass. */
  level: number;
  /** The peak whose key col is the pass between them; null if they never join above sea level. */
  pass: Peak | null;
}

export class DivideTree {
  constructor(
    readonly peaks: Peak[],
    readonly floor: number,
    readonly minProminence: number,
  ) {}

  static fromFile(file: PeaksFile): DivideTree {
    const peaks: Peak[] = file.lat.map((lat, i) => ({
      id: i,
      lat,
      lon: file.lon[i],
      height: file.height[i],
      prominence: file.prominence[i],
      colHeight: file.colHeight[i],
      col: file.col[i],
      parent: file.parent[i] < 0 ? null : file.parent[i],
      population: file.population[i],
      areaKm2: file.areaKm2[i],
      name: file.name[i] || null,
      country: file.name[i] ? file.country[i] : null,
      nameContained: file.name[i] ? file.nameContained[i] === 1 : null,
    }));
    return new DivideTree(peaks, file.floor, file.minProminence);
  }

  get(id: number): Peak {
    return this.peaks[id];
  }

  /** From the peak up to its island summit, inclusive. */
  lineage(id: number): Peak[] {
    const out: Peak[] = [];
    for (let n: number | null = id; n !== null; n = this.peaks[n].parent) {
      out.push(this.peaks[n]);
    }
    return out;
  }

  /**
   * Key col heights never rise walking up the tree, so the merge level of two
   * peaks is the lowest col on the tree path between them.
   */
  mergeLevel(a: number, b: number): MergeResult {
    if (a === b) return { level: this.peaks[a].height, pass: null };
    const seen = new Map<number, MergeResult>();
    let level = Infinity;
    let pass: Peak | null = null;
    for (let n: number | null = a; n !== null; n = this.peaks[n].parent) {
      seen.set(n, { level, pass });
      const p = this.peaks[n];
      if (p.colHeight < level) {
        level = p.colHeight;
        pass = p;
      }
    }
    level = Infinity;
    pass = null;
    for (let n: number | null = b; n !== null; n = this.peaks[n].parent) {
      const hit = seen.get(n);
      if (hit) return hit.level < level ? hit : { level, pass };
      const p = this.peaks[n];
      if (p.colHeight < level) {
        level = p.colHeight;
        pass = p;
      }
    }
    return { level: this.floor, pass: null };
  }

  /** Peaks at or above a prominence threshold, most prominent first. */
  atLeast(minProminence: number): Peak[] {
    return this.peaks
      .filter((p) => p.prominence >= minProminence)
      .sort((x, y) => y.prominence - x.prominence);
  }
}

export function peakLabel(peak: Peak): string {
  if (!peak.name) return `Unnamed peak ${peak.id}`;
  return peak.nameContained ? peak.name : `near ${peak.name}`;
}
