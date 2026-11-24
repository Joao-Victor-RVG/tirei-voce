import { useDeferredValue, useState } from "react";
import { Navigate } from "react-router-dom";

import { errorMessage } from "@/api/client";
import { Alert, Button, Card, ErrorState, Input, PageLoader } from "@/components/ui";
import { useMe } from "@/features/auth/api";
import {
  useAdminMetrics,
  useAdminUsers,
  useSetUserActive,
  type AdminMetrics,
} from "@/features/admin/api";
import { STATUS_LABEL } from "@/features/groups/status";
import { formatShortDate } from "@/lib/format";

const number = new Intl.NumberFormat("pt-BR", { notation: "compact", maximumFractionDigits: 1 });

export function AdminPage() {
  const me = useMe();
  if (me.data && !me.data.is_admin) return <Navigate to="/groups" replace />;
  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-3xl font-black">Painel admin</h1>
        <p className="text-sm text-gray-600">
          Só números agregados: pares, conversas e listas nunca aparecem aqui.
        </p>
      </header>
      <Metrics />
      <Users />
    </div>
  );
}

function StatTile({ label, value, detail }: { label: string; value: number; detail?: string }) {
  return (
    <div className="rounded-3xl bg-white p-4 shadow-sm ring-1 ring-black/5">
      <p className="text-sm font-bold text-gray-600">{label}</p>
      <p className="mt-1 text-3xl font-black">{number.format(value)}</p>
      {detail && <p className="text-sm text-gray-600">{detail}</p>}
    </div>
  );
}

function Metrics() {
  const metrics = useAdminMetrics();
  if (metrics.isPending) return <PageLoader />;
  if (metrics.isError)
    return <ErrorState message={errorMessage(metrics.error)} onRetry={() => metrics.refetch()} />;
  const m = metrics.data;
  return (
    <section aria-labelledby="metricas" className="space-y-4">
      <h2 id="metricas" className="sr-only">
        Métricas
      </h2>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatTile label="Usuários" value={m.users.total} detail={`+${m.users.last_7d} em 7 dias`} />
        <StatTile label="Grupos" value={m.groups.total} detail={`+${m.groups.last_7d} em 7 dias`} />
        <StatTile label="Sorteios" value={m.draws.total} detail={`+${m.draws.last_7d} em 7 dias`} />
        <StatTile label="Mensagens no chat" value={m.chat_messages_7d} detail="últimos 7 dias" />
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <StatusBars metrics={m} />
        <Card className="space-y-4">
          <GiftMeter purchased={m.gifts_purchased} total={m.gifts_total} />
          <dl className="grid grid-cols-2 gap-3 text-sm">
            <Fact label="E-mails confirmados" value={`${m.users_verified} de ${m.users.total}`} />
            <Fact
              label="Média por grupo"
              value={`${m.avg_group_size.toLocaleString("pt-BR")} pessoas`}
            />
            <Fact label="Participações ativas" value={String(m.participants)} />
            <Fact label="Aparelhos com push" value={String(m.push_subscriptions)} />
            <Fact label="Sorteios agendados" value={String(m.scheduled_draws_pending)} />
          </dl>
        </Card>
      </div>
    </section>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-gray-600">{label}</dt>
      <dd className="font-bold">{value}</dd>
    </div>
  );
}

/** Uma cor só (magnitude), valor escrito ao lado: a cor nunca é a única pista. */
function StatusBars({ metrics }: { metrics: AdminMetrics }) {
  const entries = Object.entries(metrics.groups_by_status) as Array<
    [keyof typeof STATUS_LABEL, number]
  >;
  const max = Math.max(1, ...entries.map(([, n]) => n));
  return (
    <Card>
      <h3 className="mb-3 font-extrabold">Grupos por status</h3>
      <ul className="space-y-2">
        {entries.map(([status, n]) => (
          <li
            key={status}
            className="grid grid-cols-[8.5rem_1fr_2.5rem] items-center gap-2 text-sm"
            title={`${STATUS_LABEL[status]}: ${n}`}
          >
            <span className="truncate text-gray-700">{STATUS_LABEL[status]}</span>
            <span className="h-3 rounded-full bg-black/5">
              <span
                className="block h-3 rounded-full bg-(--accent)"
                style={{ width: `${(n / max) * 100}%`, minWidth: n ? "4px" : 0 }}
              />
            </span>
            <span className="text-right font-bold tabular-nums">{n}</span>
          </li>
        ))}
      </ul>
    </Card>
  );
}

