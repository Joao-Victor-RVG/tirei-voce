import { useState } from "react";

import type { Group } from "@/api/types";
import { Button } from "@/components/ui";

import { inviteUrl } from "./status";

export function ShareInvite({ group }: { group: Group }) {
  const [copied, setCopied] = useState(false);
  const url = inviteUrl(group.invite_code);
  const text = `${group.theme.emoji} Bora participar do ${group.display_name} “${group.title}”? Entra pelo link:`;
  const canShare = typeof navigator !== "undefined" && typeof navigator.share === "function";

  const share = async () => {
    try {
      await navigator.share({ title: group.title, text, url });
    } catch {
      // usuário cancelou o compartilhamento
    }
  };

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2500);
    } catch {
      window.prompt("Copie o link do convite:", url);
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 rounded-2xl bg-black/[0.03] p-3">
        <code className="min-w-0 flex-1 truncate text-sm">{url}</code>
      </div>
      <div className="grid gap-2 sm:grid-cols-3">
        {canShare && <Button onClick={share}>Compartilhar</Button>}
        <a
          href={`https://wa.me/?text=${encodeURIComponent(`${text} ${url}`)}`}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex min-h-11 items-center justify-center rounded-full bg-[#25D366] px-5 font-bold text-white hover:brightness-105"
        >
          WhatsApp
        </a>
        <Button variant="secondary" onClick={copy} aria-live="polite">
          {copied ? "Link copiado! ✓" : "Copiar link"}
        </Button>
      </div>
    </div>
  );
}
