"use client";

import { useState } from "react";
import type { Verrijking } from "@/lib/types";
import { bouwjaarKleur, dakType, doelKort, euro, getal, m2, pct } from "@/lib/format";
import { Chip, Kengetal, Regel, Sectie, SignaalKaart, Skelet, Statusstip } from "@/components/ui";

interface Props {
  resultaat: Verrijking | null;
  laden: boolean;
  fout: string | null;
  onVoorbeeld: (lat: number, lng: number) => void;
}

export const VOORBEELDEN = [
  { naam: "Nieuwe Kerk, Amsterdam", sub: "rijksmonument uit 1380", lat: 52.3737, lng: 4.8916 },
  { naam: "Coolsingel 40, Rotterdam", sub: "stadhuis, kantoorfunctie", lat: 51.92272, lng: 4.4792 },
  { naam: "Domplein, Utrecht", sub: "binnenstad", lat: 52.0906, lng: 5.1225 },
];

export default function Zijpaneel({ resultaat, laden, fout, onVoorbeeld }: Props) {
  return (
    <aside className="flex h-full flex-col overflow-y-auto bg-env-50 md:border-l md:border-env-200">
      <div className="flex flex-col gap-3 p-4">
        {laden && <Skelet />}

        {fout && !laden && (
          <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-900">
            <div className="font-semibold">Dat lukte niet</div>
            <div className="mt-1">{fout}</div>
          </div>
        )}

        {!laden && !fout && !resultaat && <Leeg onVoorbeeld={onVoorbeeld} />}

        {resultaat && !laden && <Resultaat r={resultaat} />}
      </div>
    </aside>
  );
}

function Leeg({ onVoorbeeld }: { onVoorbeeld: (lat: number, lng: number) => void }) {
  return (
    <div className="flex flex-col gap-4 pt-2">
      <div>
        <h2 className="text-lg font-semibold text-env-900">Klik een perceel aan</h2>
        <p className="mt-1 text-sm leading-relaxed text-env-900/65">
          Zoek een adres of klik op de kaart. Je krijgt per perceel de panden, adressen, hoogte, erfgoedstatus en
          buurtcijfers, allemaal uit open data en met bronvermelding.
        </p>
      </div>
      <div>
        <div className="mb-2 text-[11px] font-medium uppercase tracking-wide text-env-900/50">Probeer eens</div>
        <div className="flex flex-col gap-2">
          {VOORBEELDEN.map((v) => (
            <button
              key={v.naam}
              type="button"
              onClick={() => onVoorbeeld(v.lat, v.lng)}
              className="flex items-center justify-between rounded-xl border border-env-200/70 bg-white px-4 py-3 text-left transition hover:border-env-700 hover:shadow-sm"
            >
              <span>
                <span className="block text-sm font-medium text-env-900">{v.naam}</span>
                <span className="block text-xs text-env-900/55">{v.sub}</span>
              </span>
              <span className="text-env-700">→</span>
            </button>
          ))}
        </div>
      </div>
      <div className="grid grid-cols-2 gap-2 text-xs text-env-900/60">
        {["Kadaster", "BAG", "3D BAG", "RCE", "CBS"].map((b) => (
          <span key={b} className="flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-env-700" /> {b}
          </span>
        ))}
        <span className="flex items-center gap-1.5">
          <span className="h-1.5 w-1.5 rounded-full bg-env-700" /> PDOK Locatieserver
        </span>
      </div>
    </div>
  );
}

