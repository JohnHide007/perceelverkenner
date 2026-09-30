"""Hoogte, bouwlagen en dakvlakken per pand uit de 3D BAG (TU Delft).

De 3D BAG combineert de BAG-pandcontouren met de hoogtemetingen van het AHN (laseraltimetrie).
Daaruit halen we per pand: hoe hoog het is, hoeveel bouwlagen, wat voor dak het heeft en hoeveel
m² plat en schuin dak er ligt. Dat laatste is de basis voor een indicatie van zonnepanelen.

De API is open (geen sleutel) en per pand op te vragen: één verzoek per pand, dus we beperken
ons tot de grootste panden op het perceel en vragen ze tegelijk op.
"""

import asyncio

import httpx

from . import haal_json

NAAM = "3D BAG (hoogte en dak)"
URL = "https://api.3dbag.nl/collections/pand/items"
MAX_PANDEN = 12      # één API-call per pand; grote percelen anders te traag
GELIJKTIJDIG = 4     # niet meer dan 4 verzoeken tegelijk naar de 3D BAG
RETRY_WACHT_S = 0.3  # korte pauze voor de tweede poging


def _num(waarde) -> float | None:
    try:
        return float(waarde)
    except (TypeError, ValueError):
        return None


def _rond(waarde: float | None, decimalen: int = 1) -> float | None:
    return None if waarde is None else round(waarde, decimalen)


def verwerk(antwoord: dict, pand_id: str) -> dict | None:
    """Vertaalt het CityJSON-antwoord van de 3D BAG naar onze eigen, platte velden."""
    objecten = ((antwoord or {}).get("feature") or {}).get("CityObjects") or {}
    attrs = (objecten.get(f"NL.IMBAG.Pand.{pand_id}") or {}).get("attributes")
    if not attrs:
        # Sommige antwoorden hebben een andere sleutel; pak dan het eerste object met attributen
        attrs = next((o.get("attributes") for o in objecten.values() if o.get("attributes")), None)
    if not attrs:
        return None

    maaiveld = _num(attrs.get("b3_h_maaiveld"))
    dak_70p = _num(attrs.get("b3_h_dak_70p"))
    dak_max = _num(attrs.get("b3_h_dak_max"))
    # Hoogtes in de 3D BAG zijn t.o.v. NAP; wij willen hoogte boven het maaiveld
    hoogte = dak_70p - maaiveld if dak_70p is not None and maaiveld is not None else None
    nok = dak_max - maaiveld if dak_max is not None and maaiveld is not None else None

    return {
        "hoogte_m": _rond(hoogte),
        "nokhoogte_m": _rond(nok),
        "bouwlagen": int(attrs["b3_bouwlagen"]) if _num(attrs.get("b3_bouwlagen")) is not None else None,
        "dak_type": attrs.get("b3_dak_type"),
        "dak_plat_m2": _rond(_num(attrs.get("b3_opp_dak_plat"))),
        "dak_schuin_m2": _rond(_num(attrs.get("b3_opp_dak_schuin"))),
        "volume_m3": _rond(_num(attrs.get("b3_volume_lod22")), 0),
        "meting": f"{attrs.get('b3_pw_bron', '?').upper()} {attrs.get('b3_pw_datum', '')}".strip(),
    }


class _Mislukt(Exception):
    """Eén pand kon niet worden opgehaald (na een retry)."""


async def _haal_pand(client: httpx.AsyncClient, pand_id: str, rem: asyncio.Semaphore) -> tuple[str, dict | None]:
    url = f"{URL}/NL.IMBAG.Pand.{pand_id}"
    for poging in (1, 2):  # de 3D BAG geeft bij drukte soms een losse 502; één keer opnieuw proberen
        try:
            async with rem:
                antwoord = await haal_json(client, url)
            return pand_id, verwerk(antwoord, pand_id)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return pand_id, None  # pand (nog) niet in de 3D BAG, geen fout
            fout: Exception = exc
        except (httpx.TransportError, ValueError) as exc:
            fout = exc
        if poging == 1:
            await asyncio.sleep(RETRY_WACHT_S)
    raise _Mislukt(pand_id) from fout


async def haal(client: httpx.AsyncClient, pand_ids: list[str]) -> dict:
    """3D-kenmerken per pand-id, plus totalen over het perceel.

    Een los pand dat faalt telt als 'mislukt' maar breekt de bron niet. Pas als álle
    panden falen, geven we de fout door (dan is de service zelf waarschijnlijk stuk).
    """
    gekozen = pand_ids[:MAX_PANDEN]
    rem = asyncio.Semaphore(GELIJKTIJDIG)
    resultaten = await asyncio.gather(*(_haal_pand(client, pid, rem) for pid in gekozen), return_exceptions=True)

    mislukt = [r for r in resultaten if isinstance(r, BaseException)]
    if gekozen and len(mislukt) == len(gekozen):
        oorzaak = mislukt[0].__cause__ or mislukt[0]
        raise oorzaak

    per_pand = {pid: data for r in resultaten if not isinstance(r, BaseException) for pid, data in [r]}
    gevonden = [d for d in per_pand.values() if d]

    hoogtes = [d["hoogte_m"] for d in gevonden if d["hoogte_m"] is not None]
    lagen = [d["bouwlagen"] for d in gevonden if d["bouwlagen"] is not None]
    return {
        "per_pand": per_pand,
        "opgevraagd": len(gekozen),
        "gevonden": len(gevonden),
        "mislukt": len(mislukt),
        "overgeslagen": max(len(pand_ids) - len(gekozen), 0),
        "hoogste_pand_m": max(hoogtes, default=None),
        "meeste_bouwlagen": max(lagen, default=None),
        "dak_plat_m2": round(sum(d["dak_plat_m2"] or 0 for d in gevonden), 1),
        "dak_schuin_m2": round(sum(d["dak_schuin_m2"] or 0 for d in gevonden), 1),
        "volume_m3": round(sum(d["volume_m3"] or 0 for d in gevonden)),
    }
