import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { mockApi, renderRoute, unauthorized } from "@/test/render";

const ME = {
  id: "u1",
  name: "Ana",
  email: "ana@example.com",
  email_verified: false,
  avatar_url: null,
  shirt_size: null,
  shoe_size: null,
  has_password: true,
  has_google: false,
  email_reminders: true,
  phone: null,
  whatsapp_opt_in: false,
  is_admin: false,
};

afterEach(() => {
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

test("login com erro mostra a mensagem da API", async () => {
  mockApi((url) => {
    if (url.pathname.endsWith("/me")) return unauthorized;
    if (url.pathname.endsWith("/auth/config"))
      return { body: { google_enabled: false, whatsapp_enabled: false } };
    if (url.pathname.endsWith("/auth/login"))
      return {
        status: 401,
        body: { error: { code: "invalid_credentials", message: "E-mail ou senha incorretos." } },
      };
  });
  renderRoute("/login");
  const user = userEvent.setup();
  await user.type(await screen.findByLabelText("E-mail"), "ana@example.com");
  await user.type(screen.getByLabelText("Senha"), "errada123");
  await user.click(screen.getByRole("button", { name: "Entrar" }));
  expect(await screen.findByText("E-mail ou senha incorretos.")).toBeInTheDocument();
});

test("login valida campos antes de chamar a API", async () => {
  const calls = mockApi((url) =>
    url.pathname.endsWith("/me")
      ? unauthorized
      : { body: { google_enabled: true, whatsapp_enabled: false } },
  );
  renderRoute("/login");
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Entrar" }));
  expect(await screen.findByText("Informe seu e-mail.")).toBeInTheDocument();
  expect(calls.some((c) => c.path === "/auth/login")).toBe(false);
  expect(screen.getByRole("link", { name: /Entrar com Google/ })).toHaveAttribute(
    "href",
    "/api/v1/auth/google/start?next=%2Fgroups",
  );
});

test("login bem-sucedido volta para o next", async () => {
  let loggedIn = false;
  mockApi((url) => {
    if (url.pathname.endsWith("/me")) return loggedIn ? { body: ME } : unauthorized;
    if (url.pathname.endsWith("/auth/config"))
      return { body: { google_enabled: false, whatsapp_enabled: false } };
    if (url.pathname.endsWith("/auth/login")) {
      loggedIn = true;
      return { body: ME };
    }
    if (url.pathname.endsWith("/invites/abcdefghijkl")) return undefined;
  });
  const { router } = renderRoute("/login?next=%2Fprofile");
  const user = userEvent.setup();
  await user.type(await screen.findByLabelText("E-mail"), "ana@example.com");
  await user.type(screen.getByLabelText("Senha"), "certa-123");
  await user.click(screen.getByRole("button", { name: "Entrar" }));
  await waitFor(() => expect(router.state.location.pathname).toBe("/profile"));
});

test("next externo é ignorado", async () => {
  mockApi((url) =>
    url.pathname.endsWith("/me")
      ? unauthorized
      : { body: { google_enabled: false, whatsapp_enabled: false } },
  );
  renderRoute("/login?next=https%3A%2F%2Fevil.com");
  expect(await screen.findByRole("link", { name: "Cadastre-se" })).toHaveAttribute(
    "href",
    "/register?next=%2Fgroups",
  );
});

test("cadastro leva para a tela de confirmar e-mail", async () => {
  let registered = false;
  const calls = mockApi((url) => {
    if (url.pathname.endsWith("/me")) return registered ? { body: ME } : unauthorized;
    if (url.pathname.endsWith("/auth/config"))
      return { body: { google_enabled: false, whatsapp_enabled: false } };
    if (url.pathname.endsWith("/auth/register")) {
      registered = true;
      return { status: 201, body: ME };
    }
  });
  const { router } = renderRoute("/register");
  const user = userEvent.setup();
  await user.type(await screen.findByLabelText("Seu nome"), "Ana");
  await user.type(screen.getByLabelText("E-mail"), "ana@example.com");
  await user.type(screen.getByLabelText("Senha"), "uma-senha-forte");
  await user.click(screen.getByRole("button", { name: "Criar conta" }));
  await waitFor(() => expect(router.state.location.pathname).toBe("/verify-email"));
  expect(await screen.findByText("ana@example.com")).toBeInTheDocument();
  expect(calls.find((c) => c.path === "/auth/register")?.body).toEqual({
    name: "Ana",
    email: "ana@example.com",
    password: "uma-senha-forte",
  });
});

test("cadastro com e-mail repetido marca o campo", async () => {
  mockApi((url) => {
    if (url.pathname.endsWith("/me")) return unauthorized;
    if (url.pathname.endsWith("/auth/config"))
      return { body: { google_enabled: false, whatsapp_enabled: false } };
    if (url.pathname.endsWith("/auth/register"))
      return {
        status: 409,
        body: { error: { code: "email_taken", message: "Este e-mail já está cadastrado." } },
      };
  });
  renderRoute("/register");
  const user = userEvent.setup();
  await user.type(await screen.findByLabelText("Seu nome"), "Ana");
  await user.type(screen.getByLabelText("E-mail"), "ana@example.com");
  await user.type(screen.getByLabelText("Senha"), "uma-senha-forte");
  await user.click(screen.getByRole("button", { name: "Criar conta" }));
  expect(await screen.findByText("Este e-mail já está cadastrado.")).toBeInTheDocument();
  expect(screen.getByLabelText("E-mail")).toHaveAttribute("aria-invalid", "true");
});

test("verifica o e-mail pelo token só uma vez", async () => {
  const calls = mockApi((url) => {
    if (url.pathname.endsWith("/me")) return unauthorized;
    if (url.pathname.endsWith("/auth/verify-email"))
      return { body: { ...ME, email_verified: true } };
  });
  renderRoute("/verify-email?token=abc123abc123");
  expect(await screen.findByText("E-mail confirmado!")).toBeInTheDocument();
  expect(calls.filter((c) => c.path === "/auth/verify-email")).toHaveLength(1);
});

test("token inválido oferece novo link", async () => {
  mockApi((url) => {
    if (url.pathname.endsWith("/me")) return unauthorized;
    if (url.pathname.endsWith("/auth/verify-email"))
      return {
        status: 400,
        body: {
          error: {
            code: "invalid_token",
            message: "Este link é inválido ou expirou. Peça um novo.",
          },
        },
      };
  });
  renderRoute("/verify-email?token=abc123abc123");
  expect(await screen.findByText("Link inválido ou expirado")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Pedir um novo link" })).toBeInTheDocument();
});

test("esqueci a senha mostra resposta genérica", async () => {
  mockApi((url) => {
    if (url.pathname.endsWith("/me")) return unauthorized;
    if (url.pathname.endsWith("/auth/forgot-password"))
      return {
        status: 202,
        body: { message: "Se o e-mail existir, enviaremos um link para redefinir a senha." },
      };
  });
  renderRoute("/forgot-password");
  const user = userEvent.setup();
  await user.type(await screen.findByLabelText("E-mail"), "x@example.com");
  await user.click(screen.getByRole("button", { name: "Enviar link" }));
  expect(await screen.findByText(/Se o e-mail existir/)).toBeInTheDocument();
});

test("redefinir senha confere a confirmação", async () => {
  const calls = mockApi((url) => {
    if (url.pathname.endsWith("/me")) return unauthorized;
    if (url.pathname.endsWith("/auth/reset-password")) return { status: 204 };
  });
  renderRoute("/reset-password?token=tok123tok123");
  const user = userEvent.setup();
  await user.type(await screen.findByLabelText("Nova senha"), "nova-senha-forte");
  await user.type(screen.getByLabelText("Repita a senha"), "outra-coisa");
  await user.click(screen.getByRole("button", { name: "Salvar senha" }));
  expect(await screen.findByText("As senhas não conferem.")).toBeInTheDocument();

  await user.clear(screen.getByLabelText("Repita a senha"));
  await user.type(screen.getByLabelText("Repita a senha"), "nova-senha-forte");
  await user.click(screen.getByRole("button", { name: "Salvar senha" }));
  expect(await screen.findByText("Senha alterada!")).toBeInTheDocument();
  expect(calls.find((c) => c.path === "/auth/reset-password")?.body).toEqual({
    token: "tok123tok123",
    password: "nova-senha-forte",
  });
});

test("rota protegida manda para o login com next", async () => {
  mockApi((url) =>
    url.pathname.endsWith("/me")
      ? unauthorized
      : { body: { google_enabled: false, whatsapp_enabled: false } },
  );
  const { router } = renderRoute("/profile");
  await waitFor(() => expect(router.state.location.pathname).toBe("/login"));
  expect(router.state.location.search).toBe("?next=%2Fprofile");
});

test("401 renova a sessão uma vez e repete a requisição", async () => {
  let refreshed = false;
  const calls = mockApi((url) => {
    if (url.pathname.endsWith("/auth/refresh")) {
      refreshed = true;
      return { body: ME };
    }
    if (url.pathname.endsWith("/me"))
      return refreshed ? { body: { ...ME, email_verified: true } } : unauthorized;
  });
  renderRoute("/profile");
  expect(await screen.findByRole("heading", { name: "Meu perfil" })).toBeInTheDocument();
  expect(calls.filter((c) => c.path === "/auth/refresh")).toHaveLength(1);
});

test("perfil mostra opção de notificações quando o push está habilitado", async () => {
  mockApi((url) => {
    if (url.pathname.endsWith("/me")) return { body: { ...ME, email_verified: true } };
    if (url.pathname.endsWith("/push/config"))
      return { body: { enabled: true, public_key: "BPUB", subscribed: false } };
  });
  renderRoute("/profile");
  expect(await screen.findByText("Notificações neste aparelho")).toBeInTheDocument();
  // jsdom não tem PushManager: mostra o aviso em vez do botão.
  expect(screen.getByText("Este navegador não suporta notificações.")).toBeInTheDocument();
});

test("perfil esconde notificações quando o push está desligado no servidor", async () => {
  mockApi((url) => {
    if (url.pathname.endsWith("/me")) return { body: { ...ME, email_verified: true } };
    if (url.pathname.endsWith("/push/config"))
      return { body: { enabled: false, public_key: null, subscribed: false } };
  });
  renderRoute("/profile");
  expect(await screen.findByRole("heading", { name: "Meu perfil" })).toBeInTheDocument();
  expect(screen.queryByText("Notificações neste aparelho")).not.toBeInTheDocument();
});

test("perfil desliga lembretes por e-mail", async () => {
  const me = { ...ME, email_verified: true, email_reminders: true };
  const calls = mockApi((url, init) => {
    if (url.pathname.endsWith("/me") && init.method === "PATCH") {
      Object.assign(me, JSON.parse(String(init.body)));
      return { body: me };
    }
    if (url.pathname.endsWith("/me")) return { body: me };
    if (url.pathname.endsWith("/push/config"))
      return { body: { enabled: false, public_key: null, subscribed: false } };
  });
  renderRoute("/profile");
  const user = userEvent.setup();
  const toggle = await screen.findByRole("checkbox", { name: /Lembretes por e-mail/ });
  expect(toggle).toBeChecked();
  await user.click(toggle);
  await user.click(screen.getByRole("button", { name: "Salvar" }));
  await waitFor(() =>
    expect(calls.find((c) => c.method === "PATCH")?.body).toMatchObject({ email_reminders: false }),
  );
});

test("perfil mostra WhatsApp só quando há provedor e salva o opt-in", async () => {
  const calls = mockApi((url, init) => {
    if (url.pathname.endsWith("/me") && init.method === "PATCH")
      return {
        body: { ...ME, email_verified: true, phone: "+5511987654321", whatsapp_opt_in: true },
      };
    if (url.pathname.endsWith("/me")) return { body: { ...ME, email_verified: true } };
    if (url.pathname.endsWith("/auth/config"))
      return { body: { google_enabled: false, whatsapp_enabled: true } };
    if (url.pathname.endsWith("/push/config"))
      return { body: { enabled: false, public_key: null, subscribed: false } };
  });
  renderRoute("/profile");
  const user = userEvent.setup();
  await user.type(await screen.findByLabelText("Celular com DDD"), "(11) 98765-4321");
  await user.click(screen.getByRole("checkbox", { name: /WhatsApp/ }));
  await user.click(screen.getByRole("button", { name: "Salvar WhatsApp" }));
  await waitFor(() =>
    expect(calls.find((c) => c.method === "PATCH")?.body).toEqual({
      phone: "(11) 98765-4321",
      whatsapp_opt_in: true,
    }),
  );
});

test("excluir conta pede a senha e volta para o início", async () => {
  const calls = mockApi((url, init) => {
    if (url.pathname.endsWith("/me/delete") && init.method === "POST")
      return { body: { mode: "anonymized" } };
    if (url.pathname.endsWith("/me")) return { body: { ...ME, email_verified: true } };
    if (url.pathname.endsWith("/push/config"))
      return { body: { enabled: false, public_key: null, subscribed: false } };
    if (url.pathname.endsWith("/auth/config"))
      return { body: { google_enabled: false, whatsapp_enabled: false } };
  });
  const { router } = renderRoute("/profile");
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Excluir minha conta" }));
  await user.type(screen.getByLabelText("Sua senha"), "minha-senha-123");
  await user.click(screen.getByRole("button", { name: "Excluir para sempre" }));
  await waitFor(() => expect(router.state.location.pathname).toBe("/"));
  expect(calls.find((c) => c.path === "/me/delete")?.body).toEqual({ password: "minha-senha-123" });
});
