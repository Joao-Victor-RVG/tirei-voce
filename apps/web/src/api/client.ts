const BASE_URL = "/api/v1";
const CSRF_COOKIE = "tv_csrf";

export type ApiErrorDetails = Record<string, unknown> | Array<Record<string, unknown>> | undefined;

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: ApiErrorDetails;

  constructor(status: number, code: string, message: string, details?: ApiErrorDetails) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

const NETWORK_ERROR = "Não foi possível conectar. Verifique sua internet e tente novamente.";
const GENERIC_ERROR = "Ops! Algo deu errado. Tente novamente.";

function readCookie(name: string): string | null {
  const match = document.cookie.split("; ").find((part) => part.startsWith(`${name}=`));
  return match ? decodeURIComponent(match.slice(name.length + 1)) : null;
}

let csrfPromise: Promise<string> | null = null;

async function csrfToken(): Promise<string> {
  const existing = readCookie(CSRF_COOKIE);
  if (existing) return existing;
  csrfPromise ??= fetch(`${BASE_URL}/auth/csrf`, { credentials: "same-origin" })
    .then((r) => r.json() as Promise<{ csrf_token: string }>)
    .then((body) => body.csrf_token)
    .finally(() => {
      csrfPromise = null;
    });
  return csrfPromise;
}

// Uma única renovação por vez: várias requisições com 401 esperam a mesma promessa.
let refreshPromise: Promise<boolean> | null = null;

function refreshSession(): Promise<boolean> {
  refreshPromise ??= (async () => {
    try {
      const response = await fetch(`${BASE_URL}/auth/refresh`, {
        method: "POST",
        credentials: "same-origin",
        headers: { "X-CSRF-Token": await csrfToken() },
      });
      return response.ok;
    } catch {
      return false;
    } finally {
      refreshPromise = null;
    }
  })();
  return refreshPromise;
}

type RequestOptions = {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  query?: Record<string, string | number | undefined | null>;
  headers?: Record<string, string>;
  /** Não tenta renovar a sessão em caso de 401 (usado no próprio login/refresh). */
  skipRefresh?: boolean;
};

const NO_REFRESH_PATHS = ["/auth/login", "/auth/register", "/auth/refresh", "/auth/logout"];

export async function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const method = options.method ?? "GET";
  const url = new URL(`${BASE_URL}${path}`, window.location.origin);
  for (const [key, value] of Object.entries(options.query ?? {})) {
    if (value !== undefined && value !== null && value !== "")
      url.searchParams.set(key, String(value));
  }

  const send = async (): Promise<Response> => {
    const headers: Record<string, string> = { Accept: "application/json", ...options.headers };
    if (options.body !== undefined) headers["Content-Type"] = "application/json";
    if (method !== "GET") headers["X-CSRF-Token"] = await csrfToken();
    return fetch(url, {
      method,
      headers,
      credentials: "same-origin",
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    });
  };

  let response: Response;
  try {
    response = await send();
    const canRefresh = !options.skipRefresh && !NO_REFRESH_PATHS.includes(path);
    if (response.status === 401 && canRefresh && (await refreshSession())) {
      response = await send();
    }
  } catch {
    throw new ApiError(0, "network_error", NETWORK_ERROR);
  }

  if (response.status === 204) return undefined as T;
  const data: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const error = (
      data as { error?: { code?: string; message?: string; details?: ApiErrorDetails } }
    )?.error;
    throw new ApiError(
      response.status,
      error?.code ?? "http_error",
      error?.message ?? GENERIC_ERROR,
      error?.details,
    );
  }
  return data as T;
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return GENERIC_ERROR;
}
