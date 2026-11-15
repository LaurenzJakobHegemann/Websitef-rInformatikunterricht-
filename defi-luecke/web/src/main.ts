import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import './style.css';

import { colorFor, makeClasses, NO_DATA, SCALE, type Classes } from './colors';
import { TILE_ATTRIBUTION, TILE_MAX_ZOOM, TILE_URL } from './config';
import { DataError, loadGaps, loadRegion, loadRegions, type RegionData } from './data';
import {
  ACCESS_LABEL,
  fmtDate,
  fmtDec,
  fmtInt,
  fmtMeters,
  fmtPct,
  h,
  safeOsmUrl,
  scenarioLabel,
  scenarioShort,
  VARIANT_LABEL,
} from './format';
import type { AedProps, Metric, MuniProps, RegionIndexEntry, Recommendation } from './types';

const $ = <T extends HTMLElement>(id: string): T => {
  const el = document.getElementById(id);
  if (!el) throw new Error(`Element #${id} fehlt`);
  return el as T;
};

// ------------------------------------------------------------------ state
interface State {
  data: RegionData | null;
  radius: number;
  scenario: string;
  variant: string;
  k: number;
  selected: string | null; // municipality AGS
  layers: { aeds: boolean; gaps: boolean; rec: boolean };
}
const state: State = {
  data: null,
  radius: 300,
  scenario: 'all',
  variant: 'A',
  k: 5,
  selected: null,
  layers: { aeds: true, gaps: false, rec: false },
};

// -------------------------------------------------------------------- map
const map = L.map('map', { zoomControl: true, minZoom: 6, maxZoom: TILE_MAX_ZOOM }).setView(
  [50.0, 7.0],
  9,
);
L.tileLayer(TILE_URL, { maxZoom: TILE_MAX_ZOOM, attribution: TILE_ATTRIBUTION }).addTo(map);
map.attributionControl.setPrefix(
  '<a href="https://leafletjs.com" target="_blank" rel="noopener noreferrer">Leaflet</a>',
);

let muniLayer: L.GeoJSON | null = null;
const muniById = new Map<string, L.Path>();
const aedLayer = L.layerGroup();
const aedMarkers: { marker: L.Marker; props: AedProps }[] = [];
const gapsLayer = L.layerGroup();
const recLayer = L.layerGroup();
const gapsRenderer = L.canvas({ padding: 0.3 });
let classes: Classes = makeClasses([]);
let gapsToken = 0;

const legendControl = new L.Control({ position: 'bottomleft' });
legendControl.onAdd = () => {
  const div = L.DomUtil.create('div', 'legend');
  div.id = 'legend';
  L.DomEvent.disableClickPropagation(div);
  return div;
};
legendControl.addTo(map);

function renderLegend(): void {
  const el = document.getElementById('legend');
  if (!el) return;
  el.replaceChildren(
    h('div', { class: 'legend-title' }, `Abdeckung (Radius ${fmtInt(state.radius)} m, ${scenarioShort(state.scenario)})`),
  );
  const bar = h('div', { class: 'legend-bar', role: 'list' });
  SCALE.forEach((color, i) => {
    const lo = i === 0 ? 0 : classes.breaks[i - 1];
    const hi = classes.breaks[i];
    bar.append(
      h(
        'div',
        { class: 'legend-item', role: 'listitem' },
        h('span', { class: 'swatch', style: `background:${color}` }),
        h('span', { class: 'legend-lbl' }, `${Math.round(lo * 100)}–${Math.round(hi * 100)} %`),
      ),
    );
  });
  el.append(bar);
  const nodata = h(
    'div',
    { class: 'legend-nodata' },
    h('span', { class: 'swatch', style: `background:${NO_DATA}` }),
    h('span', { class: 'legend-lbl' }, 'keine Daten'),
  );
  el.append(nodata);
}

// ------------------------------------------------------------- helpers
function metricFor(
  level: 'municipality' | 'vg' | 'district',
  id: string,
  radius = state.radius,
  scenario = state.scenario,
): Metric | undefined {
  return state.data?.metrics.levels[level]?.[id]?.radii[String(radius)]?.[scenario];
}

