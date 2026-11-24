import { Link, useParams, useSearchParams } from "react-router-dom";

import { ApiError, errorMessage } from "@/api/client";
import type { Group } from "@/api/types";
import { EmptyState, ErrorState, PageLoader } from "@/components/ui";
import { useGroup } from "@/features/groups/api";
import { StatusBadge } from "@/features/groups/StatusBadge";
import { DrawTab } from "@/features/groups/tabs/DrawTab";
import { OverviewTab } from "@/features/groups/tabs/OverviewTab";
import { ParticipantsTab } from "@/features/groups/tabs/ParticipantsTab";
import { RulesTab } from "@/features/groups/tabs/RulesTab";
import { WishlistTab } from "@/features/groups/tabs/WishlistTab";
import { cx } from "@/lib/cx";
import { themeStyle, themeVars } from "@/lib/themes";

type TabId = "overview" | "participants" | "wishlist" | "rules" | "draw";

const TABS: Array<{ id: TabId; label: string; organizerOnly?: boolean }> = [
  { id: "overview", label: "Visão geral" },
  { id: "participants", label: "Participantes" },
  { id: "wishlist", label: "Minha lista" },
  { id: "rules", label: "Regras", organizerOnly: true },
  { id: "draw", label: "Sorteio" },
];

export function GroupPage() {
  const { groupId = "" } = useParams();
  const group = useGroup(groupId);

  if (group.isPending) return <PageLoader />;
  if (group.isError) {
    if (group.error instanceof ApiError && group.error.status === 404) {
      return (
        <EmptyState emoji="🔍" title="Grupo não encontrado">
          Talvez você não participe dele ou o link esteja errado.{" "}
          <Link to="/groups" className="font-bold text-(--accent-text) underline">
            Ver meus grupos
          </Link>
        </EmptyState>
      );
    }
    return <ErrorState message={errorMessage(group.error)} onRetry={() => group.refetch()} />;
  }
  return <GroupView group={group.data} />;
}

function GroupView({ group }: { group: Group }) {
  const [params, setParams] = useSearchParams();
  const organizer = group.my_role === "owner";
  const tabs = TABS.filter((tab) => !tab.organizerOnly || organizer);
  const defaultTab: TabId = group.status === "DRAWN" ? "draw" : "overview";
  const requested = params.get("tab") as TabId | null;
  const active = tabs.some((t) => t.id === requested) ? (requested as TabId) : defaultTab;

  return (
    <div className="space-y-5" style={themeVars(group.theme.slug)}>
      <header className="space-y-2">
        <Link to="/groups" className="text-sm font-bold text-gray-600 hover:underline">
          ← Meus grupos
        </Link>
        <div className="flex items-start gap-3">
          <span
            aria-hidden
            className="flex size-16 shrink-0 items-center justify-center rounded-3xl bg-(--accent-soft) text-4xl"
          >
            {group.theme.emoji}
          </span>
          <div className="min-w-0 space-y-1">
            <h1 className="text-2xl leading-tight font-black break-words">{group.title}</h1>
            <p className="text-gray-600">{group.display_name}</p>
            <StatusBadge status={group.status} />
          </div>
        </div>
        <p className="text-sm font-semibold text-(--accent-text)">
          {themeStyle(group.theme.slug).tagline}
        </p>
      </header>

      <nav aria-label="Seções do grupo" className="-mx-4 overflow-x-auto px-4">
        <div role="tablist" className="flex min-w-max gap-1 rounded-full bg-black/5 p-1">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              role="tab"
              id={`tab-${tab.id}`}
              aria-selected={active === tab.id}
              aria-controls="tab-panel"
              onClick={() => setParams({ tab: tab.id }, { replace: true })}
              className={cx(
                "rounded-full px-4 py-2 text-sm font-bold whitespace-nowrap transition",
                active === tab.id ? "bg-white shadow-sm" : "hover:text-ink text-gray-600",
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </nav>

      <section id="tab-panel" role="tabpanel" aria-labelledby={`tab-${active}`}>
        {active === "overview" && <OverviewTab group={group} />}
        {active === "participants" && <ParticipantsTab group={group} />}
        {active === "wishlist" && <WishlistTab group={group} />}
        {active === "rules" && organizer && <RulesTab group={group} />}
        {active === "draw" && <DrawTab group={group} />}
      </section>
    </div>
  );
}
