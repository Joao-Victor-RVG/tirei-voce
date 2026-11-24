import type { FieldErrors, UseFormRegister } from "react-hook-form";

import { Field, Input, TextArea } from "@/components/ui";

import type { EventValues } from "./eventForm";

type Props<T extends EventValues> = {
  register: UseFormRegister<T>;
  errors: FieldErrors<T>;
};

export function EventFields<T extends EventValues>({ register, errors }: Props<T>) {
  const reg = register as unknown as UseFormRegister<EventValues>;
  const err = errors as FieldErrors<EventValues>;
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        <Field label="Valor mínimo (R$)" error={err.min_value?.message}>
          {(id) => <Input id={id} inputMode="decimal" placeholder="50,00" {...reg("min_value")} />}
        </Field>
        <Field label="Valor máximo (R$)" error={err.max_value?.message}>
          {(id) => <Input id={id} inputMode="decimal" placeholder="100,00" {...reg("max_value")} />}
        </Field>
      </div>
      <Field
        label="Data e hora do evento"
        error={err.event_at?.message}
        hint="Horário de Brasília."
      >
        {(id) => <Input id={id} type="datetime-local" {...reg("event_at")} />}
      </Field>
      <Field label="Local" error={err.event_location?.message}>
        {(id) => <Input id={id} placeholder="Ex.: Casa da vó" {...reg("event_location")} />}
      </Field>
      <Field label="Link do mapa (opcional)" error={err.event_maps_url?.message}>
        {(id) => (
          <Input
            id={id}
            type="url"
            inputMode="url"
            placeholder="https://maps.app.goo.gl/…"
            {...reg("event_maps_url")}
          />
        )}
      </Field>
      <Field
        label="Prazo para entrar no grupo (opcional)"
        error={err.join_deadline_at?.message}
        hint="Depois disso, ninguém mais entra pelo convite."
      >
        {(id) => <Input id={id} type="datetime-local" {...reg("join_deadline_at")} />}
      </Field>
      <Field label="Regras e recados (opcional)" error={err.description?.message}>
        {(id) => (
          <TextArea
            id={id}
            placeholder="Ex.: Nada de presente repetido do ano passado 😅"
            {...reg("description")}
          />
        )}
      </Field>
    </div>
  );
}