function recsFor(
  variant: string,
  scope: 'district' | 'municipality',
  id: string,
): { items: Recommendation[]; scenario: string } {
  const data = state.data;
  if (!data) return { items: [], scenario: state.scenario };
  const byScen = data.recommendations[scope]?.[variant]?.[id]?.[String(state.radius)];
  if (!byScen) return { items: [], scenario: state.scenario };
  const scenario = byScen[state.scenario] ? state.scenario : Object.keys(byScen)[0];
  return { items: byScen[scenario] ?? [], scenario };
}

function option(value: string, label: string, selected: boolean): HTMLOptionElement {
  const o = h('option', { value }, label);
  o.selected = selected;
  return o;
}

function showError(message: string | null): void {
  const el = $('data-error');
  if (message === null) {
    el.hidden = true;
    return;
  }
  el.hidden = false;
  el.replaceChildren(
    h('strong', null, 'Keine Daten gefunden. '),
    message,
    h(
      'span',
      null,
      ' Die Dateien werden von der Pipeline erzeugt (`python -m pipeline.cli run --region <Region>`) und liegen danach unter web/public/data/. Details stehen in der README.',
    ),
  );
}

// ------------------------------------------------------------ rendering
function renderAedStat(): void {
  const el = $('aed-stat');
  const s = state.data?.meta.aed_stats;
  if (!s || s.public_in_region === 0) {
    el.replaceChildren();
    return;
  }
  const share = s.share_access_unknown;
  el.replaceChildren(
    h('span', { class: 'big' }, fmtPct(share)),
    ' der ',
    fmtInt(s.public_in_region),
    ' öffentlich eingetragenen AEDs haben ',
    h('strong', null, 'unbekannte Zugangszeiten'),
    ' (keine Öffnungszeiten in OpenStreetMap). 24/7: ',
    fmtInt(s.by_access_class['24/7']),
    ', eingeschränkt: ',
    fmtInt(s.by_access_class.restricted),
    '.',
  );
}

function styleFor(feature: GeoJSON.Feature | undefined): L.PathOptions {
  const p = feature?.properties as MuniProps | undefined;
  const m = p ? metricFor('municipality', p.ags) : undefined;
  const sel = p?.ags === state.selected;
  return {
    fillColor: colorFor(m?.coverage_rate, classes),
    fillOpacity: 0.72,
    color: sel ? '#000000' : '#ffffff',
    weight: sel ? 3 : 1,
    opacity: 1,
  };
}

function tooltipText(p: MuniProps): string {
  const m = metricFor('municipality', p.ags);
  return `${p.name}: ${fmtPct(m?.coverage_rate)}`;
}

function refreshChoropleth(): void {
  const data = state.data;
  if (!data) return;
  const rates: number[] = [];
  for (const f of data.municipalities.features) {
    const r = metricFor('municipality', f.properties.ags)?.coverage_rate;
    if (r !== null && r !== undefined) rates.push(r);
  }
  classes = makeClasses(rates);
  muniLayer?.eachLayer((layer) => {
    const path = layer as L.Path & { feature?: GeoJSON.Feature };
    path.setStyle(styleFor(path.feature));
    const p = path.feature?.properties as MuniProps | undefined;
    if (p) path.setTooltipContent(tooltipText(p));
  });
  const selPath = state.selected ? muniById.get(state.selected) : undefined;
  selPath?.bringToFront();
  renderLegend();
}

function buildMunicipalities(): void {
  const data = state.data;
  if (!data) return;
  muniLayer?.remove();
  muniById.clear();
  muniLayer = L.geoJSON(data.municipalities, {
    style: (f) => styleFor(f),
    onEachFeature: (feature, layer) => {
      const p = feature.properties as MuniProps;
      muniById.set(p.ags, layer as L.Path);
      layer.bindTooltip(tooltipText(p), { sticky: true, direction: 'top' });
      layer.on('click', () => selectMunicipality(p.ags, false));
    },
  }).addTo(map);
  muniLayer.bringToBack();
}

function aedIcon(p: AedProps): L.DivIcon {
  const cls = p.access_class === '24/7' ? 'a247' : p.access_class === 'restricted' ? 'ares' : 'aunk';
  return L.divIcon({
    className: `aed-icon ${cls}`,
    html: '<span></span>',
    iconSize: [20, 20],
    iconAnchor: [10, 10],
    popupAnchor: [0, -10],
  });
}

