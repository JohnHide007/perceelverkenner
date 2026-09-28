# Perceelverkenner

Interactieve kaart van Nederland: klik een kadastraal perceel aan en zie wat erop staat. Next.js + FastAPI + Docker Compose, met open data van PDOK.

## Structuur
- `frontend/` – Next.js-app met kaart en kadastrale WMS-laag (PDOK)
- `backend/` – FastAPI-service die percelen verrijkt

## Starten

    docker compose up --build

Daarna: http://localhost:3000
