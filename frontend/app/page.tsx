"use client";

import dynamic from "next/dynamic";
import { useCallback, useRef, useState } from "react";
import Zijpaneel from "@/components/Zijpaneel";
import type { Verrijking } from "@/lib/types";

// Leaflet heeft `window` nodig, dus de kaart alleen in de browser renderen (niet op de server)
const Kaart = dynamic(() => import("@/components/Kaart"), {
  ssr: false,
  loading: () => <div className="flex h-full items-center justify-center text-sm">Kaart laden…</div>,
});

export default function Home() {
  const [resultaat, setResultaat] = useState<Verrijking | null>(null);
  const [laden, setLaden] = useState(false);
  const [fout, setFout] = useState<string | null>(null);
  const laatsteKlik = useRef(0);

  const bijKlik = useCallback(async (lat: number, lng: number) => {
    const klik = ++laatsteKlik.current; // om een trager, ouder antwoord te negeren
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

  return (
    <main className="flex h-screen flex-col md:flex-row">
      <div className="h-[55vh] flex-1 md:h-full">
        <Kaart onKlik={bijKlik} resultaat={resultaat} />
      </div>
      <div className="md:h-full md:w-[380px]">
        <Zijpaneel resultaat={resultaat} laden={laden} fout={fout} />
      </div>
    </main>
  );
}
