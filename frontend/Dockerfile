# syntax=docker/dockerfile:1
FROM node:22-alpine AS build
WORKDIR /app
COPY frontend/package*.json ./
# BuildKit cache saves fetched npm tarballs between future builds.
# Replace with npm ci after committing a verified package-lock.json.
RUN --mount=type=cache,id=superapp-bgremoval-npm-node22,target=/root/.npm,sharing=locked \
    npm install --no-audit --no-fund --prefer-offline
COPY frontend/ ./
RUN npm run build

FROM nginx:1.27-alpine
COPY ops/nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=4s --start-period=10s CMD wget -q -O /dev/null http://127.0.0.1:80/healthz || exit 1
