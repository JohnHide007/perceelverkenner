"""Tests voor de geo-logica. Geen netwerk: alle geometrieën zijn verzonnen of komen uit voorbeelden/."""

import json
from pathlib import Path

import pytest
from shapely.geometry import Polygon, box, mapping, shape

from verrijking import (
    MIN_OVERLAP_M2,
    RD,
    WGS84,
    analyseer,
    herprojecteer,
    maak_geldig,
)

WEB_MERCATOR = "EPSG:3857"
VOORBEELD = Path(__file__).parent.parent / "voorbeelden" / "dam_perceel.json"

# Testperceel: 20 x 20 m in RD (400 m²), ergens in Amersfoort
X0, Y0 = 155_000.0, 463_000.0
PERCEEL = box(X0, Y0, X0 + 20, Y0 + 20)


def pand(geom, **props) -> dict:
    """Bouwt een BAG-achtige GeoJSON-feature, zoals de WFS die teruggeeft."""
    basis = {"identificatie": "0000100000000001", "bouwjaar": "2000", "status": "Pand in gebruik",
             "gebruiksdoel": "woonfunctie", "aantal_verblijfsobjecten": "1"}
    return {"type": "Feature", "geometry": mapping(geom), "properties": {**basis, **props}}


# ---------- herprojecteer ----------

def test_zelfde_stelsel_geeft_hetzelfde_object_terug():
    assert herprojecteer(PERCEEL, RD, RD) is PERCEEL


def test_rd_naar_wgs84_klopt_voor_amersfoort():
    # Het nulpunt van RD ligt bij de Onze Lieve Vrouwetoren in Amersfoort
    punt = herprojecteer(box(X0, Y0, X0 + 1, Y0 + 1), RD, WGS84).centroid
    assert punt.x == pytest.approx(5.387, abs=0.001)   # lengtegraad
    assert punt.y == pytest.approx(52.155, abs=0.001)  # breedtegraad


def test_heen_en_terug_verschuift_minder_dan_een_millimeter():
    terug = herprojecteer(herprojecteer(PERCEEL, RD, WGS84), WGS84, RD)
    # Hausdorff-afstand: de grootste afstand tussen een punt van de ene vorm en de andere
    assert terug.hausdorff_distance(PERCEEL) < 0.001


def test_web_mercator_blaast_oppervlak_op_en_rd_niet():
    """Waarom de backend in RD rekent: Web Mercator overdrijft oppervlak op 52° NB ~2,6x."""
    in_mercator = herprojecteer(PERCEEL, RD, WEB_MERCATOR)
    assert in_mercator.area / PERCEEL.area == pytest.approx(2.65, abs=0.05)
    terug_in_rd = herprojecteer(in_mercator, WEB_MERCATOR, RD)
    assert terug_in_rd.area == pytest.approx(400, abs=0.5)


# ---------- maak_geldig ----------

def test_geldige_polygoon_blijft_ongewijzigd():
    assert maak_geldig(PERCEEL) is PERCEEL


def test_zelfsnijdende_polygoon_wordt_gerepareerd():
    vlinder = Polygon([(0, 0), (10, 10), (10, 0), (0, 10)])  # "bowtie": lijnen kruisen elkaar
    assert not vlinder.is_valid
    assert maak_geldig(vlinder).is_valid


# ---------- analyseer: welke panden tellen mee? ----------

def test_pand_volledig_op_perceel_telt_mee():
    uitkomst = analyseer(PERCEEL, [pand(box(X0 + 5, Y0 + 5, X0 + 15, Y0 + 15))])
    assert uitkomst["bebouwing"]["aantal_panden"] == 1
    assert uitkomst["bebouwing"]["bebouwd_m2"] == pytest.approx(100)
    assert uitkomst["bebouwing"]["onbebouwd_m2"] == pytest.approx(300)
    assert uitkomst["bebouwing"]["bebouwingsgraad_pct"] == pytest.approx(25)
    assert uitkomst["panden"][0]["aandeel_op_perceel_pct"] == pytest.approx(100)


def test_buurpand_in_bbox_zonder_overlap_wordt_genegeerd():
    buur = pand(box(X0 + 25, Y0, X0 + 35, Y0 + 10))  # 5 m naast het perceel
    uitkomst = analyseer(PERCEEL, [buur])
    assert uitkomst["bebouwing"]["aantal_panden"] == 0
    assert uitkomst["genegeerd"][0]["reden"].startswith("raakt het perceel niet")


