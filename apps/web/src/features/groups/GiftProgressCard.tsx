import { errorMessage } from "@/api/client";
import { Alert, Card } from "@/components/ui";

import { useGiftProgress } from "./api";

export function GiftProgressCard({ groupId }: { groupId: string }) {
  const progress = useGiftProgress(groupId, true);
  if (progress.isPending) return null;
  if (progress.isError) return <Alert>{errorMessage(progress.error)}</Alert>;
  const { purchased, total } = progress.data;
  const percent = total ? Math.round((purchased / total) * 100) : 0;
  return (
    <Card className="space-y-2">
      <div className="flex items-baseline justify-between">
        <h2 className="text-lg font-extrabold">Presentes comprados</h2>
        <span className="font-black text-(--accent-text)">
          {purchased} de {total}
        </span>
      </div>
      <div
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={total}
        aria-valuenow={purchased}
        aria-label="Presentes comprados"
        className="h-3 overflow-hidden rounded-full bg-black/10"
      >
        <div
          className="h-full rounded-full bg-(--accent) transition-all"
          style={{ width: `${percent}%` }}
        />
      </div>
      <p className="text-sm text-gray-600">Só o total: ninguém fica sabendo quem já comprou.</p>
    </Card>
  );
}
