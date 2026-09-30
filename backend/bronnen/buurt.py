"""Buurtcijfers van het CBS (Kerncijfers wijken en buurten) rond het perceel.

Het CBS publiceert per buurt honderden kengetallen. Wij pakken de handvol die iets zeggen over
de markt waarin het perceel ligt: woningwaarde, koop/huur, stedelijkheid, dichtheid en
voorzieningen. Waarden die het CBS afschermt (te weinig waarnemingen) komen als -99997 binnen;
die worden hier `None`.
"""

import httpx
from shapely.geometry.base import BaseGeometry

from . import features, haal_json, wfs_params

JAAR = 2024
NAAM = f"Buurtcijfers (CBS {JAAR})"
URL = f"https://service.pdok.nl/cbs/wijkenbuurten/{JAAR}/wfs/v1_0"
STEDELIJKHEID = {1: "zeer sterk stedelijk", 2: "sterk stedelijk", 3: "matig stedelijk", 4: "weinig stedelijk", 5: "niet stedelijk"}

# CBS-veld -> (onze naam, schaal). Schaal 1000 zet 'x 1000 euro' om naar euro.
VELDEN = {
    "aantalInwoners": ("inwoners", 1),
    "aantalHuishoudens": ("huishoudens", 1),
    "gemiddeldeHuishoudsgrootte": ("huishoudsgrootte", 1),
    "bevolkingsdichtheidInwonersPerKm2": ("inwoners_per_km2", 1),
    "omgevingsadressendichtheid": ("adressen_per_km2", 1),
    "woningvoorraad": ("woningen", 1),
    "gemiddeldeWoningwaarde": ("woz_gemiddeld_eur", 1000),
    "percentageKoopwoningen": ("koop_pct", 1),
    "percentageHuurwoningen": ("huur_pct", 1),
    "percHuurwoningenInBezitWoningcorporaties": ("corporatie_pct", 1),
    "percentageEengezinswoning": ("eengezins_pct", 1),
    "percentageMeergezinswoning": ("meergezins_pct", 1),
    "percentageBouwjaarklasseVanaf2000": ("bouwjaar_vanaf_2000_pct", 1),
    "percentageLeegstandWoningen": ("leegstand_pct", 1),
    "aantalBedrijfsvestigingen": ("bedrijfsvestigingen", 1),
    "gemiddeldGasverbruikTotaal": ("gasverbruik_m3", 1),
    "gemiddeldElektriciteitsverbruikTotaal": ("elektriciteitsverbruik_kwh", 1),
    "percentageWoningenMetStadsverwarming": ("stadsverwarming_pct", 1),
    "groteSupermarktGemiddeldeAfstandInKm": ("afstand_supermarkt_km", 1),
    "huisartsenpraktijkGemiddeldeAfstandInKm": ("afstand_huisarts_km", 1),
    "oppervlakteTotaalInHa": ("oppervlakte_ha", 1),
}


def _waarde(raw, schaal: int):
    try:
        getal = float(raw)
    except (TypeError, ValueError):
        return None
    if getal <= -99990:  # CBS-code voor 'geheim' of 'onbekend'
        return None
    getal *= schaal
    return int(getal) if getal.is_integer() else round(getal, 1)


def verwerk(props: dict) -> dict:
    """Vertaalt de CBS-velden naar onze eigen namen en maakt afgeschermde waarden None."""
    cijfers = {naam: _waarde(props.get(veld), schaal) for veld, (naam, schaal) in VELDEN.items()}
    stedelijkheid = _waarde(props.get("stedelijkheidAdressenPerKm2"), 1)
    return {
        "buurt": props.get("buurtnaam"),
        "buurtcode": props.get("buurtcode"),
        "wijkcode": props.get("wijkcode"),
        "gemeente": props.get("gemeentenaam"),
        "postcode": props.get("meestVoorkomendePostcode") or None,
        "stedelijkheid": STEDELIJKHEID.get(int(stedelijkheid)) if stedelijkheid else None,
        "jaar": JAAR,
        **cijfers,
    }


async def haal(client: httpx.AsyncClient, perceel_rd: BaseGeometry) -> dict | None:
    """De buurt waarin het zwaartepunt van het perceel ligt."""
    c = perceel_rd.representative_point()  # ligt gegarandeerd binnen het perceel, ook bij een L-vorm
    bbox = (c.x - 0.5, c.y - 0.5, c.x + 0.5, c.y + 0.5)
    antwoord = await haal_json(client, URL, wfs_params("wijkenbuurten:buurten", bbox, 1))
    gevonden = features(antwoord)
    if not gevonden:
        return None
    return verwerk(gevonden[0].get("properties") or {})
