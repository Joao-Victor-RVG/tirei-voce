import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { Link, useSearchParams } from "react-router-dom";
import type { z } from "zod";

import { Alert, Button, Field, Input } from "@/components/ui";
import { meKey, useResetPassword } from "@/features/auth/api";
import { AuthCard } from "@/features/auth/AuthCard";
import { resetSchema } from "@/features/auth/schemas";
import { applyApiError } from "@/lib/forms";

type Values = z.infer<typeof resetSchema>;

export function ResetPasswordPage() {
  const [params] = useSearchParams();
  const token = params.get("token");
  const reset = useResetPassword();
  const queryClient = useQueryClient();
  const form = useForm<Values>({ resolver: zodResolver(resetSchema) });
  const { errors, isSubmitting } = form.formState;

  if (!token) {
    return (
      <AuthCard emoji="⏰" title="Link incompleto">
        <Link
          to="/forgot-password"
          className="block text-center font-bold text-(--accent-text) hover:underline"
        >
          Pedir um novo link
        </Link>
      </AuthCard>
    );
  }

  const onSubmit = form.handleSubmit(async ({ password }) => {
    try {
      await reset.mutateAsync({ token, password });
      queryClient.setQueryData(meKey, null); // todas as sessões foram encerradas
    } catch (error) {
      applyApiError(error, form.setError, { weak_password: "password" });
    }
  });

  if (reset.isSuccess) {
    return (
      <AuthCard emoji="✅" title="Senha alterada!" subtitle="Entre de novo com a senha nova.">
        <Link
          to="/login"
          className="flex min-h-11 w-full items-center justify-center rounded-full bg-(--accent) px-5 font-bold text-white"
        >
          Entrar
        </Link>
      </AuthCard>
    );
  }

  return (
    <AuthCard emoji="🔒" title="Crie uma nova senha">
      <form onSubmit={onSubmit} noValidate className="space-y-4">
        <Field label="Nova senha" error={errors.password?.message} hint="Mínimo de 8 caracteres.">
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
        <Field label="Repita a senha" error={errors.confirm?.message}>
          {(id) => (
            <Input
              id={id}
              type="password"
              autoComplete="new-password"
              aria-invalid={!!errors.confirm}
              {...form.register("confirm")}
            />
          )}
        </Field>
        {errors.root && <Alert>{errors.root.message}</Alert>}
        <Button type="submit" block loading={isSubmitting}>
          Salvar senha
        </Button>
      </form>
    </AuthCard>
  );
}
