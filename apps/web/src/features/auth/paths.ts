export function loginPath(next: string): string {
  return `/login?${new URLSearchParams({ next })}`;
}

/** Só aceita caminhos internos (evita open redirect via ?next=). */
export function safeNext(value: string | null, fallback = "/groups"): string {
  if (!value || !value.startsWith("/") || value.startsWith("//") || value.includes("\\"))
    return fallback;
  return value;
}