function aedPopup(p: AedProps): HTMLElement {
  const data = state.data;
  const rows: [string, string][] = [];
  rows.push(['Zugang', ACCESS_LABEL[p.access_class] ?? p.access_class]);
  if (p.opening_hours) rows.push(['Öffnungszeiten', p.opening_hours]);
  if (p.indoor) rows.push(['Lage', p.indoor === 'yes' ? 'im Gebäude' : p.indoor === 'no' ? 'außen' : p.indoor]);
  if (p.level) rows.push(['Ebene', p.level]);
  if (p.operator) rows.push(['Betreiber', p.operator]);
  if (p.description) rows.push(['Beschreibung', p.description]);
  const checked = p.check_date ?? p.survey_date;
  if (checked) rows.push(['Zuletzt geprüft (OSM)', fmtDate(checked)]);
  const dl = h('dl', { class: 'kv' });
  for (const [k, v] of rows) dl.append(h('dt', null, k), h('dd', null, v));
  return h(
    'div',
    { class: 'popup' },
    h('strong', null, p.defibrillator_location ?? 'Defibrillator (keine Ortsbeschreibung eingetragen)'),
    dl,
    !p.is_public && h('p', { class: 'hint' }, 'Nicht öffentlich zugänglich – wird in keinem Szenario gezählt.'),
    !p.in_region && h('p', { class: 'hint' }, 'Liegt im Pufferbereich außerhalb der Region.'),
    h('p', { class: 'hint' }, `Datenstand: ${fmtDate(data?.meta.snapshot_date)}`),
    h(
      'a',
      { href: safeOsmUrl(p.osm_url, p.osm_id), target: '_blank', rel: 'noopener noreferrer' },
      'Objekt in OpenStreetMap ansehen',
    ),
  );
}

function buildAeds(): void {
  aedLayer.clearLayers();
  aedMarkers.length = 0;
  for (const f of state.data?.aeds.features ?? []) {
    if (f.geometry.type !== 'Point') continue;
    const p = f.properties as AedProps;
    const [lon, lat] = f.geometry.coordinates;
    const title = `AED, Zugang ${ACCESS_LABEL[p.access_class] ?? p.access_class}${p.defibrillator_location ? ': ' + p.defibrillator_location : ''}`;
    const marker = L.marker([lat, lon], { icon: aedIcon(p), title, alt: title, keyboard: true });
    marker.bindPopup(() => aedPopup(p), { maxWidth: 300 });
    aedLayer.addLayer(marker);
    aedMarkers.push({ marker, props: p });
  }
}

function refreshAeds(): void {
  for (const { marker, props } of aedMarkers) {
    marker.setOpacity(props.scenarios.includes(state.scenario) ? 1 : 0.35);
  }
}

async function refreshGaps(): Promise<void> {
  const msg = $('gaps-msg');
  gapsLayer.clearLayers();
  msg.hidden = true;
  if (!state.layers.gaps || !state.data) return;
  const token = ++gapsToken;
  try {
    const g = await loadGaps(state.data.meta.region, state.scenario, state.radius);
    if (token !== gapsToken) return;
    let total = 0;
    for (const [lon, lat, pop] of g.cells) {
      total += pop;
      L.circleMarker([lat, lon], {
        renderer: gapsRenderer,
        radius: Math.min(7, 2 + Math.sqrt(pop) * 0.8),
        color: '#7a2e00',
        weight: 1,
        fillColor: '#ff8c1a',
        fillOpacity: 0.75,
        interactive: false,
      }).addTo(gapsLayer);
    }
    msg.hidden = false;
    msg.textContent = `${fmtInt(g.cells.length)} bewohnte Zellen (100 m) ohne AED im Radius, zusammen ${fmtInt(total)} Einwohner.`;
  } catch {
    if (token !== gapsToken) return;
    msg.hidden = false;
    msg.textContent = 'Für diese Kombination liegen keine Lücken-Daten vor.';
  }
}

function recIcon(n: number, variant: string): L.DivIcon {
  return L.divIcon({
    className: `rec-icon v${variant}`,
    html: `<span>${n}</span>`,
    iconSize: [26, 26],
    iconAnchor: [13, 13],
    popupAnchor: [0, -13],
  });
}

