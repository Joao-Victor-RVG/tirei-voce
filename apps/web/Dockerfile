# syntax=docker/dockerfile:1.7
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
