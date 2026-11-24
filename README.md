# Tirei Você! 🎁

Plataforma web de amigo secreto (e variações como Amigo da Onça e Amigo Calcinha): crie o grupo,
compartilhe o link no WhatsApp, cada um monta sua lista de desejos e o sorteio respeita as
restrições (casais, famílias, pares bloqueados). Cada pessoa vê **apenas** quem tirou.

| Pasta | O quê |
|---|---|
| `apps/api` | API em Python 3.12 + FastAPI, SQLAlchemy 2 async, Alembic, arq (gerenciada com **uv**) |
| `apps/web` | SPA React 18 + TypeScript + Vite + Tailwind + TanStack Query (gerenciada com **pnpm**) |
| `infra` | `docker-compose.yml` (dev) e `docker-compose.prod.yml` (simulação de produção) |
| `.github/workflows/ci.yml` | Lint, tipos, testes, contrato OpenAPI e build das imagens |
| `render.yaml` | Blueprint de deploy no Render |

## Como rodar (dev)

Pré-requisitos: Docker com Compose v2 e `make`.

```bash
cp .env.example .env
make dev
```

- App: http://localhost:5173
- API: http://localhost:8000 (Swagger em http://localhost:8000/api/docs)

O compose sobe Postgres 16, Redis 7, API, worker e web, com **hot reload** no back (uvicorn
`--reload` e `watchfiles` no worker) e no front (Vite). Migrations e seed dos temas rodam
automaticamente ao subir a API.

**E-mails em dev:** nada é enviado de verdade. O link de verificação e o de redefinição de senha
aparecem no log do worker:

```bash
docker compose -f infra/docker-compose.yml logs -f worker   # procure por "verify-email?token="
```

### Comandos

| Comando | O que faz |
|---|---|
| `make dev` / `make down` | Sobe / derruba o ambiente de desenvolvimento |
| `make test` | Testes do back (Postgres real do compose) e do front |
| `make lint` | ruff + mypy (back), ESLint + Prettier + tsc (front) |
| `make migrate` | `alembic upgrade head` dentro do container |
| `make migration m="descrição"` | Gera uma migration nova (autogenerate) |
| `make seed` | Carrega os temas iniciais (idempotente) |
| `make api-types` | Regenera `openapi.json` e os tipos TypeScript do front |
| `make keys` | Gera `JWT_SECRET`, `DRAW_ENCRYPTION_KEY` e `DRAW_HMAC_KEY` |
| `make prod-up` | Sobe as imagens de produção em http://localhost:8080 |

