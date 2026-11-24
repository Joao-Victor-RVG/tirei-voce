# Prompt — Projeto "Tirei Você!" 🎁

Você vai me ajudar a construir do zero o **Tirei Você!**, uma plataforma web de amigo secreto (e variações cômicas como "Amigo da Onça", "Amigo Calcinha" etc.). O repositório se chama `tirei-voce` e é um **monorepo**.

Quero algo **simples e robusto**: poucas peças móveis, código limpo, tipado, testado e pronto para escalar horizontalmente. Não adicione tecnologias além das listadas sem me perguntar antes.

---

## 1. Como você deve trabalhar

1. **Antes de escrever código**, leia este documento inteiro e me apresente um plano curto da Fase 1 (estrutura de pastas + ordem de implementação). Espere meu OK.
2. Implemente **em pequenos passos**, cada um terminando com o projeto rodando e os testes passando. Faça um commit por passo, com mensagens no padrão Conventional Commits (`feat:`, `fix:`, `chore:`…).
3. Implemente **somente a Fase 1** (seção 10) até eu pedir as próximas.
4. Quando algo deste documento for ambíguo ou conflitante, **pergunte** em vez de supor.
5. Código, nomes de variáveis, tabelas e endpoints em **inglês**; textos da interface e mensagens ao usuário em **português (pt-BR)**.
6. Ao final de cada passo, me diga em poucas linhas o que foi feito e como testar.

---

## 2. Stack técnica (definida)

| Camada | Tecnologia |
|---|---|
| Backend | **Python 3.12 + FastAPI**, Pydantic v2, **SQLAlchemy 2 (async)** + asyncpg, **Alembic** para migrations |
| Banco | **PostgreSQL 16** |
| Cache / filas / rate limit | **Redis 7** + **arq** (worker de jobs assíncronos) |
| Frontend | **React 18 + TypeScript + Vite**, **Tailwind CSS**, **TanStack Query**, React Router, React Hook Form + Zod |
| Autenticação | **E-mail e senha** + **Login com Google (OAuth 2.0 / OIDC)** |
| E-mail transacional | Provedor via API (ex.: Resend) atrás de uma interface `EmailSender`; em dev, um sender que só loga no console |
| Infra | **Docker** (imagens separadas para api, worker e web) + **docker-compose** para dev; deploy em **Render ou Railway** |
| Qualidade | Backend: **ruff**, **mypy**, **pytest** (+ pytest-asyncio, httpx). Frontend: **ESLint**, **Prettier**, **Vitest** + Testing Library |
| CI | **GitHub Actions**: lint + type-check + testes em todo PR |
| Gerenciador de pacotes | Backend: **uv**. Frontend: **pnpm** |

---

## 3. Estrutura do monorepo

```
tirei-voce/
├── apps/
│   ├── api/                # FastAPI
│   │   ├── app/
│   │   │   ├── core/       # config, security, db, redis, logging
│   │   │   ├── modules/    # um pacote por domínio: auth, users, groups, participants,
│   │   │   │               # rules, wishlist, draws, notifications
│   │   │   │   └── <mod>/  # models.py, schemas.py, repository.py, service.py, router.py
│   │   │   ├── workers/    # jobs do arq
│   │   │   └── main.py
│   │   ├── migrations/     # Alembic
│   │   └── tests/
│   └── web/                # React + Vite
│       └── src/
│           ├── api/        # client HTTP + hooks do TanStack Query
│           ├── features/   # auth, groups, wishlist, draw...
│           ├── components/ # UI reutilizável
│           └── pages/
├── infra/
│   └── docker-compose.yml
├── .github/workflows/ci.yml
├── .env.example
└── README.md
```

Regra de arquitetura do backend: **router → service → repository**. Routers só fazem HTTP; regras de negócio ficam nos services; acesso ao banco só nos repositories.

---

## 4. Domínio e jornada do usuário

1. O usuário cria uma conta (e-mail + senha ou Google) e faz login.
2. Cria um **grupo**: escolhe o **tipo/tema** (Amigo Secreto, Amigo da Onça, Amigo Calcinha ou nome personalizado), define **valor mínimo e máximo** do presente, **data, hora e local** do evento, **prazo de inscrição** e regras.
3. Compartilha um **link/código de convite**.
4. Os amigos entram no grupo e preenchem a **lista de desejos** e o que **não querem ganhar**.
5. O organizador configura **restrições** (ex.: casais não se tiram) e executa o **sorteio**.
6. Cada participante vê **apenas** quem tirou e a lista de desejos dessa pessoa.

