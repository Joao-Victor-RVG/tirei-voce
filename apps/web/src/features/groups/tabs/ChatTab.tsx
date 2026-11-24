import { useEffect, useRef, useState } from "react";

import { errorMessage } from "@/api/client";
import type { ChatMessage, ChatThreadId, Group } from "@/api/types";
import { Alert, Avatar, Button, Card, ErrorState, PageLoader } from "@/components/ui";
import { cx } from "@/lib/cx";
import { formatShortDateTime } from "@/lib/format";

import {
  fetchOlderMessages,
  useChatMessages,
  useChatThreads,
  useMarkRead,
  useSendMessage,
} from "../chatApi";

const HINTS: Record<ChatThreadId, string> = {
  match: "Você sabe com quem está falando; a outra pessoa não sabe que é você. 🤫",
  santa: "Quem te tirou está do outro lado. Pergunte o que quiser!",
};

export function ChatTab({ group }: { group: Group }) {
  const threads = useChatThreads(group.id, true);
  const [open, setOpen] = useState<ChatThreadId | null>(null);

  if (threads.isPending) return <PageLoader />;
  if (threads.isError)
    return <ErrorState message={errorMessage(threads.error)} onRetry={() => threads.refetch()} />;

  const current = threads.data.find((t) => t.thread === open);
  if (current) {
    return (
      <ChatThread
        group={group}
        thread={current.thread}
        title={current.title}
        onBack={() => setOpen(null)}
      />
    );
  }

  return (
    <div className="space-y-3">
      {threads.data.map((t) => (
        <button
          key={t.thread}
          type="button"
          onClick={() => setOpen(t.thread)}
          className="flex w-full items-center gap-3 rounded-3xl bg-white p-4 text-left shadow-sm ring-1 ring-black/5 hover:ring-(--accent)"
        >
          {t.thread === "santa" ? (
            <span
              aria-hidden
              className="flex size-12 items-center justify-center rounded-full bg-(--accent-soft) text-2xl"
            >
              🎅
            </span>
          ) : (
            <Avatar name={t.title} size="size-12" />
          )}
          <span className="min-w-0 flex-1">
            <span className="block text-sm font-bold text-(--accent-text)">
              {t.thread === "match" ? "Quem você tirou" : "Quem te tirou"}
            </span>
            <span className="block truncate font-extrabold">{t.title}</span>
            <span className="block truncate text-sm text-gray-600">
              {t.last_message
                ? `${t.last_message.from_me ? "Você: " : ""}${t.last_message.body}`
                : "Nenhuma mensagem ainda"}
            </span>
          </span>
          {t.unread > 0 && (
            <span
              aria-label={`${t.unread} não lidas`}
              className="flex min-w-6 items-center justify-center rounded-full bg-(--accent) px-2 py-0.5 text-sm font-black text-white"
            >
              {t.unread}
            </span>
          )}
        </button>
      ))}
    </div>
  );
}

function ChatThread({
  group,
  thread,
  title,
  onBack,
}: {
  group: Group;
  thread: ChatThreadId;
  title: string;
  onBack: () => void;
}) {
  const latest = useChatMessages(group.id, thread);
  const send = useSendMessage(group.id, thread);
  const markRead = useMarkRead(group.id, thread);
  const [older, setOlder] = useState<ChatMessage[]>([]);
  const [olderCursor, setOlderCursor] = useState<string | null | undefined>(undefined);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const [text, setText] = useState("");
  const bottom = useRef<HTMLDivElement>(null);
  const readonly = group.status === "FINISHED";

  const items = latest.data?.items ?? [];
  const lastId = items.at(-1)?.id;
  const hasUnreadFromOther = items.some((m) => !m.from_me);
  const { mutate: markAsRead } = markRead;

  useEffect(() => {
    // Marca como lida sempre que chega mensagem nova enquanto a conversa está aberta.
    if (lastId && hasUnreadFromOther) markAsRead();
  }, [lastId, hasUnreadFromOther, markAsRead]);

  useEffect(() => {
    bottom.current?.scrollIntoView?.({ block: "end" });
  }, [lastId]);

  const cursor = olderCursor === undefined ? latest.data?.next_cursor : olderCursor;

  const loadOlder = async () => {
    if (!cursor) return;
    setLoadingOlder(true);
    try {
      const page = await fetchOlderMessages(group.id, thread, cursor);
      setOlder((prev) => [...page.items, ...prev]);
      setOlderCursor(page.next_cursor);
    } finally {
      setLoadingOlder(false);
    }
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const body = text.trim();
    if (!body) return;
    try {
      await send.mutateAsync(body);
      setText("");
    } catch {
      // erro exibido abaixo
    }
  };

  const all = [...older, ...items];
  return (
    <Card className="flex flex-col gap-3">
      <div className="flex items-center gap-3">
        <Button
          variant="ghost"
          className="min-h-9 px-3"
          onClick={onBack}
          aria-label="Voltar para as conversas"
        >
          ←
        </Button>
        <div>
          <h2 className="font-extrabold">{title}</h2>
          <p className="text-xs text-gray-600">{HINTS[thread]}</p>
        </div>
      </div>

      <div
        className="max-h-[55vh] min-h-48 space-y-2 overflow-y-auto rounded-2xl bg-black/[0.03] p-3"
        aria-live="polite"
      >
        {cursor && (
          <div className="text-center">
            <Button
              variant="ghost"
              className="min-h-8 text-sm"
              loading={loadingOlder}
              onClick={loadOlder}
            >
              Ver mensagens anteriores
            </Button>
          </div>
        )}
        {latest.isPending ? (
          <PageLoader />
        ) : latest.isError ? (
          <ErrorState message={errorMessage(latest.error)} onRetry={() => latest.refetch()} />
        ) : all.length === 0 ? (
          <p className="py-8 text-center text-sm text-gray-500">Comece a conversa! 💬</p>
        ) : (
          all.map((m) => (
            <div key={m.id} className={cx("flex", m.from_me ? "justify-end" : "justify-start")}>
              <div
                className={cx(
                  "max-w-[80%] rounded-2xl px-3 py-2",
                  m.from_me
                    ? "rounded-br-sm bg-(--accent) text-white"
                    : "rounded-bl-sm bg-white ring-1 ring-black/5",
                )}
              >
                <p className="break-words whitespace-pre-line">{m.body}</p>
                <p
                  className={cx(
                    "mt-1 text-right text-[11px]",
                    m.from_me ? "text-white/80" : "text-gray-500",
                  )}
                >
                  {formatShortDateTime(m.created_at)}
                </p>
              </div>
            </div>
          ))
        )}
        <div ref={bottom} />
      </div>

      {readonly ? (
        <Alert tone="info">O grupo foi encerrado: o chat está só para leitura.</Alert>
      ) : (
        <form onSubmit={submit} className="flex items-end gap-2">
          <label htmlFor="chat-input" className="sr-only">
            Mensagem
          </label>
          <textarea
            id="chat-input"
            value={text}
            maxLength={1000}
            rows={1}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                void submit(e);
              }
            }}
            placeholder="Escreva uma mensagem…"
            className="max-h-32 min-h-11 flex-1 resize-none rounded-2xl bg-white px-4 py-3 ring-1 ring-black/10 focus:ring-2 focus:ring-(--accent) focus:outline-none"
          />
          <Button type="submit" loading={send.isPending} disabled={!text.trim()}>
            Enviar
          </Button>
        </form>
      )}
      {send.isError && <Alert>{errorMessage(send.error)}</Alert>}
    </Card>
  );
}
