import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
  type QueryKey,
} from "@tanstack/react-query";

import { api } from "@/api/client";
import type {
  BlockedPair,
  Circle,
  DrawResult,
  DrawValidation,
  Group,
  GroupCreate,
  GroupPage,
  GroupUpdate,
  InvitePreview,
  JoinResult,
  MyMatch,
  Participant,
  Preferences,
  Theme,
  WishlistItem,
  WishlistItemCreate,
  WishlistItemUpdate,
} from "@/api/types";

export const groupKeys = {
  all: ["groups"] as const,
  list: () => [...groupKeys.all, "list"] as const,
  detail: (id: string) => [...groupKeys.all, id] as const,
  participants: (id: string) => [...groupKeys.all, id, "participants"] as const,
  wishlist: (id: string) => [...groupKeys.all, id, "wishlist"] as const,
  preferences: (id: string) => [...groupKeys.all, id, "preferences"] as const,
  circles: (id: string) => [...groupKeys.all, id, "circles"] as const,
  pairs: (id: string) => [...groupKeys.all, id, "pairs"] as const,
  validation: (id: string) => [...groupKeys.all, id, "validation"] as const,
  match: (id: string) => [...groupKeys.all, id, "match"] as const,
};

function useInvalidate() {
  const queryClient = useQueryClient();
  return (...keys: QueryKey[]) =>
    Promise.all(keys.map((queryKey) => queryClient.invalidateQueries({ queryKey })));
}

// --- Temas e grupos ---

export function useThemes() {
  return useQuery({
    queryKey: ["themes"],
    queryFn: () => api<Theme[]>("/themes"),
    staleTime: Infinity,
  });
}

export function useMyGroups() {
  return useInfiniteQuery({
    queryKey: groupKeys.list(),
    queryFn: ({ pageParam }) =>
      api<GroupPage>("/groups", { query: { cursor: pageParam, limit: 20 } }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last) => last.next_cursor ?? undefined,
  });
}

export function useGroup(id: string) {
  return useQuery({ queryKey: groupKeys.detail(id), queryFn: () => api<Group>(`/groups/${id}`) });
}

export function useCreateGroup() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: async ({ data, open }: { data: GroupCreate; open: boolean }) => {
      const group = await api<Group>("/groups", { method: "POST", body: data });
      return open ? api<Group>(`/groups/${group.id}/open`, { method: "POST" }) : group;
    },
    onSuccess: () => invalidate(groupKeys.list()),
  });
}

function useGroupMutation<TVars>(id: string, request: (vars: TVars) => Promise<Group>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: request,
    onSuccess: async (group) => {
      queryClient.setQueryData(groupKeys.detail(id), group);
      await queryClient.invalidateQueries({ queryKey: groupKeys.list() });
    },
  });
}

export function useUpdateGroup(id: string) {
  return useGroupMutation(id, (data: GroupUpdate) =>
    api<Group>(`/groups/${id}`, { method: "PATCH", body: data }),
  );
}

export function useGroupTransition(id: string) {
  return useGroupMutation(id, (action: "open" | "close" | "finish") =>
    api<Group>(`/groups/${id}/${action}`, { method: "POST" }),
  );
}

export function useRegenerateInvite(id: string) {
  return useGroupMutation(id, () =>
    api<Group>(`/groups/${id}/invite-code/regenerate`, { method: "POST" }),
  );
}

// --- Convites ---

export function useInvitePreview(code: string) {
  return useQuery({
    queryKey: ["invite", code],
    queryFn: () => api<InvitePreview>(`/invites/${code}`),
  });
}

export function useJoinGroup(code: string) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: () => api<JoinResult>(`/invites/${code}/join`, { method: "POST" }),
    onSuccess: () => invalidate(groupKeys.all),
  });
}

// --- Participantes ---

export function useParticipants(id: string) {
  return useQuery({
    queryKey: groupKeys.participants(id),
    queryFn: () => api<Participant[]>(`/groups/${id}/participants`),
  });
}

export function useRemoveParticipant(id: string) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (participantId: string) =>
      api<void>(`/groups/${id}/participants/${participantId}`, { method: "DELETE" }),
    onSuccess: () =>
      invalidate(
        groupKeys.participants(id),
        groupKeys.detail(id),
        groupKeys.circles(id),
        groupKeys.pairs(id),
        groupKeys.validation(id),
      ),
  });
}

export function useSetCoOrganizer(id: string) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ participantId, promote }: { participantId: string; promote: boolean }) =>
      api<Participant>(`/groups/${id}/participants/${participantId}/co-organizer`, {
        method: promote ? "PUT" : "DELETE",
      }),
    onSuccess: () => invalidate(groupKeys.participants(id)),
  });
}

