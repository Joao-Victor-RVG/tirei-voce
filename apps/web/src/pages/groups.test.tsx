import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { mockApi, renderRoute, unauthorized } from "@/test/render";
import { group, ME, THEMES } from "@/test/fixtures";

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
});

const json = (body: unknown, status = 200) => ({ status, body });

test("meus grupos lista os cards com status e data", async () => {
  mockApi((url) => {
    if (url.pathname.endsWith("/me")) return json(ME);
    if (url.pathname.endsWith("/groups"))
      return json({
        items: [
          {
            id: "g1",
            title: "Natal da Família",
            display_name: "Amigo Secreto",
            theme: THEMES[0],
            event_at: "2099-12-24T23:00:00Z",
            status: "OPEN",
            my_role: "owner",
            participant_count: 3,
          },
        ],
        next_cursor: null,
      });
  });
  renderRoute("/groups");
  const card = await screen.findByRole("link", { name: /Natal da Família/ });
  expect(within(card).getByText("Inscrições abertas")).toBeInTheDocument();
  expect(within(card).getByText(/24\/12\/2099/)).toBeInTheDocument();
  expect(within(card).getByText(/3 pessoas/)).toBeInTheDocument();
});

test("meus grupos vazio mostra CTA", async () => {
  mockApi((url) => {
    if (url.pathname.endsWith("/me")) return json(ME);
    if (url.pathname.endsWith("/groups")) return json({ items: [], next_cursor: null });
  });
  renderRoute("/groups");
  expect(await screen.findByText("Nenhum grupo por aqui ainda")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "+ Criar grupo" })).toHaveAttribute(
    "href",
    "/groups/new",
  );
});

test("erro ao carregar grupos permite tentar de novo", async () => {
  mockApi((url) => {
    if (url.pathname.endsWith("/me")) return json(ME);
    if (url.pathname.endsWith("/groups"))
      return json(
        { error: { code: "internal_error", message: "Ops! Algo deu errado. Tente novamente." } },
        500,
      );
  });
  renderRoute("/groups");
  expect(await screen.findByText("Ops! Algo deu errado. Tente novamente.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Tentar de novo" })).toBeInTheDocument();
});

test("wizard cria o grupo, abre inscrições e vai para a página", async () => {
  const calls = mockApi((url, init) => {
    if (url.pathname.endsWith("/me")) return json(ME);
    if (url.pathname.endsWith("/themes")) return json(THEMES);
    if (url.pathname.endsWith("/groups") && init.method === "POST")
      return json(group({ status: "DRAFT" }), 201);
    if (url.pathname.endsWith("/groups/g1/open")) return json(group());
    if (url.pathname.endsWith("/groups/g1")) return json(group());
  });
  const { router } = renderRoute("/groups/new");
  const user = userEvent.setup();

  await user.click(await screen.findByText("Amigo da Onça"));
  await user.click(screen.getByRole("button", { name: "Continuar" }));
  expect(await screen.findByText("Dê um nome ao grupo.")).toBeInTheDocument();
  await user.type(screen.getByLabelText("Nome do grupo"), "Onça do Escritório");
  await user.click(screen.getByRole("button", { name: "Continuar" }));

  await user.type(await screen.findByLabelText("Valor mínimo (R$)"), "30");
  await user.type(screen.getByLabelText("Valor máximo (R$)"), "20");
  await user.click(screen.getByRole("button", { name: "Continuar" }));
  expect(await screen.findByText("Deve ser maior ou igual ao mínimo.")).toBeInTheDocument();
  await user.clear(screen.getByLabelText("Valor máximo (R$)"));
  await user.type(screen.getByLabelText("Valor máximo (R$)"), "50,90");
  await user.type(screen.getByLabelText(/Local/), "Escritório");
  await user.click(screen.getByRole("button", { name: "Continuar" }));

  expect(await screen.findByText("Onça do Escritório")).toBeInTheDocument();
  expect(screen.getByText(/R\$\s30,00 a R\$\s50,90/)).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: /Criar grupo/ }));

  await waitFor(() => expect(router.state.location.pathname).toBe("/groups/g1"));
  const created = calls.find((c) => c.path === "/groups" && c.method === "POST");
  expect(created?.body).toMatchObject({
    theme_slug: "amigo-da-onca",
    title: "Onça do Escritório",
    min_value_cents: 3000,
    max_value_cents: 5090,
    event_location: "Escritório",
    custom_name: null,
  });
  expect(calls.some((c) => c.path === "/groups/g1/open")).toBe(true);
});

