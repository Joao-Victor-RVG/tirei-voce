import { errorMessage } from "@/api/client";
import { Alert, Spinner } from "@/components/ui";

import { useDrawValidation } from "./api";

/** Validação ao vivo: recalculada sempre que regras ou participantes mudam. */
export function DrawValidationCard({ groupId }: { groupId: string }) {
  const validation = useDrawValidation(groupId);
  if (validation.isPending)
    return (
      <div className="flex justify-center py-2 text-(--accent)">
        <Spinner />
      </div>
    );
  if (validation.isError) return <Alert>{errorMessage(validation.error)}</Alert>;
  const { possible, message, most_constrained: tight } = validation.data;
  return (
    <Alert tone={possible ? "success" : "warning"}>
      <span aria-live="polite">
        {possible ? "✅ " : "⚠️ "}
        {message}
      </span>
      {!possible && tight.length > 0 && (
        <span className="mt-1 block font-normal">
          Com menos opções:{" "}
          {tight
            .map((p) => `${p.name} (${p.options} ${p.options === 1 ? "opção" : "opções"})`)
            .join(", ")}
          .
        </span>
      )}
    </Alert>
  );
}
