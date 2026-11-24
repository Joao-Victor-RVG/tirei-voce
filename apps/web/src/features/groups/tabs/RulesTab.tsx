import { useState } from "react";

import { errorMessage } from "@/api/client";
import type { Circle, Group, Participant } from "@/api/types";
import { Alert, Button, Card, ErrorState, Field, Input, PageLoader } from "@/components/ui";
import { cx } from "@/lib/cx";

import {
  useBlockedPairs,
  useCircles,
  useCreateCircle,
  useCreatePair,
  useDeleteCircle,
  useDeletePair,
  useParticipants,
  useUpdateCircle,
} from "../api";
import { DrawValidationCard } from "../DrawValidationCard";
import { isFrozen } from "../status";

export function RulesTab({ group }: { group: Group }) {
  const participants = useParticipants(group.id);
  const circles = useCircles(group.id);
  const pairs = useBlockedPairs(group.id);
  const frozen = isFrozen(group.status);

  if (participants.isPending || circles.isPending || pairs.isPending) return <PageLoader />;
  const failed = participants.error ?? circles.error ?? pairs.error;
  if (failed)
    return (
      <ErrorState
        message={errorMessage(failed)}
        onRetry={() => {
          void participants.refetch();
          void circles.refetch();
          void pairs.refetch();
        }}
      />
    );

  const people = participants.data ?? [];
  return (
    <div className="space-y-4">
      {frozen ? (
        <Alert tone="info">O sorteio já foi feito: as regras estão congeladas.</Alert>
      ) : (
        <DrawValidationCard groupId={group.id} />
      )}
      <CirclesCard
        groupId={group.id}
        circles={circles.data ?? []}
        people={people}
        frozen={frozen}
      />
      <PairsCard groupId={group.id} people={people} frozen={frozen} />
    </div>
  );
}