function refreshRecs(): void {
  recLayer.clearLayers();
  const box = $('recbox');
  const summary = $('rec-summary');
  const msg = $('rec-msg');
  box.hidden = !state.layers.rec;
  msg.hidden = true;
  summary.textContent = '';
  const data = state.data;
  if (!state.layers.rec || !data) return;
  const { items, scenario } = recsFor(state.variant, 'district', data.meta.district_id);
  const shown = items.filter((r) => r.rank <= state.k);
  if (!items.length) {
    msg.hidden = false;
    msg.textContent = `Für Radius ${fmtInt(state.radius)} m und Variante ${state.variant} liegen keine Empfehlungen vor.`;
    return;
  }
  if (scenario !== state.scenario) {
    msg.hidden = false;
    msg.textContent = `Empfehlungen wurden nur für das Szenario „${scenarioShort(scenario)}“ berechnet.`;
  }
  for (const r of shown) {
    const m = L.marker([r.lat, r.lon], {
      icon: recIcon(r.rank, state.variant),
      title: `Empfohlener Standort ${r.rank}: ${r.label ?? ''}`,
      alt: `Empfohlener Standort ${r.rank}`,
      keyboard: true,
    });
    m.bindPopup(() => recPopup(r), { maxWidth: 280 });
    recLayer.addLayer(m);
  }
  const last = shown[shown.length - 1];
  if (last) {
    const gain = shown.reduce((a, r) => a + (r.added_population ?? 0), 0);
    summary.textContent = `${shown.length} neue Standorte erreichen zusätzlich ${fmtInt(gain)} Einwohner; Abdeckung im Kreis danach ${fmtPct(last.cumulative_rate)}.`;
  }
}

function recPopup(r: Recommendation): HTMLElement {
  return h(
    'div',
    { class: 'popup' },
    h('strong', null, `Empfohlener Standort ${r.rank}`),
    h('p', null, r.label ?? 'ohne Bezeichnung'),
    h(
      'dl',
      { class: 'kv' },
      h('dt', null, 'Zugewinn'),
      h('dd', null, `${fmtInt(r.added_population)} Einwohner`),
      h('dt', null, 'Abdeckung danach'),
      h('dd', null, fmtPct(r.cumulative_rate)),
    ),
    h('p', { class: 'hint' }, 'Rechnerischer Vorschlag, keine Planung vor Ort.'),
  );
}

// ----------------------------------------------------------- profile
function metricRow(dl: HTMLElement, k: string, v: string): void {
  dl.append(h('dt', null, k), h('dd', null, v));
}

function renderProfile(): void {
  const el = $('profile');
  const data = state.data;
  if (!data) {
    el.replaceChildren();
    return;
  }
  const sel = state.selected;
  const isMuni = sel !== null;
  const id = isMuni ? sel : data.meta.district_id;
  const level = isMuni ? 'municipality' : 'district';
  const name = isMuni
    ? (data.metrics.levels.municipality[id]?.name ?? id)
    : (data.meta.district_name ?? data.meta.name);
  const m = metricFor(level, id);
  const head = h('h2', null, name);
  const sub = h(
    'p',
    { class: 'hint' },
    isMuni ? 'Gemeinde' : 'Gesamte Region',
    ` · Radius ${fmtInt(state.radius)} m · ${scenarioShort(state.scenario)}`,
  );
  const children: (Node | null)[] = [head, sub];
  if (!m) {
    children.push(h('p', null, 'Für diese Auswahl liegen keine Kennzahlen vor.'));
  } else {
    children.push(
      h(
        'p',
        { class: 'quote' },
        h('span', { class: 'big' }, fmtPct(m.coverage_rate)),
        ` der Einwohner erreichen einen AED (${fmtInt(m.covered_population)} von ${fmtInt(m.population)}).`,
      ),
    );
    const dl = h('dl', { class: 'kv' });
    if (isMuni) {
      metricRow(dl, 'Rang im Kreis', m.rank ? `${m.rank} von ${m.rank_of} (1 = beste Abdeckung)` : '–');
    }
    metricRow(dl, 'Ø Distanz zum nächsten AED', fmtMeters(m.mean_distance_m));
    metricRow(dl, 'Median der Distanz', fmtMeters(m.median_distance_m));
    metricRow(dl, 'AEDs im Gebiet', fmtInt(m.aeds_in_area));
    metricRow(dl, 'AEDs je 10.000 Einwohner', fmtDec(m.aeds_per_10k));
    metricRow(dl, 'Zugang unbekannt', fmtPct(m.share_access_unknown));
    metricRow(dl, 'Angaben fehlen (Zugang/Zeiten)', fmtPct(m.share_aeds_missing_info));
    children.push(dl);
    if (m.aeds_in_area === 0) {
      children.push(h('p', { class: 'hint' }, 'Hier ist in diesem Szenario kein AED eingetragen. OpenStreetMap kann unvollständig sein.'));
    }
  }
  if (isMuni) {
    const { items, scenario } = recsFor(state.variant, 'municipality', id);
    const top = items.slice(0, 3);
    const block = h('div', { class: 'recs' }, h('h3', null, `Empfohlene Standorte (Variante ${state.variant})`));
    if (!top.length) {
      block.append(h('p', { class: 'hint' }, 'Keine Empfehlungen für diese Auswahl vorhanden.'));
    } else {
      const ol = h('ol');
      for (const r of top) {
        const btn = h('button', { type: 'button', class: 'link' }, `${r.label ?? 'Standort'}`);
        btn.addEventListener('click', () => {
          map.setView([r.lat, r.lon], Math.max(map.getZoom(), 16));
          L.popup({ maxWidth: 280 }).setLatLng([r.lat, r.lon]).setContent(recPopup(r)).openOn(map);
        });
        ol.append(h('li', null, btn, ` (+${fmtInt(r.added_population)} Einwohner)`));
      }
      block.append(ol);
      if (scenario !== state.scenario) {
        block.append(h('p', { class: 'hint' }, `Berechnet für das Szenario „${scenarioShort(scenario)}“.`));
      }
    }
    children.push(block);
    const reset = h('button', { type: 'button', class: 'btn secondary' }, 'Auswahl aufheben');
    reset.addEventListener('click', () => selectMunicipality(null));
    children.push(reset);
  }
  el.replaceChildren(...children.filter((c): c is Node => c !== null));
}

