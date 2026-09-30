"use client";

import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { Verrijking } from "@/lib/types";
import { BOUWJAARKLASSEN, KLEUR_ONBEKEND, bouwjaarKleur, doelKort, getal } from "@/lib/format";

const ACHTERGRONDEN = {
  grijs: {
    label: "Kaart",
    url: "https://service.pdok.nl/brt/achtergrondkaart/wmts/v2_0/grijs/EPSG:3857/{z}/{x}/{y}.png",
    maxNativeZoom: 19,
  },
  luchtfoto: {
    label: "Luchtfoto",
    url: "https://service.pdok.nl/hwh/luchtfotorgb/wmts/v1_0/Actueel_orthoHR/EPSG:3857/{z}/{x}/{y}.jpeg",
    maxNativeZoom: 19,
  },
} as const;
type Achtergrond = keyof typeof ACHTERGRONDEN;

const KADASTER_WMS = "https://service.pdok.nl/kadaster/kadastralekaart/wms/v5_0";
const START: L.LatLngTuple = [52.3731, 4.8926]; // de Dam in Amsterdam
const MIN_ZOOM_PERCELEN = 16;

export interface Vlucht {
  lat: number;
  lng: number;
  zoom?: number;
  volgnummer: number; // verandert bij elke nieuwe vlucht, ook naar dezelfde plek
}

interface Props {
  onKlik: (lat: number, lng: number) => void;
  resultaat: Verrijking | null;
  vlucht: Vlucht | null;
  klikpunt: { lat: number; lng: number } | null;
}

