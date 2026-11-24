import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Alert, Avatar, Button, Card, Field, Input, PageLoader } from "@/components/ui";
import { useMe, useUpdateMe } from "@/features/auth/api";
import { PushCard } from "@/features/auth/PushCard";
import { VerifyEmailBanner } from "@/features/auth/VerifyEmailBanner";
import { applyApiError } from "@/lib/forms";

const schema = z.object({
  name: z.string().trim().min(1, "Informe seu nome.").max(100),
  shirt_size: z.string().trim().max(10, "Máximo de 10 caracteres."),
  shoe_size: z.string().trim().max(10, "Máximo de 10 caracteres."),
});
type Values = z.infer<typeof schema>;

export function ProfilePage() {
  const me = useMe();
  if (!me.data) return <PageLoader />;
  return <ProfileForm key={me.data.id} me={me.data} />;
}

function ProfileForm({ me }: { me: NonNullable<ReturnType<typeof useMe>["data"]> }) {
  const update = useUpdateMe();
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: me.name,
      shirt_size: me.shirt_size ?? "",
      shoe_size: me.shoe_size ?? "",
    },
  });
  const { errors, isSubmitting } = form.formState;

  const onSubmit = form.handleSubmit(async (values) => {
    try {
      await update.mutateAsync({
        name: values.name,
        shirt_size: values.shirt_size || null,
        shoe_size: values.shoe_size || null,
      });
    } catch (error) {
      applyApiError(error, form.setError);
    }
  });

  return (
    <div className="space-y-4">
      <VerifyEmailBanner />
      <div className="flex items-center gap-4">
        <Avatar name={me.name} url={me.avatar_url} size="size-16" />
        <div>
          <h1 className="text-2xl font-black">Meu perfil</h1>
          <p className="text-gray-600">{me.email}</p>
        </div>
      </div>
      <Card>
        <form onSubmit={onSubmit} noValidate className="space-y-4">
          <Field label="Nome" error={errors.name?.message}>
            {(id) => <Input id={id} aria-invalid={!!errors.name} {...form.register("name")} />}
          </Field>
          <p className="text-sm text-gray-600">
            Os tamanhos aparecem só para quem tirar você no sorteio.
          </p>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Camiseta" error={errors.shirt_size?.message}>
              {(id) => <Input id={id} placeholder="Ex.: M" {...form.register("shirt_size")} />}
            </Field>
            <Field label="Calçado" error={errors.shoe_size?.message}>
              {(id) => (
                <Input
                  id={id}
                  placeholder="Ex.: 38"
                  inputMode="numeric"
                  {...form.register("shoe_size")}
                />
              )}
            </Field>
          </div>
          {errors.root && <Alert>{errors.root.message}</Alert>}
          {update.isSuccess && !form.formState.isDirty && (
            <Alert tone="success">Perfil salvo!</Alert>
          )}
          <Button type="submit" loading={isSubmitting}>
            Salvar
          </Button>
        </form>
      </Card>
      <PushCard />
    </div>
  );
}
