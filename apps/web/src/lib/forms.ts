import type { FieldValues, Path, UseFormSetError } from "react-hook-form";

import { ApiError, errorMessage } from "@/api/client";

/** Joga erros da API nos campos do formulário (ou no erro geral "root"). */
export function applyApiError<T extends FieldValues>(
  error: unknown,
  setError: UseFormSetError<T>,
  fieldsByCode: Partial<Record<string, Path<T>>> = {},
): void {
  if (error instanceof ApiError) {
    const field = fieldsByCode[error.code];
    if (field) {
      setError(field, { message: error.message });
      return;
    }
    if (error.code === "validation_error" && Array.isArray(error.details)) {
      let matched = false;
      for (const detail of error.details) {
        const name = String(detail.field ?? "") as Path<T>;
        if (name) {
          setError(name, { message: "Valor inválido." });
          matched = true;
        }
      }
      if (matched) return;
    }
  }
  setError("root", { message: errorMessage(error) });
}

const NEXT_KEY = "tv_next";

/** Guarda para onde voltar depois de confirmar o e-mail (o link do e-mail não carrega isso). */
export function rememberNext(next: string): void {
  try {
    sessionStorage.setItem(NEXT_KEY, next);
  } catch {
    // modo privado/armazenamento bloqueado: segue sem lembrar
  }
}

export function popRememberedNext(): string | null {
  try {
    const value = sessionStorage.getItem(NEXT_KEY);
    sessionStorage.removeItem(NEXT_KEY);
    return value;
  } catch {
    return null;
  }
}
