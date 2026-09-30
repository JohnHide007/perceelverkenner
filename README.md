# Perceelverkenner

Interactieve kaart van Nederland: klik een kadastraal perceel aan en zie wat erop staat. Next.js + FastAPI + Docker Compose, met open data van PDOK.

## Structuur
- `frontend/` – Next.js-app met kaart en kadastrale WMS-laag (PDOK)
- `backend/` – FastAPI-service die percelen verrijkt

## Starten

    docker compose up --build

Daarna: http://localhost:3000

## Tests

Backend (29 tests, geen netwerk nodig: PDOK wordt nagebootst):

    cd backend
    pip install -r requirements-dev.txt
    pytest -v

Bij elke pull request draait GitHub Actions (`.github/workflows/ci.yml`) de backend-tests, lint + typecheck + build van de frontend, en een check op `docker-compose.yml`.
