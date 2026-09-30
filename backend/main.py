"""Perceelverkenner backend: verrijkt kadastrale percelen met open data.

Opbouw van een verrijking:
1. BAG-panden op het perceel (de kern; als dit faalt is het antwoord een 502)
2. Extra bronnen als losse modules in `bronnen/` (adressen, 3D-hoogte, erfgoed, buurtcijfers).
   Ze draaien tegelijk en mogen los van elkaar falen: een haperende bron levert dan
   status "fout" in `bronnen` op, de rest van het antwoord blijft staan.
3. `signalen.py` vat de bronnen samen in korte, herleidbare conclusies.
"""

import asyncio
import xml.etree.ElementTree as ET

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from pyproj.exceptions import CRSError
from shapely.geometry import mapping, shape

import signalen
from bronnen import adressen, buurt, erfgoed, hoogte, veilig
from verrijking import RD, WGS84, analyseer, herprojecteer, maak_geldig

KADASTER_WMS = "https://service.pdok.nl/kadaster/kadastralekaart/wms/v5_0"
BAG_WFS = "https://service.pdok.nl/lv/bag/wfs/v2_0"
TIMEOUT = 15  # seconden
BAG_MAX = 1000  # maximum aantal panden dat we per perceel bij de BAG WFS opvragen

app = FastAPI(title="Perceelverkenner API", version="0.3.0")


class VerrijkVerzoek(BaseModel):
    """Wat de frontend naar /verrijk stuurt."""

    perceel: dict = Field(description="GeoJSON-feature van de laag Perceelvlak (uit GetFeatureInfo)")
    crs: str = Field(default=RD, description="Stelsel van de geometrie, bv. EPSG:28992 of EPSG:3857")


def _local(tag: str) -> str:
    """'{http://www.opengis.net/wms}Layer' -> 'Layer' (namespace eraf)."""
    return tag.rsplit("}", 1)[-1]


def _child_text(element: ET.Element, name: str) -> str | None:
    """Tekst van het directe kind-element met deze naam, of None."""
    for child in element:
        if _local(child.tag) == name:
            return child.text
    return None


def _naar_float(waarde) -> float | None:
    try:
        return float(waarde)
    except (TypeError, ValueError):
        return None


@app.get("/health")
def health() -> dict:
    """Leeft de service? Docker Compose gebruikt dit als healthcheck."""
    return {"status": "ok"}


@app.get("/lagen")
async def lagen() -> dict:
    """Haalt GetCapabilities op bij PDOK en geeft de beschikbare lagen terug."""
    params = {"SERVICE": "WMS", "REQUEST": "GetCapabilities"}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.get(KADASTER_WMS, params=params)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"PDOK niet bereikbaar: {exc}")

    try:
        root = ET.fromstring(response.content)
    except ET.ParseError:
        raise HTTPException(status_code=502, detail="PDOK gaf geen geldige XML terug voor GetCapabilities")

    resultaat = []
    for element in root.iter():
        if _local(element.tag) != "Layer":
            continue
        naam = _child_text(element, "Name")
        if naam is None:  # groepslagen zonder naam kun je niet opvragen
            continue
        resultaat.append(
            {
                "naam": naam,
                "titel": _child_text(element, "Title"),
                "opvraagbaar": element.get("queryable") == "1",
            }
        )
    return {"bron": KADASTER_WMS, "aantal": len(resultaat), "lagen": resultaat}


async def _haal_panden(bounds: tuple[float, float, float, float], client: httpx.AsyncClient | None = None) -> list[dict]:
    """Alle BAG-panden die de rechthoek rond het perceel raken (in RD)."""
    minx, miny, maxx, maxy = bounds
    params = {
        "SERVICE": "WFS",
        "VERSION": "2.0.0",
        "REQUEST": "GetFeature",
        "TYPENAMES": "bag:pand",
        "BBOX": f"{minx},{miny},{maxx},{maxy},EPSG:28992",
        "SRSNAME": "EPSG:28992",
        "OUTPUTFORMAT": "application/json",
        "COUNT": str(BAG_MAX),
    }
    try:
        if client is None:
            async with httpx.AsyncClient(timeout=TIMEOUT) as eigen_client:
                response = await eigen_client.get(BAG_WFS, params=params)
        else:
            response = await client.get(BAG_WFS, params=params)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"BAG WFS niet bereikbaar: {exc}")
    try:
        return response.json().get("features", [])
    except ValueError:
        raise HTTPException(status_code=502, detail=f"BAG WFS gaf geen JSON: {response.text[:300]}")