### Ciclo de vida do grupo (máquina de estados)

`DRAFT → OPEN → CLOSED → DRAWN → FINISHED`

- `DRAFT`: organizador configurando; ninguém entra ainda.
- `OPEN`: convites ativos; participantes entram e editam listas; restrições editáveis.
- `CLOSED`: inscrições fechadas; ninguém entra; restrições ainda editáveis.
- `DRAWN`: sorteio feito; regras e participantes **congelados**.
- `FINISHED`: evento passou; grupo somente leitura.

Toda transição passa por um único método do service que valida a transição permitida. Ações proibidas no estado atual retornam **409 Conflict** com mensagem clara.

---

## 5. Modelo de dados (Fase 1)

Use UUID (v7, se possível) como PK, `created_at`/`updated_at` em todas as tabelas, timestamps com timezone (armazenar em UTC; exibir em `America/Sao_Paulo`). Valores monetários em **centavos (integer)**.

- **users**: id, name, email (único, case-insensitive), password_hash (nullable p/ contas só Google), google_sub (único, nullable), email_verified_at, avatar_url, shirt_size, shoe_size, is_active.
- **refresh_tokens**: id, user_id, token_hash, expires_at, revoked_at, user_agent, ip.
- **email_tokens**: id, user_id, purpose (`verify_email` | `reset_password`), token_hash, expires_at, used_at.
- **group_themes**: id, slug, display_name, emoji, description. Seed inicial: `amigo-secreto`, `amigo-da-onca`, `amigo-calcinha`.
- **groups**: id, owner_id, theme_id, custom_name (nullable), title, description, min_value_cents, max_value_cents, event_at, event_location, event_maps_url, join_deadline_at, status, invite_code (aleatório, não sequencial, único), max_participants (default 100).
- **participants**: id, group_id, user_id, role (`owner` | `co_owner` | `member`), joined_at, left_at. Único por (group_id, user_id).
- **wishlist_items**: id, participant_id, title, url, price_hint_cents, priority (1–3), notes.
- **participant_preferences**: participant_id, dislikes (texto), notes (texto).
- **exclusion_circles**: id, group_id, name (ex.: "Casal João e Maria", "Família Silva").
- **exclusion_circle_members**: circle_id, participant_id. Ninguém de um mesmo círculo pode tirar outro membro dele.
- **blocked_pairs**: id, group_id, giver_participant_id, receiver_participant_id, bidirectional (bool).
- **draws**: id, group_id, version, executed_by, executed_at, seed_hash. Único por (group_id, version); só a versão mais recente é válida.
- **draw_assignments**: id, draw_id, giver_participant_id, receiver_encrypted, receiver_lookup_hash.

### Sigilo do sorteio (requisito crítico)

- `receiver_encrypted` = receiver_participant_id criptografado com **Fernet** (chave `DRAW_ENCRYPTION_KEY` via env).
- `receiver_lookup_hash` = `HMAC-SHA256(DRAW_HMAC_KEY, draw_id + receiver_participant_id)`, para permitir buscar "quem me tirou" (necessário no chat anônimo da Fase 2) sem expor o par em claro.
- **Nenhum endpoint** retorna pares de outras pessoas, nem para o organizador. O único endpoint é "meu amigo secreto", que retorna o receiver do participante autenticado.
- Não logue pares em nenhum lugar (logs, erros, Sentry).
- Escreva testes que garantam que o organizador **não** consegue obter os pares por nenhum endpoint.

---

## 6. Motor de regras e algoritmo do sorteio

Entrada: participantes ativos do grupo + `exclusion_circles` + `blocked_pairs`.

1. Monte o grafo de **arestas permitidas** `giver → receiver`, removendo:
   - a própria pessoa;
   - membros do mesmo círculo de exclusão;
   - pares bloqueados (nos dois sentidos se `bidirectional`).
2. **Validação de viabilidade**: verifique se existe um **emparelhamento perfeito** no grafo bipartido (Hopcroft–Karp). Se não existir, retorne **422** com mensagem amigável ("Com as restrições atuais não existe sorteio possível. Revise os círculos/pares bloqueados.") e, se possível, aponte os participantes com menos opções.
   - Exponha também um endpoint `POST /groups/{id}/draw/validate` para o organizador checar antes de sortear.