function selectMunicipality(ags: string | null, zoom = true): void {
  const prev = state.selected ? muniById.get(state.selected) : undefined;
  state.selected = ags;
  if (prev) (prev as L.Path).setStyle(styleFor((prev as unknown as { feature?: GeoJSON.Feature }).feature));
  if (ags) {
    const path = muniById.get(ags) as (L.Path & { getBounds?: () => L.LatLngBounds }) | undefined;
    if (path) {
      path.setStyle(styleFor((path as unknown as { feature?: GeoJSON.Feature }).feature));
      path.bringToFront();
      if (zoom && path.getBounds) map.fitBounds(path.getBounds(), { padding: [20, 20], maxZoom: 14 });
    }
  }
  renderProfile();
}

// ------------------------------------------------------------- table
function renderTable(): void {
  const body = document.querySelector<HTMLTableSectionElement>('#muni-table tbody');
  const data = state.data;
  if (!body || !data) return;
  const rows = data.municipalities.features
    .map((f) => ({ p: f.properties, m: metricFor('municipality', f.properties.ags) }))
    .sort((a, b) => (b.m?.coverage_rate ?? -1) - (a.m?.coverage_rate ?? -1));
  body.replaceChildren(
    ...rows.map(({ p, m }) => {
      const btn = h('button', { type: 'button', class: 'link' }, p.name);
      btn.addEventListener('click', () => {
        selectMunicipality(p.ags);
        $('map').scrollIntoView({ block: 'nearest' });
      });
      return h(
        'tr',
        null,
        h('td', null, m?.rank ? String(m.rank) : '–'),
        h('th', { scope: 'row' }, btn),
        h('td', null, fmtPct(m?.coverage_rate)),
        h('td', null, fmtInt(m?.population)),
      );
    }),
  );
}

// ------------------------------------------------------------ search
function norm(s: string): string {
  return s.toLocaleLowerCase('de').normalize('NFD').replace(/\p{Diacritic}/gu, '');
}

