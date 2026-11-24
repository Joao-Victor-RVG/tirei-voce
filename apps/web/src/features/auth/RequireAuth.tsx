import type { ReactElement, ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { ErrorState, PageLoader } from "@/components/ui";
import { errorMessage } from "@/api/client";

import { useMe } from "./api";
import { loginPath } from "./paths";

export function RequireAuth({ children }: { children: ReactNode }) {
  const me = useMe();
  const location = useLocation();
  if (me.isPending) return <PageLoader />;
  if (me.isError)
    return <ErrorState message={errorMessage(me.error)} onRetry={() => me.refetch()} />;
  if (!me.data) return <Navigate to={loginPath(location.pathname + location.search)} replace />;
  return <>{children}</>;
}

export function Protected({ page }: { page: ReactElement }) {
  return <RequireAuth>{page}</RequireAuth>;
}
