import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/api/client";
import type { components } from "@/api/schema";

export type AdminMetrics = components["schemas"]["AdminMetrics"];
export type AdminUser = components["schemas"]["AdminUserOut"];
type AdminUserPage = components["schemas"]["AdminUserPage"];

export function useAdminMetrics() {
  return useQuery({
    queryKey: ["admin", "metrics"],
    queryFn: () => api<AdminMetrics>("/admin/metrics"),
    refetchInterval: 60_000,
  });
}

export function useAdminUsers(q: string) {
  return useInfiniteQuery({
    queryKey: ["admin", "users", q],
    queryFn: ({ pageParam }) =>
      api<AdminUserPage>("/admin/users", { query: { q, cursor: pageParam, limit: 25 } }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last) => last.next_cursor ?? undefined,
  });
}

export function useSetUserActive() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) =>
      api<AdminUser>(`/admin/users/${id}/${active ? "activate" : "deactivate"}`, {
        method: "POST",
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin"] }),
  });
}