test("membro não vê a aba Regras; organizador vê", async () => {
  mockApi((url) => {
    if (url.pathname.endsWith("/me")) return json(ME);
    if (url.pathname.endsWith("/groups/g1")) return json(group({ my_role: "member" }));
  });
  renderRoute("/groups/g1");
  expect(await screen.findByRole("tab", { name: "Visão geral" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  expect(screen.queryByRole("tab", { name: "Regras" })).not.toBeInTheDocument();
  vi.unstubAllGlobals();

  mockApi((url) => {
    if (url.pathname.endsWith("/me")) return json(ME);
    if (url.pathname.endsWith("/groups/g1")) return json(group());
  });
  renderRoute("/groups/g1");
  expect(await screen.findAllByRole("tab", { name: "Regras" })).not.toHaveLength(0);
});

test("grupo inexistente mostra mensagem amigável", async () => {
  mockApi((url) => (url.pathname.endsWith("/me") ? json(ME) : undefined));
  renderRoute("/groups/nope");
  expect(await screen.findByText("Grupo não encontrado")).toBeInTheDocument();
});

test("visão geral mostra contagem regressiva e compartilhamento", async () => {
  mockApi((url) => {
    if (url.pathname.endsWith("/me")) return json(ME);
    if (url.pathname.endsWith("/groups/g1")) return json(group());
  });
  renderRoute("/groups/g1");
  expect(await screen.findByLabelText("Contagem regressiva para o evento")).toBeInTheDocument();
  const whatsapp = screen.getByRole("link", { name: "WhatsApp" });
  expect(whatsapp.getAttribute("href")).toContain("https://wa.me/?text=");
  expect(decodeURIComponent(whatsapp.getAttribute("href")!)).toContain("/i/abcdefghijkl");
  expect(screen.getByText(/R\$\s50,00 a R\$\s100,00/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Fechar inscrições" })).toBeInTheDocument();
});

test("regras: validação ao vivo e criação de círculo", async () => {
  let circles: unknown[] = [];
  let possible = true;
  const calls = mockApi((url, init) => {
    const path = url.pathname.replace("/api/v1", "");
    if (path === "/me") return json(ME);
    if (path === "/groups/g1") return json(group());
    if (path === "/groups/g1/participants")
      return json(
        ["Ana", "Bia", "Caio"].map((name, i) => ({
          id: `p${i + 1}`,
          user: { id: `u${i + 1}`, name, avatar_url: null },
          role: i === 0 ? "owner" : "member",
          joined_at: "2026-11-01T00:00:00Z",
          is_me: i === 0,
        })),
      );
    if (path === "/groups/g1/exclusion-circles" && init.method === "POST") {
      possible = false;
      circles = [
        {
          id: "c1",
          name: "Casal",
          members: [
            { participant_id: "p1", name: "Ana" },
            { participant_id: "p2", name: "Bia" },
          ],
        },
      ];
      return json(circles[0], 201);
    }
    if (path === "/groups/g1/exclusion-circles") return json(circles);
    if (path === "/groups/g1/blocked-pairs") return json([]);
    if (path === "/groups/g1/draw/validate")
      return json({
        possible,
        participant_count: 3,
        min_participants: 3,
        message: possible
          ? "Tudo certo! O sorteio é possível com as regras atuais."
          : "Com as restrições atuais não existe sorteio possível.",
        most_constrained: possible ? [] : [{ participant_id: "p3", name: "Caio", options: 0 }],
      });
  });
  renderRoute("/groups/g1?tab=rules");
  const user = userEvent.setup();
  expect(await screen.findByText(/Tudo certo!/)).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "+ Círculo" }));
  await user.type(screen.getByLabelText("Nome do círculo"), "Casal");
  await user.click(screen.getByText("Ana", { selector: "label" }));
  await user.click(screen.getByText("Bia", { selector: "label" }));
  await user.click(screen.getByRole("button", { name: "Salvar" }));

  expect(await screen.findByText(/não existe sorteio possível/)).toBeInTheDocument();
  expect(screen.getByText(/Caio \(0 opções\)/)).toBeInTheDocument();
  expect(
    calls.find((c) => c.path === "/groups/g1/exclusion-circles" && c.method === "POST")?.body,
  ).toEqual({
    name: "Casal",
    participant_ids: ["p1", "p2"],
  });
});

test("sorteio: organizador confirma e envia Idempotency-Key", async () => {
  let drawn = false;
  const headers: Array<Record<string, string>> = [];
  mockApi((url, init) => {
    const path = url.pathname.replace("/api/v1", "");
    if (path === "/me") return json(ME);
    if (path === "/groups/g1") return json(group({ status: drawn ? "DRAWN" : "CLOSED" }));
    if (path === "/groups/g1/draw/validate")
      return json({
        possible: true,
        participant_count: 4,
        min_participants: 3,
        message: "Tudo certo!",
        most_constrained: [],
      });
    if (path === "/groups/g1/draw") {
      headers.push(init.headers as Record<string, string>);
      drawn = true;
      return json({
        draw_id: "d1",
        version: 1,
        executed_at: "2026-11-01T00:00:00Z",
        participant_count: 4,
      });
    }
  });
  renderRoute("/groups/g1?tab=draw");
  const user = userEvent.setup();
  const button = await screen.findByRole("button", { name: /Sortear/ });
  await waitFor(() => expect(button).toBeEnabled());
  await user.click(button);
  await user.click(await screen.findByRole("button", { name: "Sim, sortear!" }));
  expect(await screen.findByRole("button", { name: /Toque para revelar/ })).toBeInTheDocument();
  expect(headers[0]?.["Idempotency-Key"]).toMatch(/[0-9a-f-]{36}/);
});

test("revelação: só busca o par ao tocar e mostra a lista", async () => {
  const calls = mockApi((url) => {
    const path = url.pathname.replace("/api/v1", "");
    if (path === "/me") return json(ME);
    if (path === "/groups/g1") return json(group({ status: "DRAWN", my_role: "member" }));
    if (path === "/groups/g1/my-match")
      return json({
        participant_id: "p3",
        name: "Caio",
        avatar_url: null,
        shirt_size: "G",
        shoe_size: "42",
        wishlist: [
          {
            id: "w1",
            title: "Fone de ouvido",
            url: null,
            price_hint_cents: 15000,
            priority: 1,
            notes: null,
          },
        ],
        preferences: { dislikes: "Perfume", notes: null },
        gift_purchased: false,
      });
    if (path === "/groups/g1/my-match/gift") return json({ purchased: true });
  });
  renderRoute("/groups/g1");
  const user = userEvent.setup();
  const reveal = await screen.findByRole("button", { name: /Toque para revelar/ });
  expect(calls.some((c) => c.path === "/groups/g1/my-match")).toBe(false);

  await user.click(reveal);
  expect(await screen.findByRole("heading", { name: "Caio" })).toBeInTheDocument();
  expect(screen.getByText("Fone de ouvido")).toBeInTheDocument();
  expect(screen.getByText("Perfume")).toBeInTheDocument();
  expect(screen.getByText("👕 G")).toBeInTheDocument();
  expect(localStorage.getItem("tv_revealed:g1")).toBe("1");
  expect(JSON.stringify(localStorage)).not.toContain("Caio");

  await user.click(screen.getByRole("button", { name: /Já comprei/ }));
  expect(await screen.findByText("Presente comprado!")).toBeInTheDocument();
  expect(calls.find((c) => c.path === "/groups/g1/my-match/gift")?.body).toEqual({
    purchased: true,
  });
});

test("convite sem login oferece cadastro e volta para o convite", async () => {
  mockApi((url) => {
    if (url.pathname.endsWith("/me")) return unauthorized;
    if (url.pathname.endsWith("/invites/abcdefghijkl"))
      return json({
        title: "Natal da Família",
        display_name: "Amigo Secreto",
        theme: THEMES[0],
        event_at: "2099-12-24T23:00:00Z",
        event_location: "Casa da vó",
        min_value_cents: 5000,
        max_value_cents: 10000,
        organizer_name: "Ana",
        participant_count: 3,
        can_join: true,
        reason: null,
      });
  });
  renderRoute("/i/abcdefghijkl");
  expect(await screen.findByText("Ana te convidou para o")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Quero participar!" })).toHaveAttribute(
    "href",
    "/register?next=%2Fi%2Fabcdefghijkl",
  );
  expect(screen.getByRole("link", { name: "Já tenho conta" })).toHaveAttribute(
    "href",
    "/login?next=%2Fi%2Fabcdefghijkl",
  );
});

test("convite logado entra no grupo", async () => {
  mockApi((url, init) => {
    const path = url.pathname.replace("/api/v1", "");
    if (path === "/me") return json(ME);
    if (path === "/invites/abcdefghijkl/join" && init.method === "POST")
      return json({ group_id: "g1", already_member: false });
    if (path === "/invites/abcdefghijkl")
      return json({
        title: "Natal",
        display_name: "Amigo Secreto",
        theme: THEMES[0],
        event_at: null,
        event_location: null,
        min_value_cents: null,
        max_value_cents: null,
        organizer_name: "Ana",
        participant_count: 3,
        can_join: true,
        reason: null,
      });
    if (path === "/groups/g1") return json(group({ my_role: "member" }));
  });
  const { router } = renderRoute("/i/abcdefghijkl");
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: /Participar/ }));
  await waitFor(() => expect(router.state.location.pathname).toBe("/groups/g1"));
});

