import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";
import type { z } from "zod";

import { Alert, Button, Field, Input } from "@/components/ui";
import { useMe, useRegister } from "@/features/auth/api";
import { AuthCard } from "@/features/auth/AuthCard";
import { GoogleButton } from "@/features/auth/GoogleButton";
import { safeNext } from "@/features/auth/paths";
import { registerSchema } from "@/features/auth/schemas";
import { applyApiError, rememberNext } from "@/lib/forms";

type Values = z.infer<typeof registerSchema>;

export function RegisterPage() {
  const [params] = useSearchParams();
  const next = safeNext(params.get("next"));
  const me = useMe();
  const register = useRegister();
  const navigate = useNavigate();
  const form = useForm<Values>({ resolver: zodResolver(registerSchema) });
  const { errors, isSubmitting } = form.formState;

  if (me.data) return <Navigate to={next} replace />;

  const onSubmit = form.handleSubmit(async (values) => {
    try {
      await register.mutateAsync(values);
      rememberNext(next);
      navigate("/verify-email", { replace: true });
    } catch (error) {
      applyApiError(error, form.setError, { email_taken: "email", weak_password: "password" });
    }
  });

  return (
    <AuthCard emoji="🎉" title="Crie sua conta" subtitle="Leva menos de um minuto.">
      <div className="space-y-4">
        <GoogleButton next={next} />
        <form onSubmit={onSubmit} noValidate className="space-y-4">
          <Field label="Seu nome" error={errors.name?.message}>
            {(id) => (
              <Input
                id={id}
                autoComplete="name"
                aria-invalid={!!errors.name}
                {...form.register("name")}
              />
            )}
          </Field>
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
          <Field label="Senha" error={errors.password?.message} hint="Mínimo de 8 caracteres.">
            {(id) => (
              <Input
                id={id}
                type="password"
                autoComplete="new-password"
                aria-invalid={!!errors.password}
                {...form.register("password")}
              />
            )}
          </Field>
          {errors.root && <Alert>{errors.root.message}</Alert>}
          <Button type="submit" block loading={isSubmitting}>
            Criar conta
          </Button>
          <p className="text-center text-xs text-gray-500">
            Ao continuar você concorda com os{" "}
            <Link to="/termos" className="underline">
              termos
            </Link>{" "}
            e a{" "}
            <Link to="/privacidade" className="underline">
              política de privacidade
            </Link>
            .
          </p>
        </form>
        <p className="text-center text-sm text-gray-600">
          Já tem conta?{" "}
          <Link
            to={`/login?${new URLSearchParams({ next })}`}
            className="font-bold text-(--accent-text) hover:underline"
          >
            Entrar
          </Link>
        </p>
      </div>
    </AuthCard>
  );
}
