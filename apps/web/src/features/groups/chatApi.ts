import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/api/client";
import type { ChatMessage, ChatPage, ChatThreadId, ChatThreadSummary } from "@/api/types";

import { groupKeys } from "./api";

export const POLL_MS = 10_000;

const chatKeys = {
  threads: (id: string) => [...groupKeys.all, id, "chat-threads"] as const,
  messages: (id: string, thread: ChatThreadId) =>
    [...groupKeys.all, id, "chat-messages", thread] as const,
};

export function useChatThreads(groupId: string, enabled: boolean) {
  return useQuery({
    queryKey: chatKeys.threads(groupId),
    queryFn: () => api<ChatThreadSummary[]>(`/groups/${groupId}/chats`),
    enabled,
    refetchInterval: POLL_MS * 3,
  });
}

/** Últimas mensagens da conversa, atualizadas por polling enquanto a tela está aberta. */
export function useChatMessages(groupId: string, thread: ChatThreadId) {
  return useQuery({
    queryKey: chatKeys.messages(groupId, thread),
    queryFn: () =>
      api<ChatPage>(`/groups/${groupId}/chats/${thread}/messages`, { query: { limit: 50 } }),
    refetchInterval: POLL_MS,
  });
}

export function fetchOlderMessages(groupId: string, thread: ChatThreadId, before: string) {
  return api<ChatPage>(`/groups/${groupId}/chats/${thread}/messages`, {
    query: { before, limit: 50 },
  });
}

export function useSendMessage(groupId: string, thread: ChatThreadId) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: string) =>
      api<ChatMessage>(`/groups/${groupId}/chats/${thread}/messages`, {
        method: "POST",
        body: { body },
      }),
    onSuccess: (message) => {
      queryClient.setQueryData<ChatPage>(chatKeys.messages(groupId, thread), (old) =>
        old ? { ...old, items: [...old.items, message] } : old,
      );
      void queryClient.invalidateQueries({ queryKey: chatKeys.threads(groupId) });
    },
  });
}

export function useMarkRead(groupId: string, thread: ChatThreadId) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api<void>(`/groups/${groupId}/chats/${thread}/read`, { method: "POST" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: chatKeys.threads(groupId) }),
  });
}
