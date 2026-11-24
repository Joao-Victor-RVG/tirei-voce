import { useEffect, useState } from "react";

import { errorMessage } from "@/api/client";
import type { Group } from "@/api/types";
import { Alert, Avatar, Button, Card } from "@/components/ui";
import { formatDateTime } from "@/lib/format";

import { useMySanta } from "./api";
import { Countdown } from "./Countdown";

/** No dia do evento: cada um descobre quem o tirou (e só isso). */
export function SantaRevealCard({ group }: { group: Group }) {
  const eventAt = group.event_at;
  const [now, setNow] = useState(() => Date.now());
  const [asked, setAsked] = useState(false);
  const open = !!eventAt && now >= Date.parse(eventAt);
  const santa = useMySanta(group.id, open && asked);

  useEffect(() => {
    if (!eventAt || open) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [eventAt, open]);

  if (!eventAt) return null;

  return (
    <Card className="space-y-3 text-center">
      <h2 className="text-lg font-extrabold">🕵️ Quem me tirou?</h2>
      {!open ? (
        <>
          <p className="text-sm text-gray-600">
            A revelação abre no horário do evento: {formatDateTime(eventAt)}.
          </p>
          <Countdown target={eventAt} />
        </>
      ) : santa.data ? (
        <div className="animate-pop-in space-y-2">
          <div className="flex justify-center">
            <Avatar name={santa.data.name} url={santa.data.avatar_url} size="size-20 text-2xl" />
          </div>
          <p className="text-sm font-bold text-(--accent-text)">Quem te tirou foi</p>
          <p className="text-3xl font-black">{santa.data.name}</p>
        </div>
      ) : (
        <>
          <p className="text-sm text-gray-600">Chegou a hora! Toque para descobrir.</p>
          <Button onClick={() => setAsked(true)} loading={santa.isFetching}>
            Revelar 🎉
          </Button>
          {santa.isError && <Alert>{errorMessage(santa.error)}</Alert>}
        </>
      )}
    </Card>
  );
}
