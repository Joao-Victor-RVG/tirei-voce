import type { GroupStatus } from "@/api/types";
import { cx } from "@/lib/cx";

import { STATUS_CLASSES, STATUS_LABEL } from "./status";

export function StatusBadge({ status }: { status: GroupStatus }) {
  return (
    <span
      className={cx(
        "inline-flex rounded-full px-2.5 py-1 text-xs font-extrabold",
        STATUS_CLASSES[status],
      )}
    >
      {STATUS_LABEL[status]}
    </span>
  );
}
