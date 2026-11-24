import type { WishlistItem } from "@/api/types";
import { formatCents } from "@/lib/format";

import { PRIORITY_LABEL } from "./priority";

export function WishlistItemView({ item }: { item: WishlistItem }) {
  return (
    <div className="min-w-0 flex-1 space-y-1">
      <p className="font-bold break-words">{item.title}</p>
      <p className="flex flex-wrap gap-x-3 gap-y-1 text-sm text-gray-600">
        <span>{PRIORITY_LABEL[item.priority]}</span>
        {item.price_hint_cents != null && <span>~ {formatCents(item.price_hint_cents)}</span>}
        {item.url && (
          <a
            href={item.url}
            target="_blank"
            rel="noopener noreferrer nofollow"
            className="font-bold text-(--accent-text) underline"
          >
            Ver link
          </a>
        )}
      </p>
      {item.notes && <p className="text-sm whitespace-pre-line">{item.notes}</p>}
    </div>
  );
}
