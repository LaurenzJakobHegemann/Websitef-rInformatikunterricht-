export type Scenario = string; // "all" | "night_strict" | "night_optimistic"
export type AccessClass = '24/7' | 'restricted' | 'unknown';

export interface RegionIndexEntry {
  key: string;
  name: string | null;
  snapshot_date: string | null;
  generated_at: string | null;
}

export interface Meta {
  region: string;
  name: string;
  district_id: string;
  district_name: string | null;
  snapshot_date: string | null;
  census_date: string;
  boundaries_date: string;
  attributions: string[];
  radii_m: number[];
  scenarios: Scenario[];
  variants: string[];
  detour_factor: number | null;
  k_max_district: number;
  aed_stats: {
    public_in_region: number;
    by_access_class: Record<AccessClass, number>;
    share_access_unknown: number | null;
    total_in_file: number;
  };
  bbox: [number, number, number, number]; // minLon, minLat, maxLon, maxLat
  generated_at: string;
}

export interface Metric {
  population: number | null;
  covered_population: number | null;
  coverage_rate: number | null;
  mean_distance_m: number | null;
  median_distance_m: number | null;
  aeds_in_area: number | null;
  aeds_per_10k: number | null;
  share_aeds_missing_info: number | null;
  share_access_unknown: number | null;
  rank: number | null;
  rank_of: number;
}

export interface MetricEntry {
  name: string | null;
  radii: Record<string, Record<Scenario, Metric>>;
}

export interface MetricsFile {
  levels: Record<'municipality' | 'vg' | 'district', Record<string, MetricEntry>>;
}

export interface Recommendation {
  rank: number;
  lon: number;
  lat: number;
  label: string | null;
  added_population: number | null;
  cumulative_covered: number | null;
  cumulative_rate: number | null;
}

type ByRadiusScenario = Record<string, Record<Scenario, Recommendation[]>>;
export interface RecommendationsFile {
  district: Record<string, Record<string, ByRadiusScenario>>; // variant -> scope_id -> ...
  municipality: Record<string, Record<string, ByRadiusScenario>>;
}

export interface GapsFile {
  scenario: Scenario;
  radius_m: number;
  cells: [number, number, number][]; // lon, lat, population
}

export interface AedProps {
  osm_id: number;
  osm_url: string;
  access_class: AccessClass;
  is_public: boolean;
  in_region: boolean;
  scenarios: Scenario[];
  defibrillator_location: string | null;
  opening_hours: string | null;
  indoor: string | null;
  level: string | null;
  operator: string | null;
  description: string | null;
  check_date: string | null;
  survey_date: string | null;
}

export interface MuniProps {
  ags: string;
  name: string;
  vg_ars: string | null;
  population: number | null;
  ewz: number | null;
}