3. **Sorteio**: emparelhamento aleatório. Embaralhe a ordem dos givers e das listas de adjacência com `secrets.SystemRandom` e rode a busca de emparelhamento. Garanta que o resultado é uma **permutação**: cada pessoa dá exatamente um presente e recebe exatamente um.
4. Preferência opcional (flag no grupo `prefer_single_cycle`, default `true`): tente primeiro formar **um único ciclo** (A→B→C→…→A) por backtracking aleatório com limite de tentativas; se não achar, caia no emparelhamento geral do passo 3.
5. Mínimo de **3 participantes** para sortear.
6. **Idempotência e concorrência**: execute o sorteio dentro de uma transação com `SELECT … FOR UPDATE` na linha do grupo (ou advisory lock por group_id). Se o status já for `DRAWN`, retorne 409. Aceite header `Idempotency-Key`.
7. O algoritmo fica num módulo **puro** (sem I/O) e tem testes unitários + **testes de propriedade** (hypothesis) cobrindo: ninguém tira a si mesmo, nenhuma restrição é violada, todos dão e recebem exatamente uma vez, e casos impossíveis são detectados.

---

## 7. Autenticação e segurança

- **Senhas** com **Argon2id** (`argon2-cffi`). Política mínima: 8 caracteres e checagem contra uma lista de senhas comuns.
- **Verificação de e-mail** obrigatória para contas com senha, via token de uso único (expira em 24 h). Sem e-mail verificado, o usuário pode logar, mas não pode criar nem entrar em grupos.
- **Reset de senha** via token de uso único (expira em 1 h). A resposta é sempre genérica ("se o e-mail existir, enviaremos um link").
- **Google OAuth**: fluxo Authorization Code com PKCE + `state`; validar o `id_token`. Se o e-mail do Google já existir com conta de senha e estiver verificado, **vincular** (`google_sub`) à conta existente.
- **Sessão**: access token **JWT** curto (15 min) + refresh token opaco (30 dias) armazenado com hash e **rotacionado** a cada uso (detectar reuso → revogar todos os tokens do usuário). Ambos em **cookies `HttpOnly`, `Secure`, `SameSite=Lax`**. Proteção CSRF com double-submit token para métodos mutáveis.
- **Rate limiting** com Redis: login, registro, reset de senha, reenvio de verificação e entrada por convite.
- `invite_code` gerado com `secrets.token_urlsafe` (≥ 10 caracteres), regenerável pelo organizador.
- **Autorização** em todo endpoint de grupo: verificar se o usuário é participante e qual é o seu papel. Retornar **404** (não 403) para grupos de que o usuário não participa, para não vazar a existência deles.
- CORS restrito à origem do frontend; headers de segurança (HSTS, X-Content-Type-Options, etc.).
- Nunca commitar segredos; tudo via variáveis de ambiente, documentadas em `.env.example`.

---

## 8. API (Fase 1)

Prefixo `/api/v1`. Erros no formato `{ "error": { "code": "...", "message": "..." } }`. Paginação por cursor onde houver listas.

**Auth**
- `POST /auth/register`, `POST /auth/login`, `POST /auth/logout`, `POST /auth/refresh`
- `POST /auth/verify-email`, `POST /auth/resend-verification`
- `POST /auth/forgot-password`, `POST /auth/reset-password`
- `GET /auth/google/start`, `GET /auth/google/callback`
- `GET /me`, `PATCH /me`

**Grupos**
- `GET /themes`
- `POST /groups`, `GET /groups` (meus grupos), `GET /groups/{id}`, `PATCH /groups/{id}`
- `POST /groups/{id}/open`, `POST /groups/{id}/close`, `POST /groups/{id}/finish`
- `POST /groups/{id}/invite-code/regenerate`
- `GET /invites/{code}` (preview público mínimo: título, tema, data, organizador), `POST /invites/{code}/join`

**Participantes**
- `GET /groups/{id}/participants`, `DELETE /groups/{id}/participants/{pid}` (organizador remove; somente antes de `DRAWN`), `POST /groups/{id}/leave`

**Regras**
- CRUD `/groups/{id}/exclusion-circles` (+ membros)
- CRUD `/groups/{id}/blocked-pairs`

**Lista de desejos**
- CRUD `/groups/{id}/me/wishlist`, `PUT /groups/{id}/me/preferences`

**Sorteio**
- `POST /groups/{id}/draw/validate`
- `POST /groups/{id}/draw`
- `GET /groups/{id}/my-match`: retorna nome, avatar, tamanhos, lista de desejos e preferências de quem eu tirei.

