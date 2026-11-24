import { screen } from "@testing-library/react";

import { mockApi, renderRoute, unauthorized } from "@/test/render";

afterEach(() => vi.unstubAllGlobals());

test("landing mostra o CTA para visitantes", async () => {
  mockApi((url) => (url.pathname.endsWith("/me") ? unauthorized : undefined));
  renderRoute("/");
  expect(await screen.findByRole("link", { name: "Criar meu amigo secreto" })).toHaveAttribute(
    "href",
    "/register",
  );
});

test("página inexistente mostra 404 amigável", async () => {
  mockApi((url) => (url.pathname.endsWith("/me") ? unauthorized : undefined));
  renderRoute("/nao-existe");
  expect(await screen.findByText("Página não encontrada")).toBeInTheDocument();
});