test("convite fechado mostra o motivo", async () => {
  mockApi((url) => {
    if (url.pathname.endsWith("/me")) return json(ME);
    if (url.pathname.endsWith("/invites/abcdefghijkl"))
      return json({
        title: "Natal",
        display_name: "Amigo Secreto",
        theme: THEMES[0],
        event_at: null,
        event_location: null,
        min_value_cents: null,
        max_value_cents: null,
        organizer_name: "Ana",
        participant_count: 3,
        can_join: false,
        reason: "As inscrições deste grupo estão encerradas.",
      });
  });
  renderRoute("/i/abcdefghijkl");
  expect(
    await screen.findByText("As inscrições deste grupo estão encerradas."),
  ).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Participar/ })).not.toBeInTheDocument();
});

test("dono promove coorganizador e coorganizador vê a aba Regras", async () => {
  const people = [
    {
      id: "p1",
      user: { id: "u1", name: "Ana", avatar_url: null },
      role: "owner",
      joined_at: "2026-11-01T00:00:00Z",
      is_me: true,
    },
    {
      id: "p2",
      user: { id: "u2", name: "Bia", avatar_url: null },
      role: "member",
      joined_at: "2026-11-01T00:00:00Z",
      is_me: false,
    },
  ];
  const calls = mockApi((url, init) => {
    const path = url.pathname.replace("/api/v1", "");
    if (path === "/me") return json(ME);
    if (path === "/groups/g1") return json(group());
    if (path === "/groups/g1/participants") return json(people);
    if (path === "/groups/g1/participants/p2/co-organizer" && init.method === "PUT") {
      people[1]!.role = "co_owner";
      return json(people[1]);
    }
  });
  renderRoute("/groups/g1?tab=participants");
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Tornar coorganizador" }));
  expect(await screen.findByText("Coorganização")).toBeInTheDocument();
  expect(calls.some((c) => c.method === "PUT" && c.path.endsWith("/co-organizer"))).toBe(true);
  vi.unstubAllGlobals();

  mockApi((url) => {
    if (url.pathname.endsWith("/me")) return json(ME);
    if (url.pathname.endsWith("/groups/g1")) return json(group({ my_role: "co_owner" }));
  });
  renderRoute("/groups/g1");
  expect((await screen.findAllByRole("tab", { name: "Regras" })).length).toBeGreaterThan(0);
});

