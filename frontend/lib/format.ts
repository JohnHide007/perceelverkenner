// Kleine opmaakhulpjes voor het zijpaneel en de kaart. Alles in Nederlandse notatie.

export const getal = (n: number | null | undefined, decimalen = 0): string =>
  n == null ? "–" : n.toLocaleString("nl-NL", { maximumFractionDigits: decimalen });

export const m2 = (n: number | null | undefined, decimalen = 0): string =>
  n == null ? "–" : `${getal(n, decimalen)} m²`;

export const euro = (n: number | null | undefined): string =>
  n == null ? "–" : `€ ${getal(n)}`;

export const pct = (n: number | null | undefined, decimalen = 0): string =>
  n == null ? "–" : `${getal(n, decimalen)}%`;

/** "woonfunctie" -> "woon", "bijeenkomstfunctie" -> "bijeenkomst" */
export const doelKort = (doel: string): string => doel.replace(/functie$/, "");

// Bouwjaarklassen: de kleur van een pand op de kaart en in de legenda
export const BOUWJAARKLASSEN: { label: string; tot: number; kleur: string }[] = [
  { label: "vóór 1900", tot: 1900, kleur: "#0B2A26" },
  { label: "1900–1944", tot: 1945, kleur: "#2F5D4F" },
  { label: "1945–1979", tot: 1980, kleur: "#5E8C73" },
  { label: "1980–1999", tot: 2000, kleur: "#9BBFA9" },
  { label: "2000 en later", tot: Infinity, kleur: "#D9A441" },
];
export const KLEUR_ONBEKEND = "#8A9491";

export const bouwjaarKleur = (bouwjaar: number | null | undefined): string => {
  if (bouwjaar == null) return KLEUR_ONBEKEND;
  return BOUWJAARKLASSEN.find((k) => bouwjaar < k.tot)?.kleur ?? KLEUR_ONBEKEND;
};

export const dakType = (type: string | null | undefined): string =>
  ({ horizontal: "plat dak", slanted: "schuin dak", multiple: "samengesteld dak", no_points: "onbekend" } as Record<string, string>)[
    type ?? ""
  ] ?? (type ?? "onbekend");
