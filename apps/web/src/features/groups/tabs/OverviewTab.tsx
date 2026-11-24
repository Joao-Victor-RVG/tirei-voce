import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { errorMessage } from "@/api/client";
import type { Group } from "@/api/types";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { Alert, Button, Card } from "@/components/ui";
import { formatDateTime, formatValueRange } from "@/lib/format";
import { applyApiError } from "@/lib/forms";

import { useGroupTransition, useRegenerateInvite, useUpdateGroup } from "../api";
import { Countdown } from "../Countdown";
import { EventFields } from "../EventFields";
import { eventPayload, eventSchema, eventValuesFromGroup, type EventValues } from "../eventForm";
import { ShareInvite } from "../ShareInvite";
import { isOrganizer } from "../status";

export function OverviewTab({ group }: { group: Group }) {
  const organizer = isOrganizer(group);
  const [editing, setEditing] = useState(false);
  const range = formatValueRange(group.min_value_cents, group.max_value_cents);

  return (
    <div className="space-y-4">
      {group.event_at && (
        <Card>
          <Countdown target={group.event_at} />
        </Card>
      )}

      {editing ? (
        <EditEvent group={group} onDone={() => setEditing(false)} />
      ) : (
        <Card className="space-y-3">
          <dl className="space-y-3">
            <Detail
              icon="📅"
              label="Quando"
              value={group.event_at ? formatDateTime(group.event_at) : "Data a definir"}
            />
            <Detail
              icon="📍"
              label="Onde"
              value={
                group.event_location || group.event_maps_url ? (
                  <>
                    {group.event_location}
                    {group.event_maps_url && (
                      <a
                        href={group.event_maps_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="ml-2 font-bold text-(--accent-text) underline"
                      >
                        Ver no mapa
                      </a>
                    )}
                  </>
                ) : (
                  "Local a definir"
                )
              }
            />
            <Detail icon="💸" label="Valor do presente" value={range ?? "Sem valor definido"} />
            {group.join_deadline_at && (
              <Detail
                icon="⏳"
                label="Entradas até"
                value={formatDateTime(group.join_deadline_at)}
              />
            )}
            <Detail
              icon="👥"
              label="Participantes"
              value={`${group.participant_count} de até ${group.max_participants}`}
            />
            <Detail icon="🧑‍🎄" label="Organização" value={group.owner.name} />
          </dl>
          {group.description && (
            <p className="rounded-2xl bg-black/[0.03] p-3 whitespace-pre-line">
              {group.description}
            </p>
          )}
          {organizer && group.status !== "FINISHED" && (
            <Button variant="ghost" onClick={() => setEditing(true)}>
              Editar informações
            </Button>
          )}
        </Card>
      )}

      <InviteCard group={group} />
      {organizer && <OrganizerActions group={group} />}
    </div>
  );
}

function Detail({ icon, label, value }: { icon: string; label: string; value: React.ReactNode }) {
  return (
    <div className="flex gap-3">
      <span aria-hidden className="text-xl">
        {icon}
      </span>
      <div>
        <dt className="text-sm font-bold text-gray-600">{label}</dt>
        <dd className="font-semibold">{value}</dd>
      </div>
    </div>
  );
}

function InviteCard({ group }: { group: Group }) {
  const organizer = isOrganizer(group);
  const regenerate = useRegenerateInvite(group.id);
  const [confirm, setConfirm] = useState(false);

  if (group.status !== "OPEN") {
    const message =
      group.status === "DRAFT"
        ? organizer
          ? "Abra as inscrições para o link de convite funcionar."
          : "O organizador ainda não abriu as inscrições."
        : "As inscrições estão fechadas.";
    return (
      <Card>
        <h2 className="mb-1 text-lg font-extrabold">Convite</h2>
        <p className="text-gray-600">{message}</p>
      </Card>
    );
  }

  return (
    <Card className="space-y-3">
      <h2 className="text-lg font-extrabold">Chame a galera</h2>
      <ShareInvite group={group} />
      {organizer && (
        <>
          <button
            type="button"
            onClick={() => setConfirm(true)}
            className="text-sm font-bold text-gray-600 underline-offset-2 hover:underline"
          >
            Gerar novo link (o antigo para de funcionar)
          </button>
          {regenerate.isError && <Alert>{errorMessage(regenerate.error)}</Alert>}
          <ConfirmDialog
            open={confirm}
            title="Gerar um novo link?"
            confirmLabel="Gerar novo link"
            loading={regenerate.isPending}
            onClose={() => setConfirm(false)}
            onConfirm={async () => {
              await regenerate.mutateAsync().catch(() => undefined);
              setConfirm(false);
            }}
          >
            Quem já entrou continua no grupo, mas o link atual deixa de funcionar.
          </ConfirmDialog>
        </>
      )}
    </Card>
  );
}

function OrganizerActions({ group }: { group: Group }) {
  const transition = useGroupTransition(group.id);
  const [confirmFinish, setConfirmFinish] = useState(false);
  const run = (action: "open" | "close" | "finish") =>
    transition.mutateAsync(action).catch(() => undefined);

  return (
    <Card className="space-y-3">
      <h2 className="text-lg font-extrabold">Organização</h2>
      {group.status === "DRAFT" && (
        <>
          <p className="text-gray-600">
            O grupo está em rascunho. Quando estiver tudo certo, abra as inscrições.
          </p>
          <Button onClick={() => run("open")} loading={transition.isPending}>
            Abrir inscrições
          </Button>
        </>
      )}
      {group.status === "OPEN" && (
        <>
          <p className="text-gray-600">
            Todo mundo entrou? Feche as inscrições para ninguém mais entrar.
          </p>
          <Button variant="secondary" onClick={() => run("close")} loading={transition.isPending}>
            Fechar inscrições
          </Button>
        </>
      )}
      {group.status === "CLOSED" && (
        <>
          <p className="text-gray-600">Inscrições fechadas. Falta alguém? Você pode reabrir.</p>
          <Button variant="secondary" onClick={() => run("open")} loading={transition.isPending}>
            Reabrir inscrições
          </Button>
        </>
      )}
      {group.status === "DRAWN" && (
        <>
          <p className="text-gray-600">
            Depois da troca de presentes, encerre o grupo (ele fica só para consulta).
          </p>
          <Button variant="secondary" onClick={() => setConfirmFinish(true)}>
            Encerrar grupo
          </Button>
        </>
      )}
      {group.status === "FINISHED" && (
        <p className="text-gray-600">Grupo encerrado. Obrigado por brincar! 💝</p>
      )}
      {transition.isError && <Alert>{errorMessage(transition.error)}</Alert>}
      <ConfirmDialog
        open={confirmFinish}
        title="Encerrar o grupo?"
        confirmLabel="Encerrar"
        loading={transition.isPending}
        onClose={() => setConfirmFinish(false)}
        onConfirm={async () => {
          await run("finish");
          setConfirmFinish(false);
        }}
      >
        O grupo fica somente leitura. Essa ação não pode ser desfeita.
      </ConfirmDialog>
    </Card>
  );
}

function EditEvent({ group, onDone }: { group: Group; onDone: () => void }) {
  const update = useUpdateGroup(group.id);
  const form = useForm<EventValues>({
    resolver: zodResolver(eventSchema),
    defaultValues: eventValuesFromGroup(group),
  });
  const { errors, isSubmitting, dirtyFields } = form.formState;

  const onSubmit = form.handleSubmit(async (values) => {
    // Só envia o que mudou (datas antigas já passadas não devem ser revalidadas).
    const payload = eventPayload(values);
    const changed = Object.fromEntries(
      Object.entries(payload).filter(([key]) => {
        const field =
          (
            { min_value_cents: "min_value", max_value_cents: "max_value" } as Record<
              string,
              keyof EventValues
            >
          )[key] ?? (key as keyof EventValues);
        return dirtyFields[field];
      }),
    );
    try {
      await update.mutateAsync(changed);
      onDone();
    } catch (error) {
      applyApiError(error, form.setError);
    }
  });

  return (
    <Card>
      <form onSubmit={onSubmit} noValidate className="space-y-4">
        <h2 className="text-lg font-extrabold">Editar informações</h2>
        <EventFields register={form.register} errors={errors} />
        {errors.root && <Alert>{errors.root.message}</Alert>}
        <div className="flex gap-2">
          <Button type="submit" loading={isSubmitting}>
            Salvar
          </Button>
          <Button type="button" variant="secondary" onClick={onDone}>
            Cancelar
          </Button>
        </div>
      </form>
    </Card>
  );
}
