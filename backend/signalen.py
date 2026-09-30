"""Meerdere bronnen, één conclusie: korte, herleidbare signalen over het perceel.

Elke regel hier is bewust simpel en transparant: een drempel, een tekst en de bron waar het
signaal op steunt. Geen model, geen black box. Als een bron ontbreekt, vallen de bijbehorende
signalen gewoon weg.

Soorten: "kans" (ontwikkel- of verduurzamingspotentieel), "let-op" (beperking of risico),
"info" (context die je wilt weten).
"""

KWP_PER_M2_PLAT_DAK = 0.1   # indicatief: ~10 m² plat dak per kWp, inclusief loopruimte en schaduw
ISOLATIE_EISEN_SINDS = 1992  # Bouwbesluit: vanaf dan gelden isolatie-eisen voor nieuwbouw


def _signaal(soort: str, tekst: str, bron: str) -> dict:
    return {"soort": soort, "tekst": tekst, "bron": bron}


def _nl(getal: float) -> str:
    """4474.7 -> '4.475' (Nederlandse duizendtallen, geen decimalen)."""
    return f"{getal:,.0f}".replace(",", ".")


def bepaal(bebouwing: dict, adressen: dict | None, hoogte: dict | None, erfgoed: dict | None, buurt: dict | None) -> list[dict]:
    signalen: list[dict] = []

    # --- erfgoed: beperkingen ---
    if erfgoed:
        monumenten = erfgoed.get("rijksmonumenten") or []
        if monumenten:
            nummers = ", ".join(m["nummer"] for m in monumenten if m.get("nummer"))
            signalen.append(
                _signaal(
                    "let-op",
                    f"Rijksmonument (nr. {nummers}): verbouwen en verduurzamen zijn vergunningplichtig.",
                    "RCE",
                )
            )
        for gebied in erfgoed.get("gebieden") or []:
            naam = f" '{gebied['naam']}'" if gebied.get("naam") else ""
            signalen.append(_signaal("let-op", f"Ligt in {gebied['soort']}{naam}: welstand en bestemming zijn strenger.", "RCE"))

    # --- bebouwing: ontwikkelruimte en bouwjaar ---
    onbebouwd = bebouwing.get("onbebouwd_m2") or 0
    graad = bebouwing.get("bebouwingsgraad_pct")
    if graad is not None and onbebouwd >= 200 and graad <= 70:
        signalen.append(
            _signaal("kans", f"{_nl(onbebouwd)} m² onbebouwd ({100 - graad:.0f}%): ruimte voor uitbreiding of buitenruimte.", "Kadaster + BAG")
        )
    oudste = bebouwing.get("oudste_bouwjaar")
    if oudste and oudste < ISOLATIE_EISEN_SINDS:
        signalen.append(
            _signaal("let-op", f"Oudste pand uit {oudste}: gebouwd vóór de isolatie-eisen van {ISOLATIE_EISEN_SINDS}, reken op een verduurzamingsopgave.", "BAG")
        )

    # --- 3D: zonnepotentieel ---
    if hoogte and (hoogte.get("dak_plat_m2") or 0) >= 50:
        plat = hoogte["dak_plat_m2"]
        kwp = plat * KWP_PER_M2_PLAT_DAK
        signalen.append(
            _signaal("kans", f"{_nl(plat)} m² plat dak: indicatief ruimte voor ~{_nl(kwp)} kWp zonnepanelen.", "3D BAG")
        )

    # --- adressen: gebruik ---
    if adressen and adressen.get("aantal"):
        top = (adressen.get("per_gebruiksdoel") or [{}])[0]
        doel = top.get("gebruiksdoel", "").replace("functie", "")
        signalen.append(
            _signaal(
                "info",
                f"{adressen['aantal']} adres(sen), {_nl(adressen.get('gebruiksoppervlak_m2') or 0)} m² gebruiksoppervlak; vooral {doel or 'onbekend'}.",
                "BAG",
            )
        )

    # --- buurt: markt ---
    if buurt:
        delen = []
        if buurt.get("woz_gemiddeld_eur"):
            delen.append(f"gemiddelde WOZ € {_nl(buurt['woz_gemiddeld_eur'])}")
        if buurt.get("huur_pct") is not None:
            corp = f" ({buurt['corporatie_pct']}% corporatie)" if buurt.get("corporatie_pct") is not None else ""
            delen.append(f"{buurt['huur_pct']}% huur{corp}")
        if delen:
            signalen.append(_signaal("info", f"Buurt {buurt.get('buurt') or '?'}: " + ", ".join(delen) + ".", f"CBS {buurt.get('jaar')}"))
        if (buurt.get("leegstand_pct") or 0) >= 5:
            signalen.append(_signaal("let-op", f"Leegstand in de buurt: {buurt['leegstand_pct']}% van de woningen.", f"CBS {buurt.get('jaar')}"))

    return signalen
