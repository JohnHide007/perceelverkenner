// BFF-route: de browser praat alleen met deze route, nooit direct met de backend.
// Stap 1: vraag PDOK welk perceel onder het klikpunt ligt (GetFeatureInfo).
// Stap 2: stuur dat perceel naar onze eigen backend voor de verrijking.

const KADASTER_WMS = "https://service.pdok.nl/kadaster/kadastralekaart/wms/v5_0";
const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

const AARDSTRAAL = 6378137; // meter; Web Mercator rekent met een bol
const HALVE_BREEDTE = 5; // grootte van het vierkantje rond het klikpunt (Web Mercator-meters)

/** Zet lengte/breedtegraad om naar Web Mercator (EPSG:3857), het stelsel van de kaart. */
function naarWebMercator(lat: number, lng: number) {
  const x = (AARDSTRAAL * lng * Math.PI) / 180;
  const y = AARDSTRAAL * Math.log(Math.tan(Math.PI / 4 + (lat * Math.PI) / 360));
  return { x, y };
}

function fout(bericht: string, status: number) {
  return Response.json({ fout: bericht }, { status });
}

/** Haalt de onderliggende oorzaak uit een netwerkfout, bv. ECONNREFUSED. */
function oorzaak(e: unknown): string {
  const err = e as { message?: string; cause?: { code?: string } };
  return err.cause?.code ?? err.message ?? "onbekende fout";
}

export async function POST(request: Request) {
  let lat: unknown;
  let lng: unknown;
  try {
    ({ lat, lng } = await request.json());
  } catch {
    return fout("Ongeldige JSON", 400);
  }
  if (typeof lat !== "number" || typeof lng !== "number") {
    return fout("lat en lng (getallen) zijn verplicht", 400);
  }

  // Stap 1: welk perceel ligt hier?
  const { x, y } = naarWebMercator(lat, lng);
  const params = new URLSearchParams({
    SERVICE: "WMS",
    VERSION: "1.3.0",
    REQUEST: "GetFeatureInfo",
    LAYERS: "Perceelvlak",
    QUERY_LAYERS: "Perceelvlak",
    STYLES: "",
    CRS: "EPSG:3857",
    BBOX: [x - HALVE_BREEDTE, y - HALVE_BREEDTE, x + HALVE_BREEDTE, y + HALVE_BREEDTE].join(","),
    WIDTH: "101",
    HEIGHT: "101",
    I: "50",
    J: "50",
    INFO_FORMAT: "application/json",
  });

  let pdok: { features?: unknown[]; crs?: { properties?: { name?: string } } };
  try {
    const res = await fetch(`${KADASTER_WMS}?${params}`, { signal: AbortSignal.timeout(10_000) });
    if (!res.ok) return fout(`PDOK gaf status ${res.status}`, 502);
    pdok = await res.json();
  } catch (e) {
    return fout(`PDOK niet bereikbaar (${oorzaak(e)})`, 502);
  }

  const perceel = pdok.features?.[0];
  if (!perceel) return fout("Geen perceel op deze plek (water of weg zonder perceel?)", 404);
  const crs = pdok.crs?.properties?.name ?? "EPSG:3857";

  // Stap 2: laat de backend het verhaal vertellen
  let res: Response;
  try {
    res = await fetch(`${BACKEND_URL}/verrijk`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ perceel, crs }),
      signal: AbortSignal.timeout(20_000),
    });
  } catch (e) {
    return fout(`Backend niet bereikbaar op ${BACKEND_URL} (${oorzaak(e)})`, 502);
  }

  const body = await res.json().catch(() => null);
  if (!res.ok) return fout(body?.detail ?? `Backend gaf status ${res.status}`, 502);
  return Response.json(body);
}
