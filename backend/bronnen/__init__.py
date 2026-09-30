"""Databronnen als losse modules met één vaste antwoordvorm.

Elke module levert een `async def haal(client, ...) -> dict` en twee constanten: NAAM en URL.
De orchestratie in main.py roept `veilig()` aan: die meet de duur, vangt fouten af en geeft altijd
hetzelfde blok terug, zodat één haperende bron nooit het hele antwoord onderuit haalt.

Antwoordvorm van `veilig()`:

    {
        "naam": "Adressen (BAG)",     # leesbare naam van de bron
        "bron": "https://...",        # de service die is aangesproken (bronvermelding)
        "status": "ok" | "fout",      # is de bron gelukt?
        "duur_ms": 123,               # hoe lang de bron erover deed
        "data": {...} | None,         # het resultaat van de module (None bij fout)
        "fout": None | "melding",     # waarom het misging (alleen bij fout)
    }
"""

import logging
from time import perf_counter
from typing import Any, Awaitable

import httpx

log = logging.getLogger("perceelverkenner.bronnen")


async def veilig(naam: str, url: str, coro: Awaitable[Any]) -> dict:
    """Voert één bron uit en vertaalt het resultaat (of de fout) naar de vaste antwoordvorm."""
    start = perf_counter()
    try:
        data = await coro
        status, fout = "ok", None
    except Exception as exc:  # noqa: BLE001 - bewust breed: een bron mag nooit de rest slopen
        data, status, fout = None, "fout", _leesbare_fout(exc)
        log.warning("Bron %s mislukt: %s", naam, fout)
    return {
        "naam": naam,
        "bron": url,
        "status": status,
        "duur_ms": round((perf_counter() - start) * 1000),
        "data": data,
        "fout": fout,
    }


def _leesbare_fout(exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        return f"service gaf status {exc.response.status_code}"
    if isinstance(exc, httpx.TimeoutException):
        return "service reageerde niet op tijd"
    if isinstance(exc, httpx.HTTPError):
        return f"service niet bereikbaar ({exc.__class__.__name__})"
    return f"{exc.__class__.__name__}: {exc}"[:200]


async def haal_json(client: httpx.AsyncClient, url: str, params: dict | None = None) -> Any:
    """GET + JSON, met nette fouten als de service iets anders dan JSON teruggeeft."""
    response = await client.get(url, params=params)
    response.raise_for_status()
    try:
        return response.json()
    except ValueError as exc:
        raise ValueError(f"service gaf geen JSON: {response.text[:120]!r}") from exc


def wfs_params(typename: str, bbox: tuple[float, float, float, float], count: int, extra: dict | None = None) -> dict:
    """Standaardparameters voor een PDOK WFS 2.0.0 GetFeature in RD (EPSG:28992)."""
    minx, miny, maxx, maxy = bbox
    return {
        "SERVICE": "WFS",
        "VERSION": "2.0.0",
        "REQUEST": "GetFeature",
        "TYPENAMES": typename,
        "BBOX": f"{minx},{miny},{maxx},{maxy},EPSG:28992",
        "SRSNAME": "EPSG:28992",
        "OUTPUTFORMAT": "application/json",
        "COUNT": str(count),
        **(extra or {}),
    }


def features(antwoord: Any) -> list[dict]:
    """De features uit een GeoJSON-FeatureCollection, of leeg als de vorm niet klopt."""
    if isinstance(antwoord, dict) and isinstance(antwoord.get("features"), list):
        return [f for f in antwoord["features"] if isinstance(f, dict)]
    return []
