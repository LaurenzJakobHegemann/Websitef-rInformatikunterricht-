import { DATA_BASE } from './config';
import type {
  AedProps,
  GapsFile,
  MetricsFile,
  Meta,
  MuniProps,
  RecommendationsFile,
  RegionIndexEntry,
} from './types';

export class DataError extends Error {}

export async function loadJson<T>(url: string): Promise<T> {
  let res: Response;
  try {
    res = await fetch(url, { cache: 'no-cache' });
  } catch {
    throw new DataError(`Datei nicht erreichbar: ${url}`);
  }
  if (!res.ok) throw new DataError(`Datei nicht gefunden (${res.status}): ${url}`);
  try {
    return (await res.json()) as T;
  } catch {
    // Dev servers answer unknown paths with index.html; treat that as "missing".
    throw new DataError(`Datei ist kein gültiges JSON: ${url}`);
  }
}

export type FC<P> = GeoJSON.FeatureCollection<GeoJSON.Geometry, P>;

export interface RegionData {
  meta: Meta;
  metrics: MetricsFile;
  municipalities: FC<MuniProps>;
  aeds: FC<AedProps>;
  recommendations: RecommendationsFile;
}

export async function loadRegions(): Promise<RegionIndexEntry[]> {
  const idx = await loadJson<{ regions: RegionIndexEntry[] }>(`${DATA_BASE}regions.json`);
  return idx.regions ?? [];
}

export async function loadRegion(key: string): Promise<RegionData> {
  const base = `${DATA_BASE}${encodeURIComponent(key)}/`;
  const [meta, metrics, municipalities, aeds, recommendations] = await Promise.all([
    loadJson<Meta>(`${base}meta.json`),
    loadJson<MetricsFile>(`${base}metrics.json`),
    loadJson<FC<MuniProps>>(`${base}municipalities.geojson`),
    loadJson<FC<AedProps>>(`${base}aeds.geojson`),
    loadJson<RecommendationsFile>(`${base}recommendations.json`),
  ]);
  return { meta, metrics, municipalities, aeds, recommendations };
}

const gapsCache = new Map<string, Promise<GapsFile>>();
export function loadGaps(region: string, scenario: string, radius: number): Promise<GapsFile> {
  const url = `${DATA_BASE}${encodeURIComponent(region)}/gaps_${scenario}_${radius}.json`;
  let p = gapsCache.get(url);
  if (!p) {
    p = loadJson<GapsFile>(url);
    p.catch(() => gapsCache.delete(url));
    gapsCache.set(url, p);
  }
  return p;
}