function setupSearch(): void {
  const input = $<HTMLInputElement>('inp-search');
  const list = $('search-results');
  const close = () => {
    list.hidden = true;
    input.setAttribute('aria-expanded', 'false');
  };
  const choose = (ags: string) => {
    const name = state.data?.metrics.levels.municipality[ags]?.name ?? '';
    input.value = name;
    close();
    selectMunicipality(ags);
  };
  const update = () => {
    const q = norm(input.value.trim());
    const data = state.data;
    list.replaceChildren();
    if (!q || !data) return close();
    const hits = data.municipalities.features
      .map((f) => f.properties)
      .filter((p) => norm(p.name).includes(q))
      .sort((a, b) => Number(norm(b.name).startsWith(q)) - Number(norm(a.name).startsWith(q)) || a.name.localeCompare(b.name, 'de'))
      .slice(0, 8);
    if (!hits.length) {
      list.append(h('li', { class: 'none', role: 'option', 'aria-disabled': 'true' }, 'Keine Gemeinde gefunden'));
    }
    for (const p of hits) {
      const li = h('li', { role: 'option', 'aria-selected': 'false' });
      const b = h('button', { type: 'button' }, p.name);
      b.addEventListener('click', () => choose(p.ags));
      li.append(b);
      list.append(li);
    }
    list.hidden = false;
    input.setAttribute('aria-expanded', 'true');
  };
  input.addEventListener('input', update);
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') close();
    if (e.key === 'Enter') {
      e.preventDefault();
      list.querySelector<HTMLButtonElement>('button')?.click();
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      list.querySelector<HTMLButtonElement>('button')?.focus();
    }
  });
  list.addEventListener('keydown', (e) => {
    const t = e.target as HTMLElement;
    const li = t.closest('li');
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      li?.nextElementSibling?.querySelector('button')?.focus();
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      const prev = li?.previousElementSibling?.querySelector('button');
      (prev ?? input).focus();
    } else if (e.key === 'Escape') {
      close();
      input.focus();
    }
  });
}

// -------------------------------------------------------------- setup
function refreshAll(): void {
  refreshChoropleth();
  refreshAeds();
  renderTable();
  renderProfile();
  void refreshGaps();
  refreshRecs();
}

function syncLayerVisibility(): void {
  const set = (layer: L.Layer, on: boolean) => {
    if (on && !map.hasLayer(layer)) layer.addTo(map);
    if (!on && map.hasLayer(layer)) layer.remove();
  };
  set(aedLayer, state.layers.aeds);
  set(gapsLayer, state.layers.gaps);
  set(recLayer, state.layers.rec);
}

function fillControls(data: RegionData): void {
  const meta = data.meta;
  const radii = meta.radii_m;
  if (!radii.includes(state.radius)) state.radius = radii.includes(300) ? 300 : radii[0];
  if (!meta.scenarios.includes(state.scenario)) state.scenario = meta.scenarios[0];
  if (!meta.variants.includes(state.variant)) state.variant = meta.variants[0];
  $('sel-radius').replaceChildren(...radii.map((r) => option(String(r), `${fmtInt(r)} m`, r === state.radius)));
  $('sel-scenario').replaceChildren(
    ...meta.scenarios.map((s) => option(s, scenarioLabel(s), s === state.scenario)),
  );
  const kmax = Math.max(1, Math.min(20, meta.k_max_district || 20));
  const rng = $<HTMLInputElement>('rng-k');
  rng.max = String(kmax);
  state.k = Math.min(state.k, kmax);
  rng.value = String(state.k);
  $('out-k').textContent = String(state.k);

  const seg = $('seg-variant');
  seg.replaceChildren(
    ...meta.variants.map((v) => {
      const input = h('input', { type: 'radio', name: 'variant', value: v });
      input.checked = v === state.variant;
      input.addEventListener('change', () => {
        state.variant = v;
        renderProfile();
        refreshRecs();
      });
      return h('label', { class: 'radio' }, input, ` ${VARIANT_LABEL[v] ?? v}`);
    }),
  );
}

function fillStaticPages(data: RegionData): void {
  const meta = data.meta;
  const dl = $('meth-sources');
  dl.replaceChildren(
    h('dt', null, 'Region'),
    h('dd', null, meta.name),
    h('dt', null, 'AED-Standorte (OpenStreetMap)'),
    h('dd', null, `Snapshot vom ${fmtDate(meta.snapshot_date)}; Auswertung gegen diesen festen Datenstand, nicht gegen Live-Daten.`),
    h('dt', null, 'Bevölkerung (Zensus 2022, 100-m-Gitter)'),
    h('dd', null, `Stichtag ${meta.census_date}`),
    h('dt', null, 'Verwaltungsgrenzen (BKG VG250)'),
    h('dd', null, `Stand ${meta.boundaries_date}`),
    h('dt', null, 'Daten erzeugt am'),
    h('dd', null, fmtDate(meta.generated_at)),
    h('dt', null, 'Quellenvermerke'),
    h('dd', null, h('ul', null, ...meta.attributions.map((a) => h('li', null, a)))),
  );
  $('meth-detour').textContent = meta.detour_factor !== null ? fmtDec(meta.detour_factor).replace(/,0$/, '') : '–';
  $('meth-radii').textContent = meta.radii_m.map((r) => `${fmtInt(r)} m`).join(', ');
  $('footer-attrib').replaceChildren(
    ...meta.attributions.filter((a) => !a.includes('OpenStreetMap')).map((a, i, arr) =>
      document.createTextNode(a + (i < arr.length - 1 ? ' · ' : '')),
    ),
    document.createTextNode(` · AED-Datenstand: ${fmtDate(meta.snapshot_date)}`),
  );
}

