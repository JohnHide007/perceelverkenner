"""Tests voor de losse bronmodules en de vaste antwoordvorm. Alle services zijn nagebootst."""

import asyncio
import json

import httpx
import pytest
from shapely.geometry import box, mapping

import signalen
from bronnen import adressen, buurt, erfgoed, hoogte, veilig

PERCEEL = box(121_200, 487_400, 121_300, 487_500)  # 100 x 100 m, in RD


def client_met(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def run(coro):
    return asyncio.run(coro)


def collectie(*features: dict) -> httpx.Response:
    return httpx.Response(200, json={"type": "FeatureCollection", "features": list(features)})


# ---------- veilig(): de vaste antwoordvorm ----------

def test_veilig_geeft_data_en_duur_bij_succes():
    async def bron():
        return {"x": 1}

    blok = run(veilig("Test", "https://voorbeeld", bron()))
    assert blok["status"] == "ok" and blok["data"] == {"x": 1} and blok["fout"] is None
    assert set(blok) == {"naam", "bron", "status", "duur_ms", "data", "fout"}


@pytest.mark.parametrize(
    "exc, verwacht",
    [
        (httpx.ConnectError("weg"), "niet bereikbaar"),
        (httpx.ReadTimeout("traag"), "niet op tijd"),
        (ValueError("rare data"), "ValueError: rare data"),
    ],
)
def test_veilig_vangt_fouten_af_in_plaats_van_te_crashen(exc, verwacht):
    async def bron():
        raise exc

    blok = run(veilig("Test", "https://voorbeeld", bron()))
    assert blok["status"] == "fout" and blok["data"] is None
    assert verwacht in blok["fout"]


# ---------- adressen (BAG verblijfsobjecten) ----------

def vbo(pand: str, **props) -> dict:
    basis = {"identificatie": f"vbo-{pand}-{props.get('huisnummer', 1)}", "pandidentificatie": pand,
             "openbare_ruimte": "Dam", "huisnummer": 1, "huisletter": "", "toevoeging": "",
             "postcode": "1012JS", "woonplaats": "Amsterdam", "gebruiksdoel": "woonfunctie",
             "oppervlakte": 80, "status": "Verblijfsobject in gebruik"}
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [121_250, 487_450]},
            "properties": {**basis, **props}}


def test_adressen_filtert_op_panden_van_dit_perceel_en_telt_op():
    def handler(request):
        assert request.url.params["TYPENAMES"] == "bag:verblijfsobject"
        return collectie(
            vbo("pandA", huisnummer=1, oppervlakte=100, gebruiksdoel="winkelfunctie"),
            vbo("pandA", huisnummer=2, oppervlakte=60),
            vbo("pandB", huisnummer=3, oppervlakte=1000),               # buurpand: telt niet mee
            vbo("pandA", huisnummer=4, status="Niet gerealiseerd verblijfsobject"),  # geen echt adres
            vbo("pandC,pandA", huisnummer=5, oppervlakte=40),          # object over twee panden
        )

    data = run(adressen.haal(client_met(handler), PERCEEL.bounds, {"pandA"}))
    assert data["aantal"] == 3
    assert data["gebruiksoppervlak_m2"] == 200
    assert [d["gebruiksdoel"] for d in data["per_gebruiksdoel"]] == ["winkelfunctie", "woonfunctie"]
    assert data["per_gebruiksdoel"][1] == {"gebruiksdoel": "woonfunctie", "aantal": 2, "oppervlakte_m2": 100}
    assert data["postcodes"] == ["1012JS"] and data["woonplaats"] == "Amsterdam"
    assert data["items"][0]["adres"] == "Dam 1"


def test_adressen_zonder_panden_vraagt_niets_op():
    def handler(request):
        raise AssertionError("er had geen verzoek mogen zijn")

    data = run(adressen.haal(client_met(handler), PERCEEL.bounds, set()))
    assert data["aantal"] == 0 and data["items"] == []


def test_adres_met_huisletter_en_toevoeging():
    assert adressen._adres({"openbare_ruimte": "Coolsingel", "huisnummer": 93, "huisletter": "A", "toevoeging": "03"}) == "Coolsingel 93A-03"


# ---------- hoogte (3D BAG) ----------

def cityjson(pand: str, **attrs) -> dict:
    basis = {"b3_h_maaiveld": -3.8, "b3_h_dak_70p": 2.0, "b3_h_dak_max": 5.7, "b3_bouwlagen": 2,
             "b3_dak_type": "slanted", "b3_opp_dak_plat": 43.3, "b3_opp_dak_schuin": 9.2,
             "b3_volume_lod22": 284.0, "b3_pw_bron": "ahn5", "b3_pw_datum": 2023}
    return {"feature": {"CityObjects": {f"NL.IMBAG.Pand.{pand}": {"attributes": {**basis, **attrs}}}}}


