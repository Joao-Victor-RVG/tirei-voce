import { z } from "zod";

import type { Group, GroupUpdate } from "@/api/types";
import { centsToInput, isoToLocalInput, localInputToIso, parseReais } from "@/lib/format";

const money = z
  .string()
  .trim()
  .refine((v) => v === "" || parseReais(v) !== null, "Valor inválido.");

/** Campos de evento compartilhados pelo wizard e pela edição do grupo. */
export const eventSchema = z
  .object({
    min_value: money,
    max_value: money,
    event_at: z.string(),
    event_location: z.string().trim().max(200, "Máximo de 200 caracteres."),
    event_maps_url: z
      .string()
      .trim()
      .refine(
        (v) => v === "" || /^https?:\/\/\S+$/.test(v),
        "Cole um link que comece com https://",
      ),
    join_deadline_at: z.string(),
    wishlist_deadline_at: z.string(),
    description: z.string().trim().max(2000, "Máximo de 2000 caracteres."),
  })
  .superRefine((v, ctx) => {
    const min = parseReais(v.min_value);
    const max = parseReais(v.max_value);
    if (min !== null && max !== null && max < min) {
      ctx.addIssue({
        code: "custom",
        path: ["max_value"],
        message: "Deve ser maior ou igual ao mínimo.",
      });
    }
    const now = Date.now();
    const eventAt = localInputToIso(v.event_at);
    const deadline = localInputToIso(v.join_deadline_at);
    if (eventAt && Date.parse(eventAt) <= now) {
      ctx.addIssue({ code: "custom", path: ["event_at"], message: "Escolha uma data no futuro." });
    }
    if (deadline && Date.parse(deadline) <= now) {
      ctx.addIssue({
        code: "custom",
        path: ["join_deadline_at"],
        message: "Escolha uma data no futuro.",
      });
    }
    const wishlistDeadline = localInputToIso(v.wishlist_deadline_at);
    if (wishlistDeadline && Date.parse(wishlistDeadline) <= now) {
      ctx.addIssue({
        code: "custom",
        path: ["wishlist_deadline_at"],
        message: "Escolha uma data no futuro.",
      });
    }
    if (eventAt && wishlistDeadline && Date.parse(wishlistDeadline) > Date.parse(eventAt)) {
      ctx.addIssue({
        code: "custom",
        path: ["wishlist_deadline_at"],
        message: "O prazo precisa ser antes do evento.",
      });
    }
    if (eventAt && deadline && Date.parse(deadline) > Date.parse(eventAt)) {
      ctx.addIssue({
        code: "custom",
        path: ["join_deadline_at"],
        message: "O prazo precisa ser antes do evento.",
      });
    }
  });

export type EventValues = z.infer<typeof eventSchema>;

export const emptyEvent: EventValues = {
  min_value: "",
  max_value: "",
  event_at: "",
  event_location: "",
  event_maps_url: "",
  join_deadline_at: "",
  wishlist_deadline_at: "",
  description: "",
};

export function eventValuesFromGroup(group: Group): EventValues {
  return {
    min_value: centsToInput(group.min_value_cents),
    max_value: centsToInput(group.max_value_cents),
    event_at: isoToLocalInput(group.event_at),
    event_location: group.event_location ?? "",
    event_maps_url: group.event_maps_url ?? "",
    join_deadline_at: isoToLocalInput(group.join_deadline_at),
    wishlist_deadline_at: isoToLocalInput(group.wishlist_deadline_at),
    description: group.description ?? "",
  };
}

type EventPayload = Pick<
  GroupUpdate,
  | "min_value_cents"
  | "max_value_cents"
  | "event_at"
  | "event_location"
  | "event_maps_url"
  | "join_deadline_at"
  | "wishlist_deadline_at"
  | "description"
>;

export function eventPayload(v: EventValues): EventPayload {
  return {
    min_value_cents: parseReais(v.min_value),
    max_value_cents: parseReais(v.max_value),
    event_at: localInputToIso(v.event_at),
    event_location: v.event_location || null,
    event_maps_url: v.event_maps_url || null,
    join_deadline_at: localInputToIso(v.join_deadline_at),
    wishlist_deadline_at: localInputToIso(v.wishlist_deadline_at),
    description: v.description || null,
  };
}
