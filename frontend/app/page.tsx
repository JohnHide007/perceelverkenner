"use client";

import dynamic from "next/dynamic";
import { useCallback, useRef, useState } from "react";
import Zijpaneel from "@/components/Zijpaneel";
import Zoekbalk from "@/components/Zoekbalk";
import type { Vlucht } from "@/components/Kaart";
import type { Verrijking, Zoekresultaat } from "@/lib/types";

// Leaflet heeft `window` nodig, dus de kaart alleen in de browser renderen (niet op de server)
const Kaart = dynamic(() => import("@/components/Kaart"), {
  ssr: false,
  loading: () => <div className="flex h-full items-center justify-center text-sm text-env-900/60">Kaart laden…</div>,
});

export default function Home() {
  const [resultaat, setResultaat] = useState<Verrijking | null>(null);
  const [laden, setLaden] = useState(false);
  const [fout, setFout] = useState<string | null>(null);
  const [vlucht, setVlucht] = useState<Vlucht | null>(null);
  const [klikpunt, setKlikpunt] = useState<{ lat: number; lng: number } | null>(null);
  const laatsteKlik = useRef(0);

  const bijKlik = useCallback(async (lat: number, lng: number) => {
    const klik = ++laatsteKlik.current; // om een trager, ouder antwoord te negeren
    setKlikpunt({ lat, lng });
    setLaden(true);
    setFout(null);
    try {
      const res = await fetch("/api/perceel", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ lat, lng }),
      });
      const data = await res.json();
      if (klik !== laatsteKlik.current) return;
      if (!res.ok) {
        setResultaat(null);
        setFout(data.fout ?? "Er ging iets mis");
      } else {
        setResultaat(data);
      }
    } catch {
      if (klik === laatsteKlik.current) setFout("De frontend-server is niet bereikbaar");
    } finally {
      if (klik === laatsteKlik.current) setLaden(false);
    }
  }, []);

  // Naar een plek vliegen en, als het een adres is, meteen het perceel eronder ophalen
  const gaNaar = useCallback(
    (lat: number, lng: number, ophalen: boolean, zoom = 18) => {
      setVlucht((v) => ({ lat, lng, zoom, volgnummer: (v?.volgnummer ?? 0) + 1 }));
      if (ophalen) void bijKlik(lat, lng);
    },
    [bijKlik],
  );

  const bijZoekresultaat = useCallback(
    (r: Zoekresultaat) => {
      // Een straat of plaats is geen perceel: alleen heen vliegen, verder uitgezoomd
      const isAdres = r.type === "adres";
      gaNaar(r.lat, r.lng, isAdres, isAdres ? 18 : r.type === "woonplaats" ? 13 : 16);
    },
    [gaNaar],
  );

  return (
    <main className="flex h-screen flex-col md:flex-row">
      <div className="relative h-[52vh] flex-1 md:h-full">
        <Kaart onKlik={bijKlik} resultaat={resultaat} vlucht={vlucht} klikpunt={klikpunt} />

        {/* Zwevende kop: naam + zoekbalk */}
        <div className="pointer-events-none absolute left-4 right-4 top-4 z-[1000] flex flex-col gap-2 md:right-auto md:w-[26rem]">
          <div className="pointer-events-auto flex items-center gap-3 self-start rounded-xl bg-env-900 px-3.5 py-2 text-white shadow-md">
            <Logo />
            <div className="leading-tight">
              <div className="text-sm font-semibold">Perceelverkenner</div>
              <div className="text-[11px] text-white/70">Open data per kadastraal perceel</div>
            </div>
          </div>
          <div className="pointer-events-auto">
            <Zoekbalk onKies={bijZoekresultaat} />
          </div>
        </div>
      </div>

      <div className="h-[48vh] md:h-full md:w-[400px] md:shrink-0">
        <Zijpaneel resultaat={resultaat} laden={laden} fout={fout} onVoorbeeld={(lat, lng) => gaNaar(lat, lng, true)} />
      </div>
    </main>
  );
}

function Logo() {
  return (
    <svg className="h-7 w-7 shrink-0" viewBox="0 0 28 28" fill="none" aria-hidden>
      <path d="M4 10.5 14 5l10 5.5-10 5.5-10-5.5Z" fill="#BFD3C6" />
      <path d="M4 15.5 14 21l10-5.5" stroke="#5E8C73" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M4 20 14 25.5 24 20" stroke="#BFD3C6" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" opacity="0.6" />
    </svg>
  );
}
