import { useState } from "react";

import { errorMessage } from "@/api/client";
import type { Group } from "@/api/types";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { Alert, Button, Card, EmptyState, Field, Input } from "@/components/ui";
import { formatDateTime, isoToLocalInput, localInputToIso } from "@/lib/format";

import { useDrawValidation, useExecuteDraw, useUpdateGroup } from "../api";
import { DrawValidationCard } from "../DrawValidationCard";
import { GiftProgressCard } from "../GiftProgressCard";
import { RevealCard } from "../RevealCard";
import { isDrawn, isOrganizer } from "../status";

export function DrawTab({ group }: { group: Group }) {
  if (isDrawn(group.status))
    return (
      <div className="space-y-4">
        {isOrganizer(group) && <GiftProgressCard groupId={group.id} />}
        <RevealCard group={group} />
      </div>
    );
  if (isOrganizer(group)) return <OrganizerDraw group={group} />;
  return (
    <Card>
      <EmptyState emoji="⏳" title="Aguardando o sorteio">
        Quando {group.owner.name} sortear, você vai ver aqui quem tirou.
      </EmptyState>
    </Card>
  );
}

function OrganizerDraw({ group }: { group: Group }) {
  const validation = useDrawValidation(group.id);
  const draw = useExecuteDraw(group.id);
  const [confirm, setConfirm] = useState(false);
  const [idempotencyKey, setIdempotencyKey] = useState(() => crypto.randomUUID());
  const possible = validation.data?.possible ?? false;
  const canDraw = group.status === "OPEN" || group.status === "CLOSED";

  return (
    <Card className="space-y-4 text-center">
      <div className="animate-wiggle text-6xl" aria-hidden>
        {group.theme.emoji}
      </div>
      <h2 className="text-2xl font-black">Hora do sorteio!</h2>
      <p className="text-gray-600">
        Depois do sorteio, participantes e regras ficam congelados. Ninguém, nem você, consegue ver
        quem tirou quem: cada pessoa só vê o próprio amigo secreto.
      </p>
      {canDraw ? (
        <DrawValidationCard groupId={group.id} />
      ) : (
        <Alert tone="info">Abra as inscrições do grupo antes de sortear.</Alert>
      )}
      {group.status === "OPEN" && (
        <p className="text-sm text-gray-600">
          Dica: feche as inscrições antes, para ninguém ficar de fora.
        </p>
      )}
      {draw.isError && <Alert>{errorMessage(draw.error)}</Alert>}
      <Button block disabled={!canDraw || !possible} onClick={() => setConfirm(true)}>
        Sortear agora 🎲
      </Button>
      {canDraw && <ScheduleDraw group={group} />}
      <ConfirmDialog
        open={confirm}
        title="Sortear agora?"
        confirmLabel="Sim, sortear!"
        loading={draw.isPending}
        onClose={() => setConfirm(false)}
        onConfirm={async () => {
          try {
            await draw.mutateAsync(idempotencyKey);
          } catch {
            setIdempotencyKey(crypto.randomUUID());
          }
          setConfirm(false);
        }}
      >
        O sorteio não pode ser desfeito. {validation.data?.participant_count ?? 0} pessoas vão
        participar.
      </ConfirmDialog>
    </Card>
  );
}

function ScheduleDraw({ group }: { group: Group }) {
  const update = useUpdateGroup(group.id);
  const [value, setValue] = useState(() => isoToLocalInput(group.draw_scheduled_at));
  const [error, setError] = useState<string | null>(null);

  const save = async (iso: string | null) => {
    setError(null);
    if (iso && Date.parse(iso) <= Date.now()) return setError("Escolha um horário no futuro.");
    try {
      await update.mutateAsync({ draw_scheduled_at: iso });
      if (!iso) setValue("");
    } catch (e) {
      setError(errorMessage(e));
    }
  };

  return (
    <div className="space-y-3 rounded-2xl bg-black/[0.03] p-4 text-left">
      <h3 className="font-extrabold">⏰ Sorteio automático</h3>
      {group.draw_scheduled_at ? (
        <>
          <p className="text-sm">
            Agendado para <strong>{formatDateTime(group.draw_scheduled_at)}</strong>. Se as regras
            impedirem, avisamos a organização.
          </p>
          <Button variant="secondary" loading={update.isPending} onClick={() => save(null)}>
            Cancelar agendamento
          </Button>
        </>
      ) : (
        <>
          <p className="text-sm text-gray-600">
            Prefere deixar marcado? O sorteio acontece sozinho no horário.
          </p>
          <Field label="Data e hora do sorteio" hint="Horário de Brasília.">
            {(id) => (
              <Input
                id={id}
                type="datetime-local"
                value={value}
                onChange={(e) => setValue(e.target.value)}
              />
            )}
          </Field>
          <Button
            variant="secondary"
            loading={update.isPending}
            disabled={!value}
            onClick={() => save(localInputToIso(value))}
          >
            Agendar sorteio
          </Button>
        </>
      )}
      {error && <Alert>{error}</Alert>}
    </div>
  );
}
