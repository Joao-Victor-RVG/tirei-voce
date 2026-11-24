import type { ReactNode } from "react";

export function AuthCard({
  emoji,
  title,
  subtitle,
  children,
}: {
  emoji: string;
  title: string;
  subtitle?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="mx-auto max-w-md space-y-6 py-4">
      <div className="space-y-2 text-center">
        <div className="text-5xl" aria-hidden>
          {emoji}
        </div>
        <h1 className="text-3xl font-black">{title}</h1>
        {subtitle && <p className="text-gray-600">{subtitle}</p>}
      </div>
      <div className="rounded-3xl bg-white p-6 shadow-sm ring-1 ring-black/5">{children}</div>
    </div>
  );
}
