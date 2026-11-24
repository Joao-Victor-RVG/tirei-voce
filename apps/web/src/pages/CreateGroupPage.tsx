import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { Navigate, useNavigate } from "react-router-dom";
import { z } from "zod";

import { errorMessage } from "@/api/client";
import { Alert, Button, Card, ErrorState, Field, Input, PageLoader } from "@/components/ui";
import { useMe } from "@/features/auth/api";
import { useCreateGroup, useThemes } from "@/features/groups/api";
import { EventFields } from "@/features/groups/EventFields";
import { emptyEvent, eventPayload, eventSchema } from "@/features/groups/eventForm";
import { cx } from "@/lib/cx";
import { formatDateTime, formatValueRange, localInputToIso, parseReais } from "@/lib/format";
import { applyApiError } from "@/lib/forms";
import { themeStyle, themeVars } from "@/lib/themes";

const basicsSchema = z.object({
  theme_slug: z.string().min(1, "Escolha um tema."),
  title: z.string().trim().min(2, "Dê um nome ao grupo.").max(120, "Nome muito longo."),
  custom_name: z
    .string()
    .trim()
    .max(60, "Máximo de 60 caracteres.")
    .refine((v) => v === "" || v.length >= 2, "Use pelo menos 2 letras."),
});

const schema = z.intersection(basicsSchema, eventSchema);
type Values = z.infer<typeof schema>;

const STEPS = ["Tema e nome", "Valores, data e local", "Revisão"] as const;
const STEP_FIELDS: Array<Array<keyof Values>> = [
  ["theme_slug", "title", "custom_name"],
  [
    "min_value",
    "max_value",
    "event_at",
    "event_location",
    "event_maps_url",
    "join_deadline_at",
    "wishlist_deadline_at",
    "description",
  ],
  [],
];

