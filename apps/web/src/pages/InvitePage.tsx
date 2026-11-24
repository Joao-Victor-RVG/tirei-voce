import { Link, Navigate, useNavigate, useParams } from "react-router-dom";

import { ApiError, errorMessage } from "@/api/client";
import { Alert, Button, Card, EmptyState, ErrorState, PageLoader } from "@/components/ui";
import { useMe } from "@/features/auth/api";
import { loginPath } from "@/features/auth/paths";
import { VerifyEmailBanner } from "@/features/auth/VerifyEmailBanner";
import { useInvitePreview, useJoinGroup } from "@/features/groups/api";
import { formatDateTime, formatValueRange } from "@/lib/format";
import { rememberNext } from "@/lib/forms";
import { themeStyle, themeVars } from "@/lib/themes";

export function InvitePage() {
  const { code = "" } = useParams();
  const me = useMe();
  const preview = useInvitePreview(code);
  const join = useJoinGroup(code);
  const navigate = useNavigate();
  const here = `/i/${code}`;

  if (preview.isPending || me.isPending) return <PageLoader />;
  if (preview.isError) {
    if (preview.error instanceof ApiError && preview.error.status === 404) {
      return (
        <EmptyState emoji="💌" title="Convite inválido">
          Este link não existe ou foi trocado pelo organizador. Peça um link novo.
        </EmptyState>
      );
    }
    return <ErrorState message={errorMessage(preview.error)} onRetry={() => preview.refetch()} />;
  }
  if (join.isSuccess) return <Navigate to={`/groups/${join.data.group_id}`} replace />;

  const invite = preview.data;
  const range = formatValueRange(invite.min_value_cents, invite.max_value_cents);
  const user = me.data;

  const onJoin = async () => {
    try {
      const result = await join.mutateAsync();
      navigate(`/groups/${result.group_id}`, { replace: true });
    } catch {
      // mensagem exibida abaixo
    }
  };

  return (
    <div className="mx-auto max-w-md space-y-4" style={themeVars(invite.theme.slug)}>
      <VerifyEmailBanner />
      <Card className="space-y-4 text-center">
        <div className="animate-pop-in text-7xl" aria-hidden>
          {invite.theme.emoji}
        </div>
        <p className="font-bold text-(--accent-text)">{invite.organizer_name} te convidou para o</p>
        <h1 className="text-3xl font-black break-words">{invite.title}</h1>
        <p className="text-gray-600">
          {invite.display_name} · {themeStyle(invite.theme.slug).tagline}
        </p>
        <dl className="space-y-2 rounded-2xl bg-black/[0.03] p-4 text-left text-sm">
          {invite.event_at && (
            <div>
              <dt className="font-bold text-gray-600">📅 Quando</dt>
              <dd className="font-semibold">{formatDateTime(invite.event_at)}</dd>
            </div>
          )}
          {invite.event_location && (
            <div>
              <dt className="font-bold text-gray-600">📍 Onde</dt>
              <dd className="font-semibold">{invite.event_location}</dd>
            </div>
          )}
          {range && (
            <div>
              <dt className="font-bold text-gray-600">💸 Valor do presente</dt>
              <dd className="font-semibold">{range}</dd>
            </div>
          )}
          <div>
            <dt className="font-bold text-gray-600">👥 Já confirmados</dt>
            <dd className="font-semibold">{invite.participant_count}</dd>
          </div>
        </dl>

        {!invite.can_join ? (
          <Alert tone="warning">{invite.reason}</Alert>
        ) : !user ? (
          <div className="space-y-2">
            <Link
              to={`/register?${new URLSearchParams({ next: here })}`}
              onClick={() => rememberNext(here)}
              className="flex min-h-12 w-full items-center justify-center rounded-full bg-(--accent) px-5 text-lg font-extrabold text-white"
            >
              Quero participar!
            </Link>
            <Link
              to={loginPath(here)}
              className="block text-sm font-bold text-(--accent-text) hover:underline"
            >
              Já tenho conta
            </Link>
          </div>
        ) : !user.email_verified ? (
          <Button
            block
            onClick={() => {
              rememberNext(here);
              navigate("/verify-email");
            }}
          >
            Confirmar meu e-mail para participar
          </Button>
        ) : (
          <Button block onClick={onJoin} loading={join.isPending} className="min-h-12 text-lg">
            Participar 🎉
          </Button>
        )}
        {join.isError && <Alert>{errorMessage(join.error)}</Alert>}
      </Card>
    </div>
  );
}
