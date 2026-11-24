import { Link } from "react-router-dom";

import { errorMessage } from "@/api/client";
import { Button, EmptyState, ErrorState, PageLoader } from "@/components/ui";
import { useMe } from "@/features/auth/api";
import { VerifyEmailBanner } from "@/features/auth/VerifyEmailBanner";
import { useMyGroups } from "@/features/groups/api";
import { StatusBadge } from "@/features/groups/StatusBadge";
import { formatShortDateTime } from "@/lib/format";
import { themeVars } from "@/lib/themes";

export function GroupsPage() {
  const me = useMe();
  const groups = useMyGroups();
  const verified = !!me.data?.email_verified;
  const items = groups.data?.pages.flatMap((page) => page.items) ?? [];

  const createButton = verified ? (
    <Link
      to="/groups/new"
      className="inline-flex min-h-11 items-center rounded-full bg-(--accent) px-5 font-bold text-white shadow-sm hover:brightness-110"
    >
      + Criar grupo
    </Link>
  ) : null;

  return (
    <div className="space-y-5">
      <VerifyEmailBanner />
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-3xl font-black">Meus grupos</h1>
        {items.length > 0 && createButton}
      </div>

      {groups.isPending ? (
        <PageLoader />
      ) : groups.isError ? (
        <ErrorState message={errorMessage(groups.error)} onRetry={() => groups.refetch()} />
      ) : items.length === 0 ? (
        <EmptyState emoji="🎄" title="Nenhum grupo por aqui ainda">
          <p className="mb-4">Crie um amigo secreto ou abra o link de convite que te mandaram.</p>
          {createButton}
        </EmptyState>
      ) : (
        <>
          <ul className="space-y-3">
            {items.map((group) => (
              <li key={group.id} style={themeVars(group.theme.slug)}>
                <Link
                  to={`/groups/${group.id}`}
                  className="flex items-center gap-4 rounded-3xl bg-white p-4 shadow-sm ring-1 ring-black/5 transition hover:ring-(--accent)"
                >
                  <span
                    aria-hidden
                    className="flex size-14 shrink-0 items-center justify-center rounded-2xl bg-(--accent-soft) text-3xl"
                  >
                    {group.theme.emoji}
                  </span>
                  <span className="min-w-0 flex-1 space-y-1">
                    <span className="block truncate text-lg font-extrabold">{group.title}</span>
                    <span className="block text-sm text-gray-600">
                      {group.display_name} · {group.participant_count}{" "}
                      {group.participant_count === 1 ? "pessoa" : "pessoas"}
                    </span>
                    <span className="flex flex-wrap items-center gap-2 text-sm text-gray-600">
                      <StatusBadge status={group.status} />
                      {group.event_at && <span>📅 {formatShortDateTime(group.event_at)}</span>}
                    </span>
                  </span>
                </Link>
              </li>
            ))}
          </ul>
          {groups.hasNextPage && (
            <div className="text-center">
              <Button
                variant="secondary"
                loading={groups.isFetchingNextPage}
                onClick={() => groups.fetchNextPage()}
              >
                Carregar mais
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
