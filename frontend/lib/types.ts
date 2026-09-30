import type { Geometry } from "geojson";

// Vorm van het antwoord van de backend (POST /verrijk). Houd dit gelijk met backend/main.py.

export interface Hoogte3D {
  hoogte_m: number | null;
  nokhoogte_m: number | null;
  bouwlagen: number | null;
  dak_type: string | null;
  dak_plat_m2: number | null;
  dak_schuin_m2: number | null;
  volume_m3: number | null;
  meting: string;
}

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
  hoogte: Hoogte3D | null; // uit de 3D BAG, null als niet gevonden of bron faalde
}

export interface GenegeerdPand {
  identificatie: string;
  overlap_m2: number;
  aandeel_op_perceel_pct: number;
  reden: string;
}

export interface Adres {
  identificatie: string;
  adres: string;
  postcode: string | null;
  woonplaats: string | null;
  gebruiksdoel: string[];
  oppervlakte_m2: number | null;
  status: string | null;
  pand: string;
}

export interface Adressen {
  aantal: number;
  gebruiksoppervlak_m2: number;
  per_gebruiksdoel: { gebruiksdoel: string; aantal: number; oppervlakte_m2: number }[];
  postcodes: string[];
  woonplaats?: string | null;
  afgekapt?: boolean;
  items: Adres[];
}

export interface HoogteTotaal {
  opgevraagd: number;
  gevonden: number;
  mislukt: number; // panden waarvoor de 3D BAG (ook na een retry) geen antwoord gaf
  overgeslagen: number;
  hoogste_pand_m: number | null;
  meeste_bouwlagen: number | null;
  dak_plat_m2: number;
  dak_schuin_m2: number;
  volume_m3: number;
}

export interface Erfgoed {
  rijksmonumenten: { nummer: string | null; url: string | null; sinds: string | null }[];
  gebieden: { soort: string; naam: string | null; url: string | null; sinds: string | null }[];
  beschermd: boolean;
}

export interface Buurt {
  buurt: string | null;
  buurtcode: string | null;
  wijkcode: string | null;
  gemeente: string | null;
  postcode: string | null;
  stedelijkheid: string | null;
  jaar: number;
  inwoners: number | null;
  huishoudens: number | null;
  huishoudsgrootte: number | null;
  inwoners_per_km2: number | null;
  adressen_per_km2: number | null;
  woningen: number | null;
  woz_gemiddeld_eur: number | null;
  koop_pct: number | null;
  huur_pct: number | null;
  corporatie_pct: number | null;
  eengezins_pct: number | null;
  meergezins_pct: number | null;
  bouwjaar_vanaf_2000_pct: number | null;
  leegstand_pct: number | null;
  bedrijfsvestigingen: number | null;
  gasverbruik_m3: number | null;
  elektriciteitsverbruik_kwh: number | null;
  stadsverwarming_pct: number | null;
  afstand_supermarkt_km: number | null;
  afstand_huisarts_km: number | null;
  oppervlakte_ha: number | null;
}

export type SignaalSoort = "kans" | "let-op" | "info";

export interface Signaal {
  soort: SignaalSoort;
  tekst: string;
  bron: string;
}

export interface Bron {
  naam: string;
  bron: string; // URL van de service
  status: "ok" | "fout";
  duur_ms: number | null;
  fout: string | null;
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
  adressen: Adressen | null;
  hoogte: HoogteTotaal | null;
  erfgoed: Erfgoed | null;
  buurt: Buurt | null;
  signalen: Signaal[];
  waarschuwingen?: string[]; // bv. als de BAG het maximum aantal panden teruggaf
  bronnen: Bron[];
}

// Vorm van het antwoord van /api/zoek (PDOK Locatieserver)
export interface Zoekresultaat {
  id: string;
  type: "adres" | "weg" | "woonplaats" | "postcode" | string;
  naam: string;
  lat: number;
  lng: number;
}
