import { useState } from "react";

import { errorMessage } from "@/api/client";
import type { Me } from "@/api/types";
import { Alert, Button, Card, Field, Input } from "@/components/ui";

import { useAuthConfig, useUpdateMe } from "./api";

export function WhatsAppCard({ me }: { me: Me }) {
  const config = useAuthConfig();
  const update = useUpdateMe();
  const [phone, setPhone] = useState(me.phone ?? "");
  const [optIn, setOptIn] = useState(me.whatsapp_opt_in);

  if (!config.data?.whatsapp_enabled) return null;

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const saved = await update.mutateAsync({ phone, whatsapp_opt_in: optIn });
      setPhone(saved.phone ?? "");
      setOptIn(saved.whatsapp_opt_in);
    } catch {
      // erro exibido abaixo
    }
  };

  return (
    <Card>
      <form onSubmit={save} className="space-y-3">
        <h2 className="text-lg font-extrabold">Avisos pelo WhatsApp</h2>
        <Field label="Celular com DDD" hint="Só usamos para os avisos que você autorizar.">
          {(id) => (
            <Input
              id={id}
              type="tel"
              inputMode="tel"
              autoComplete="tel-national"
              placeholder="(11) 98765-4321"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
            />
          )}
        </Field>
        <label className="flex items-start gap-3">
          <input
            type="checkbox"
            className="mt-1 size-5 accent-(--accent)"
            checked={optIn}
            onChange={(e) => setOptIn(e.target.checked)}
          />
          <span className="text-sm">Quero receber lembretes do amigo secreto pelo WhatsApp.</span>
        </label>
        {update.isError && <Alert>{errorMessage(update.error)}</Alert>}
        <Button type="submit" variant="secondary" loading={update.isPending}>
          Salvar WhatsApp
        </Button>
      </form>
    </Card>
  );
}