Gere o OpenAPI automaticamente e, no frontend, gere os tipos TypeScript a partir dele (`openapi-typescript`).

---

## 9. Frontend (Fase 1)

**Mobile-first** (a maioria vai abrir pelo link do WhatsApp), acessível e com identidade visual alegre e festiva. Cada tema pode trocar emoji, cor de destaque e textos.

Páginas:
- Landing simples (`/`) com CTA "Criar meu amigo secreto".
- Cadastro, login (com botão "Entrar com Google"), verificar e-mail, esqueci a senha, redefinir senha.
- **Meus grupos** (`/groups`): cards com tema, data e status.
- **Criar grupo**: wizard em 3 passos (tema e nome → valores, data e local → revisão).
- **Página do grupo** (`/groups/:id`), com abas:
  - *Visão geral*: dados do evento, contagem regressiva, botão de compartilhar convite (Web Share API, com fallback de copiar link e link para WhatsApp).
  - *Participantes*.
  - *Minha lista*: lista de desejos e "não quero ganhar".
  - *Regras* (só organizador): círculos de exclusão e pares bloqueados, com validação ao vivo.
  - *Sorteio*: o organizador vê o botão "Sortear" (com confirmação); após o sorteio, todos veem um card **"Você tirou…"** com revelação animada ao tocar.
- **Entrar por convite** (`/i/:code`): preview do grupo; se não estiver logado, faz login/cadastro e volta para o convite.

Requisitos de UI: estados de loading, vazio e erro em todas as telas; mensagens de erro em pt-BR; datas no formato brasileiro; valores em R$.

---

## 10. Fases

### Fase 1 — MVP (implementar agora)
1. Esqueleto do monorepo, docker-compose (postgres, redis, api, worker, web), `.env.example`, README com "como rodar".
2. Backend base: config (pydantic-settings), DB async, Alembic, logging estruturado (JSON), healthcheck `/health` (checa DB e Redis), tratamento global de erros.
3. Auth completa (seção 7), incluindo e-mails enviados pelo worker (arq).
4. Grupos, temas (seed), máquina de estados e convites.
5. Participantes, lista de desejos e preferências.
6. Motor de regras e sorteio (seção 6), com os testes de propriedade.
7. Frontend de todas as telas da seção 9.
8. CI no GitHub Actions; Dockerfiles de produção (multi-stage, usuário não root); instruções de deploy no Render/Railway.

### Fase 2 — Engajamento (não implementar ainda)
Chat anônimo entre giver e receiver; "presente comprado" (organizador vê só o progresso agregado); lembretes agendados (prazo da lista, 1 dia e 2 horas antes do evento); PWA com push; coorganizadores.

### Fase 3 — Escala e retenção (não implementar ainda)
Sorteio automático agendado; "não repetir pares da edição anterior" (duplicar grupo); página de revelação no dia do evento; notificações por WhatsApp; métricas e painel admin; exclusão de conta e retenção de dados (LGPD).

Modele o banco da Fase 1 já pensando nessas fases, mas **não** crie tabelas ou código delas agora.

---

## 11. Requisitos não funcionais

- **Stateless**: a API não guarda estado em memória; precisa rodar com N réplicas atrás de um load balancer.
- **Performance**: índices em todas as FKs e colunas de busca (`invite_code`, `email`, `google_sub`); evitar N+1 (use `selectinload`); p95 < 200 ms nos endpoints comuns.
- **Testes**: cobertura ≥ 80% no backend, com foco em services, autorização e sorteio. Testes de integração contra um Postgres real (container no CI).
- **Observabilidade**: request-id em todos os logs; integração opcional com Sentry via env (desligada por padrão).
- **LGPD**: coletar só o necessário; política de privacidade e termos como páginas estáticas placeholder.
- **DX**: `make` (ou scripts) com `dev`, `test`, `lint`, `migrate`, `seed`. Hot reload no back e no front em dev.

---

## 12. Definição de pronto (Fase 1)

- `docker compose up` sobe tudo e eu consigo, pelo navegador: criar conta, verificar e-mail (link aparece no log em dev), criar grupo, convidar 3+ usuários, configurar um casal como círculo de exclusão, sortear e ver "Você tirou…" em cada conta.
- O organizador **não** consegue ver os pares por nenhum meio da aplicação.
- CI verde (lint, types, testes).
- README explica setup, variáveis de ambiente, arquitetura e deploy.

Comece lendo tudo e me mostrando o plano da Fase 1.
