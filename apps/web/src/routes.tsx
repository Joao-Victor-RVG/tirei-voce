import type { RouteObject } from "react-router-dom";

import { Layout } from "@/components/Layout";
import { RequireAuth } from "@/features/auth/RequireAuth";
import { ForgotPasswordPage } from "@/pages/ForgotPasswordPage";
import { LandingPage } from "@/pages/LandingPage";
import { LoginPage } from "@/pages/LoginPage";
import { ProfilePage } from "@/pages/ProfilePage";
import { RegisterPage } from "@/pages/RegisterPage";
import { ResetPasswordPage } from "@/pages/ResetPasswordPage";
import { NotFoundPage, PrivacyPage, TermsPage } from "@/pages/StaticPages";
import { VerifyEmailPage } from "@/pages/VerifyEmailPage";

export const routes: RouteObject[] = [
  {
    element: <Layout />,
    children: [
      { path: "/", element: <LandingPage /> },
      { path: "/login", element: <LoginPage /> },
      { path: "/register", element: <RegisterPage /> },
      { path: "/verify-email", element: <VerifyEmailPage /> },
      { path: "/forgot-password", element: <ForgotPasswordPage /> },
      { path: "/reset-password", element: <ResetPasswordPage /> },
      {
        path: "/profile",
        element: (
          <RequireAuth>
            <ProfilePage />
          </RequireAuth>
        ),
      },
      { path: "/privacidade", element: <PrivacyPage /> },
      { path: "/termos", element: <TermsPage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
];
