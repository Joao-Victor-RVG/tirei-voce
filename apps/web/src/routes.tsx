import type { RouteObject } from "react-router-dom";

import { Layout } from "@/components/Layout";
import { LandingPage } from "@/pages/LandingPage";
import { NotFoundPage, PrivacyPage, TermsPage } from "@/pages/StaticPages";

export const routes: RouteObject[] = [
  {
    element: <Layout />,
    children: [
      { path: "/", element: <LandingPage /> },
      { path: "/privacidade", element: <PrivacyPage /> },
      { path: "/termos", element: <TermsPage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
];
