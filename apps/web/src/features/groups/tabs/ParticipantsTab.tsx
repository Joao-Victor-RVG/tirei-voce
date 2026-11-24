import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { errorMessage } from "@/api/client";
import type { Group, Participant } from "@/api/types";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { Alert, Avatar, Button, Card, EmptyState, ErrorState, PageLoader } from "@/components/ui";

import { useLeaveGroup, useParticipants, useRemoveParticipant, useSetCoOrganizer } from "../api";
import { isFrozen, isOrganizer, isOwner } from "../status";

const ROLE_LABEL: Record<Participant["role"], string | null> = {
  owner: "Organização",
  co_owner: "Coorganização",
  member: null,
};

export function ParticipantsTab({ group }: { group: Group }) {
  const participants = useParticipants(group.id);
  const remove = useRemoveParticipant(group.id);
  const setRole = useSetCoOrganizer(group.id);
  const leave = useLeaveGroup(group.id);
  const navigate = useNavigate();
  const [toRemove, setToRemove] = useState<Participant | null>(null);
  const [confirmLeave, setConfirmLeave] = useState(false);
  const organizer = isOrganizer(group);
  const owner = isOwner(group);
  const frozen = isFrozen(group.status);
  const finished = group.status === "FINISHED";

  if (participants.isPending) return <PageLoader />;
  if (participants.isError)
    return (
      <ErrorState
        message={errorMessage(participants.error)}
        onRetry={() => participants.refetch()}
      />
    );

  const people = participants.data;
  const canRemove = (person: Participant) =>
    organizer && !frozen && person.role !== "owner" && (owner || person.role === "member");

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
            <li key={person.id} className="flex flex-wrap items-center gap-3 py-3">
              <Avatar name={person.user.name} url={person.user.avatar_url} />
              <span className="min-w-0 flex-1">
                <span className="block truncate font-bold">
                  {person.user.name}{" "}
                  {person.is_me && <span className="font-normal text-gray-500">(você)</span>}
                </span>
                {ROLE_LABEL[person.role] && (
                  <span className="text-sm text-(--accent-text)">{ROLE_LABEL[person.role]}</span>
                )}
              </span>
              <span className="flex gap-1">
                {owner && !finished && person.role !== "owner" && (
                  <Button
                    variant="ghost"
                    className="min-h-9 px-3 text-sm"
                    loading={setRole.isPending && setRole.variables?.participantId === person.id}
                    onClick={() =>
                      setRole.mutate({
                        participantId: person.id,
                        promote: person.role === "member",
                      })
                    }
                  >
                    {person.role === "member" ? "Tornar coorganizador" : "Tirar da coorganização"}
                  </Button>
                )}
                {canRemove(person) && (
                  <Button
                    variant="ghost"
                    className="min-h-9 px-3 text-sm"
                    onClick={() => setToRemove(person)}
                  >
                    Remover
                  </Button>
                )}
              </span>
            </li>
          ))}
        </ul>
        {remove.isError && <Alert>{errorMessage(remove.error)}</Alert>}
        {setRole.isError && <Alert>{errorMessage(setRole.error)}</Alert>}
        {owner && !finished && (
          <p className="mt-3 text-sm text-gray-600">
            Coorganizadores ajudam a configurar o grupo e podem sortear. Ninguém, nem a organização,
            vê quem tirou quem.
          </p>
        )}
      </Card>

      {!owner && !frozen && (
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