Para rodar testes e lint fora do Docker: instale [uv](https://docs.astral.sh/uv/) e
[pnpm 9](https://pnpm.io/), rode `(cd apps/api && uv sync)` e `(cd apps/web && pnpm install)`.
Os testes do back usam o Postgres e o Redis do compose (`make dev` rodando), num banco separado
`tirei_voce_test`.

## Variáveis de ambiente

Todas documentadas em [`.env.example`](.env.example). As principais:

| Variável | Obrigatória em produção | Descrição |
|---|---|---|
| `ENVIRONMENT` | sim | `development`, `test` ou `production` (ativa as travas abaixo) |
| `FRONTEND_URL` | sim | Origem do front: CORS e links dos e-mails |
| `DATABASE_URL` | sim | Postgres (`postgres://` e `postgresql://` são convertidos para asyncpg) |
| `REDIS_URL` | sim | Redis: fila do worker, rate limit, state do OAuth e idempotência |
| `JWT_SECRET` | sim | ≥ 32 caracteres. Assina o access token (15 min) |
| `DRAW_ENCRYPTION_KEY` | sim | Chave **Fernet** que cifra o resultado do sorteio |
| `DRAW_HMAC_KEY` | sim | ≥ 32 caracteres. HMAC de busca e de integridade do sorteio |
| `COOKIE_SECURE` | sim (`true`) | `false` só em dev (http) |
| `EMAIL_PROVIDER` | — | `console` (dev) ou `resend` |
| `RESEND_API_KEY`, `EMAIL_FROM` | com Resend | Envio de e-mail transacional |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` | não | Login com Google (sem elas o botão some) |
| `SENTRY_DSN` | não | Sentry desligado por padrão |

Em produção a API **se recusa a subir** com os segredos padrão de dev, `JWT_SECRET` curto ou
`COOKIE_SECURE=false`.

> ⚠️ Trocar `DRAW_ENCRYPTION_KEY` ou `DRAW_HMAC_KEY` depois de um sorteio torna os resultados
> antigos ilegíveis. Guarde-as num cofre.

## Arquitetura

```
Navegador ──► web (nginx: SPA + proxy /api) ──► api (FastAPI, N réplicas) ──► Postgres
                                                     │
                                                     └──► Redis ◄── worker (arq: e-mails)
```

- **Mesma origem:** o nginx serve o SPA e repassa `/api/*` para a API (em dev, o proxy do Vite faz
  o mesmo). Por isso os cookies `SameSite=Lax` funcionam sem CORS entre domínios, e a API pode
  ficar só na rede privada.
- **Stateless:** nada fica em memória entre requisições. Sessão em cookies, state/PKCE do OAuth,
  rate limit e `Idempotency-Key` no Redis. Dá para rodar várias réplicas da API.
- **Backend em camadas:** cada domínio em `app/modules/<mod>/` com
  `models → repository → service → router`. Routers só fazem HTTP, as regras de negócio ficam nos
  services e o acesso ao banco nos repositories. Módulos: `auth`, `users`, `groups`,
  `participants`, `wishlist`, `rules`, `draws`, `notifications`.
- **Máquina de estados do grupo:** `DRAFT → OPEN ⇄ CLOSED → DRAWN → FINISHED`. Toda transição
  passa por `groups.service.transition()`; ações proibidas no estado atual retornam **409**.
- **Autorização:** quem não participa de um grupo recebe **404** (não revela que ele existe);
  ações de organizador retornam 403 para membros.
- **Erros** sempre como `{ "error": { "code", "message" } }`, com mensagens em pt-BR.
- **Observabilidade:** logs em JSON com `request_id` (propagado pelo nginx) e Sentry opcional,
  configurado para não coletar corpos, variáveis locais nem dados pessoais.
- **Frontend:** tipos gerados do OpenAPI (`openapi-typescript`). O client HTTP envia o token CSRF
  (double-submit) e renova a sessão uma única vez em caso de 401.

### Autenticação

- Senhas com **Argon2id**, mínimo de 8 caracteres e bloqueio de senhas comuns.
- Access token JWT de 15 min + refresh token opaco de 30 dias, guardado só como hash e
  **rotacionado** a cada uso. Reusar um refresh antigo revoga todas as sessões do usuário.
- Cookies `HttpOnly`, `Secure`, `SameSite=Lax` + CSRF double-submit (`X-CSRF-Token`).
- Verificação de e-mail obrigatória para criar e entrar em grupos (token de uso único, 24 h).
  Reset de senha por token de 1 h, com resposta sempre genérica.
- Google: Authorization Code + PKCE + `state` (amarrado a cookie) + `nonce`; o `id_token` é
  validado contra o JWKS do Google. Se já existe conta com o mesmo e-mail, ela é vinculada. Se
  essa conta tinha senha mas **nunca confirmou o e-mail**, a senha é removida (proteção contra
  pré-cadastro com e-mail alheio).
- Rate limit no Redis: login, cadastro, reset, reenvio de verificação, preview e entrada por
  convite.

### Sorteio e sigilo

- O motor (`app/modules/draws/engine.py`) é **puro** (sem I/O). Ele monta o grafo de arestas
  permitidas (sem auto-sorteio, círculos de exclusão e pares bloqueados) e valida a viabilidade
  com **Hopcroft–Karp**. Primeiro tenta um **ciclo único** (A→B→C→…→A) por backtracking aleatório
  com orçamento de passos; se não achar, cai no emparelhamento perfeito aleatório. Toda a
  aleatoriedade vem de `secrets.SystemRandom`.
- Testes de propriedade (hypothesis) garantem permutação válida e regras respeitadas, e comparam
  a detecção de casos impossíveis com força bruta.
- Execução em transação com `SELECT … FOR UPDATE` na linha do grupo + `Idempotency-Key`: dois
  cliques simultâneos geram um único sorteio.
- No banco, `receiver_encrypted` é cifrado com Fernet. `receiver_lookup_hash` é um HMAC
  (necessário para o chat anônimo da Fase 2) e `seed_hash` é o HMAC do resultado completo
  (detecta adulteração).
- **Nenhum endpoint devolve pares**, nem para o organizador: o único é `GET /groups/{id}/my-match`.
  Um teste varre todas as rotas GET do OpenAPI como organizador procurando pares alheios.
  Nenhum log contém pares.

## Deploy

As imagens de produção são multi-stage e rodam com **usuário não root**:

| Imagem | Build | Processo |
|---|---|---|
| api | `docker build --target api apps/api` | uvicorn (porta `$PORT`, `WEB_CONCURRENCY` workers) |
| worker | `docker build --target worker apps/api` | `arq app.workers.main.WorkerSettings` |
| web | `docker build --target web apps/web` | nginx-unprivileged (porta 8080) |

Antes de cada deploy da API rode as migrations: `alembic upgrade head && python -m app.seed`.

Para testar as imagens localmente: `make keys >> .env`, depois `make prod-up` e abra
http://localhost:8080. Em http puro os cookies `Secure` não funcionam no Safari; use Chrome ou
Firefox, que tratam `localhost` como seguro.

### Render

1. Faça o fork/push do repositório e, no Render, crie um **Blueprint** apontando para ele. O
   `render.yaml` cria o web (público), a API (serviço privado), o worker, o Postgres e o Key Value.
2. Preencha as variáveis marcadas como `sync: false` no grupo `tirei-voce`:
   - `FRONTEND_URL`: a URL pública do web (ex.: `https://tirei-voce-web.onrender.com`);
   - `GOOGLE_REDIRECT_URI`: `<FRONTEND_URL>/api/v1/auth/google/callback`;
   - `DRAW_ENCRYPTION_KEY`: saída de `make keys`;
   - `RESEND_API_KEY` e `EMAIL_FROM`.

   `JWT_SECRET` e `DRAW_HMAC_KEY` são gerados pelo Render.
3. As migrations rodam no `preDeployCommand` da API.
4. No Google Cloud Console, cadastre `GOOGLE_REDIRECT_URI` como *Authorized redirect URI*.

### Railway

1. Crie um projeto com **Postgres** e **Redis** (plugins).
2. Crie três serviços a partir do repositório, todos com builder **Dockerfile**. O último estágio
   de cada Dockerfile é o de produção (`api` e `web`), então não é preciso escolher target.

   | Serviço | Root directory | Start command | Rede |
   |---|---|---|---|
   | `api` | `apps/api` | (padrão da imagem) | só privada |
   | `worker` | `apps/api` | `arq app.workers.main.WorkerSettings` | só privada |
   | `web` | `apps/web` | (padrão da imagem) | domínio público |

3. Variáveis:
   - **api** e **worker:** `DATABASE_URL=${{Postgres.DATABASE_URL}}`,
     `REDIS_URL=${{Redis.REDIS_URL}}`, mais os segredos da tabela acima e `ENVIRONMENT=production`.
   - **api:** também `HOST=::`, porque a rede privada do Railway é IPv6.
   - **web:** `API_UPSTREAM=http://api.railway.internal:8000` e `REAL_IP_FROM` com a faixa de
     IPs do proxy de borda do Railway.
4. Em **api**, configure o *Pre-deploy command*: `alembic upgrade head && python -m app.seed`.

> `REAL_IP_FROM` define em quais saltos o nginx confia para descobrir o IP real do visitante
> (usado no rate limit). Com `0.0.0.0/0` tudo funciona, mas um cliente pode forjar o
> `X-Forwarded-For` e driblar o limite por IP. Os limites por e-mail e por usuário continuam
> valendo.

## Fases

- **Fase 1 (MVP, implementada):** contas, grupos, convites, listas, regras, sorteio e todas as
  telas.
- **Fase 2:** chat anônimo, "presente comprado", lembretes, PWA/push, coorganizadores.
- **Fase 3:** sorteio agendado, não repetir pares, revelação no evento, WhatsApp, painel admin,
  LGPD (exclusão de conta).
