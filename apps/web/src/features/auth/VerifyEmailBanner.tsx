import { Link } from "react-router-dom";

import { useMe } from "./api";

export function VerifyEmailBanner() {
  const me = useMe();
  if (!me.data || me.data.email_verified) return null;
  return (
    <div
      role="status"
      className="rounded-2xl bg-amber-50 p-4 text-sm text-amber-900 ring-1 ring-amber-200"
    >
      <strong>Confirme seu e-mail</strong> para criar grupos e entrar em convites.{" "}
      <Link to="/verify-email" className="font-bold underline">
        Reenviar link
      </Link>
    </div>
  );
}
