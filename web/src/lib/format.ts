const compact = new Intl.NumberFormat("en", {
  notation: "compact",
  maximumFractionDigits: 1,
});
const whole = new Intl.NumberFormat("en", { maximumFractionDigits: 0 });

/** People per km², whole numbers with separators. */
export function density(value: number): string {
  return whole.format(Math.round(value));
}

export function people(value: number): string {
  return compact.format(value);
}

export function area(km2: number): string {
  return `${compact.format(km2)} km²`;
}

/** Map a 0..1 slider position onto a log scale between min and max. */
export function logScale(t: number, min: number, max: number): number {
  return Math.exp(Math.log(min) + t * (Math.log(max) - Math.log(min)));
}

export function logPosition(value: number, min: number, max: number): number {
  return (Math.log(value) - Math.log(min)) / (Math.log(max) - Math.log(min));
}

/** Round a slider value to a tidy number of significant figures. */
export function tidy(value: number): number {
  if (value <= 0) return 0;
  const magnitude = 10 ** Math.floor(Math.log10(value));
  return Math.round(value / magnitude) * magnitude;
}
