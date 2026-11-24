import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";
import type { z } from "zod";

import { Alert, Button, Field, Input } from "@/components/ui";
import { useLogin, useMe } from "@/features/auth/api";
import { AuthCard } from "@/features/auth/AuthCard";
import { GoogleButton } from "@/features/auth/GoogleButton";
import { safeNext } from "@/features/auth/paths";
import { loginSchema } from "@/features/auth/schemas";
import { applyApiError } from "@/lib/forms";

const GOOGLE_ERRORS: Record<string, string> = {
  google_disabled: "O login com Google não está disponível no momento.",
  google_email_unverified: "Seu e-mail no Google não está verificado.",
  google_account_conflict: "Este e-mail já está vinculado a outra conta Google.",
  account_disabled: "Esta conta está desativada.",
};

type Values = z.infer<typeof loginSchema>;

export function LoginPage() {
  const [params] = useSearchParams();
  const next = safeNext(params.get("next"));
  const googleError = params.get("error");
  const me = useMe();
  const login = useLogin();
  const navigate = useNavigate();
  const form = useForm<Values>({ resolver: zodResolver(loginSchema) });
  const { errors, isSubmitting } = form.formState;

  if (me.data) return <Navigate to={next} replace />;

  const onSubmit = form.handleSubmit(async (values) => {
    try {
      await login.mutateAsync(values);
      navigate(next, { replace: true });
    } catch (error) {
      applyApiError(error, form.setError);
    }
  });

  return (
    <AuthCard emoji="👋" title="Que bom te ver!" subtitle="Entre para ver seus amigos secretos.">
      <div className="space-y-4">
        {googleError && (
          <Alert>
            {GOOGLE_ERRORS[googleError] ?? "Não foi possível entrar com o Google. Tente novamente."}
          </Alert>
        )}
        <GoogleButton next={next} />
        <form onSubmit={onSubmit} noValidate className="space-y-4">
          <Field label="E-mail" error={errors.email?.message}>
            {(id) => (
              <Input
                id={id}
                type="email"
                autoComplete="email"
                inputMode="email"
                aria-invalid={!!errors.email}
                {...form.register("email")}
              />
            )}
          </Field>
          <Field label="Senha" error={errors.password?.message}>
            {(id) => (
              <Input
                id={id}
                type="password"
                autoComplete="current-password"
                aria-invalid={!!errors.password}
                {...form.register("password")}
              />
            )}
          </Field>
          {errors.root && <Alert>{errors.root.message}</Alert>}
          <Button type="submit" block loading={isSubmitting}>
            Entrar
          </Button>
        </form>
        <div className="flex flex-col items-center gap-2 text-sm">
          <Link to="/forgot-password" className="font-bold text-(--accent-text) hover:underline">
            Esqueci minha senha
          </Link>
          <p className="text-gray-600">
            Ainda não tem conta?{" "}
            <Link
              to={`/register?${new URLSearchParams({ next })}`}
              className="font-bold text-(--accent-text) hover:underline"
            >
              Cadastre-se
            </Link>
          </p>
        </div>
      </div>
    </AuthCard>
  );
}
