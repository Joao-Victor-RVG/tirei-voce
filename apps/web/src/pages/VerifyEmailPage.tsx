import { useEffect, useRef } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { errorMessage } from "@/api/client";
import { Alert, Button, Spinner } from "@/components/ui";
import { useMe, useResendVerification, useVerifyEmail } from "@/features/auth/api";
import { AuthCard } from "@/features/auth/AuthCard";
import { safeNext } from "@/features/auth/paths";
import { popRememberedNext } from "@/lib/forms";

export function VerifyEmailPage() {
  const [params] = useSearchParams();
  const token = params.get("token");
  return token ? <ConfirmToken token={token} /> : <CheckInbox />;
}

function ConfirmToken({ token }: { token: string }) {
  const verify = useVerifyEmail();
  const started = useRef<string | null>(null);
  const { mutate } = verify;

  useEffect(() => {
    // O token é de uso único: garante uma só chamada (inclusive no StrictMode).
    if (started.current === token) return;
    started.current = token;
    mutate(token);
  }, [token, mutate]);

  if (verify.isSuccess) {
    const next = safeNext(popRememberedNext());
    return (
      <AuthCard
        emoji="✅"
        title="E-mail confirmado!"
        subtitle="Agora é só aproveitar a brincadeira."
      >
        <Link
          to={next}
          className="flex min-h-11 w-full items-center justify-center rounded-full bg-(--accent) px-5 font-bold text-white"
        >
          Continuar
        </Link>
      </AuthCard>
    );
  }
  if (verify.isError) {
    return (
      <AuthCard emoji="⏰" title="Link inválido ou expirado">
        <div className="space-y-4">
          <Alert>{errorMessage(verify.error)}</Alert>
          <Link
            to="/verify-email"
            className="block text-center font-bold text-(--accent-text) hover:underline"
          >
            Pedir um novo link
          </Link>
        </div>
      </AuthCard>
    );
  }
  return (
    <AuthCard emoji="📬" title="Confirmando seu e-mail…">
      <div className="flex justify-center text-(--accent)">
        <Spinner className="size-8" />
      </div>
    </AuthCard>
  );
}

function CheckInbox() {
  const me = useMe();
  const resend = useResendVerification();

  if (me.data?.email_verified) {
    return (
      <AuthCard emoji="✅" title="Seu e-mail já está confirmado">
        <Link
          to="/groups"
          className="block text-center font-bold text-(--accent-text) hover:underline"
        >
          Ir para meus grupos
        </Link>
      </AuthCard>
    );
  }

  return (
    <AuthCard
      emoji="📬"
      title="Confirme seu e-mail"
      subtitle={
        me.data ? (
          <>
            Enviamos um link para <strong>{me.data.email}</strong>. Abra seu e-mail e toque em
            “Confirmar e-mail”.
          </>
        ) : (
          "Abra o link que enviamos para o seu e-mail."
        )
      }
    >
      <div className="space-y-4 text-center">
        <p className="text-sm text-gray-600">Não chegou? Confira a caixa de spam ou peça outro.</p>
        {resend.isSuccess && <Alert tone="success">{resend.data.message}</Alert>}
        {resend.isError && <Alert>{errorMessage(resend.error)}</Alert>}
        {me.data ? (
          <Button
            variant="secondary"
            block
            loading={resend.isPending}
            onClick={() => resend.mutate()}
          >
            Reenviar e-mail
          </Button>
        ) : (
          <Link to="/login" className="font-bold text-(--accent-text) hover:underline">
            Entrar para reenviar
          </Link>
        )}
        {me.data && (
          <Link to="/groups" className="block text-sm font-bold text-gray-600 hover:underline">
            Fazer isso depois
          </Link>
        )}
      </div>
    </AuthCard>
  );
}
