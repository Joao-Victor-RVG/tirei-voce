import { useState } from "react";

import { errorMessage } from "@/api/client";
import type { Group } from "@/api/types";
import { Avatar, Button, Card, ErrorState, PageLoader } from "@/components/ui";
import { formatValueRange } from "@/lib/format";

import { useMyMatch } from "./api";
import { WishlistItemView } from "./WishlistItemView";

const CONFETTI = ["🎉", "✨", "🎊", "💝", "⭐", "🎁"];

function revealedKey(groupId: string) {
  return `tv_revealed:${groupId}`;
}

function wasRevealed(groupId: string): boolean {
  try {
    return localStorage.getItem(revealedKey(groupId)) === "1";
  } catch {
    return false;
  }
}

export function RevealCard({ group }: { group: Group }) {
  const [revealed, setRevealed] = useState(() => wasRevealed(group.id));
  const [animate, setAnimate] = useState(false);
  const match = useMyMatch(group.id, revealed);

  const reveal = () => {
    setRevealed(true);
    setAnimate(true);
    try {
      localStorage.setItem(revealedKey(group.id), "1"); // guarda só que revelou, nunca o nome
    } catch {
      // armazenamento indisponível
    }
  };

  if (!revealed) {
    return (
      <Card className="text-center">
        <button
          type="button"
          onClick={reveal}
          className="group flex w-full flex-col items-center gap-4 rounded-3xl py-8 focus-visible:outline-offset-4"
        >
          <span className="animate-wiggle text-8xl transition group-hover:scale-110" aria-hidden>
            🎁
          </span>
          <span className="text-2xl font-black">Você tirou…</span>
          <span className="rounded-full bg-(--accent) px-6 py-3 font-extrabold text-white shadow-md">
            Toque para revelar
          </span>
          <span className="text-sm text-gray-500">Confira se ninguém está espiando 👀</span>
        </button>
      </Card>
    );
  }

  if (match.isPending) return <PageLoader />;
  if (match.isError)
    return <ErrorState message={errorMessage(match.error)} onRetry={() => match.refetch()} />;

  const person = match.data;
  const range = formatValueRange(group.min_value_cents, group.max_value_cents);
  return (
    <div className="relative space-y-4">
      {animate && (
        <div
          aria-hidden
          className="pointer-events-none absolute inset-x-0 top-0 h-0 overflow-visible"
        >
          {Array.from({ length: 18 }, (_, i) => (
            <span
              key={i}
              className="absolute text-2xl"
              style={{
                left: `${(i * 37) % 100}%`,
                animation: `confetti-fall ${1.6 + (i % 5) * 0.3}s ease-in ${(i % 6) * 0.1}s both`,
              }}
            >
              {CONFETTI[i % CONFETTI.length]}
            </span>
          ))}
        </div>
      )}
      <Card className="animate-pop-in space-y-3 text-center">
        <p className="font-bold text-(--accent-text)">Você tirou</p>
        <div className="flex justify-center">
          <Avatar name={person.name} url={person.avatar_url} size="size-24 text-3xl" />
        </div>
        <h2 className="text-4xl font-black">{person.name}</h2>
        <p className="text-sm text-gray-600">Shhh! Isso fica entre você e o Tirei Você! 🤫</p>
        {range && <p className="font-semibold">Valor combinado: {range}</p>}
        {(person.shirt_size || person.shoe_size) && (
          <div className="flex justify-center gap-2">
            {person.shirt_size && (
              <span className="rounded-full bg-(--accent-soft) px-3 py-1 text-sm font-bold text-(--accent-text)">
                👕 {person.shirt_size}
              </span>
            )}
            {person.shoe_size && (
              <span className="rounded-full bg-(--accent-soft) px-3 py-1 text-sm font-bold text-(--accent-text)">
                👟 {person.shoe_size}
              </span>
            )}
          </div>
        )}
      </Card>

      <Card className="space-y-3">
        <h3 className="text-lg font-extrabold">Lista de desejos de {person.name}</h3>
        {person.wishlist.length === 0 ? (
          <p className="text-gray-600">
            {person.name} ainda não colocou nada na lista. Fique de olho!
          </p>
        ) : (
          <ul className="space-y-2">
            {person.wishlist.map((item) => (
              <li key={item.id} className="rounded-2xl bg-black/[0.03] p-3">
                <WishlistItemView item={item} />
              </li>
            ))}
          </ul>
        )}
      </Card>

      {(person.preferences.dislikes || person.preferences.notes) && (
        <Card className="space-y-2">
          {person.preferences.dislikes && (
            <div>
              <h3 className="font-extrabold">🚫 Não quer ganhar</h3>
              <p className="whitespace-pre-line">{person.preferences.dislikes}</p>
            </div>
          )}
          {person.preferences.notes && (
            <div>
              <h3 className="font-extrabold">💡 Dicas</h3>
              <p className="whitespace-pre-line">{person.preferences.notes}</p>
            </div>
          )}
        </Card>
      )}
      <div className="text-center">
        <Button variant="ghost" onClick={() => match.refetch()} loading={match.isFetching}>
          Atualizar lista
        </Button>
      </div>
    </div>
  );
}
