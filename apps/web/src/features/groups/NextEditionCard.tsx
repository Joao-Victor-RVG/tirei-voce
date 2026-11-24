import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { errorMessage } from "@/api/client";
import type { Group } from "@/api/types";
import { Alert, Button, Card, Field, Input } from "@/components/ui";
import { localInputToIso } from "@/lib/format";

import { useDuplicateGroup } from "./api";

/** "Criar próxima edição": copia as configurações e, por padrão, evita repetir os pares. */
export function NextEditionCard({ group }: { group: Group }) {
  const duplicate = useDuplicateGroup(group.id);
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState(group.title);
  const [eventAt, setEventAt] = useState("");
  const [avoid, setAvoid] = useState(true);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const created = await duplicate.mutateAsync({
        title: title.trim() || undefined,
        event_at: localInputToIso(eventAt),
        avoid_previous_pairs: avoid,
      });
      navigate(`/groups/${created.id}`);
    } catch {
      // erro exibido abaixo
    }
  };

  return (
    <Card className="space-y-3">
      <h2 className="text-lg font-extrabold">🔁 Próxima edição</h2>
      <p className="text-sm text-gray-600">
        Crie o grupo do ano que vem com as mesmas configurações. A galera entra de novo pelo convite
        novo.
      </p>
      {!open ? (
        <Button variant="secondary" onClick={() => setOpen(true)}>
          Criar próxima edição
        </Button>
      ) : (
        <form onSubmit={submit} className="space-y-3">
          <Field label="Nome da nova edição">
            {(id) => <Input id={id} value={title} onChange={(e) => setTitle(e.target.value)} />}
          </Field>
          <Field label="Data do evento (opcional)" hint="Horário de Brasília.">
            {(id) => (
              <Input
                id={id}
                type="datetime-local"
                value={eventAt}
                onChange={(e) => setEventAt(e.target.value)}
              />
            )}
          </Field>
          <label className="flex items-start gap-3 rounded-2xl bg-black/[0.03] p-3">
            <input
              type="checkbox"
              className="mt-1 size-5 accent-(--accent)"
              checked={avoid}
              onChange={(e) => setAvoid(e.target.checked)}
            />
            <span>
              <span className="block font-bold">Não repetir os pares desta edição</span>
              <span className="block text-sm text-gray-600">
                Ninguém tira de novo quem tirou agora. Continua secreto: nem a organização vê os
                pares.
              </span>
            </span>
          </label>
          {duplicate.isError && <Alert>{errorMessage(duplicate.error)}</Alert>}
          <div className="flex gap-2">
            <Button type="submit" loading={duplicate.isPending}>
              Criar
            </Button>
            <Button type="button" variant="secondary" onClick={() => setOpen(false)}>
              Cancelar
            </Button>
          </div>
        </form>
      )}
    </Card>
  );
}
