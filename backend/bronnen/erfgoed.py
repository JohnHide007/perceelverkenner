"""Cultureel erfgoed (Rijksdienst voor het Cultureel Erfgoed via PDOK).

Twee lagen uit dezelfde WFS:
- punten: rijksmonumenten (één punt per monument, met het nummer in het monumentenregister)
- vlakken: beschermde stads- en dorpsgezichten en UNESCO-werelderfgoed

Een monumentstatus is voor vastgoed geen detail: verduurzamen en verbouwen zijn vergunningplichtig
en de mogelijkheden zijn beperkt. Daarom hoort dit in het perceelbeeld.
"""

import asyncio

import httpx
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

from . import features, haal_json, wfs_params

NAAM = "Erfgoed (RCE)"
URL = "https://service.pdok.nl/rce/ps-ch/wfs/v1_0"
MARGE_M = 2.0  # monumentpunten liggen soms net naast de perceelgrens
SOORTEN = {
    "nlps-rijksmonumenten": "rijksmonument",
    "nlps-stadsendorpsgezichten": "beschermd stads- of dorpsgezicht",
    "nlps-werelderfgoed": "UNESCO-werelderfgoed",
}


def _nummer(props: dict) -> str | None:
    """Het rijksmonumentnummer, zoals het monumentenregister het gebruikt.

    Let op: `localid` (bv. 27428.00) is een intern id van de dataset, níet het monumentnummer.
    Het echte nummer staat aan het eind van de link naar het register:
    https://monumentenregister.cultureelerfgoed.nl/monumenten/5940 -> '5940'.
    """
    laatste = str(props.get("ciCitation") or "").rstrip("/").rsplit("/", 1)[-1]
    return laatste if laatste.isdigit() else None


async def haal(client: httpx.AsyncClient, perceel_rd: BaseGeometry) -> dict:
    bbox = perceel_rd.buffer(MARGE_M).bounds
    punten, vlakken = await asyncio.gather(
        haal_json(client, URL, wfs_params("ps-ch:rce_inspire_points", bbox, 200)),
        haal_json(client, URL, wfs_params("ps-ch:rce_inspire_polygons", bbox, 20)),
    )

    zone = perceel_rd.buffer(MARGE_M)
    monumenten = []
    for f in features(punten):
        p = f.get("properties") or {}
        if p.get("namespace") not in (None, "nlps-rijksmonumenten"):
            continue
        try:
            punt = shape(f["geometry"])
        except (KeyError, TypeError, ValueError):
            continue
        if not zone.contains(punt):
            continue
        monumenten.append(
            {
                "nummer": _nummer(p),
                "url": p.get("ciCitation"),
                "sinds": (p.get("legalfoundationdate") or "")[:4] or None,
            }
        )

    gebieden = []
    for f in features(vlakken):
        p = f.get("properties") or {}
        try:
            vlak = shape(f["geometry"])
        except (KeyError, TypeError, ValueError):
            continue
        if not vlak.intersects(perceel_rd):
            continue
        gebieden.append(
            {
                "soort": SOORTEN.get(p.get("namespace"), p.get("namespace") or "beschermd gebied"),
                "naam": p.get("text") or None,
                "url": p.get("ciCitation"),
                "sinds": (p.get("legalfoundationdate") or "")[:4] or None,
            }
        )

    monumenten.sort(key=lambda m: int(m["nummer"]) if m["nummer"] else 0)
    return {
        "rijksmonumenten": monumenten,
        "gebieden": gebieden,
        "beschermd": bool(monumenten or gebieden),
    }
