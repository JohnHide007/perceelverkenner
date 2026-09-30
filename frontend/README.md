# Perceelverkenner: frontend

Next.js-app (App Router) met een Leaflet-kaart. Zie de [README in de hoofdmap](../README.md) voor het geheel.

| Bestand | Rol |
|---|---|
| `app/page.tsx` | Kaart en zijpaneel; stuurt een klik naar `/api/perceel` |
| `app/api/perceel/route.ts` | API-route (server-side): klikpunt → PDOK `GetFeatureInfo` → backend `/verrijk` |
| `components/Kaart.tsx` | Leaflet-kaart met de PDOK-achtergrond en de kadastrale WMS-laag; tekent perceel en panden |
| `components/Zijpaneel.tsx` | Kengetallen, panden, afgevallen kandidaten en waarschuwingen |
| `lib/types.ts` | Vorm van het antwoord van de backend |

## Lokaal draaien

```bash
npm install
npm run dev
```

Open http://localhost:3000. De backend moet draaien op het adres in `BACKEND_URL` (standaard `http://localhost:8000`, zie `.env.example`). Dat adres wordt alleen server-side gebruikt; de browser praat nooit direct met de backend.

## Controles

```bash
npm run lint
npx tsc --noEmit
npm run build
```

Dezelfde controles draaien in GitHub Actions bij elke pull request.