export function CreateGroupPage() {
  const me = useMe();
  const themes = useThemes();
  const create = useCreateGroup();
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [openNow, setOpenNow] = useState(true);
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { theme_slug: "amigo-secreto", title: "", custom_name: "", ...emptyEvent },
    mode: "onTouched",
  });
  const { errors, isSubmitting } = form.formState;
  const values = useWatch({ control: form.control }) as Values;

  if (me.data && !me.data.email_verified) return <Navigate to="/verify-email" replace />;
  if (themes.isPending) return <PageLoader />;
  if (themes.isError)
    return <ErrorState message={errorMessage(themes.error)} onRetry={() => themes.refetch()} />;

  const next = async () => {
    if (await form.trigger(STEP_FIELDS[step])) setStep((s) => s + 1);
  };

  const onSubmit = form.handleSubmit(async (v) => {
    try {
      const group = await create.mutateAsync({
        data: {
          theme_slug: v.theme_slug,
          title: v.title,
          custom_name: v.custom_name || null,
          ...eventPayload(v),
        },
        open: openNow,
      });
      navigate(`/groups/${group.id}`, { replace: true });
    } catch (error) {
      applyApiError(error, form.setError);
    }
  });

  const selected = themes.data.find((t) => t.slug === values.theme_slug);
  const range = formatValueRange(parseReais(values.min_value), parseReais(values.max_value));
  const eventIso = localInputToIso(values.event_at);

  return (
    <div className="space-y-5" style={themeVars(values.theme_slug)}>
      <div>
        <p className="text-sm font-bold text-(--accent-text)">
          Passo {step + 1} de {STEPS.length}
        </p>
        <h1 className="text-3xl font-black">{STEPS[step]}</h1>
        <div className="mt-3 flex gap-2" aria-hidden>
          {STEPS.map((label, i) => (
            <span
              key={label}
              className={cx(
                "h-1.5 flex-1 rounded-full",
                i <= step ? "bg-(--accent)" : "bg-black/10",
              )}
            />
          ))}
        </div>
      </div>

      <form onSubmit={(e) => (step === 2 ? onSubmit(e) : (e.preventDefault(), next()))} noValidate>
        <Card className="space-y-5">
          {step === 0 && (
            <>
              <fieldset className="space-y-2">
                <legend className="mb-2 text-sm font-bold">Qual é a brincadeira?</legend>
                <div className="grid gap-2">
                  {themes.data.map((theme) => (
                    <label
                      key={theme.slug}
                      style={themeVars(theme.slug)}
                      className={cx(
                        "flex cursor-pointer items-center gap-3 rounded-2xl p-3 ring-1 transition",
                        values.theme_slug === theme.slug
                          ? "bg-(--accent-soft) ring-2 ring-(--accent)"
                          : "ring-black/10 hover:bg-black/[0.02]",
                      )}
                    >
                      <input
                        type="radio"
                        value={theme.slug}
                        className="sr-only"
                        {...form.register("theme_slug")}
                      />
                      <span className="text-3xl" aria-hidden>
                        {theme.emoji}
                      </span>
                      <span>
                        <span className="block font-extrabold">{theme.display_name}</span>
                        <span className="block text-sm text-gray-600">{theme.description}</span>
                      </span>
                    </label>
                  ))}
                </div>
              </fieldset>
              <Field label="Nome do grupo" error={errors.title?.message}>
                {(id) => (
                  <Input
                    id={id}
                    placeholder="Ex.: Natal da Família Silva"
                    aria-invalid={!!errors.title}
                    {...form.register("title")}
                  />
                )}
              </Field>
              <Field
                label="Nome personalizado da brincadeira (opcional)"
                error={errors.custom_name?.message}
                hint={`Em vez de “${selected?.display_name ?? ""}”. Ex.: Amigo Chocolate.`}
              >
                {(id) => <Input id={id} {...form.register("custom_name")} />}
              </Field>
            </>
          )}

          {step === 1 && <EventFields register={form.register} errors={errors} />}

          {step === 2 && (
            <div className="space-y-4">
              <div className="flex items-center gap-3">
                <span className="text-5xl" aria-hidden>
                  {selected?.emoji}
                </span>
                <div>
                  <p className="text-xl font-black">{values.title}</p>
                  <p className="text-gray-600">{values.custom_name || selected?.display_name}</p>
                </div>
              </div>
              <dl className="grid gap-3 text-sm">
                <ReviewItem label="Valor do presente" value={range ?? "Sem valor definido"} />
                <ReviewItem
                  label="Quando"
                  value={eventIso ? formatDateTime(eventIso) : "A definir"}
                />
                <ReviewItem label="Onde" value={values.event_location || "A definir"} />
                {values.join_deadline_at && (
                  <ReviewItem
                    label="Entradas até"
                    value={formatDateTime(localInputToIso(values.join_deadline_at))}
                  />
                )}
              </dl>
              <p className="text-sm text-gray-600">{themeStyle(values.theme_slug).tagline}</p>
              <label className="flex items-start gap-3 rounded-2xl bg-black/[0.03] p-3">
                <input
                  type="checkbox"
                  className="mt-1 size-5 accent-(--accent)"
                  checked={openNow}
                  onChange={(e) => setOpenNow(e.target.checked)}
                />
                <span>
                  <span className="block font-bold">Abrir inscrições agora</span>
                  <span className="block text-sm text-gray-600">
                    O link de convite já funciona assim que o grupo for criado.
                  </span>
                </span>
              </label>
              {errors.root && <Alert>{errors.root.message}</Alert>}
            </div>
          )}

          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-between">
            {step > 0 ? (
              <Button type="button" variant="secondary" onClick={() => setStep((s) => s - 1)}>
                Voltar
              </Button>
            ) : (
              <span />
            )}
            <Button type="submit" loading={isSubmitting}>
              {step === 2 ? "Criar grupo 🎉" : "Continuar"}
            </Button>
          </div>
        </Card>
      </form>
    </div>
  );
}

function ReviewItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl bg-black/[0.03] p-3">
      <dt className="font-bold text-gray-600">{label}</dt>
      <dd className="font-semibold">{value}</dd>
    </div>
  );
}