def test_hoogte_rekent_om_naar_hoogte_boven_maaiveld():
    data = hoogte.verwerk(cityjson("p1"), "p1")
    assert data["hoogte_m"] == pytest.approx(5.8)     # 2.0 - (-3.8): NAP-hoogte -> boven maaiveld
    assert data["nokhoogte_m"] == pytest.approx(9.5)
    assert data["bouwlagen"] == 2 and data["dak_type"] == "slanted"
    assert data["meting"] == "AHN5 2023"


def test_hoogte_haalt_meerdere_panden_tegelijk_en_slaat_onbekende_over():
    def handler(request):
        pand = request.url.path.rsplit(".", 1)[-1]
        if pand == "p2":
            return httpx.Response(404, json={"detail": "not found"})
        return httpx.Response(200, json=cityjson(pand, b3_opp_dak_plat=100.0, b3_bouwlagen=4))

    data = run(hoogte.haal(client_met(handler), ["p1", "p2", "p3"]))
    assert data["opgevraagd"] == 3 and data["gevonden"] == 2
    assert data["per_pand"]["p2"] is None
    assert data["dak_plat_m2"] == 200.0 and data["meeste_bouwlagen"] == 4


def test_hoogte_beperkt_het_aantal_panden(monkeypatch):
    monkeypatch.setattr(hoogte, "MAX_PANDEN", 2)
    opgevraagd = []

    def handler(request):
        opgevraagd.append(request.url.path)
        return httpx.Response(200, json=cityjson("x"))

    data = run(hoogte.haal(client_met(handler), ["a", "b", "c", "d"]))
    assert len(opgevraagd) == 2 and data["overgeslagen"] == 2


def test_hoogte_een_haperend_pand_breekt_de_bron_niet(monkeypatch):
    """De 3D BAG gaf live soms een losse 502. Eén pand dat (ook na een retry) faalt, telt als mislukt."""
    monkeypatch.setattr(hoogte, "RETRY_WACHT_S", 0)
    pogingen = {"p1": 0, "p2": 0, "p3": 0}

    def handler(request):
        pand = request.url.path.rsplit(".", 1)[-1]
        pogingen[pand] += 1
        if pand == "p2":
            return httpx.Response(502)                        # blijft stuk
        if pand == "p3" and pogingen["p3"] == 1:
            return httpx.Response(502)                        # eerste keer stuk, retry lukt
        return httpx.Response(200, json=cityjson(pand))

    data = run(hoogte.haal(client_met(handler), ["p1", "p2", "p3"]))
    assert data["gevonden"] == 2 and data["mislukt"] == 1
    assert "p2" not in data["per_pand"] and data["per_pand"]["p3"] is not None
    assert pogingen == {"p1": 1, "p2": 2, "p3": 2}


def test_hoogte_geeft_fout_door_bij_serverstoring(monkeypatch):
    monkeypatch.setattr(hoogte, "RETRY_WACHT_S", 0)

    def handler(request):
        return httpx.Response(503)

    with pytest.raises(httpx.HTTPStatusError):
        run(hoogte.haal(client_met(handler), ["p1"]))


# ---------- erfgoed (RCE) ----------

def punt(x, y, **props) -> dict:
    basis = {"namespace": "nlps-rijksmonumenten", "localid": "27428.00",
             "ciCitation": "https://monumentenregister.cultureelerfgoed.nl/monumenten/18246",
             "legalfoundationdate": "1984-05-08"}
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [x, y]}, "properties": {**basis, **props}}


def test_erfgoed_monument_op_perceel_en_gezicht_eromheen():
    def handler(request):
        if request.url.params["TYPENAMES"].endswith("points"):
            return collectie(
                punt(121_250, 487_450),                             # midden op het perceel
                punt(121_301, 487_450, ciCitation="https://monumentenregister.cultureelerfgoed.nl/monumenten/3797"),  # 1 m buiten de grens: binnen de marge
                punt(121_350, 487_450, ciCitation="https://monumentenregister.cultureelerfgoed.nl/monumenten/1"),     # buurperceel
            )
        gezicht = {"type": "Feature", "geometry": mapping(PERCEEL.buffer(500)),
                   "properties": {"namespace": "nlps-stadsendorpsgezichten", "text": "Amsterdam - Binnen de Singelgracht",
                                  "legalfoundationdate": "1999-05-26"}}
        return collectie(gezicht)

    data = run(erfgoed.haal(client_met(handler), PERCEEL))
    # Het nummer komt uit de registerlink, niet uit `localid` (27428 is een intern id)
    assert [m["nummer"] for m in data["rijksmonumenten"]] == ["3797", "18246"]
    assert data["rijksmonumenten"][1]["sinds"] == "1984"
    assert data["gebieden"] == [{"soort": "beschermd stads- of dorpsgezicht", "naam": "Amsterdam - Binnen de Singelgracht",
                                 "url": None, "sinds": "1999"}]
    assert data["beschermd"] is True


