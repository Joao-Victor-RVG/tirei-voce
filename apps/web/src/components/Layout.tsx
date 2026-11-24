import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";

import { useLogout, useMe } from "@/features/auth/api";
import { cx } from "@/lib/cx";

import { Avatar } from "./ui";

export function Layout() {
  const me = useMe();
  const logout = useLogout();
  const navigate = useNavigate();

  const onLogout = async () => {
    await logout.mutateAsync().catch(() => undefined);
    navigate("/");
  };

  return (
    <div className="flex min-h-dvh flex-col">
      <a
        href="#conteudo"
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:rounded-full focus:bg-white focus:px-4 focus:py-2"
      >
        Pular para o conteúdo
      </a>
      <header className="bg-paper/90 sticky top-0 z-20 border-b border-black/5 backdrop-blur">
        <div className="mx-auto flex max-w-3xl items-center justify-between gap-3 px-4 py-3">
          <Link
            to={me.data ? "/groups" : "/"}
            className="flex items-center gap-2 text-lg font-black"
          >
            <span aria-hidden className="text-2xl">
              🎁
            </span>
            Tirei Você!
          </Link>
          {me.data ? (
            <nav className="flex items-center gap-1 text-sm font-bold" aria-label="Principal">
              <NavLink
                to="/groups"
                className={({ isActive }) =>
                  cx("rounded-full px-3 py-2", isActive ? "bg-black/5" : "hover:bg-black/5")
                }
              >
                Meus grupos
              </NavLink>
              {me.data.is_admin && (
                <NavLink
                  to="/admin"
                  className={({ isActive }) =>
                    cx("rounded-full px-3 py-2", isActive ? "bg-black/5" : "hover:bg-black/5")
                  }
                >
                  Admin
                </NavLink>
              )}
              <NavLink
                to="/profile"
                className="rounded-full p-1 hover:bg-black/5"
                aria-label="Meu perfil"
              >
                <Avatar name={me.data.name} url={me.data.avatar_url} size="size-8" />
              </NavLink>
              <button
                type="button"
                onClick={onLogout}
                className="rounded-full px-3 py-2 hover:bg-black/5"
              >
                Sair
              </button>
            </nav>
          ) : (
            me.data === null && (
              <Link
                to="/login"
                className="rounded-full px-4 py-2 text-sm font-bold hover:bg-black/5"
              >
                Entrar
              </Link>
            )
          )}
        </div>
      </header>
      <main id="conteudo" className="mx-auto w-full max-w-3xl flex-1 px-4 py-6">
        <Outlet />
      </main>
      <footer className="mx-auto w-full max-w-3xl px-4 py-6 text-center text-sm text-gray-500">
        <Link to="/privacidade" className="underline-offset-2 hover:underline">
          Privacidade
        </Link>
        {" · "}
        <Link to="/termos" className="underline-offset-2 hover:underline">
          Termos de uso
        </Link>
      </footer>
    </div>
  );
}
