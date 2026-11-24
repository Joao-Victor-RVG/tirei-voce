export const TIMEZONE = "America/Sao_Paulo";

const currency = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

export function formatCents(cents: number | null | undefined): string {
  return cents == null ? "" : currency.format(cents / 100);
}

export function formatValueRange(min?: number | null, max?: number | null): string | null {
  if (min != null && max != null)
    return min === max ? formatCents(min) : `${formatCents(min)} a ${formatCents(max)}`;
  if (max != null) return `até ${formatCents(max)}`;
  if (min != null) return `a partir de ${formatCents(min)}`;
  return null;
}

/** "12,50" | "12" | "1.234,56" -> centavos. Retorna null se vazio/ inválido. */
export function parseReais(value: string): number | null {
  const cleaned = value
    .replace(/[^\d,.-]/g, "")
    .replace(/\./g, "")
    .replace(",", ".");
  if (!cleaned) return null;
  const number = Number(cleaned);
  return Number.isFinite(number) && number >= 0 ? Math.round(number * 100) : null;
}

export function centsToInput(cents: number | null | undefined): string {
  return cents == null ? "" : (cents / 100).toFixed(2).replace(".", ",");
}

const dateTime = new Intl.DateTimeFormat("pt-BR", {
  timeZone: TIMEZONE,
  weekday: "long",
  day: "2-digit",
  month: "long",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

const shortDate = new Intl.DateTimeFormat("pt-BR", {
  timeZone: TIMEZONE,
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
});

const shortDateTime = new Intl.DateTimeFormat("pt-BR", {
  timeZone: TIMEZONE,
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

export function formatDateTime(iso: string | null | undefined): string {
  return iso ? dateTime.format(new Date(iso)) : "";
}

export function formatShortDate(iso: string | null | undefined): string {
  return iso ? shortDate.format(new Date(iso)) : "";
}

export function formatShortDateTime(iso: string | null | undefined): string {
  return iso ? shortDateTime.format(new Date(iso)) : "";
}

/** Valor de <input type="datetime-local"> (horário de Brasília) -> ISO em UTC. */
export function localInputToIso(value: string): string | null {
  if (!value) return null;
  const [date, time] = value.split("T");
  if (!date || !time) return null;
  // Brasília não tem horário de verão desde 2019: UTC-03:00.
  return new Date(`${date}T${time}:00-03:00`).toISOString();
}

/** ISO -> valor para <input type="datetime-local"> no horário de Brasília. */
export function isoToLocalInput(iso: string | null | undefined): string {
  if (!iso) return "";
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: TIMEZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(new Date(iso));
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? "";
  return `${get("year")}-${get("month")}-${get("day")}T${get("hour")}:${get("minute")}`;
}

export type Countdown = {
  days: number;
  hours: number;
  minutes: number;
  seconds: number;
  past: boolean;
};

export function countdown(targetIso: string, now: number = Date.now()): Countdown {
  const diff = new Date(targetIso).getTime() - now;
  const total = Math.max(0, Math.floor(diff / 1000));
  return {
    days: Math.floor(total / 86400),
    hours: Math.floor((total % 86400) / 3600),
    minutes: Math.floor((total % 3600) / 60),
    seconds: total % 60,
    past: diff <= 0,
  };
}
