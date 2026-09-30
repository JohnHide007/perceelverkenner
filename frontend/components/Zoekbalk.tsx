"use client";

import { useEffect, useRef, useState } from "react";
import type { Zoekresultaat } from "@/lib/types";

interface Props {
  onKies: (r: Zoekresultaat) => void;
}

const TYPE_LABEL: Record<string, string> = { adres: "adres", weg: "straat", woonplaats: "plaats", postcode: "postcode" };

export default function Zoekbalk({ onKies }: Props) {
  const [tekst, setTekst] = useState("");
  const [resultaten, setResultaten] = useState<Zoekresultaat[]>([]);
  const [open, setOpen] = useState(false);
  const [actief, setActief] = useState(0);
  const [bezig, setBezig] = useState(false);
  const laatsteVraag = useRef(0);

  // Zoeken met een korte vertraging, zodat niet elke toetsaanslag een verzoek wordt
  useEffect(() => {
    const q = tekst.trim();
    if (q.length < 3) {
      setResultaten([]);
      return;
    }
    const vraag = ++laatsteVraag.current;
    const timer = setTimeout(async () => {
      setBezig(true);
      try {
        const res = await fetch(`/api/zoek?q=${encodeURIComponent(q)}`);
        const data = await res.json();
        if (vraag !== laatsteVraag.current) return; // er is al een nieuwere vraag
        setResultaten(data.resultaten ?? []);
        setActief(0);
        setOpen(true);
      } catch {
        if (vraag === laatsteVraag.current) setResultaten([]);
      } finally {
        if (vraag === laatsteVraag.current) setBezig(false);
      }
    }, 250);
    return () => clearTimeout(timer);
  }, [tekst]);

  const kies = (r: Zoekresultaat) => {
    setTekst(r.naam);
    setOpen(false);
    onKies(r);
  };

  const opToets = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!open || resultaten.length === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActief((a) => (a + 1) % resultaten.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActief((a) => (a - 1 + resultaten.length) % resultaten.length);
    } else if (e.key === "Enter") {
      e.preventDefault();
      kies(resultaten[actief]);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  };

  return (
    <div className="relative w-full">
      <div className="flex items-center gap-2 rounded-xl border border-env-200 bg-white/95 px-3 shadow-md backdrop-blur">
        <svg className="h-4 w-4 shrink-0 text-env-700" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
          <circle cx="9" cy="9" r="6" />
          <path d="m14 14 4 4" strokeLinecap="round" />
        </svg>
        <input
          value={tekst}
          onChange={(e) => setTekst(e.target.value)}
          onFocus={() => resultaten.length > 0 && setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 150)}
          onKeyDown={opToets}
          placeholder="Zoek een adres, straat of plaats…"
          aria-label="Zoek een adres"
          className="h-11 w-full bg-transparent text-sm text-env-900 outline-none placeholder:text-env-900/40"
        />
        {bezig && <span className="h-3 w-3 shrink-0 animate-spin rounded-full border-2 border-env-200 border-t-env-700" />}
      </div>

      {open && resultaten.length > 0 && (
        <ul className="absolute left-0 right-0 top-full z-[1001] mt-1 overflow-hidden rounded-xl border border-env-200 bg-white shadow-lg">
          {resultaten.map((r, i) => (
            <li key={r.id}>
              <button
                type="button"
                onMouseDown={(e) => e.preventDefault()} // zodat onBlur de lijst niet sluit vóór de klik
                onClick={() => kies(r)}
                onMouseEnter={() => setActief(i)}
                className={`flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-sm ${
                  i === actief ? "bg-env-100" : ""
                }`}
              >
                <span className="truncate text-env-900">{r.naam}</span>
                <span className="shrink-0 text-[11px] uppercase tracking-wide text-env-900/50">{TYPE_LABEL[r.type] ?? r.type}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
