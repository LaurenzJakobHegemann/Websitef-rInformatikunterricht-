// Central settings. Change the tile source here only.

/** Basemap tiles. OSM standard tiles: https://operations.osmfoundation.org/policies/tiles/ */
export const TILE_URL = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
export const TILE_ATTRIBUTION =
  '© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap-Mitwirkende</a>';
/** OSM standard tiles exist up to zoom 19. */
export const TILE_MAX_ZOOM = 19;

/** Where the pipeline puts the data (relative to the page, works under any base path). */
export const DATA_BASE = `${import.meta.env.BASE_URL}data/`;

export const OPENSTREETMAP_URL = 'https://www.openstreetmap.org';
export const OPENAEDMAP_URL = 'https://openaedmap.org';