function PeoplePicker({
  people,
  selected,
  onChange,
}: {
  people: Participant[];
  selected: string[];
  onChange: (ids: string[]) => void;
}) {
  return (
    <fieldset>
      <legend className="mb-2 text-sm font-bold">Quem faz parte</legend>
      <div className="flex flex-wrap gap-2">
        {people.map((person) => {
          const checked = selected.includes(person.id);
          return (
            <label
              key={person.id}
              className={cx(
                "cursor-pointer rounded-full px-3 py-2 text-sm font-bold ring-1 transition",
                checked ? "bg-(--accent) text-white ring-(--accent)" : "bg-white ring-black/10",
              )}
            >
              <input
                type="checkbox"
                className="sr-only"
                checked={checked}
                onChange={() =>
                  onChange(
                    checked ? selected.filter((id) => id !== person.id) : [...selected, person.id],
                  )
                }
              />
              {person.user.name}
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}

function CirclesCard({
  groupId,
  circles,
  people,
  frozen,
}: {
  groupId: string;
  circles: Circle[];
  people: Participant[];
  frozen: boolean;
}) {
  const create = useCreateCircle(groupId);
  const update = useUpdateCircle(groupId);
  const remove = useDeleteCircle(groupId);
  const [editing, setEditing] = useState<Circle | "new" | null>(null);
  const [name, setName] = useState("");
  const [members, setMembers] = useState<string[]>([]);
  const [formError, setFormError] = useState<string | null>(null);

  const start = (circle: Circle | "new") => {
    setEditing(circle);
    setName(circle === "new" ? "" : circle.name);
    setMembers(circle === "new" ? [] : circle.members.map((m) => m.participant_id));
    setFormError(null);
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return setFormError("Dê um nome ao círculo (ex.: Casal João e Maria).");
    if (members.length < 2) return setFormError("Escolha pelo menos 2 pessoas.");
    try {
      const data = { name: name.trim(), participant_ids: members };
      if (editing === "new") await create.mutateAsync(data);
      else if (editing) await update.mutateAsync({ circleId: editing.id, data });
      setEditing(null);
    } catch (error) {
      setFormError(errorMessage(error));
    }
  };

  return (
    <Card className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-lg font-extrabold">Círculos de exclusão</h2>
        {!frozen && editing === null && (
          <Button className="min-h-9 px-4 text-sm" onClick={() => start("new")}>
            + Círculo
          </Button>
        )}
      </div>
      <p className="text-sm text-gray-600">
        Ninguém tira outra pessoa do mesmo círculo. Use para casais e famílias.
      </p>

      {editing !== null && (
        <form onSubmit={submit} className="space-y-3 rounded-2xl bg-(--accent-soft)/50 p-4">
          <Field label="Nome do círculo">
            {(id) => (
              <Input
                id={id}
                value={name}
                placeholder="Ex.: Casal João e Maria"
                onChange={(e) => setName(e.target.value)}
              />
            )}
          </Field>
          <PeoplePicker people={people} selected={members} onChange={setMembers} />
          {formError && <Alert>{formError}</Alert>}
          <div className="flex gap-2">
            <Button type="submit" loading={create.isPending || update.isPending}>
              Salvar
            </Button>
            <Button type="button" variant="secondary" onClick={() => setEditing(null)}>
              Cancelar
            </Button>
          </div>
        </form>
      )}

      {circles.length === 0 ? (
        editing === null && <p className="text-sm text-gray-500">Nenhum círculo ainda.</p>
      ) : (
        <ul className="space-y-2">
          {circles.map((circle) => (
            <li key={circle.id} className="flex items-start gap-3 rounded-2xl bg-black/[0.03] p-3">
              <div className="min-w-0 flex-1">
                <p className="font-bold">{circle.name}</p>
                <p className="text-sm text-gray-600">
                  {circle.members.map((m) => m.name).join(", ")}
                </p>
              </div>
              {!frozen && (
                <div className="flex shrink-0 gap-1">
                  <Button
                    variant="ghost"
                    className="min-h-9 px-3 text-sm"
                    onClick={() => start(circle)}
                  >
                    Editar
                  </Button>
                  <Button
                    variant="ghost"
                    className="min-h-9 px-3 text-sm"
                    onClick={() => remove.mutate(circle.id)}
                    aria-label={`Excluir círculo ${circle.name}`}
                  >
                    Excluir
                  </Button>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
      {remove.isError && <Alert>{errorMessage(remove.error)}</Alert>}
    </Card>
  );
}

function PairsCard({
  groupId,
  people,
  frozen,
}: {
  groupId: string;
  people: Participant[];
  frozen: boolean;
}) {
  const pairs = useBlockedPairs(groupId);
  const create = useCreatePair(groupId);
  const remove = useDeletePair(groupId);
  const [giver, setGiver] = useState("");
  const [receiver, setReceiver] = useState("");
  const [bidirectional, setBidirectional] = useState(true);
  const [formError, setFormError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    if (!giver || !receiver) return setFormError("Escolha as duas pessoas.");
    if (giver === receiver) return setFormError("Escolha duas pessoas diferentes.");
    try {
      await create.mutateAsync({
        giver_participant_id: giver,
        receiver_participant_id: receiver,
        bidirectional,
      });
      setGiver("");
      setReceiver("");
    } catch (error) {
      setFormError(errorMessage(error));
    }
  };

  const select = (id: string, label: string, value: string, onChange: (v: string) => void) => (
    <select
      id={id}
      aria-label={label}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="block w-full rounded-2xl bg-white px-4 py-3 ring-1 ring-black/10 focus:ring-2 focus:ring-(--accent) focus:outline-none"
    >
      <option value="">Escolha…</option>
      {people.map((p) => (
        <option key={p.id} value={p.id}>
          {p.user.name}
        </option>
      ))}
    </select>
  );

  return (
    <Card className="space-y-3">
      <h2 className="text-lg font-extrabold">Pares bloqueados</h2>
      <p className="text-sm text-gray-600">
        Para casos específicos: “fulano não pode tirar ciclano”.
      </p>
      {!frozen && (
        <form onSubmit={submit} className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Quem">{(id) => select(id, "Quem", giver, setGiver)}</Field>
            <Field label="Não pode tirar">
              {(id) => select(id, "Não pode tirar", receiver, setReceiver)}
            </Field>
          </div>
          <label className="flex items-center gap-2 text-sm font-semibold">
            <input
              type="checkbox"
              className="size-5 accent-(--accent)"
              checked={bidirectional}
              onChange={(e) => setBidirectional(e.target.checked)}
            />
            Vale para os dois lados
          </label>
          {formError && <Alert>{formError}</Alert>}
          <Button type="submit" variant="secondary" loading={create.isPending}>
            Bloquear par
          </Button>
        </form>
      )}
      {(pairs.data ?? []).length === 0 ? (
        <p className="text-sm text-gray-500">Nenhum par bloqueado.</p>
      ) : (
        <ul className="space-y-2">
          {(pairs.data ?? []).map((pair) => (
            <li key={pair.id} className="flex items-center gap-3 rounded-2xl bg-black/[0.03] p-3">
              <span className="min-w-0 flex-1 font-semibold">
                {pair.giver.name} {pair.bidirectional ? "⇄" : "→"} {pair.receiver.name}
              </span>
              {!frozen && (
                <Button
                  variant="ghost"
                  className="min-h-9 px-3 text-sm"
                  onClick={() => remove.mutate(pair.id)}
                  aria-label={`Desbloquear ${pair.giver.name} e ${pair.receiver.name}`}
                >
                  Excluir
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
