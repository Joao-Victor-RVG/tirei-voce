# Tirei Você! 🎁

Plataforma de amigo secreto (e variações como Amigo da Onça e Amigo Calcinha).

Monorepo:

| Pasta | O quê |
|---|---|
| `apps/api` | API em Python 3.12 + FastAPI (gerenciada com **uv**) |
| `apps/web` | Frontend React 18 + TypeScript + Vite (gerenciado com **pnpm**) |
| `infra` | `docker-compose.yml` para desenvolvimento |

## Como rodar

Pré-requisitos: Docker (com Compose v2) e `make`.

```bash
cp .env.example .env
make dev
```

- Frontend: http://localhost:5173
- API: http://localhost:8000 (docs em http://localhost:8000/docs)

Back e front têm hot reload: edite os arquivos e o container recarrega.

### Rodando testes e lint localmente

Requer [uv](https://docs.astral.sh/uv/) e [pnpm](https://pnpm.io/) 9.

```bash
(cd apps/api && uv sync)
(cd apps/web && pnpm install)
make test
make lint
```

Rode `make help` para ver todos os comandos.
