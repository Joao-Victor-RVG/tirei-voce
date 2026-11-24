import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { errorMessage } from "@/api/client";
import type { Group, WishlistItem } from "@/api/types";
import {
  Alert,
  Button,
  Card,
  EmptyState,
  ErrorState,
  Field,
  Input,
  PageLoader,
  TextArea,
} from "@/components/ui";
import { centsToInput, parseReais } from "@/lib/format";
import { applyApiError } from "@/lib/forms";

import {
  useAddWishlistItem,
  useDeleteWishlistItem,
  usePreferences,
  useSavePreferences,
  useUpdateWishlistItem,
  useWishlist,
} from "../api";
import { PRIORITY_LABEL } from "../priority";
import { WishlistItemView } from "../WishlistItemView";

const itemSchema = z.object({
  title: z.string().trim().min(1, "O que você quer ganhar?").max(120, "Máximo de 120 caracteres."),
  url: z
    .string()
    .trim()
    .refine((v) => v === "" || /^https?:\/\/\S+$/.test(v), "Cole um link que comece com https://"),
  price: z
    .string()
    .trim()
    .refine((v) => v === "" || parseReais(v) !== null, "Valor inválido."),
  priority: z.enum(["1", "2", "3"]),
  notes: z.string().trim().max(1000, "Máximo de 1000 caracteres."),
});
type ItemValues = z.infer<typeof itemSchema>;

const EMPTY_ITEM: ItemValues = { title: "", url: "", price: "", priority: "2", notes: "" };

export function WishlistTab({ group }: { group: Group }) {
  const readonly = group.status === "FINISHED";
  const items = useWishlist(group.id);
  const [editing, setEditing] = useState<WishlistItem | "new" | null>(null);

  return (
    <div className="space-y-4">
      <Card className="space-y-3">
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-lg font-extrabold">Minha lista de desejos</h2>
          {!readonly && editing === null && (
            <Button className="min-h-9 px-4 text-sm" onClick={() => setEditing("new")}>
              + Item
            </Button>
          )}
        </div>
        <p className="text-sm text-gray-600">Só quem tirar você vai ver esta lista.</p>
        {editing !== null && (
          <ItemForm
            groupId={group.id}
            item={editing === "new" ? null : editing}
            onDone={() => setEditing(null)}
          />
        )}
        {items.isPending ? (
          <PageLoader />
        ) : items.isError ? (
          <ErrorState message={errorMessage(items.error)} onRetry={() => items.refetch()} />
        ) : items.data.length === 0 ? (
          editing === null && (
            <EmptyState emoji="📝" title="Sua lista está vazia">
              Dê umas dicas para o seu amigo secreto não errar!
            </EmptyState>
          )
        ) : (
          <ul className="space-y-2">
            {items.data.map((item) => (
              <WishlistRow
                key={item.id}
                groupId={group.id}
                item={item}
                readonly={readonly}
                onEdit={() => setEditing(item)}
              />
            ))}
          </ul>
        )}
      </Card>
      <PreferencesCard groupId={group.id} readonly={readonly} />
    </div>
  );
}

function WishlistRow({
  groupId,
  item,
  readonly,
  onEdit,
}: {
  groupId: string;
  item: WishlistItem;
  readonly: boolean;
  onEdit: () => void;
}) {
  const remove = useDeleteWishlistItem(groupId);
  return (
    <li className="flex items-start gap-3 rounded-2xl bg-black/[0.03] p-3">
      <WishlistItemView item={item} />
      {!readonly && (
        <div className="flex shrink-0 gap-1">
          <Button variant="ghost" className="min-h-9 px-3 text-sm" onClick={onEdit}>
            Editar
          </Button>
          <Button
            variant="ghost"
            className="min-h-9 px-3 text-sm"
            loading={remove.isPending}
            onClick={() => remove.mutate(item.id)}
            aria-label={`Excluir ${item.title}`}
          >
            Excluir
          </Button>
        </div>
      )}
    </li>
  );
}

