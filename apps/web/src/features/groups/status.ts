import type { GroupStatus } from "@/api/types";

export const STATUS_LABEL: Record<GroupStatus, string> = {
  DRAFT: "Rascunho",
  OPEN: "Inscrições abertas",
  CLOSED: "Inscrições fechadas",
  DRAWN: "Sorteado",
  FINISHED: "Encerrado",
};

export const STATUS_CLASSES: Record<GroupStatus, string> = {
  DRAFT: "bg-gray-100 text-gray-700",
  OPEN: "bg-emerald-100 text-emerald-800",
  CLOSED: "bg-amber-100 text-amber-900",
  DRAWN: "bg-(--accent-soft) text-(--accent-text)",
  FINISHED: "bg-gray-200 text-gray-600",
};

export const isFrozen = (status: GroupStatus) => status === "DRAWN" || status === "FINISHED";
export const isDrawn = isFrozen;

export function inviteUrl(code: string): string {
  return `${window.location.origin}/i/${code}`;
}