@app.post("/verrijk")
async def verrijk(verzoek: VerrijkVerzoek) -> dict:
    """Ontvangt een perceel en geeft terug wat erop staat, uit meerdere bronnen."""
    try:
        perceel = maak_geldig(shape(verzoek.perceel["geometry"]))
        perceel_rd = herprojecteer(perceel, verzoek.crs, RD)
    except (KeyError, TypeError, ValueError, AttributeError, CRSError) as exc:
        raise HTTPException(status_code=422, detail=f"Ongeldig perceel: {exc}")

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        # Ronde 1: de panden (kern) en de bronnen die alleen het perceel nodig hebben, tegelijk
        panden, erfgoed_blok, buurt_blok = await asyncio.gather(
            _haal_panden(perceel_rd.bounds, client),
            veilig(erfgoed.NAAM, erfgoed.URL, erfgoed.haal(client, perceel_rd)),
            veilig(buurt.NAAM, buurt.URL, buurt.haal(client, perceel_rd)),
            return_exceptions=True,  # eerst alle drie laten afronden, dan pas een fout van de kern doorgeven
        )
        if isinstance(panden, BaseException):
            raise panden  # de HTTPException (502) uit _haal_panden
        analyse = analyseer(perceel_rd, panden)

        # Ronde 2: bronnen die de pand-id's nodig hebben (grootste overlap eerst)
        pand_ids = [p["identificatie"] for p in analyse["panden"]]
        adressen_blok, hoogte_blok = await asyncio.gather(
            veilig(adressen.NAAM, adressen.URL, adressen.haal(client, perceel_rd.bounds, set(pand_ids))),
            veilig(hoogte.NAAM, hoogte.URL, hoogte.haal(client, pand_ids)),
        )

    # 3D-kenmerken bij het bijbehorende pand hangen; de totalen blijven apart in `hoogte`
    hoogte_data = hoogte_blok["data"]
    per_pand = hoogte_data.pop("per_pand", {}) if hoogte_data else {}
    for pand in analyse["panden"]:
        pand["hoogte"] = per_pand.get(pand["identificatie"])

    waarschuwingen = []
    if len(panden) >= BAG_MAX:
        # De WFS kapt stil af bij COUNT: bij een heel groot perceel kunnen panden ontbreken
        waarschuwingen.append(
            f"De BAG gaf het maximum van {BAG_MAX} panden terug; bij dit grote perceel ontbreken er mogelijk panden."
        )
    if hoogte_data and hoogte_data["mislukt"]:
        waarschuwingen.append(
            f"3D BAG: {hoogte_data['mislukt']} pand(en) gaven geen antwoord; hoogte en dak zijn daar onvolledig."
        )
    if hoogte_data and hoogte_data["overgeslagen"]:
        waarschuwingen.append(
            f"3D-kenmerken alleen opgehaald voor de {hoogte_data['opgevraagd']} grootste panden "
            f"({hoogte_data['overgeslagen']} overgeslagen)."
        )

    props = verzoek.perceel.get("properties") or {}
    kern = [
        {"naam": "Kadastrale kaart (Kadaster)", "bron": KADASTER_WMS, "status": "ok", "duur_ms": None, "fout": None},
        {"naam": "Panden (BAG)", "bron": BAG_WFS, "status": "ok", "duur_ms": None, "fout": None},
    ]
    extra = [adressen_blok, hoogte_blok, erfgoed_blok, buurt_blok]

    return {
        "perceel": {
            "aanduiding": " ".join(
                str(props.get(k, "")) for k in ("kadastraleGemeenteWaarde", "sectie", "perceelnummer")
            ).strip(),
            "oppervlakte_kadaster_m2": _naar_float(props.get("kadastraleGrootteWaarde")),
            "oppervlakte_berekend_m2": analyse["perceel_m2"],
            "geometry": mapping(herprojecteer(perceel_rd, RD, WGS84)),
        },
        "bebouwing": analyse["bebouwing"],
        "kandidaten_in_bbox": len(panden),
        "panden": analyse["panden"],
        "genegeerd": analyse["genegeerd"],
        "adressen": adressen_blok["data"],
        "hoogte": hoogte_blok["data"],
        "erfgoed": erfgoed_blok["data"],
        "buurt": buurt_blok["data"],
        "signalen": signalen.bepaal(
            analyse["bebouwing"], adressen_blok["data"], hoogte_blok["data"], erfgoed_blok["data"], buurt_blok["data"]
        ),
        "waarschuwingen": waarschuwingen,
        # Bronvermelding: welke services zijn aangesproken, en of dat lukte
        "bronnen": kern + [{k: v for k, v in blok.items() if k != "data"} for blok in extra],
    }
