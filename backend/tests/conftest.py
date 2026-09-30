"""Gedeelde testopzet: geen enkele test praat met het echte internet.

Elke `httpx.AsyncClient` krijgt standaard een nep-transport dat 'niets gevonden' teruggeeft
(lege FeatureCollection, 404 bij de 3D BAG). Tests die iets specifieks willen nabootsen,
geven hun eigen `transport=` mee (zie `nep_pdok` in test_pdok.py) of vervangen functies.
"""

import httpx
import pytest

ECHTE_CLIENT = httpx.AsyncClient  # vóór het patchen bewaren, anders patch je jezelf


def leeg_antwoord(request: httpx.Request) -> httpx.Response:
    if "3dbag" in request.url.host:
        return httpx.Response(404, json={"detail": "niet gevonden"})
    return httpx.Response(200, json={"type": "FeatureCollection", "features": []})


@pytest.fixture(autouse=True)
def geen_netwerk(monkeypatch):
    standaard = httpx.MockTransport(leeg_antwoord)
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: ECHTE_CLIENT(**{"transport": standaard, **kw}))