async function openRegion(key: string): Promise<void> {
  showError(null);
  try {
    const data = await loadRegion(key);
    state.data = data;
    state.selected = null;
    fillControls(data);
    fillStaticPages(data);
    buildMunicipalities();
    buildAeds();
    syncLayerVisibility();
    const [w, s, e, n] = data.meta.bbox;
    map.fitBounds([[s, w], [n, e]], { padding: [10, 10] });
    renderAedStat();
    refreshAll();
  } catch (err) {
    state.data = null;
    showError(
      err instanceof DataError
        ? `Für die Region „${key}“ fehlen Dateien (${err.message}).`
        : 'Die Daten konnten nicht gelesen werden.',
    );
  }
}

function bindControls(): void {
  $('sel-radius').addEventListener('change', (e) => {
    state.radius = Number((e.target as HTMLSelectElement).value);
    refreshAll();
  });
  $('sel-scenario').addEventListener('change', (e) => {
    state.scenario = (e.target as HTMLSelectElement).value;
    refreshAll();
  });
  const layerBox = (id: string, key: keyof State['layers']) =>
    $<HTMLInputElement>(id).addEventListener('change', (e) => {
      state.layers[key] = (e.target as HTMLInputElement).checked;
      syncLayerVisibility();
      void refreshGaps();
      refreshRecs();
    });
  layerBox('chk-aeds', 'aeds');
  layerBox('chk-gaps', 'gaps');
  layerBox('chk-rec', 'rec');
  $<HTMLInputElement>('rng-k').addEventListener('input', (e) => {
    state.k = Number((e.target as HTMLInputElement).value);
    $('out-k').textContent = String(state.k);
    refreshRecs();
  });
  setupSearch();
}

// ------------------------------------------------------------- routing
function route(initial = false): void {
  const hash = location.hash.replace(/^#\/?/, '');
  const view = hash === 'melden' || hash === 'methodik' ? hash : 'map';
  for (const id of ['map', 'melden', 'methodik']) {
    $(`view-${id}`).hidden = id !== view;
  }
  document.querySelectorAll<HTMLAnchorElement>('[data-nav]').forEach((a) => {
    if (a.dataset.nav === view) a.setAttribute('aria-current', 'page');
    else a.removeAttribute('aria-current');
  });
  document.title =
    view === 'melden'
      ? 'Fehlenden Defi melden – Defi-Lücke'
      : view === 'methodik'
        ? 'Methodik und Grenzen – Defi-Lücke'
        : 'Defi-Lücke – AED-Versorgung auf der Karte';
  if (view === 'map') setTimeout(() => map.invalidateSize(), 0);
  if (!initial) {
    window.scrollTo(0, 0);
    $('main').focus({ preventScroll: true });
  }
}

async function init(): Promise<void> {
  bindControls();
  renderLegend();
  window.addEventListener('hashchange', () => route());
  route(true);

  let regions: RegionIndexEntry[] = [];
  try {
    regions = await loadRegions();
  } catch {
    showError('Die Regionsliste (regions.json) fehlt.');
    return;
  }
  if (!regions.length) {
    showError('Die Regionsliste ist leer.');
    return;
  }
  const sel = $<HTMLSelectElement>('sel-region');
  sel.replaceChildren(...regions.map((r, i) => option(r.key, r.name ?? r.key, i === 0)));
  $('region-row').hidden = regions.length < 2;
  sel.addEventListener('change', () => void openRegion(sel.value));
  await openRegion(regions[0].key);
}

void init();
