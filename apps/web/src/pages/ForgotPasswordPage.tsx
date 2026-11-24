import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";
import { z } from "zod";

import { Alert, Button, Field, Input } from "@/components/ui";
import { useForgotPassword } from "@/features/auth/api";
import { AuthCard } from "@/features/auth/AuthCard";
import { emailSchema } from "@/features/auth/schemas";
import { applyApiError } from "@/lib/forms";

const schema = z.object({ email: emailSchema });
type Values = z.infer<typeof schema>;

export function ForgotPasswordPage() {
  const forgot = useForgotPassword();
  const form = useForm<Values>({ resolver: zodResolver(schema) });
  const { errors, isSubmitting } = form.formState;

  const onSubmit = form.handleSubmit(async ({ email }) => {
    try {
      await forgot.mutateAsync(email);
    } catch (error) {
      applyApiError(error, form.setError);
    }
  });

  return (
    <AuthCard
      emoji="🔑"
      title="Esqueceu a senha?"
      subtitle="A gente te manda um link para criar outra."
    >
      {forgot.isSuccess ? (
        <div className="space-y-4 text-center">
          <Alert tone="success">{forgot.data.message}</Alert>
          <Link to="/login" className="font-bold text-(--accent-text) hover:underline">
            Voltar para o login
          </Link>
        </div>
      ) : (
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
          {errors.root && <Alert>{errors.root.message}</Alert>}
          <Button type="submit" block loading={isSubmitting}>
            Enviar link
          </Button>
          <Link
            to="/login"
            className="block text-center text-sm font-bold text-gray-600 hover:underline"
          >
            Lembrei a senha
          </Link>
        </form>
      )}
    </AuthCard>
  );
}
