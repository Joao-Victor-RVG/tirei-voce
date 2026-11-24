import { useState } from "react";

import { errorMessage } from "@/api/client";
import type { Group } from "@/api/types";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { Alert, Button, Card, EmptyState } from "@/components/ui";

import { useDrawValidation, useExecuteDraw } from "../api";
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
        Sortear 🎲
      </Button>
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
