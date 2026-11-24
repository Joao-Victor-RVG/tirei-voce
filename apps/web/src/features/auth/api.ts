import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, ApiError } from "@/api/client";
import type { AuthConfig, Me, MeUpdate } from "@/api/types";

export const meKey = ["me"] as const;

/** Usuário logado, ou null se não houver sessão. */
export function useMe() {
  return useQuery({
    queryKey: meKey,
    queryFn: async () => {
      try {
        return await api<Me>("/me");
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) return null;
        throw error;
      }
    },
    staleTime: 60_000,
  });
}

export function useAuthConfig() {
  return useQuery({
    queryKey: ["auth-config"],
    queryFn: () => api<AuthConfig>("/auth/config"),
    staleTime: Infinity,
  });
}

function useSetMe() {
  const queryClient = useQueryClient();
  return (me: Me | null) => queryClient.setQueryData(meKey, me);
}

export function useLogin() {
  const setMe = useSetMe();
  return useMutation({
    mutationFn: (body: { email: string; password: string }) =>
      api<Me>("/auth/login", { method: "POST", body }),
    onSuccess: setMe,
  });
}

export function useRegister() {
  const setMe = useSetMe();
  return useMutation({
    mutationFn: (body: { name: string; email: string; password: string }) =>
      api<Me>("/auth/register", { method: "POST", body }),
    onSuccess: setMe,
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api<void>("/auth/logout", { method: "POST" }),
    onSettled: () => {
      queryClient.clear();
      queryClient.setQueryData(meKey, null);
    },
  });
}

export function useVerifyEmail() {
  const setMe = useSetMe();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (token: string) =>
      api<Me>("/auth/verify-email", { method: "POST", body: { token } }),
    onSuccess: async (me) => {
      // Só atualiza o cache se a sessão atual for da mesma pessoa.
      const current = queryClient.getQueryData<Me | null>(meKey);
      if (current?.id === me.id) setMe(me);
      else await queryClient.invalidateQueries({ queryKey: meKey });
    },
  });
}

export function useResendVerification() {
  return useMutation({
    mutationFn: () => api<{ message: string }>("/auth/resend-verification", { method: "POST" }),
  });
}

export function useForgotPassword() {
  return useMutation({
    mutationFn: (email: string) =>
      api<{ message: string }>("/auth/forgot-password", { method: "POST", body: { email } }),
  });
}

export function useResetPassword() {
  return useMutation({
    mutationFn: (body: { token: string; password: string }) =>
      api<void>("/auth/reset-password", { method: "POST", body }),
  });
}

export function useUpdateMe() {
  const setMe = useSetMe();
  return useMutation({
    mutationFn: (body: MeUpdate) => api<Me>("/me", { method: "PATCH", body }),
    onSuccess: setMe,
  });
}