def test_snipper_langs_de_grens_wordt_genegeerd():
    # Buurpand steekt 0,3 m over de grens: 0,3 x 10 = 3 m² < MIN_OVERLAP_M2
    snipper = pand(box(X0 + 19.7, Y0, X0 + 29.7, Y0 + 10))
    uitkomst = analyseer(PERCEEL, [snipper])
    assert uitkomst["genegeerd"][0]["overlap_m2"] < MIN_OVERLAP_M2
    assert uitkomst["genegeerd"][0]["reden"] == "snipper langs de grens, onder de drempel"


def test_groot_pand_met_klein_aandeel_telt_mee_door_ruime_overlap():
    # 100 x 10 m pand (1000 m²), waarvan 60 m² op het perceel: 6% < 10%, maar 60 m² >= 50 m²
    groot = pand(box(X0 + 14, Y0, X0 + 114, Y0 + 10))
    uitkomst = analyseer(PERCEEL, [groot])
    assert uitkomst["bebouwing"]["aantal_panden"] == 1
    assert uitkomst["panden"][0]["overlap_m2"] == pytest.approx(60)
    assert uitkomst["panden"][0]["aandeel_op_perceel_pct"] == pytest.approx(6)


def test_middelgrote_overlap_met_klein_aandeel_telt_niet_mee():
    # 8 m² overlap (> 5 m²) maar slechts 8% van het pand en < 50 m²
    pand_buur = pand(box(X0 + 19.2, Y0, X0 + 29.2, Y0 + 10))
    uitkomst = analyseer(PERCEEL, [pand_buur])
    assert uitkomst["bebouwing"]["aantal_panden"] == 0
    assert uitkomst["genegeerd"][0]["overlap_m2"] == pytest.approx(8)


def test_pand_zonder_oppervlak_wordt_overgeslagen():
    lijn = {"type": "Feature", "geometry": {"type": "LineString", "coordinates": [[X0, Y0], [X0 + 5, Y0 + 5]]},
            "properties": {}}
    uitkomst = analyseer(PERCEEL, [lijn])
    assert uitkomst["panden"] == [] and uitkomst["genegeerd"] == []


def test_geen_panden_geeft_onbebouwd_perceel():
    uitkomst = analyseer(PERCEEL, [])
    assert uitkomst["perceel_m2"] == pytest.approx(400)
    assert uitkomst["bebouwing"]["bebouwingsgraad_pct"] == 0
    assert uitkomst["bebouwing"]["oudste_bouwjaar"] is None


# ---------- analyseer: kengetallen en BAG-eigenaardigheden ----------

def test_bouwjaren_en_gebruiksdoelen_worden_samengevat():
    panden = [
        pand(box(X0, Y0, X0 + 8, Y0 + 8), identificatie="a", bouwjaar="1380", gebruiksdoel="bijeenkomstfunctie"),
        pand(box(X0 + 10, Y0, X0 + 18, Y0 + 8), identificatie="b", bouwjaar="1978",
             gebruiksdoel="woonfunctie, winkelfunctie"),  # BAG levert soms een komma-string
        pand(box(X0, Y0 + 10, X0 + 8, Y0 + 18), identificatie="c", bouwjaar=None,
             gebruiksdoel=["woonfunctie"]),  # ...en soms een lijst
    ]
    b = analyseer(PERCEEL, panden)["bebouwing"]
    assert b["aantal_panden"] == 3
    assert (b["oudste_bouwjaar"], b["nieuwste_bouwjaar"]) == (1380, 1978)
    assert b["gebruiksdoelen"] == ["bijeenkomstfunctie", "winkelfunctie", "woonfunctie"]


def test_pandgeometrie_komt_terug_in_wgs84_voor_leaflet():
    uitkomst = analyseer(PERCEEL, [pand(box(X0 + 5, Y0 + 5, X0 + 15, Y0 + 15))])
    lon, lat = shape(uitkomst["panden"][0]["geometry"]).centroid.coords[0]
    assert 3 < lon < 8 and 50 < lat < 54  # binnen Nederland, niet in RD-meters


# ---------- echt perceel uit het voorbeeld ----------

def test_dam_perceel_oppervlak_wijkt_weinig_af_van_kadaster():
    """Nieuwe Kerk (Amsterdam F 7917): kaartgeometrie vs. vastgestelde kadastrale grootte."""
    voorbeeld = json.loads(VOORBEELD.read_text())
    perceel = maak_geldig(shape(voorbeeld["perceel"]["geometry"]))
    berekend = analyseer(perceel, [])["perceel_m2"]
    kadaster = float(voorbeeld["perceel"]["properties"]["kadastraleGrootteWaarde"])
    assert berekend == pytest.approx(4474.7, abs=0.1)
    assert abs(berekend - kadaster) / kadaster < 0.05  # < 5% verschil
