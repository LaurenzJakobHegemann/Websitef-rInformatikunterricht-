// Colour-blind-safe sequential scale: viridis, 5 classes (dark = low coverage, light = high).
export const SCALE = ['#440154', '#3b528b', '#21918c', '#5ec962', '#fde725'] as const;
export const NO_DATA = '#bdbdbd';

export interface Classes {
  /** upper bounds (fractions) of each class, last = max */
  breaks: number[];
  max: number;
}

/** Equal-width classes from 0 to the data maximum rounded up to the next 10 %. */
export function makeClasses(rates: number[]): Classes {
  const top = Math.max(0.1, ...rates.filter((r) => Number.isFinite(r)));
  const max = Math.min(1, Math.ceil(top * 10 - 1e-9) / 10);
  const step = max / SCALE.length;
  return { breaks: SCALE.map((_, i) => step * (i + 1)), max };
}

export function colorFor(rate: number | null | undefined, c: Classes): string {
  if (rate === null || rate === undefined || !Number.isFinite(rate)) return NO_DATA;
  const i = c.breaks.findIndex((b) => rate <= b + 1e-12);
  return SCALE[i === -1 ? SCALE.length - 1 : i];
}
