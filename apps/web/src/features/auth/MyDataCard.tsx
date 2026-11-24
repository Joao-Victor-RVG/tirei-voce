import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { api, errorMessage } from "@/api/client";
import type { Me } from "@/api/types";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { Alert, Button, Card, Field, Input } from "@/components/ui";

import { meKey } from "./api";

export function MyDataCard({ me }: { me: Me }) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [exporting, setExporting] = useState(false);
  const [open, setOpen] = useState(false);
  const [secret, setSecret] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const download = async () => {
    setExporting(true);
    setError(null);
    try {
      const data = await api<unknown>("/me/export");
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "tirei-voce-meus-dados.json";
      link.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setExporting(false);
    }
  };

  const remove = async () => {
    setDeleting(true);
    setError(null);
    try {
      await api("/me/delete", {
        method: "POST",
        body: me.has_password ? { password: secret } : { confirm: secret },
      });
      queryClient.clear();
      queryClient.setQueryData(meKey, null);
      navigate("/", { replace: true });
    } catch (e) {
      setError(errorMessage(e));
      setDeleting(false);
    }
  };

  return (
    <Card className="space-y-3">
      <h2 className="text-lg font-extrabold">Meus dados</h2>
      <p className="text-sm text-gray-600">
        Baixe uma cópia dos seus dados ou exclua sua conta. Grupos encerrados são apagados
        automaticamente depois de 12 meses.
      </p>
      <div className="flex flex-wrap gap-2">
        <Button variant="secondary" loading={exporting} onClick={download}>
          Baixar meus dados
        </Button>
        <Button variant="ghost" className="text-red-700" onClick={() => setOpen(true)}>
          Excluir minha conta
        </Button>
      </div>
      {error && !open && <Alert>{error}</Alert>}
      <ConfirmDialog
        open={open}
        title="Excluir sua conta?"
        confirmLabel="Excluir para sempre"
        danger
        loading={deleting}
        onClose={() => {
          setOpen(false);
          setSecret("");
          setError(null);
        }}
        onConfirm={remove}
      >
        <div className="space-y-3">
          <p>
            Apagamos seus dados pessoais, listas e mensagens. Em grupos já sorteados você aparece
            como “Participante removido”, para o sorteio dos outros continuar funcionando. Grupos
            que você criou passam para outra pessoa do grupo.
          </p>
          <Field label={me.has_password ? "Sua senha" : 'Digite "EXCLUIR" para confirmar'}>
            {(id) => (
              <Input
                id={id}
                type={me.has_password ? "password" : "text"}
                autoComplete={me.has_password ? "current-password" : "off"}
                value={secret}
                onChange={(e) => setSecret(e.target.value)}
              />
            )}
          </Field>
          {error && <Alert>{error}</Alert>}
        </div>
      </ConfirmDialog>
    </Card>
  );
}
