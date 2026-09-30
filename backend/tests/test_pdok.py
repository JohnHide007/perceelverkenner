"""Tests voor de netwerkkant: PDOK wordt vervangen door nep-antwoorden (httpx.MockTransport)."""

import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from shapely.geometry import box, mapping

import main

VOORBEELD = json.loads((Path(__file__).parent.parent / "voorbeelden" / "dam_perceel.json").read_text())
client = TestClient(main.app)

CAPABILITIES = b"""<?xml version="1.0" encoding="UTF-8"?>
<WMS_Capabilities xmlns="http://www.opengis.net/wms" version="1.3.0">
  <Capability>
    <Layer>
      <Title>Kadastrale kaart</Title>
      <Layer queryable="1"><Name>Perceelvlak</Name><Title>Perceel vlak</Title></Layer>
      <Layer queryable="0"><Name>Label</Name><Title>Perceelnummer</Title></Layer>
    </Layer>
  </Capability>
</WMS_Capabilities>"""


@pytest.fixture
def nep_pdok(monkeypatch):
    """Laat elke httpx.AsyncClient in main.py praten met een nep-server in plaats van PDOK.

    Zet `nep_pdok.antwoord` op een functie request -> httpx.Response.
    Alle verzoeken worden bewaard in `nep_pdok.verzoeken`.
    """

    class Nep:
        verzoeken: list[httpx.Request] = []
        antwoord = None

    def handler(request: httpx.Request) -> httpx.Response:
        Nep.verzoeken.append(request)
        return Nep.antwoord(request)

    echte_client = httpx.AsyncClient
    monkeypatch.setattr(
        main.httpx, "AsyncClient",
        lambda **kwargs: echte_client(transport=httpx.MockTransport(handler), **kwargs),
    )
    Nep.verzoeken = []
    return Nep


# ---------- /lagen ----------

def test_lagen_leest_capabilities(nep_pdok):
    nep_pdok.antwoord = lambda req: httpx.Response(200, content=CAPABILITIES)
    body = client.get("/lagen").json()
    assert body["aantal"] == 2  # de groepslaag zonder <Name> telt niet mee
    assert body["lagen"][0] == {"naam": "Perceelvlak", "titel": "Perceel vlak", "opvraagbaar": True}
    assert body["lagen"][1]["opvraagbaar"] is False
    assert nep_pdok.verzoeken[0].url.params["REQUEST"] == "GetCapabilities"


def test_lagen_geeft_502_bij_geen_xml(nep_pdok):
    # Bijvoorbeeld een HTML-storingspagina met status 200
    nep_pdok.antwoord = lambda req: httpx.Response(200, content=b"<html>Onderhoud</htm")
    antwoord = client.get("/lagen")
    assert antwoord.status_code == 502
    assert "geen geldige XML" in antwoord.json()["detail"]


def test_lagen_geeft_502_bij_pdok_storing(nep_pdok):
    nep_pdok.antwoord = lambda req: httpx.Response(503)
    assert client.get("/lagen").status_code == 502


# ---------- BAG WFS via /verrijk ----------

def _pand_rond(request: httpx.Request, aantal: int = 1) -> httpx.Response:
    """Nep-BAG: geeft `aantal` panden terug in de hoek van de gevraagde bbox."""
    minx, miny, *_ = (float(v) for v in request.url.params["BBOX"].split(",")[:4])
    panden = [
        {"type": "Feature", "geometry": mapping(box(minx + 10, miny + 10, minx + 30, miny + 30)),
         "properties": {"identificatie": f"pand{i}", "bouwjaar": "1900", "gebruiksdoel": "woonfunctie"}}
        for i in range(aantal)
    ]
    return httpx.Response(200, json={"type": "FeatureCollection", "features": panden})


