import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { errorMessage } from "@/api/client";
import type { Group, Participant } from "@/api/types";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { Alert, Avatar, Button, Card, EmptyState, ErrorState, PageLoader } from "@/components/ui";

import { useLeaveGroup, useParticipants, useRemoveParticipant } from "../api";
import { isFrozen } from "../status";

export function ParticipantsTab({ group }: { group: Group }) {
  const participants = useParticipants(group.id);
  const remove = useRemoveParticipant(group.id);
  const leave = useLeaveGroup(group.id);
  const navigate = useNavigate();
  const [toRemove, setToRemove] = useState<Participant | null>(null);
  const [confirmLeave, setConfirmLeave] = useState(false);
  const organizer = group.my_role === "owner";
  const frozen = isFrozen(group.status);

  if (participants.isPending) return <PageLoader />;
  if (participants.isError)
    return (
      <ErrorState
        message={errorMessage(participants.error)}
        onRetry={() => participants.refetch()}
      />
    );

  const people = participants.data;
  return (
    <div className="space-y-4">
      <Card>
        <h2 className="mb-3 text-lg font-extrabold">
          {people.length} {people.length === 1 ? "participante" : "participantes"}
        </h2>
        {people.length <= 1 && (
          <EmptyState emoji="🙋" title="Só você por enquanto">
            Compartilhe o convite na aba “Visão geral”.
          </EmptyState>
        )}
        <ul className="divide-y divide-black/5">
          {people.map((person) => (
            <li key={person.id} className="flex items-center gap-3 py-3">
              <Avatar name={person.user.name} url={person.user.avatar_url} />
              <span className="min-w-0 flex-1">
                <span className="block truncate font-bold">
                  {person.user.name}{" "}
                  {person.is_me && <span className="font-normal text-gray-500">(você)</span>}
                </span>
                {person.role === "owner" && (
                  <span className="text-sm text-(--accent-text)">Organização</span>
                )}
              </span>
              {organizer && !frozen && person.role !== "owner" && (
                <Button
                  variant="ghost"
                  className="min-h-9 px-3 text-sm"
                  onClick={() => setToRemove(person)}
                >
                  Remover
                </Button>
              )}
            </li>
          ))}
        </ul>
        {remove.isError && <Alert>{errorMessage(remove.error)}</Alert>}
      </Card>

      {!organizer && !frozen && (
        <div className="text-center">
          <Button variant="secondary" onClick={() => setConfirmLeave(true)}>
            Sair do grupo
          </Button>
          {leave.isError && <Alert>{errorMessage(leave.error)}</Alert>}
        </div>
      )}

      <ConfirmDialog
        open={toRemove !== null}
        title={`Remover ${toRemove?.user.name ?? ""}?`}
        confirmLabel="Remover"
        danger
        loading={remove.isPending}
        onClose={() => setToRemove(null)}
        onConfirm={async () => {
          if (toRemove) await remove.mutateAsync(toRemove.id).catch(() => undefined);
          setToRemove(null);
        }}
      >
        A pessoa sai do grupo e das regras do sorteio. Ela pode voltar pelo convite enquanto as
        inscrições estiverem abertas.
      </ConfirmDialog>
      <ConfirmDialog
        open={confirmLeave}
        title="Sair do grupo?"
        confirmLabel="Sair"
        danger
        loading={leave.isPending}
        onClose={() => setConfirmLeave(false)}
        onConfirm={async () => {
          try {
            await leave.mutateAsync();
            navigate("/groups", { replace: true });
          } catch {
            setConfirmLeave(false);
          }
        }}
      >
        Você deixa de participar do sorteio. Dá para voltar pelo convite enquanto estiver aberto.
      </ConfirmDialog>
    </div>
  );
}
