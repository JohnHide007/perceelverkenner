import type { Verrijking } from "@/lib/types";

interface Props {
  resultaat: Verrijking | null;
  laden: boolean;
  fout: string | null;
}

const getal = (n: number | null | undefined, decimalen = 0) =>
  n == null ? "–" : n.toLocaleString("nl-NL", { maximumFractionDigits: decimalen });

function Kengetal({ label, waarde, toelichting }: { label: string; waarde: string; toelichting?: string }) {
  return (
    <div className="rounded-lg bg-[#BFD3C6]/40 p-3">
      <div className="text-xs uppercase tracking-wide text-[#0B2A26]/70">{label}</div>
      <div className="text-lg font-semibold">{waarde}</div>
      {toelichting && <div className="text-xs text-[#0B2A26]/70">{toelichting}</div>}
    </div>
  );
}

export default function Zijpaneel({ resultaat, laden, fout }: Props) {
  return (
    <aside className="flex h-full flex-col gap-4 overflow-y-auto border-l border-[#BFD3C6] p-5">
      <header>
        <h1 className="text-xl font-bold">Perceelverkenner</h1>
        <p className="text-sm text-[#0B2A26]/70">
          Klik op een perceel. Zoom ver genoeg in om de kadastrale grenzen te zien.
        </p>
      </header>

      {laden && <p className="text-sm">Perceel ophalen…</p>}

      {fout && (
        <p className="rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-800">{fout}</p>
      )}

      {!laden && !fout && !resultaat && (
        <p className="text-sm text-[#0B2A26]/70">Nog geen perceel geselecteerd.</p>
      )}

      {resultaat && !laden && (
        <>
          {resultaat.waarschuwingen?.map((w) => (
            <p key={w} className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
              {w}
            </p>
          ))}

          <section>
            <h2 className="text-lg font-semibold">{resultaat.perceel.aanduiding}</h2>
            <div className="mt-3 grid grid-cols-2 gap-2">
              <Kengetal
                label="Oppervlakte"
                waarde={`${getal(resultaat.perceel.oppervlakte_berekend_m2)} m²`}
                toelichting={`Kadaster: ${getal(resultaat.perceel.oppervlakte_kadaster_m2)} m²`}
              />
              <Kengetal
                label="Bebouwingsgraad"
                waarde={`${getal(resultaat.bebouwing.bebouwingsgraad_pct, 1)}%`}
                toelichting={`${getal(resultaat.bebouwing.bebouwd_m2)} m² bebouwd`}
              />
              <Kengetal label="Onbebouwd" waarde={`${getal(resultaat.bebouwing.onbebouwd_m2)} m²`} />
              <Kengetal
                label="Bouwjaar"
                waarde={
                  resultaat.bebouwing.oudste_bouwjaar === resultaat.bebouwing.nieuwste_bouwjaar
                    ? `${resultaat.bebouwing.oudste_bouwjaar ?? "–"}`
                    : `${resultaat.bebouwing.oudste_bouwjaar}–${resultaat.bebouwing.nieuwste_bouwjaar}`
                }
                toelichting={`${resultaat.bebouwing.aantal_panden} pand(en)`}
              />
            </div>
          </section>

          {resultaat.bebouwing.gebruiksdoelen.length > 0 && (
            <section>
              <h3 className="mb-2 text-sm font-semibold">Gebruiksdoelen</h3>
              <div className="flex flex-wrap gap-1">
                {resultaat.bebouwing.gebruiksdoelen.map((doel) => (
                  <span key={doel} className="rounded-full bg-[#5E8C73] px-2 py-0.5 text-xs text-white">
                    {doel}
                  </span>
                ))}
              </div>
            </section>
          )}

          <section>
            <h3 className="mb-2 text-sm font-semibold">Panden op dit perceel</h3>
            {resultaat.panden.length === 0 ? (
              <p className="text-sm text-[#0B2A26]/70">Geen BAG-panden: dit perceel is onbebouwd.</p>
            ) : (
              <ul className="divide-y divide-[#BFD3C6] text-sm">
                {resultaat.panden.map((pand) => (
                  <li key={pand.identificatie} className="py-2">
                    <div className="font-medium">
                      {pand.bouwjaar ?? "Bouwjaar onbekend"} · {pand.gebruiksdoel.join(", ") || "geen gebruiksdoel"}
                    </div>
                    <div className="text-xs text-[#0B2A26]/70">
                      {getal(pand.overlap_m2)} m² op perceel ({getal(pand.aandeel_op_perceel_pct)}% van het pand)
                      · {pand.status}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="text-xs text-[#0B2A26]/70">
            <details>
              <summary className="cursor-pointer">
                {resultaat.panden.length} van {resultaat.kandidaten_in_bbox} kandidaten meegeteld,{" "}
                {resultaat.genegeerd.length} genegeerd
              </summary>
              <ul className="mt-2 space-y-1">
                {resultaat.genegeerd.map((p) => (
                  <li key={p.identificatie}>
                    {p.identificatie}: {getal(p.overlap_m2, 1)} m² ({getal(p.aandeel_op_perceel_pct, 1)}%) –{" "}
                    {p.reden}
                  </li>
                ))}
              </ul>
            </details>
            <p className="mt-3">Bronnen: Kadastrale kaart en BAG via PDOK.</p>
          </section>
        </>
      )}
    </aside>
  );
}
