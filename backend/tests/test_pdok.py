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
