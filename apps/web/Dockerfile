# Alvos: dev (compose) e web (produção: nginx servindo o SPA e repassando /api para a API).
FROM node:22-alpine AS base
RUN npm install -g pnpm@9
WORKDIR /app

# ---- dev: Vite com hot reload, código montado via volume ----
FROM base AS dev
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY . .
EXPOSE 5173
CMD ["pnpm", "dev"]

# ---- build ----
FROM base AS build
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY . .
RUN pnpm build

# ---- web: nginx sem root (porta 8080) ----
FROM nginxinc/nginx-unprivileged:1.27-alpine AS web
ENV PORT=8080 \
    API_HOSTPORT=api:8000 \
    REAL_IP_FROM=10.0.0.0/8
COPY nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s CMD wget -qO- "http://127.0.0.1:${PORT}/healthz" >/dev/null || exit 1
