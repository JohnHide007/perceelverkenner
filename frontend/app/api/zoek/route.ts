// BFF-route voor adres zoeken: de browser vraagt hier, deze route vraagt de PDOK Locatieserver.
// Zo blijft de browser bij één API (de onze) en kunnen we het antwoord klein en voorspelbaar houden.

import type { Zoekresultaat } from "@/lib/types";

const LOCATIESERVER = "https://api.pdok.nl/bzk/locatieserver/search/v3_1/free";

interface Doc {
  id: string;
  type: string;
  weergavenaam: string;
  centroide_ll?: string; // "POINT(4.89 52.37)" (lng lat)
}

export async function GET(request: Request) {
  const q = new URL(request.url).searchParams.get("q")?.trim() ?? "";
  if (q.length < 3) return Response.json({ resultaten: [] });

  const params = new URLSearchParams({
    q,
    rows: "6",
    fl: "id,type,weergavenaam,centroide_ll",
    fq: "type:(adres OR weg OR woonplaats OR postcode)",
  });

  try {
    const res = await fetch(`${LOCATIESERVER}?${params}`, { signal: AbortSignal.timeout(6_000) });
    if (!res.ok) return Response.json({ fout: `Locatieserver gaf status ${res.status}` }, { status: 502 });
    const body = (await res.json()) as { response?: { docs?: Doc[] } };

    const resultaten: Zoekresultaat[] = (body.response?.docs ?? []).flatMap((doc) => {
      const m = doc.centroide_ll?.match(/POINT\(([-\d.]+) ([-\d.]+)\)/);
      if (!m) return [];
      return [{ id: doc.id, type: doc.type, naam: doc.weergavenaam, lng: Number(m[1]), lat: Number(m[2]) }];
    });
    return Response.json({ resultaten });
  } catch {
    return Response.json({ fout: "Locatieserver niet bereikbaar" }, { status: 502 });
  }
}
