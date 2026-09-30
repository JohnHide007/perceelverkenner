import type { Geometry } from "geojson";

// Vorm van het antwoord van de backend (POST /verrijk)

export interface Pand {
  identificatie: string;
  overlap_m2: number;
  aandeel_op_perceel_pct: number;
  bouwjaar: number | null;
  status: string | null;
  gebruiksdoel: string[];
  aantal_verblijfsobjecten: number | null;
  footprint_m2: number;
  geometry: Geometry;
}

export interface GenegeerdPand {
  identificatie: string;
  overlap_m2: number;
  aandeel_op_perceel_pct: number;
  reden: string;
}

export interface Verrijking {
  perceel: {
    aanduiding: string;
    oppervlakte_kadaster_m2: number | null;
    oppervlakte_berekend_m2: number;
    geometry: Geometry;
  };
  bebouwing: {
    aantal_panden: number;
    bebouwd_m2: number;
    onbebouwd_m2: number;
    bebouwingsgraad_pct: number | null;
    oudste_bouwjaar: number | null;
    nieuwste_bouwjaar: number | null;
    gebruiksdoelen: string[];
  };
  kandidaten_in_bbox: number;
  panden: Pand[];
  genegeerd: GenegeerdPand[];
  waarschuwingen?: string[]; // bv. als de BAG het maximum aantal panden teruggaf
  bronnen: string[];
}