function Resultaat({ r }: { r: Verrijking }) {
  const b = r.bebouwing;
  const bouwjaar =
    b.oudste_bouwjaar == null
      ? "–"
      : b.oudste_bouwjaar === b.nieuwste_bouwjaar
        ? `${b.oudste_bouwjaar}`
        : `${b.oudste_bouwjaar}–${b.nieuwste_bouwjaar}`;
  const mislukt = r.bronnen.filter((x) => x.status !== "ok");

  return (
    <>
      {/* Kop */}
      <header className="px-1 pt-1">
        <div className="text-[11px] font-medium uppercase tracking-wide text-env-900/50">Kadastraal perceel</div>
        <h2 className="text-2xl font-bold leading-tight text-env-900">{r.perceel.aanduiding || "Onbekend perceel"}</h2>
        <p className="mt-1 text-sm text-env-900/65">
          {[r.buurt?.buurt, r.buurt?.gemeente ?? r.adressen?.woonplaats].filter(Boolean).join(" · ") ||
            r.adressen?.postcodes.join(", ") ||
            "Locatie zonder buurtgegevens"}
          {r.erfgoed?.beschermd && (
            <span className="ml-2">
              <Chip kleur="amber">beschermd erfgoed</Chip>
            </span>
          )}
        </p>
      </header>

      {r.waarschuwingen?.map((w) => (
        <p key={w} className="rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-[13px] text-amber-900">
          {w}
        </p>
      ))}
      {mislukt.length > 0 && (
        <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-[13px] text-red-900">
          Niet alle bronnen reageerden: {mislukt.map((x) => x.naam).join(", ")}. Zie Verantwoording.
        </p>
      )}

      {/* Kengetallen */}
      <div className="grid grid-cols-2 gap-2">
        <Kengetal
          label="Perceel"
          waarde={m2(r.perceel.oppervlakte_berekend_m2)}
          toelichting={`Kadaster: ${m2(r.perceel.oppervlakte_kadaster_m2)}`}
        />
        <Kengetal label="Bebouwd" waarde={pct(b.bebouwingsgraad_pct)} toelichting={`${m2(b.bebouwd_m2)} · ${m2(b.onbebouwd_m2)} vrij`} />
        <Kengetal label="Panden" waarde={b.aantal_panden} toelichting={`bouwjaar ${bouwjaar}`} />
        <Kengetal
          label="Adressen"
          waarde={r.adressen ? r.adressen.aantal : "–"}
          toelichting={r.adressen ? `${m2(r.adressen.gebruiksoppervlak_m2)} gebruiksoppervlak` : "bron niet beschikbaar"}
        />
        <Kengetal
          label="Hoogste pand"
          waarde={r.hoogte?.hoogste_pand_m != null ? `${getal(r.hoogte.hoogste_pand_m, 1)} m` : "–"}
          toelichting={r.hoogte?.meeste_bouwlagen != null ? `tot ${r.hoogte.meeste_bouwlagen} bouwlagen` : "geen 3D-gegevens"}
        />
        <Kengetal
          label="WOZ buurt"
          waarde={euro(r.buurt?.woz_gemiddeld_eur)}
          toelichting={r.buurt ? `gemiddeld, CBS ${r.buurt.jaar}` : "geen buurtcijfers"}
        />
      </div>

      {/* Signalen */}
      {r.signalen.length > 0 && (
        <div className="flex flex-col gap-1.5">
          {r.signalen.map((s) => (
            <SignaalKaart key={s.tekst} {...s} />
          ))}
        </div>
      )}

      {/* Panden */}
      <Sectie titel="Panden op dit perceel" bron="BAG + 3D BAG" badge={`${r.panden.length}`}>
        {r.panden.length === 0 ? (
          <p className="text-sm text-env-900/65">Geen BAG-panden: dit perceel is onbebouwd.</p>
        ) : (
          <ul className="divide-y divide-env-200/60">
            {r.panden.map((p) => (
              <li key={p.identificatie} className="flex gap-3 py-2.5">
                <span className="mt-1 h-3 w-3 shrink-0 rounded-sm" style={{ background: bouwjaarKleur(p.bouwjaar) }} />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-baseline gap-x-2 text-sm">
                    <span className="font-semibold text-env-900">{p.bouwjaar ?? "Bouwjaar onbekend"}</span>
                    <span className="text-env-900/70">{p.gebruiksdoel.map(doelKort).join(", ") || "geen gebruiksdoel"}</span>
                  </div>
                  <div className="text-xs text-env-900/55">
                    {m2(p.overlap_m2)} op perceel ({pct(p.aandeel_op_perceel_pct)} van het pand)
                    {p.aantal_verblijfsobjecten ? ` · ${p.aantal_verblijfsobjecten} verblijfsobject(en)` : ""}
                  </div>
                  {p.hoogte && (
                    <div className="text-xs text-env-900/55">
                      {p.hoogte.hoogte_m != null ? `${getal(p.hoogte.hoogte_m, 1)} m hoog` : "hoogte onbekend"}
                      {p.hoogte.bouwlagen != null ? ` · ${p.hoogte.bouwlagen} bouwlagen` : ""}
                      {` · ${dakType(p.hoogte.dak_type)}`}
                    </div>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Sectie>

      {/* Adressen */}
      {r.adressen && (
        <Sectie titel="Adressen en gebruik" bron="BAG" badge={`${r.adressen.aantal}`} open={r.adressen.aantal > 0}>
          {r.adressen.aantal === 0 ? (
            <p className="text-sm text-env-900/65">Geen verblijfsobjecten op deze panden.</p>
          ) : (
            <AdressenBlok a={r.adressen} />
          )}
        </Sectie>
      )}

      {/* Dak en volume */}
      {r.hoogte && r.hoogte.gevonden > 0 && (
        <Sectie titel="Dak en volume" bron="3D BAG" badge={`${r.hoogte.gevonden} van ${r.hoogte.opgevraagd} panden`} open={false}>
          <Regel label="Plat dak" waarde={m2(r.hoogte.dak_plat_m2)} />
          <Regel label="Schuin dak" waarde={m2(r.hoogte.dak_schuin_m2)} />
          <Regel label="Volume (LoD2.2)" waarde={`${getal(r.hoogte.volume_m3)} m³`} />
          <Regel label="Hoogste pand" waarde={r.hoogte.hoogste_pand_m != null ? `${getal(r.hoogte.hoogste_pand_m, 1)} m` : "–"} />
          <p className="mt-2 text-[11px] leading-snug text-env-900/50">
            Hoogte = 70e percentiel van het dak boven het maaiveld, gemeten met het AHN. Bouwlagen zijn een schatting van de 3D BAG.
          </p>
        </Sectie>
      )}

      {/* Erfgoed */}
      {r.erfgoed && (
        <Sectie
          titel="Erfgoed"
          bron="RCE"
          badge={r.erfgoed.beschermd ? `${r.erfgoed.rijksmonumenten.length} monument(en)` : "geen"}
          open={r.erfgoed.beschermd}
        >
          {!r.erfgoed.beschermd ? (
            <p className="text-sm text-env-900/65">Geen rijksmonument en niet in een beschermd gezicht.</p>
          ) : (
            <div className="flex flex-col gap-2 text-sm">
              {r.erfgoed.rijksmonumenten.map((mnt) => (
                <div key={mnt.nummer ?? mnt.url} className="flex items-center justify-between">
                  <span className="text-env-900">
                    Rijksmonument <span className="font-medium">{mnt.nummer ?? "?"}</span>
                    {mnt.sinds && <span className="text-env-900/55"> · sinds {mnt.sinds}</span>}
                  </span>
                  {mnt.url && (
                    <a href={mnt.url} target="_blank" rel="noreferrer" className="text-xs font-medium text-env-700 underline">
                      register ↗
                    </a>
                  )}
                </div>
              ))}
              {r.erfgoed.gebieden.map((g) => (
                <div key={`${g.soort}-${g.naam}`} className="text-env-900">
                  <span className="capitalize">{g.soort}</span>
                  {g.naam && <span className="text-env-900/70"> · {g.naam}</span>}
                  {g.sinds && <span className="text-env-900/55"> · sinds {g.sinds}</span>}
                </div>
              ))}
            </div>
          )}
        </Sectie>
      )}

      {/* Buurt */}
      {r.buurt && (
        <Sectie titel={`Buurt: ${r.buurt.buurt ?? "onbekend"}`} bron={`CBS ${r.buurt.jaar}`} badge={r.buurt.stedelijkheid ?? ""} open={false}>
          <div className="grid grid-cols-2 gap-x-4">
            <Regel label="Inwoners" waarde={getal(r.buurt.inwoners)} />
            <Regel label="Huishoudens" waarde={getal(r.buurt.huishoudens)} />
            <Regel label="Woningen" waarde={getal(r.buurt.woningen)} />
            <Regel label="Gem. WOZ" waarde={euro(r.buurt.woz_gemiddeld_eur)} />
            <Regel label="Koop / huur" waarde={`${pct(r.buurt.koop_pct)} / ${pct(r.buurt.huur_pct)}`} />
            <Regel label="Corporatiehuur" waarde={pct(r.buurt.corporatie_pct)} />
            <Regel label="Meergezins" waarde={pct(r.buurt.meergezins_pct)} />
            <Regel label="Leegstand" waarde={pct(r.buurt.leegstand_pct)} />
            <Regel label="Inwoners / km²" waarde={getal(r.buurt.inwoners_per_km2)} />
            <Regel label="Bedrijven" waarde={getal(r.buurt.bedrijfsvestigingen)} />
            <Regel label="Gas / woning" waarde={r.buurt.gasverbruik_m3 != null ? `${getal(r.buurt.gasverbruik_m3)} m³` : "–"} />
            <Regel label="Stroom / woning" waarde={r.buurt.elektriciteitsverbruik_kwh != null ? `${getal(r.buurt.elektriciteitsverbruik_kwh)} kWh` : "–"} />
            <Regel label="Supermarkt" waarde={r.buurt.afstand_supermarkt_km != null ? `${getal(r.buurt.afstand_supermarkt_km, 1)} km` : "–"} />
            <Regel label="Huisarts" waarde={r.buurt.afstand_huisarts_km != null ? `${getal(r.buurt.afstand_huisarts_km, 1)} km` : "–"} />
          </div>
          <p className="mt-2 text-[11px] leading-snug text-env-900/50">
            Buurt {r.buurt.buurtcode}, gemeente {r.buurt.gemeente}. Een streepje betekent dat het CBS de waarde afschermt.
          </p>
        </Sectie>
      )}

      {/* Verantwoording */}
      <Sectie titel="Verantwoording" badge={`${r.bronnen.length} bronnen`} open={false}>
        <ul className="divide-y divide-env-200/60 text-[13px]">
          {r.bronnen.map((bron) => (
            <li key={bron.naam} className="flex items-center gap-2 py-1.5">
              <Statusstip ok={bron.status === "ok"} />
              <a href={bron.bron} target="_blank" rel="noreferrer" className="min-w-0 flex-1 truncate text-env-900 hover:underline">
                {bron.naam}
              </a>
              <span className="shrink-0 text-xs text-env-900/50">
                {bron.status === "ok" ? (bron.duur_ms != null ? `${bron.duur_ms} ms` : "") : bron.fout}
              </span>
            </li>
          ))}
        </ul>
        <details className="mt-3 text-xs text-env-900/65">
          <summary className="cursor-pointer">
            Buren-filter: {r.panden.length} van {r.kandidaten_in_bbox} kandidaten meegeteld, {r.genegeerd.length} genegeerd
          </summary>
          <ul className="mt-2 space-y-1">
            {r.genegeerd.map((p) => (
              <li key={p.identificatie}>
                {p.identificatie}: {getal(p.overlap_m2, 1)} m² ({getal(p.aandeel_op_perceel_pct, 1)}%) – {p.reden}
              </li>
            ))}
          </ul>
        </details>
        <p className="mt-3 text-[11px] leading-snug text-env-900/50">
          Oppervlaktes zijn berekend in het Rijksdriehoekstelsel op de kaartgeometrie; de kadastrale grootte is de juridisch
          vastgestelde waarde.
        </p>
      </Sectie>
    </>
  );
}

function AdressenBlok({ a }: { a: NonNullable<Verrijking["adressen"]> }) {
  const [alles, setAlles] = useState(false);
  const MAX = 6;
  const items = alles ? a.items : a.items.slice(0, MAX);
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap gap-1.5">
        {a.per_gebruiksdoel.map((d) => (
          <Chip key={d.gebruiksdoel} kleur="grijs">
            {doelKort(d.gebruiksdoel)} · {d.aantal}× · {m2(d.oppervlakte_m2)}
          </Chip>
        ))}
      </div>
      <ul className="divide-y divide-env-200/60">
        {items.map((adres) => (
          <li key={adres.identificatie} className="flex items-baseline justify-between gap-3 py-1.5 text-[13px]">
            <span className="min-w-0 truncate text-env-900">
              {adres.adres}
              <span className="text-env-900/50"> {adres.postcode}</span>
            </span>
            <span className="shrink-0 text-env-900/65">
              {adres.gebruiksdoel.map(doelKort).join(", ")} · {m2(adres.oppervlakte_m2)}
            </span>
          </li>
        ))}
      </ul>
      {a.items.length > MAX && (
        <button type="button" onClick={() => setAlles((v) => !v)} className="self-start text-xs font-medium text-env-700 underline">
          {alles ? "Minder tonen" : `Alle ${a.items.length}${a.afgekapt ? "+" : ""} adressen tonen`}
        </button>
      )}
    </div>
  );
}