test("organização vê só o progresso agregado dos presentes", async () => {
  mockApi((url) => {
    const path = url.pathname.replace("/api/v1", "");
    if (path === "/me") return json(ME);
    if (path === "/groups/g1") return json(group({ status: "DRAWN" }));
    if (path === "/groups/g1/gift-progress") return json({ purchased: 3, total: 8 });
  });
  renderRoute("/groups/g1?tab=draw");
  expect(await screen.findByText("3 de 8")).toBeInTheDocument();
  expect(screen.getByRole("progressbar", { name: "Presentes comprados" })).toHaveAttribute(
    "aria-valuenow",
    "3",
  );
});

test("chat: lista as duas conversas e envia mensagem anônima", async () => {
  const sent: unknown[] = [];
  const history: unknown[] = [
    { id: "m2", from_me: false, body: "Qual seu tamanho?", created_at: "2026-11-20T12:00:00Z" },
  ];
  mockApi((url, init) => {
    const path = url.pathname.replace("/api/v1", "");
    if (path === "/me") return json(ME);
    if (path === "/groups/g1") return json(group({ status: "DRAWN", my_role: "member" }));
    if (path === "/groups/g1/chats")
      return json([
        { thread: "match", title: "Caio", unread: 0, last_message: null },
        {
          thread: "santa",
          title: "Seu amigo secreto",
          unread: 2,
          last_message: {
            id: "m2",
            from_me: false,
            body: "Qual seu tamanho?",
            created_at: "2026-11-20T12:00:00Z",
          },
        },
      ]);
    if (path === "/groups/g1/chats/santa/messages" && init.method === "POST") {
      const message = {
        id: "m3",
        from_me: true,
        body: JSON.parse(String(init.body)).body,
        created_at: "2026-11-20T12:05:00Z",
      };
      sent.push(message);
      history.push(message);
      return json(message, 201);
    }
    if (path === "/groups/g1/chats/santa/messages")
      return json({ items: history, next_cursor: null });
    if (path === "/groups/g1/chats/santa/read") return { status: 204 };
  });
  renderRoute("/groups/g1?tab=chat");
  const user = userEvent.setup();
  expect(await screen.findByText("Seu amigo secreto")).toBeInTheDocument();
  expect(screen.getAllByLabelText("2 não lidas").length).toBeGreaterThan(0);

  await user.click(screen.getByText("Seu amigo secreto"));
  expect(await screen.findByText("Qual seu tamanho?")).toBeInTheDocument();
  await user.type(screen.getByLabelText("Mensagem"), "M, obrigada!{Enter}");
  expect(await screen.findByText("M, obrigada!")).toBeInTheDocument();
  expect(sent).toHaveLength(1);
});