function GiftMeter({ purchased, total }: { purchased: number; total: number }) {
  const percent = total ? Math.round((purchased / total) * 100) : 0;
  return (
    <div>
      <div className="flex items-baseline justify-between">
        <h3 className="font-extrabold">Presentes comprados</h3>
        <span className="text-sm font-bold">
          {percent}% ({purchased} de {total})
        </span>
      </div>
      <div
        role="meter"
        aria-label="Presentes comprados"
        aria-valuemin={0}
        aria-valuemax={total}
        aria-valuenow={purchased}
        className="mt-2 h-3 rounded-full bg-(--accent-soft)"
      >
        <div className="h-3 rounded-full bg-(--accent)" style={{ width: `${percent}%` }} />
      </div>
    </div>
  );
}

function Users() {
  const [search, setSearch] = useState("");
  const q = useDeferredValue(search.trim());
  const users = useAdminUsers(q);
  const setActive = useSetUserActive();
  const items = users.data?.pages.flatMap((p) => p.items) ?? [];

  return (
    <section aria-labelledby="usuarios" className="space-y-3">
      <h2 id="usuarios" className="text-xl font-extrabold">
        Usuários
      </h2>
      <Input
        type="search"
        placeholder="Buscar por nome ou e-mail"
        aria-label="Buscar usuários"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
      />
      {setActive.isError && <Alert>{errorMessage(setActive.error)}</Alert>}
      {users.isPending ? (
        <PageLoader />
      ) : users.isError ? (
        <ErrorState message={errorMessage(users.error)} onRetry={() => users.refetch()} />
      ) : items.length === 0 ? (
        <p className="text-gray-600">Nenhum usuário encontrado.</p>
      ) : (
        <div className="overflow-x-auto rounded-3xl bg-white shadow-sm ring-1 ring-black/5">
          <table className="w-full text-left text-sm">
            <thead className="text-gray-600">
              <tr>
                <th className="p-3">Nome</th>
                <th className="p-3">E-mail</th>
                <th className="p-3 text-right">Grupos</th>
                <th className="p-3">Desde</th>
                <th className="p-3">Situação</th>
                <th className="p-3">
                  <span className="sr-only">Ações</span>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-black/5">
              {items.map((u) => (
                <tr key={u.id}>
                  <td className="p-3 font-bold">
                    {u.name}{" "}
                    {u.is_admin && <span className="text-xs text-(--accent-text)">(admin)</span>}
                  </td>
                  <td className="p-3">
                    {u.email}{" "}
                    {!u.email_verified && (
                      <span className="text-xs text-gray-500">(não confirmado)</span>
                    )}
                  </td>
                  <td className="p-3 text-right tabular-nums">{u.groups}</td>
                  <td className="p-3 tabular-nums">{formatShortDate(u.created_at)}</td>
                  <td className="p-3">{u.is_active ? "Ativo" : "Desativado"}</td>
                  <td className="p-3 text-right">
                    {!u.is_admin && (
                      <Button
                        variant="ghost"
                        className="min-h-8 px-3 text-sm"
                        loading={setActive.isPending && setActive.variables?.id === u.id}
                        onClick={() => setActive.mutate({ id: u.id, active: !u.is_active })}
                      >
                        {u.is_active ? "Desativar" : "Reativar"}
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {users.hasNextPage && (
        <Button
          variant="secondary"
          loading={users.isFetchingNextPage}
          onClick={() => users.fetchNextPage()}
        >
          Carregar mais
        </Button>
      )}
    </section>
  );
}