export function useLeaveGroup(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api<void>(`/groups/${id}/leave`, { method: "POST" }),
    onSuccess: async () => {
      queryClient.removeQueries({ queryKey: groupKeys.detail(id) });
      await queryClient.invalidateQueries({ queryKey: groupKeys.list() });
    },
  });
}

// --- Minha lista ---

export function useWishlist(id: string) {
  return useQuery({
    queryKey: groupKeys.wishlist(id),
    queryFn: () => api<WishlistItem[]>(`/groups/${id}/me/wishlist`),
  });
}

export function useAddWishlistItem(id: string) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (data: WishlistItemCreate) =>
      api<WishlistItem>(`/groups/${id}/me/wishlist`, { method: "POST", body: data }),
    onSuccess: () => invalidate(groupKeys.wishlist(id)),
  });
}

export function useUpdateWishlistItem(id: string) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ itemId, data }: { itemId: string; data: WishlistItemUpdate }) =>
      api<WishlistItem>(`/groups/${id}/me/wishlist/${itemId}`, { method: "PATCH", body: data }),
    onSuccess: () => invalidate(groupKeys.wishlist(id)),
  });
}

export function useDeleteWishlistItem(id: string) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (itemId: string) =>
      api<void>(`/groups/${id}/me/wishlist/${itemId}`, { method: "DELETE" }),
    onSuccess: () => invalidate(groupKeys.wishlist(id)),
  });
}

export function usePreferences(id: string) {
  return useQuery({
    queryKey: groupKeys.preferences(id),
    queryFn: () => api<Preferences>(`/groups/${id}/me/preferences`),
  });
}

export function useSavePreferences(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { dislikes: string | null; notes: string | null }) =>
      api<Preferences>(`/groups/${id}/me/preferences`, { method: "PUT", body: data }),
    onSuccess: (prefs) => queryClient.setQueryData(groupKeys.preferences(id), prefs),
  });
}

// --- Regras ---

export function useCircles(id: string, enabled = true) {
  return useQuery({
    queryKey: groupKeys.circles(id),
    queryFn: () => api<Circle[]>(`/groups/${id}/exclusion-circles`),
    enabled,
  });
}

export function useBlockedPairs(id: string, enabled = true) {
  return useQuery({
    queryKey: groupKeys.pairs(id),
    queryFn: () => api<BlockedPair[]>(`/groups/${id}/blocked-pairs`),
    enabled,
  });
}

function useRulesMutation<TVars>(id: string, request: (vars: TVars) => Promise<unknown>) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: request,
    onSuccess: () =>
      invalidate(groupKeys.circles(id), groupKeys.pairs(id), groupKeys.validation(id)),
  });
}

export function useCreateCircle(id: string) {
  return useRulesMutation(id, (data: { name: string; participant_ids: string[] }) =>
    api<Circle>(`/groups/${id}/exclusion-circles`, { method: "POST", body: data }),
  );
}

export function useUpdateCircle(id: string) {
  return useRulesMutation(
    id,
    ({
      circleId,
      data,
    }: {
      circleId: string;
      data: { name?: string; participant_ids?: string[] };
    }) =>
      api<Circle>(`/groups/${id}/exclusion-circles/${circleId}`, { method: "PATCH", body: data }),
  );
}

export function useDeleteCircle(id: string) {
  return useRulesMutation(id, (circleId: string) =>
    api<void>(`/groups/${id}/exclusion-circles/${circleId}`, { method: "DELETE" }),
  );
}

export function useCreatePair(id: string) {
  return useRulesMutation(
    id,
    (data: {
      giver_participant_id: string;
      receiver_participant_id: string;
      bidirectional: boolean;
    }) => api<BlockedPair>(`/groups/${id}/blocked-pairs`, { method: "POST", body: data }),
  );
}

export function useDeletePair(id: string) {
  return useRulesMutation(id, (pairId: string) =>
    api<void>(`/groups/${id}/blocked-pairs/${pairId}`, { method: "DELETE" }),
  );
}

// --- Sorteio ---

export function useDrawValidation(id: string, enabled = true) {
  return useQuery({
    queryKey: groupKeys.validation(id),
    queryFn: () => api<DrawValidation>(`/groups/${id}/draw/validate`, { method: "POST" }),
    enabled,
  });
}

export function useExecuteDraw(id: string) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (idempotencyKey: string) =>
      api<DrawResult>(`/groups/${id}/draw`, {
        method: "POST",
        headers: { "Idempotency-Key": idempotencyKey },
      }),
    onSuccess: () => invalidate(groupKeys.detail(id), groupKeys.list(), groupKeys.match(id)),
  });
}

export function useMyMatch(id: string, enabled: boolean) {
  return useQuery({
    queryKey: groupKeys.match(id),
    queryFn: () => api<MyMatch>(`/groups/${id}/my-match`),
    enabled,
    staleTime: 60_000,
  });
}
