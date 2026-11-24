import { QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";

import { createQueryClient } from "@/api/queryClient";
import { routes } from "@/routes";

type Handler = (url: URL, init: RequestInit) => { status?: number; body?: unknown } | undefined;

/** Simula a API: cada handler recebe a URL e devolve status/body (ou undefined para 404). */
export function mockApi(handler: Handler) {
  const calls: Array<{ method: string; path: string; body: unknown }> = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
      const url = new URL(String(input), "http://localhost");
      const body = init.body ? JSON.parse(String(init.body)) : undefined;
      calls.push({ method: init.method ?? "GET", path: url.pathname.replace("/api/v1", ""), body });
      if (url.pathname.endsWith("/auth/csrf")) {
        return new Response(JSON.stringify({ csrf_token: "t" }), { status: 200 });
      }
      const result = handler(url, init) ?? {
        status: 404,
        body: { error: { code: "not_found", message: "Não encontrado." } },
      };
      const status = result.status ?? 200;
      return new Response(status === 204 ? null : JSON.stringify(result.body ?? {}), { status });
    }),
  );
  return calls;
}

export function renderRoute(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  const queryClient = createQueryClient();
  queryClient.setDefaultOptions({ queries: { retry: false, staleTime: 0 } });
  const utils = render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return { ...utils, router, queryClient };
}

export const unauthorized = {
  status: 401,
  body: { error: { code: "unauthorized", message: "Você precisa estar logado." } },
};
