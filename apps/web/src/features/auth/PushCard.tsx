import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api, errorMessage } from "@/api/client";
import type { components } from "@/api/schema";
import { Alert, Button, Card } from "@/components/ui";
import { currentSubscription, disablePush, enablePush, pushSupport } from "@/lib/push";

type PushConfig = components["schemas"]["PushConfigOut"];

const pushKey = ["push-config"] as const;

export function PushCard() {
  const support = pushSupport();
  const queryClient = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const config = useQuery({
    queryKey: pushKey,
    queryFn: async () => {
      const subscription =
        support === "supported" ? await currentSubscription().catch(() => null) : null;
      return api<PushConfig>("/push/config", { query: { endpoint: subscription?.endpoint } });
    },
  });

  if (!config.data?.enabled) return null;

  const toggle = async () => {
    setBusy(true);
    setError(null);
    try {
      if (config.data?.subscribed) await disablePush();
      else await enablePush(config.data!.public_key!);
      await queryClient.invalidateQueries({ queryKey: pushKey });
    } catch (e) {
      setError(e instanceof Error && !("status" in e) ? e.message : errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card className="space-y-3">
      <h2 className="text-lg font-extrabold">Notificações neste aparelho</h2>
      <p className="text-sm text-gray-600">
        Avisamos quando o sorteio sair, quando chegar mensagem no chat e perto do evento.
      </p>
      {support === "needs-install" ? (
        <Alert tone="info">
          No iPhone, toque em Compartilhar → “Adicionar à Tela de Início” e abra o app por lá para
          ativar.
        </Alert>
      ) : support === "unsupported" ? (
        <Alert tone="info">Este navegador não suporta notificações.</Alert>
      ) : (
        <Button
          variant={config.data.subscribed ? "secondary" : "primary"}
          loading={busy}
          onClick={toggle}
        >
          {config.data.subscribed ? "Desativar notificações" : "Ativar notificações 🔔"}
        </Button>
      )}
      {error && <Alert>{error}</Alert>}
    </Card>
  );
}