function ItemForm({
  groupId,
  item,
  onDone,
}: {
  groupId: string;
  item: WishlistItem | null;
  onDone: () => void;
}) {
  const add = useAddWishlistItem(groupId);
  const update = useUpdateWishlistItem(groupId);
  const form = useForm<ItemValues>({
    resolver: zodResolver(itemSchema),
    defaultValues: item
      ? {
          title: item.title,
          url: item.url ?? "",
          price: centsToInput(item.price_hint_cents),
          priority: String(item.priority) as ItemValues["priority"],
          notes: item.notes ?? "",
        }
      : EMPTY_ITEM,
  });
  const { errors, isSubmitting } = form.formState;

  const onSubmit = form.handleSubmit(async (v) => {
    const data = {
      title: v.title,
      url: v.url || null,
      price_hint_cents: parseReais(v.price),
      priority: Number(v.priority),
      notes: v.notes || null,
    };
    try {
      if (item) await update.mutateAsync({ itemId: item.id, data });
      else await add.mutateAsync(data);
      onDone();
    } catch (error) {
      applyApiError(error, form.setError, { wishlist_full: "title" });
    }
  });

  return (
    <form
      onSubmit={onSubmit}
      noValidate
      className="space-y-3 rounded-2xl bg-(--accent-soft)/50 p-4"
    >
      <Field label="O que você quer?" error={errors.title?.message}>
        {(id) => (
          <Input
            id={id}
            placeholder="Ex.: Livro de receitas"
            aria-invalid={!!errors.title}
            {...form.register("title")}
          />
        )}
      </Field>
      <Field label="Link (opcional)" error={errors.url?.message}>
        {(id) => (
          <Input
            id={id}
            type="url"
            inputMode="url"
            placeholder="https://…"
            {...form.register("url")}
          />
        )}
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Preço aproximado" error={errors.price?.message}>
          {(id) => (
            <Input id={id} inputMode="decimal" placeholder="R$" {...form.register("price")} />
          )}
        </Field>
        <Field label="Prioridade">
          {(id) => (
            <select
              id={id}
              className="block w-full rounded-2xl bg-white px-4 py-3 ring-1 ring-black/10 focus:ring-2 focus:ring-(--accent) focus:outline-none"
              {...form.register("priority")}
            >
              <option value="1">{PRIORITY_LABEL[1]}</option>
              <option value="2">{PRIORITY_LABEL[2]}</option>
              <option value="3">{PRIORITY_LABEL[3]}</option>
            </select>
          )}
        </Field>
      </div>
      <Field label="Observações (opcional)" error={errors.notes?.message}>
        {(id) => (
          <TextArea id={id} placeholder="Cor, tamanho, sabor…" {...form.register("notes")} />
        )}
      </Field>
      {errors.root && <Alert>{errors.root.message}</Alert>}
      <div className="flex gap-2">
        <Button type="submit" loading={isSubmitting}>
          {item ? "Salvar" : "Adicionar"}
        </Button>
        <Button type="button" variant="secondary" onClick={onDone}>
          Cancelar
        </Button>
      </div>
    </form>
  );
}

const prefsSchema = z.object({
  dislikes: z.string().trim().max(1000, "Máximo de 1000 caracteres."),
  notes: z.string().trim().max(1000, "Máximo de 1000 caracteres."),
});
type PrefsValues = z.infer<typeof prefsSchema>;

function PreferencesCard({ groupId, readonly }: { groupId: string; readonly: boolean }) {
  const prefs = usePreferences(groupId);
  const save = useSavePreferences(groupId);
  const form = useForm<PrefsValues>({
    resolver: zodResolver(prefsSchema),
    defaultValues: { dislikes: "", notes: "" },
  });
  const { errors, isSubmitting, isDirty } = form.formState;
  const { reset } = form;

  useEffect(() => {
    if (prefs.data) reset({ dislikes: prefs.data.dislikes ?? "", notes: prefs.data.notes ?? "" });
  }, [prefs.data, reset]);

  const onSubmit = form.handleSubmit(async (v) => {
    try {
      await save.mutateAsync({ dislikes: v.dislikes || null, notes: v.notes || null });
    } catch (error) {
      applyApiError(error, form.setError);
    }
  });

  if (prefs.isPending) return null;
  if (prefs.isError)
    return <ErrorState message={errorMessage(prefs.error)} onRetry={() => prefs.refetch()} />;

  return (
    <Card>
      <form onSubmit={onSubmit} noValidate className="space-y-3">
        <h2 className="text-lg font-extrabold">O que eu não quero ganhar</h2>
        <Field label="Não quero ganhar…" error={errors.dislikes?.message}>
          {(id) => (
            <TextArea
              id={id}
              disabled={readonly}
              placeholder="Ex.: perfume, chocolate amargo, meias 😅"
              {...form.register("dislikes")}
            />
          )}
        </Field>
        <Field label="Outras dicas" error={errors.notes?.message}>
          {(id) => (
            <TextArea
              id={id}
              disabled={readonly}
              placeholder="Ex.: sou alérgica a lã, adoro gatos"
              {...form.register("notes")}
            />
          )}
        </Field>
        {errors.root && <Alert>{errors.root.message}</Alert>}
        {save.isSuccess && !isDirty && <Alert tone="success">Preferências salvas!</Alert>}
        {!readonly && (
          <Button type="submit" loading={isSubmitting} disabled={!isDirty}>
            Salvar preferências
          </Button>
        )}
      </form>
    </Card>
  );
}
