# ---- Fase 1: dependencies (gecached zolang package-lock.json niet verandert)
FROM node:24-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
# ipv4first + minder sockets: omzeilt de npm-ETIMEDOUT die we lokaal zagen
RUN NODE_OPTIONS=--dns-result-order=ipv4first \
    npm ci --maxsockets=3 --fetch-retries=5 --fetch-timeout=300000

# ---- Fase 2: bouwen
FROM node:24-slim AS build
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

# ---- Fase 3: draaien (alleen het resultaat van de build, geen broncode of devDependencies)
FROM node:24-slim AS run
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0
COPY --from=build --chown=node:node /app/.next/standalone ./
COPY --from=build --chown=node:node /app/.next/static ./.next/static
USER node
EXPOSE 3000
CMD ["node", "server.js"]
