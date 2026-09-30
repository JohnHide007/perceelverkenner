"""Adressen en verblijfsobjecten (BAG) van de panden op het perceel.

Een pand zegt wat er staat; een verblijfsobject zegt hoe het gebruikt wordt: elk adres met zijn
gebruiksoppervlakte (m² binnen de muren) en gebruiksdoel. Daarmee weet je of een pand één winkel
is of dertig appartementen, en hoeveel verhuurbare meters er ongeveer zijn.
"""

from collections import defaultdict

import httpx

from . import features, haal_json, wfs_params

NAAM = "Adressen (BAG verblijfsobjecten)"
URL = "https://service.pdok.nl/lv/bag/wfs/v2_0"
MAX = 1000       # maximum aantal verblijfsobjecten per bbox
MAX_ITEMS = 60   # meer adressen in het antwoord heeft geen zin voor het zijpaneel
NIET_MEETELLEN = ("niet gerealiseerd", "ingetrokken", "buiten gebruik")  # statussen die geen echt adres zijn


def _adres(p: dict) -> str:
    huisnummer = f"{p.get('huisnummer') or ''}{p.get('huisletter') or ''}"
    if p.get("toevoeging"):
        huisnummer += f"-{p['toevoeging']}"
    return f"{p.get('openbare_ruimte') or '?'} {huisnummer}".strip()


def _pand_ids(waarde) -> set[str]:
    """`pandidentificatie` kan meerdere panden bevatten (kommagescheiden)."""
    return {s.strip() for s in str(waarde or "").split(",") if s.strip()}


def _int(waarde) -> int | None:
    try:
        return int(waarde)
    except (TypeError, ValueError):
        return None


async def haal(client: httpx.AsyncClient, bbox: tuple[float, float, float, float], pand_ids: set[str]) -> dict:
    """Verblijfsobjecten in de bbox, gefilterd op de panden die op dit perceel staan."""
    if not pand_ids:
        return {"aantal": 0, "gebruiksoppervlak_m2": 0, "per_gebruiksdoel": [], "postcodes": [], "items": []}

    antwoord = await haal_json(client, URL, wfs_params("bag:verblijfsobject", bbox, MAX))

    items = []
    for feature in features(antwoord):
        p = feature.get("properties") or {}
        if not _pand_ids(p.get("pandidentificatie")) & pand_ids:
            continue  # hoort bij een buurpand
        status = str(p.get("status") or "")
        if any(s in status.lower() for s in NIET_MEETELLEN):
            continue
        items.append(
            {
                "identificatie": str(p.get("identificatie")),
                "adres": _adres(p),
                "postcode": p.get("postcode") or None,
                "woonplaats": p.get("woonplaats") or None,
                "gebruiksdoel": [d.strip() for d in str(p.get("gebruiksdoel") or "").split(",") if d.strip()],
                "oppervlakte_m2": _int(p.get("oppervlakte")),
                "status": status or None,
                "pand": str(p.get("pandidentificatie") or ""),
            }
        )

    # Kengetallen per gebruiksdoel: aantal adressen en m² gebruiksoppervlak
    per_doel: dict[str, dict] = defaultdict(lambda: {"aantal": 0, "oppervlakte_m2": 0})
    for item in items:
        for doel in item["gebruiksdoel"] or ["onbekend"]:
            per_doel[doel]["aantal"] += 1
            per_doel[doel]["oppervlakte_m2"] += item["oppervlakte_m2"] or 0

    items.sort(key=lambda i: (i["adres"], i["identificatie"]))
    return {
        "aantal": len(items),
        "gebruiksoppervlak_m2": sum(i["oppervlakte_m2"] or 0 for i in items),
        "per_gebruiksdoel": sorted(
            ({"gebruiksdoel": d, **v} for d, v in per_doel.items()),
            key=lambda v: (-v["oppervlakte_m2"], v["gebruiksdoel"]),
        ),
        "postcodes": sorted({i["postcode"] for i in items if i["postcode"]}),
        "woonplaats": next((i["woonplaats"] for i in items if i["woonplaats"]), None),
        "afgekapt": len(items) > MAX_ITEMS,
        "items": items[:MAX_ITEMS],
    }