def test_bag_wordt_bevraagd_in_rd_met_bbox_van_perceel(nep_pdok):
    nep_pdok.antwoord = _pand_rond
    antwoord = client.post("/verrijk", json=VOORBEELD)
    assert antwoord.status_code == 200
    params = nep_pdok.verzoeken[0].url.params
    assert params["TYPENAMES"] == "bag:pand"
    assert params["SRSNAME"] == "EPSG:28992"
    assert params["BBOX"].endswith("EPSG:28992")
    assert params["COUNT"] == str(main.BAG_MAX)
    assert antwoord.json()["waarschuwingen"] == []


def test_waarschuwing_als_bag_het_maximum_teruggeeft(nep_pdok, monkeypatch):
    monkeypatch.setattr(main, "BAG_MAX", 3)  # klein maximum, zodat de test snel blijft
    nep_pdok.antwoord = lambda req: _pand_rond(req, aantal=3)
    body = client.post("/verrijk", json=VOORBEELD).json()
    assert len(body["waarschuwingen"]) == 1
    assert "maximum van 3 panden" in body["waarschuwingen"][0]


def test_bag_zonder_json_geeft_502(nep_pdok):
    nep_pdok.antwoord = lambda req: httpx.Response(200, content=b"<ows:ExceptionReport/>")
    antwoord = client.post("/verrijk", json=VOORBEELD)
    assert antwoord.status_code == 502
    assert "geen JSON" in antwoord.json()["detail"]


def test_bag_onbereikbaar_geeft_502(nep_pdok):
    def weigeren(request):
        raise httpx.ConnectError("verbinding geweigerd", request=request)

    nep_pdok.antwoord = weigeren
    antwoord = client.post("/verrijk", json=VOORBEELD)
    assert antwoord.status_code == 502
    assert "BAG WFS niet bereikbaar" in antwoord.json()["detail"]


# ---------- extra bronnen via /verrijk ----------

def test_haperende_extra_bron_breekt_het_antwoord_niet(nep_pdok):
    """Alleen de BAG-panden zijn de kern. Als bijvoorbeeld het CBS of de 3D BAG faalt, komt dat als
    status 'fout' in de bronvermelding en blijft de rest van het antwoord gewoon staan."""

    def antwoord(request):
        if request.url.params.get("TYPENAMES") == "bag:pand":
            return _pand_rond(request)
        if "cbs" in request.url.path:
            return httpx.Response(503)
        if "3dbag" in request.url.host:
            raise httpx.ReadTimeout("traag", request=request)
        return httpx.Response(200, json={"type": "FeatureCollection", "features": []})

    nep_pdok.antwoord = antwoord
    antwoord = client.post("/verrijk", json=VOORBEELD)
    assert antwoord.status_code == 200
    body = antwoord.json()
    status = {b["naam"]: b for b in body["bronnen"]}
    assert status["Buurtcijfers (CBS 2024)"]["status"] == "fout"
    assert "status 503" in status["Buurtcijfers (CBS 2024)"]["fout"]
    assert status["3D BAG (hoogte en dak)"]["status"] == "fout"
    assert status["Erfgoed (RCE)"]["status"] == "ok"
    assert body["buurt"] is None and body["hoogte"] is None
    assert body["bebouwing"]["aantal_panden"] == 1  # de kern is er gewoon


def test_alle_bronnen_worden_tegelijk_bevraagd_in_rd(nep_pdok):
    nep_pdok.antwoord = _pand_rond
    client.post("/verrijk", json=VOORBEELD)
    hosts = sorted({r.url.host for r in nep_pdok.verzoeken})
    assert hosts == ["api.3dbag.nl", "service.pdok.nl"]
    typenames = {r.url.params.get("TYPENAMES") for r in nep_pdok.verzoeken if "TYPENAMES" in r.url.params}
    assert typenames == {"bag:pand", "bag:verblijfsobject", "ps-ch:rce_inspire_points", "ps-ch:rce_inspire_polygons", "wijkenbuurten:buurten"}
    assert all(r.url.params["SRSNAME"] == "EPSG:28992" for r in nep_pdok.verzoeken if "SRSNAME" in r.url.params)
