"""Geo-logica voor de verrijking. Bevat geen netwerkcalls, dus los te testen."""

from pyproj import Transformer
from shapely.geometry import mapping, shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform

RD = "EPSG:28992"    # Rijksdriehoekstelsel: meters, geschikt voor oppervlaktes
WGS84 = "EPSG:4326"  # lengte/breedtegraad: wat Leaflet en GeoJSON verwachten

# Wanneer telt een pand mee voor dit perceel?
MIN_OVERLAP_M2 = 5.0    # minder overlap = snipper door kleine kaartverschillen
MIN_AANDEEL = 0.10      # minstens 10% van het pand ligt op dit perceel...
RUIM_OVERLAP_M2 = 50.0  # ...of minstens 50 m² (groot pand over meerdere percelen)


def herprojecteer(geom: BaseGeometry, van: str, naar: str) -> BaseGeometry:
    """Zet een geometrie om van het ene coördinatenstelsel naar het andere."""
    if van == naar:
        return geom
    transformer = Transformer.from_crs(van, naar, always_xy=True)
    return transform(transformer.transform, geom)


def maak_geldig(geom: BaseGeometry) -> BaseGeometry:
    """Repareert zelf-snijdende polygonen; buffer(0) is de klassieke truc."""
    return geom if geom.is_valid else geom.buffer(0)


def _naar_int(waarde) -> int | None:
    try:
        return int(waarde)
    except (TypeError, ValueError):
        return None


def _gebruiksdoelen(waarde) -> list[str]:
    items = waarde if isinstance(waarde, list) else str(waarde or "").split(",")
    return [i.strip() for i in items if str(i).strip()]


def analyseer(perceel_rd: BaseGeometry, panden: list[dict]) -> dict:
    """Bepaalt welke BAG-panden op het perceel staan en rekent kengetallen uit.

    perceel_rd: perceelgeometrie in RD (meters).
    panden: GeoJSON-features uit de BAG WFS, ook in RD.
    """
    perceel_m2 = perceel_rd.area
    meegeteld, genegeerd = [], []
    bebouwd_m2 = 0.0

    for feature in panden:
        props = feature.get("properties") or {}
        pand = maak_geldig(shape(feature["geometry"]))
        if pand.area == 0:
            continue

        overlap_m2 = pand.intersection(perceel_rd).area
        aandeel = overlap_m2 / pand.area
        basis = {
            "identificatie": str(props.get("identificatie")),
            "overlap_m2": round(overlap_m2, 1),
            "aandeel_op_perceel_pct": round(aandeel * 100, 1),
        }

        telt_mee = overlap_m2 >= MIN_OVERLAP_M2 and (
            aandeel >= MIN_AANDEEL or overlap_m2 >= RUIM_OVERLAP_M2
        )
        if not telt_mee:
            reden = (
                "raakt het perceel niet (alleen binnen de bbox)"
                if overlap_m2 < 0.1
                else "snipper langs de grens, onder de drempel"
            )
            genegeerd.append({**basis, "reden": reden})
            continue

        bebouwd_m2 += overlap_m2
        meegeteld.append(
            {
                **basis,
                "bouwjaar": _naar_int(props.get("bouwjaar")),
                "status": props.get("status"),
                "gebruiksdoel": _gebruiksdoelen(props.get("gebruiksdoel")),
                "aantal_verblijfsobjecten": _naar_int(props.get("aantal_verblijfsobjecten")),
                "footprint_m2": round(pand.area, 1),
                "geometry": mapping(herprojecteer(pand, RD, WGS84)),
            }
        )

    bouwjaren = [p["bouwjaar"] for p in meegeteld if p["bouwjaar"]]
    doelen = sorted({d for p in meegeteld for d in p["gebruiksdoel"]})

    return {
        "perceel_m2": round(perceel_m2, 1),
        "bebouwing": {
            "aantal_panden": len(meegeteld),
            "bebouwd_m2": round(bebouwd_m2, 1),
            "onbebouwd_m2": round(max(perceel_m2 - bebouwd_m2, 0), 1),
            "bebouwingsgraad_pct": round(100 * bebouwd_m2 / perceel_m2, 1) if perceel_m2 else None,
            "oudste_bouwjaar": min(bouwjaren, default=None),
            "nieuwste_bouwjaar": max(bouwjaren, default=None),
            "gebruiksdoelen": doelen,
        },
        "panden": meegeteld,
        "genegeerd": genegeerd,
    }
