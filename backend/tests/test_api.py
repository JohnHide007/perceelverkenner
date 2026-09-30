"""Tests voor de endpoints. De BAG WFS wordt vervangen door een nep-functie: geen netwerk nodig."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from shapely.geometry import box, mapping

import main

VOORBEELD = json.loads((Path(__file__).parent.parent / "voorbeelden" / "dam_perceel.json").read_text())
client = TestClient(main.app)


@pytest.fixture
def nep_bag(monkeypatch):
    """Vervangt de BAG-aanroep; onthoudt de bbox waarmee hij werd aangeroepen."""
    aanroepen = []

    async def _nep(bounds, client=None):
        aanroepen.append(bounds)
        minx, miny, _, _ = bounds
        binnen = box(minx + 10, miny + 10, minx + 30, miny + 30)  # 400 m² in de hoek van de bbox
        return [{"type": "Feature", "geometry": mapping(binnen),
                 "properties": {"identificatie": "test", "bouwjaar": "1900", "gebruiksdoel": "woonfunctie"}}]

    monkeypatch.setattr(main, "_haal_panden", _nep)
    return aanroepen


def test_health():
    antwoord = client.get("/health")
    assert antwoord.status_code == 200
    assert antwoord.json() == {"status": "ok"}


def test_verrijk_met_voorbeeldperceel(nep_bag):
    antwoord = client.post("/verrijk", json=VOORBEELD)
    assert antwoord.status_code == 200
    body = antwoord.json()
    assert body["perceel"]["aanduiding"].endswith("F 7917")
    assert body["perceel"]["oppervlakte_kadaster_m2"] == 4366.0
    assert body["kandidaten_in_bbox"] == 1
    # De backend vraagt de BAG op met de bbox van het perceel in RD-meters
    minx, miny, maxx, maxy = nep_bag[0]
    assert 100_000 < minx < maxx < 130_000 and 480_000 < miny < maxy < 490_000


def test_verrijk_accepteert_web_mercator(nep_bag):
    """Zo stuurt de frontend het perceel: in EPSG:3857. De m² moeten gelijk blijven."""
    from verrijking import RD, herprojecteer
    from shapely.geometry import shape

    in_rd = shape(VOORBEELD["perceel"]["geometry"])
    in_mercator = herprojecteer(in_rd, RD, "EPSG:3857")
    verzoek = {"perceel": {**VOORBEELD["perceel"], "geometry": mapping(in_mercator)}, "crs": "EPSG:3857"}

    antwoord = client.post("/verrijk", json=verzoek)
    assert antwoord.status_code == 200
    assert antwoord.json()["perceel"]["oppervlakte_berekend_m2"] == pytest.approx(4474.7, abs=0.5)


@pytest.mark.parametrize(
    "verzoek",
    [
        {"perceel": {"properties": {}}},                              # geen geometry
        {"perceel": {"geometry": {"type": "Polygon"}}},               # geometry zonder coördinaten
        {"perceel": VOORBEELD["perceel"], "crs": "EPSG:onzin"},       # onbekend stelsel
    ],
)
def test_ongeldig_perceel_geeft_422(verzoek, nep_bag):
    antwoord = client.post("/verrijk", json=verzoek)
    assert antwoord.status_code == 422
    assert nep_bag == []  # de BAG is niet eens aangeroepen


def test_verrijk_bevat_alle_bronnen_ook_als_ze_leeg_zijn(nep_bag):
    """De extra bronnen zijn in de tests 'leeg' (zie conftest.py) maar horen altijd in het antwoord te staan."""
    body = client.post("/verrijk", json=VOORBEELD).json()
    assert body["adressen"]["aantal"] == 0
    assert body["hoogte"]["gevonden"] == 0 and body["panden"][0]["hoogte"] is None
    assert body["erfgoed"] == {"rijksmonumenten": [], "gebieden": [], "beschermd": False}
    assert body["buurt"] is None
    assert isinstance(body["signalen"], list)
    # Bronvermelding: kern (Kadaster, BAG-panden) + de vier modules, allemaal geslaagd
    assert [b["naam"] for b in body["bronnen"]][:2] == ["Kadastrale kaart (Kadaster)", "Panden (BAG)"]
    assert len(body["bronnen"]) == 6 and all(b["status"] == "ok" for b in body["bronnen"])
    assert all("data" not in b for b in body["bronnen"])  # alleen metadata, geen dubbele payload
