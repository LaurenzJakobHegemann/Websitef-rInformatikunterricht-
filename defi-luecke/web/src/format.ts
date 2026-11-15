import type { AccessClass } from './types';

const nf = new Intl.NumberFormat('de-DE');
const pf = new Intl.NumberFormat('de-DE', { maximumFractionDigits: 1, minimumFractionDigits: 1 });

export const fmtInt = (v: number | null | undefined): string =>
  v === null || v === undefined ? '–' : nf.format(Math.round(v));

/** Fraction 0..1 -> "12,3 %" */
export const fmtPct = (v: number | null | undefined): string =>
  v === null || v === undefined ? '–' : `${pf.format(v * 100)} %`;

export const fmtMeters = (v: number | null | undefined): string =>
  v === null || v === undefined ? '–' : `${nf.format(Math.round(v))} m`;

export const fmtDec = (v: number | null | undefined): string =>
  v === null || v === undefined ? '–' : pf.format(v);

/** "2026-11-15" -> "15.11.2026"; anything else unchanged. */
export function fmtDate(v: string | null | undefined): string {
  if (!v) return 'unbekannt';
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(v);
  return m ? `${m[3]}.${m[2]}.${m[1]}` : v;
}

export const ACCESS_LABEL: Record<AccessClass, string> = {
  '24/7': '24/7',
  restricted: 'eingeschränkt',
  unknown: 'unbekannt',
};

export const SCENARIO_LABEL: Record<string, string> = {
  all: 'Alle zugänglichen AEDs (tagsüber)',
  night_strict: 'Nachts, streng (nur 24/7)',
  night_optimistic: 'Nachts, optimistisch (24/7 + Außen-AEDs ohne Zeitangabe)',
};
export const SCENARIO_SHORT: Record<string, string> = {
  all: 'tagsüber',
  night_strict: 'nachts, streng',
  night_optimistic: 'nachts, optimistisch',
};
export const scenarioLabel = (s: string): string => SCENARIO_LABEL[s] ?? s;
export const scenarioShort = (s: string): string => SCENARIO_SHORT[s] ?? s;

export const VARIANT_LABEL: Record<string, string> = {
  A: 'A: bewohnte Zellen (theoretisch)',
  B: 'B: öffentliche Orte (praxisnah)',
};

type Child = Node | string | null | undefined | false;
/** Tiny DOM helper; strings become text nodes, so data can never inject HTML. */
export function h<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  attrs: Record<string, string> | null = null,
  ...children: Child[]
): HTMLElementTagNameMap[K] {
  const el = document.createElement(tag);
  if (attrs) for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  for (const c of children) {
    if (c === null || c === undefined || c === false) continue;
    el.append(typeof c === 'string' ? document.createTextNode(c) : c);
  }
  return el;
}

/** Only allow links to OSM objects. */
export function safeOsmUrl(url: string | null | undefined, id: number): string {
  if (url && /^https:\/\/www\.openstreetmap\.org\//.test(url)) return url;
  return `https://www.openstreetmap.org/node/${id}`;
}
