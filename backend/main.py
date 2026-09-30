"""Perceelverkenner backend: verrijkt kadastrale percelen met open data."""

import xml.etree.ElementTree as ET

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from pyproj.exceptions import CRSError
from shapely.geometry import mapping, shape

from verrijking import RD, WGS84, analyseer, herprojecteer, maak_geldig

KADASTER_WMS = "https://service.pdok.nl/kadaster/kadastralekaart/wms/v5_0"
BAG_WFS = "https://service.pdok.nl/lv/bag/wfs/v2_0"
TIMEOUT = 15  # seconden
BAG_MAX = 1000  # maximum aantal panden dat we per perceel bij de BAG WFS opvragen

app = FastAPI(title="Perceelverkenner API", version="0.2.0")


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
    """Leeft de service? Docker Compose gebruikt dit later als healthcheck."""
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


async def _haal_panden(bounds: tuple[float, float, float, float]) -> list[dict]:
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
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
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
    """Ontvangt een perceel en geeft terug wat erop staat volgens de BAG."""
    try:
        perceel = maak_geldig(shape(verzoek.perceel["geometry"]))
        perceel_rd = herprojecteer(perceel, verzoek.crs, RD)
    except (KeyError, TypeError, ValueError, AttributeError, CRSError) as exc:
        raise HTTPException(status_code=422, detail=f"Ongeldig perceel: {exc}")

    panden = await _haal_panden(perceel_rd.bounds)
    analyse = analyseer(perceel_rd, panden)

    waarschuwingen = []
    if len(panden) >= BAG_MAX:
        # De WFS kapt stil af bij COUNT: bij een heel groot perceel kunnen panden ontbreken
        waarschuwingen.append(
            f"De BAG gaf het maximum van {BAG_MAX} panden terug; bij dit grote perceel ontbreken er mogelijk panden."
        )

    props = verzoek.perceel.get("properties") or {}
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
        "waarschuwingen": waarschuwingen,
        "bronnen": [KADASTER_WMS, BAG_WFS],
    }
