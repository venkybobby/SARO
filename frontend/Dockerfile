# ── Stage 1: Build React/Vite app ────────────────────────────────────────────
# Build context = REPO ROOT.
# Deploy with: flyctl deploy --config frontend/fly.toml --app sarofrontend
#   --build-arg VITE_SARO_API_URL=https://saro-backend.fly.dev

FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files first for better layer caching.
# Paths are relative to build context (repo root).
COPY frontend/package*.json ./
RUN npm ci

# Copy frontend source
COPY frontend/ .

# VITE_* build args — baked into the static bundle at build time.
# Cannot be changed after the image is built.
ARG VITE_SARO_API_URL
ARG VITE_APP_ENV=production

ENV VITE_SARO_API_URL=$VITE_SARO_API_URL
ENV VITE_APP_ENV=$VITE_APP_ENV

RUN npm run build

# ── Stage 2: Serve with nginx ─────────────────────────────────────────────────
FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html

# nginx.conf path is relative to build context (repo root)
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