test("aba Chat só aparece depois do sorteio", async () => {
  mockApi((url) => {
    if (url.pathname.endsWith("/me")) return json(ME);
    if (url.pathname.endsWith("/groups/g1")) return json(group({ status: "OPEN" }));
  });
  renderRoute("/groups/g1");
  expect(await screen.findByRole("tab", { name: "Visão geral" })).toBeInTheDocument();
  expect(screen.queryByRole("tab", { name: /Chat/ })).not.toBeInTheDocument();
});

test("organização agenda o sorteio automático", async () => {
  let scheduled: string | null = null;
  const calls = mockApi((url, init) => {
    const path = url.pathname.replace("/api/v1", "");
    if (path === "/me") return json(ME);
    if (path === "/groups/g1" && init.method === "PATCH") {
      scheduled = JSON.parse(String(init.body)).draw_scheduled_at;
      return json(group({ status: "CLOSED", draw_scheduled_at: scheduled }));
    }
    if (path === "/groups/g1")
      return json(group({ status: "CLOSED", draw_scheduled_at: scheduled }));
    if (path === "/groups/g1/draw/validate")
      return json({
        possible: true,
        participant_count: 4,
        min_participants: 3,
        message: "Tudo certo!",
        most_constrained: [],
      });
  });
  renderRoute("/groups/g1?tab=draw");
  const user = userEvent.setup();
  await user.type(await screen.findByLabelText("Data e hora do sorteio"), "2099-12-20T20:00");
  await user.click(screen.getByRole("button", { name: "Agendar sorteio" }));
  expect(await screen.findByText(/Agendado para/)).toBeInTheDocument();
  expect(calls.find((c) => c.method === "PATCH")?.body).toEqual({
    draw_scheduled_at: "2099-12-20T23:00:00.000Z",
  });
});

test("organização cria a próxima edição sem repetir pares", async () => {
  const calls = mockApi((url, init) => {
    const path = url.pathname.replace("/api/v1", "");
    if (path === "/me") return json(ME);
    if (path === "/groups/g1/duplicate" && init.method === "POST")
      return json(group({ id: "g2", status: "DRAFT", previous_group_id: "g1" }), 201);
    if (path === "/groups/g1") return json(group({ status: "FINISHED" }));
    if (path === "/groups/g2")
      return json(group({ id: "g2", status: "DRAFT", previous_group_id: "g1" }));
  });
  const { router } = renderRoute("/groups/g1?tab=overview");
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Criar próxima edição" }));
  await user.clear(screen.getByLabelText("Nome da nova edição"));
  await user.type(screen.getByLabelText("Nome da nova edição"), "Natal 2027");
  expect(screen.getByRole("checkbox", { name: /Não repetir os pares/ })).toBeChecked();
  await user.click(screen.getByRole("button", { name: "Criar" }));
  await waitFor(() => expect(router.state.location.pathname).toBe("/groups/g2"));
  expect(calls.find((c) => c.path === "/groups/g1/duplicate")?.body).toEqual({
    title: "Natal 2027",
    event_at: null,
    avoid_previous_pairs: true,
  });
});

