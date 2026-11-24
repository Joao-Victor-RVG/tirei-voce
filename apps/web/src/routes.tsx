import type { RouteObject } from "react-router-dom";

import { Layout } from "@/components/Layout";
import { Protected } from "@/features/auth/RequireAuth";
import { AdminPage } from "@/pages/AdminPage";
import { CreateGroupPage } from "@/pages/CreateGroupPage";
import { ForgotPasswordPage } from "@/pages/ForgotPasswordPage";
import { GroupPage } from "@/pages/GroupPage";
import { GroupsPage } from "@/pages/GroupsPage";
import { InvitePage } from "@/pages/InvitePage";
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
      { path: "/i/:code", element: <InvitePage /> },
      { path: "/admin", element: <Protected page={<AdminPage />} /> },
      { path: "/groups", element: <Protected page={<GroupsPage />} /> },
      { path: "/groups/new", element: <Protected page={<CreateGroupPage />} /> },
      { path: "/groups/:groupId", element: <Protected page={<GroupPage />} /> },
      {
        path: "/profile",
        element: <Protected page={<ProfilePage />} />,
      },
      { path: "/privacidade", element: <PrivacyPage /> },
      { path: "/termos", element: <TermsPage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
];