def test_erfgoed_niets_gevonden():
    data = run(erfgoed.haal(client_met(lambda req: collectie()), PERCEEL))
    assert data == {"rijksmonumenten": [], "gebieden": [], "beschermd": False}


# ---------- buurt (CBS) ----------

CBS_VOORBEELD = {"buurtcode": "BU0363AD05", "buurtnaam": "Nieuwe Kerk e.o.", "wijkcode": "WK0363AD",
                 "gemeentenaam": "Amsterdam", "meestVoorkomendePostcode": "1012", "stedelijkheidAdressenPerKm2": 1,
                 "aantalInwoners": 825, "aantalHuishoudens": 565, "gemiddeldeHuishoudsgrootte": 1.5,
                 "woningvoorraad": 535, "gemiddeldeWoningwaarde": 498, "percentageKoopwoningen": 21,
                 "percentageHuurwoningen": 79, "percHuurwoningenInBezitWoningcorporaties": 6,
                 "percentageLeegstandWoningen": -99997, "gemiddeldGasverbruikTotaal": -99997}


def test_buurt_vertaalt_cbs_velden_en_afgeschermde_waarden():
    data = buurt.verwerk(CBS_VOORBEELD)
    assert data["buurt"] == "Nieuwe Kerk e.o." and data["gemeente"] == "Amsterdam"
    assert data["woz_gemiddeld_eur"] == 498_000          # CBS geeft x 1000 euro
    assert data["stedelijkheid"] == "zeer sterk stedelijk"
    assert data["huishoudsgrootte"] == 1.5
    assert data["leegstand_pct"] is None and data["gasverbruik_m3"] is None  # -99997 = geheim


def test_buurt_vraagt_op_bij_een_punt_binnen_het_perceel():
    def handler(request):
        minx, miny, maxx, maxy = (float(v) for v in request.url.params["BBOX"].split(",")[:4])
        assert PERCEEL.contains(box(minx, miny, maxx, maxy))
        return collectie({"type": "Feature", "geometry": None, "properties": CBS_VOORBEELD})

    data = run(buurt.haal(client_met(handler), PERCEEL))
    assert data["buurtcode"] == "BU0363AD05"


def test_buurt_geen_buurt_geeft_none():
    assert run(buurt.haal(client_met(lambda req: collectie()), PERCEEL)) is None


# ---------- signalen: meerdere bronnen, één conclusie ----------

def test_signalen_zonder_extra_bronnen_werkt_op_bebouwing_alleen():
    bebouwing = {"onbebouwd_m2": 2500.0, "bebouwingsgraad_pct": 40.0, "oudste_bouwjaar": 1380}
    uit = signalen.bepaal(bebouwing, None, None, None, None)
    assert [s["soort"] for s in uit] == ["kans", "let-op"]
    assert "2.500 m² onbebouwd (60%)" in uit[0]["tekst"]
    assert "1380" in uit[1]["tekst"] and uit[1]["bron"] == "BAG"


def test_signalen_combineren_alle_bronnen():
    uit = signalen.bepaal(
        {"onbebouwd_m2": 10.0, "bebouwingsgraad_pct": 98.0, "oudste_bouwjaar": 2005},
        {"aantal": 3, "gebruiksoppervlak_m2": 450, "per_gebruiksdoel": [{"gebruiksdoel": "woonfunctie"}]},
        {"dak_plat_m2": 320.0},
        {"rijksmonumenten": [{"nummer": "3797"}], "gebieden": []},
        {"buurt": "Nieuwe Kerk e.o.", "jaar": 2024, "woz_gemiddeld_eur": 498_000, "huur_pct": 79, "corporatie_pct": 6, "leegstand_pct": 7},
    )
    teksten = " | ".join(s["tekst"] for s in uit)
    assert "Rijksmonument (nr. 3797)" in teksten
    assert "320 m² plat dak" in teksten and "~32 kWp" in teksten
    assert "3 adres(sen), 450 m²" in teksten and "vooral woon" in teksten
    assert "WOZ € 498.000" in teksten and "79% huur (6% corporatie)" in teksten
    assert "Leegstand in de buurt: 7%" in teksten
    assert "onbebouwd" not in teksten and "isolatie" not in teksten  # drempels niet gehaald


def test_signalen_zijn_serialiseerbaar():
    json.dumps(signalen.bepaal({"onbebouwd_m2": 300.0, "bebouwingsgraad_pct": 50.0, "oudste_bouwjaar": None}, None, None, None, None))
