"use client";

import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { Verrijking } from "@/lib/types";

const ACHTERGROND =
  "https://service.pdok.nl/brt/achtergrondkaart/wmts/v2_0/grijs/EPSG:3857/{z}/{x}/{y}.png";
const KADASTER_WMS = "https://service.pdok.nl/kadaster/kadastralekaart/wms/v5_0";
const START: L.LatLngTuple = [52.3731, 4.8926]; // de Dam in Amsterdam

interface Props {
  onKlik: (lat: number, lng: number) => void;
  resultaat: Verrijking | null;
}

export default function Kaart({ onKlik, resultaat }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const kaartRef = useRef<L.Map | null>(null);
  const markeringRef = useRef<L.LayerGroup | null>(null);

  // De nieuwste onKlik bewaren zonder de kaart opnieuw op te bouwen
  const onKlikRef = useRef(onKlik);
  useEffect(() => {
    onKlikRef.current = onKlik;
  }, [onKlik]);

  // Kaart één keer opbouwen
  useEffect(() => {
    if (!containerRef.current || kaartRef.current) return;

    const kaart = L.map(containerRef.current).setView(START, 18);

    // Achtergrond: BRT-achtergrondkaart (grijs) van PDOK, als tegels in Web Mercator
    L.tileLayer(ACHTERGROND, {
      maxNativeZoom: 19,
      maxZoom: 21,
      attribution: 'Kaartgegevens &copy; <a href="https://www.kadaster.nl">Kadaster</a>',
    }).addTo(kaart);

    // Kadastrale grenzen: WMS-laag. Leaflet vraagt per tegel een GetMap-plaatje op.
    L.tileLayer
      .wms(KADASTER_WMS, {
        layers: "Perceelvlak",
        format: "image/png",
        transparent: true,
        version: "1.3.0",
        minZoom: 16,
        maxZoom: 21,
      })
      .addTo(kaart);

    markeringRef.current = L.layerGroup().addTo(kaart);
    kaart.on("click", (e: L.LeafletMouseEvent) => onKlikRef.current(e.latlng.lat, e.latlng.lng));
    kaartRef.current = kaart;

    return () => {
      kaart.remove();
      kaartRef.current = null;
    };
  }, []);

  // Perceel en panden tekenen zodra er een resultaat is
  useEffect(() => {
    const groep = markeringRef.current;
    if (!groep) return;
    groep.clearLayers();
    if (!resultaat) return;

    L.geoJSON(resultaat.perceel.geometry, {
      style: { color: "#0B2A26", weight: 3, fillColor: "#BFD3C6", fillOpacity: 0.25 },
    }).addTo(groep);

    for (const pand of resultaat.panden) {
      L.geoJSON(pand.geometry, {
        style: { color: "#0B2A26", weight: 1, fillColor: "#5E8C73", fillOpacity: 0.7 },
      })
        .bindTooltip(`Bouwjaar ${pand.bouwjaar ?? "onbekend"} · ${pand.overlap_m2} m² op dit perceel`)
        .addTo(groep);
    }
  }, [resultaat]);

  return <div ref={containerRef} className="h-full w-full" />;
}