test("revelação de quem me tirou só depois do evento", async () => {
  mockApi((url) => {
    const path = url.pathname.replace("/api/v1", "");
    if (path === "/me") return json(ME);
    if (path === "/groups/g1")
      return json(group({ status: "DRAWN", my_role: "member", event_at: "2020-12-24T23:00:00Z" }));
    if (path === "/groups/g1/my-santa")
      return json({ participant_id: "p9", name: "Duda", avatar_url: null });
  });
  renderRoute("/groups/g1?tab=draw");
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: /Revelar/ }));
  expect(await screen.findByText("Quem te tirou foi")).toBeInTheDocument();
  expect(screen.getByText("Duda")).toBeInTheDocument();
});

test("antes do evento mostra contagem para a revelação", async () => {
  const calls = mockApi((url) => {
    const path = url.pathname.replace("/api/v1", "");
    if (path === "/me") return json(ME);
    if (path === "/groups/g1") return json(group({ status: "DRAWN", my_role: "member" }));
  });
  renderRoute("/groups/g1?tab=draw");
  expect(await screen.findByText(/A revelação abre no horário do evento/)).toBeInTheDocument();
  expect(calls.some((c) => c.path === "/groups/g1/my-santa")).toBe(false);
});

test("painel admin mostra números agregados e desativa usuário", async () => {
  const calls = mockApi((url, init) => {
    const path = url.pathname.replace("/api/v1", "");
    if (path === "/me") return json({ ...ME, is_admin: true });
    if (path === "/admin/metrics")
      return json({
        users: { total: 1284, last_7d: 32 },
        users_verified: 1100,
        groups: { total: 210, last_7d: 12 },
        groups_by_status: { DRAFT: 10, OPEN: 50, CLOSED: 20, DRAWN: 100, FINISHED: 30 },
        draws: { total: 130, last_7d: 9 },
        participants: 1500,
        avg_group_size: 7.1,
        gifts_purchased: 400,
        gifts_total: 800,
        chat_messages_7d: 950,
        push_subscriptions: 300,
        scheduled_draws_pending: 4,
        generated_at: "2026-11-24T00:00:00Z",
      });
    if (path === "/admin/users/u2/deactivate" && init.method === "POST")
      return json({
        id: "u2",
        name: "Bia",
        email: "bia@example.com",
        email_verified: true,
        is_active: false,
        is_admin: false,
        groups: 2,
        created_at: "2026-11-01T00:00:00Z",
      });
    if (path === "/admin/users")
      return json({
        items: [
          {
            id: "u2",
            name: "Bia",
            email: "bia@example.com",
            email_verified: true,
            is_active: true,
            is_admin: false,
            groups: 2,
            created_at: "2026-11-01T00:00:00Z",
          },
        ],
        next_cursor: null,
      });
  });
  renderRoute("/admin");
  const user = userEvent.setup();
  expect(await screen.findByText("+32 em 7 dias")).toBeInTheDocument();
  expect(screen.getByText(/1,3\s?mil/)).toBeInTheDocument();
  expect(screen.getByRole("meter", { name: "Presentes comprados" })).toHaveAttribute(
    "aria-valuenow",
    "400",
  );
  expect(screen.getByTitle("Sorteado: 100")).toBeInTheDocument();
  await user.click(await screen.findByRole("button", { name: "Desativar" }));
  await waitFor(() =>
    expect(calls.some((c) => c.path === "/admin/users/u2/deactivate")).toBe(true),
  );
});

test("não admin é levado para meus grupos", async () => {
  mockApi((url) => {
    if (url.pathname.endsWith("/me")) return json(ME);
    if (url.pathname.endsWith("/groups")) return json({ items: [], next_cursor: null });
  });
  const { router } = renderRoute("/admin");
  await waitFor(() => expect(router.state.location.pathname).toBe("/groups"));
});