export default function Kaart({ onKlik, resultaat, vlucht, klikpunt }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const kaartRef = useRef<L.Map | null>(null);
  const markeringRef = useRef<L.LayerGroup | null>(null);
  const klikRef = useRef<L.LayerGroup | null>(null);
  const achtergrondLaagRef = useRef<L.TileLayer | null>(null);
  const [achtergrond, setAchtergrond] = useState<Achtergrond>("grijs");
  const [zoom, setZoom] = useState(18);

  // De nieuwste onKlik bewaren zonder de kaart opnieuw op te bouwen
  const onKlikRef = useRef(onKlik);
  useEffect(() => {
    onKlikRef.current = onKlik;
  }, [onKlik]);

  // Kaart één keer opbouwen
  useEffect(() => {
    if (!containerRef.current || kaartRef.current) return;

    const kaart = L.map(containerRef.current, { zoomControl: false }).setView(START, 18);
    L.control.zoom({ position: "bottomleft" }).addTo(kaart);

    // Achtergrond: BRT-achtergrondkaart (grijs) van PDOK, als tegels in Web Mercator
    achtergrondLaagRef.current = L.tileLayer(ACHTERGRONDEN.grijs.url, {
      maxNativeZoom: ACHTERGRONDEN.grijs.maxNativeZoom,
      maxZoom: 21,
      attribution: 'Kaartgegevens &copy; <a href="https://www.kadaster.nl">Kadaster</a> via PDOK',
    }).addTo(kaart);

    // Kadastrale grenzen: WMS-laag. Leaflet vraagt per tegel een GetMap-plaatje op.
    L.tileLayer
      .wms(KADASTER_WMS, {
        layers: "Perceelvlak",
        format: "image/png",
        transparent: true,
        version: "1.3.0",
        minZoom: MIN_ZOOM_PERCELEN,
        maxZoom: 21,
        opacity: 0.9,
      })
      .addTo(kaart);

    markeringRef.current = L.layerGroup().addTo(kaart);
    klikRef.current = L.layerGroup().addTo(kaart);
    kaart.on("click", (e: L.LeafletMouseEvent) => onKlikRef.current(e.latlng.lat, e.latlng.lng));
    kaart.on("zoomend", () => setZoom(kaart.getZoom()));
    kaartRef.current = kaart;

    return () => {
      kaart.remove();
      kaartRef.current = null;
    };
  }, []);

  // Achtergrond wisselen (kaart / luchtfoto)
  useEffect(() => {
    const laag = achtergrondLaagRef.current;
    if (!laag) return;
    laag.options.maxNativeZoom = ACHTERGRONDEN[achtergrond].maxNativeZoom;
    laag.setUrl(ACHTERGRONDEN[achtergrond].url);
  }, [achtergrond]);

  // Naar een gezocht adres vliegen
  useEffect(() => {
    if (!vlucht || !kaartRef.current) return;
    kaartRef.current.flyTo([vlucht.lat, vlucht.lng], vlucht.zoom ?? 18, { duration: 0.8 });
  }, [vlucht]);

  // Het klikpunt markeren
  useEffect(() => {
    const groep = klikRef.current;
    if (!groep) return;
    groep.clearLayers();
    if (!klikpunt) return;
    L.circleMarker([klikpunt.lat, klikpunt.lng], {
      radius: 5,
      color: "#ffffff",
      weight: 2,
      fillColor: "#0B2A26",
      fillOpacity: 1,
      interactive: false,
    }).addTo(groep);
  }, [klikpunt]);

  // Perceel en panden tekenen zodra er een resultaat is
  useEffect(() => {
    const groep = markeringRef.current;
    if (!groep) return;
    groep.clearLayers();
    if (!resultaat) return;

    L.geoJSON(resultaat.perceel.geometry, {
      style: { color: "#0B2A26", weight: 3, fillColor: "#BFD3C6", fillOpacity: 0.25, dashArray: "6 4" },
      interactive: false,
    }).addTo(groep);

    for (const pand of resultaat.panden) {
      const kleur = bouwjaarKleur(pand.bouwjaar);
      const laag = L.geoJSON(pand.geometry, {
        style: { color: "#ffffff", weight: 1.5, fillColor: kleur, fillOpacity: 0.8 },
      });
      const regels = [
        `<strong>Bouwjaar ${pand.bouwjaar ?? "onbekend"}</strong>`,
        pand.gebruiksdoel.map(doelKort).join(", ") || "geen gebruiksdoel",
        `${getal(pand.overlap_m2)} m² op dit perceel`,
        pand.hoogte?.hoogte_m != null
          ? `${getal(pand.hoogte.hoogte_m, 1)} m hoog${pand.hoogte.bouwlagen ? ` · ${pand.hoogte.bouwlagen} bouwlagen` : ""}`
          : null,
      ].filter(Boolean);
      laag
        .bindTooltip(regels.join("<br/>"), { sticky: true, className: "pv-tooltip", direction: "top", offset: [0, -6] })
        .on("mouseover", () => laag.setStyle({ weight: 3, fillOpacity: 0.95 }))
        .on("mouseout", () => laag.setStyle({ weight: 1.5, fillOpacity: 0.8 }))
        .addTo(groep);
    }
  }, [resultaat]);

  return (
    <div className="relative h-full w-full">
      <div ref={containerRef} className="h-full w-full" />

      {/* Kaart / luchtfoto */}
      <div className="absolute bottom-4 right-4 z-[1000] flex overflow-hidden rounded-lg border border-env-200 bg-white/95 text-xs shadow-md backdrop-blur">
        {(Object.keys(ACHTERGRONDEN) as Achtergrond[]).map((k) => (
          <button
            key={k}
            type="button"
            onClick={() => setAchtergrond(k)}
            className={`px-3 py-1.5 font-medium transition ${
              achtergrond === k ? "bg-env-900 text-white" : "text-env-900 hover:bg-env-100"
            }`}
          >
            {ACHTERGRONDEN[k].label}
          </button>
        ))}
      </div>

      {/* Legenda: bouwjaar */}
      {resultaat && resultaat.panden.length > 0 && (
        <div className="absolute bottom-16 left-4 z-[1000] rounded-lg border border-env-200 bg-white/95 p-2.5 text-[11px] shadow-md backdrop-blur">
          <div className="mb-1 font-semibold uppercase tracking-wide text-env-900/60">Bouwjaar</div>
          {BOUWJAARKLASSEN.map((k) => (
            <div key={k.label} className="flex items-center gap-2 leading-5">
              <span className="inline-block h-3 w-3 rounded-sm" style={{ background: k.kleur }} />
              <span className="text-env-900">{k.label}</span>
            </div>
          ))}
          <div className="flex items-center gap-2 leading-5">
            <span className="inline-block h-3 w-3 rounded-sm" style={{ background: KLEUR_ONBEKEND }} />
            <span className="text-env-900">onbekend</span>
          </div>
        </div>
      )}

      {/* Hint als je te ver uitgezoomd bent om percelen te zien */}
      {zoom < MIN_ZOOM_PERCELEN && (
        <div className="pointer-events-none absolute left-1/2 top-20 z-[1000] -translate-x-1/2 rounded-full bg-env-900/90 px-4 py-1.5 text-xs text-white shadow">
          Zoom verder in om de kadastrale grenzen te zien
        </div>
      )}
    </div>
  );
}
