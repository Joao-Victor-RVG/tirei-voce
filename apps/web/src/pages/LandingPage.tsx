import { Link, Navigate } from "react-router-dom";

import { useMe } from "@/features/auth/api";

const THEMES = [
  { emoji: "🎁", name: "Amigo Secreto", text: "O clássico de fim de ano." },
  { emoji: "🐆", name: "Amigo da Onça", text: "Quanto pior o presente, melhor!" },
  { emoji: "🩲", name: "Amigo Calcinha", text: "Conforto e muita risada." },
];

const STEPS = [
  "Crie o grupo e defina valor, data e local.",
  "Mande o link no WhatsApp da galera.",
  "Cada um monta sua lista de desejos.",
  "Sorteie: cada pessoa só vê quem tirou.",
];

export function LandingPage() {
  const me = useMe();
  if (me.data) return <Navigate to="/groups" replace />;

  return (
    <div className="space-y-10 py-4">
      <section className="space-y-5 text-center">
        <div className="animate-wiggle text-7xl" aria-hidden>
          🎁
        </div>
        <h1 className="text-4xl font-black tracking-tight text-balance sm:text-5xl">
          Amigo secreto sem papelzinho e sem spoiler
        </h1>
        <p className="mx-auto max-w-md text-lg text-gray-600">
          Organize o sorteio pelo celular, compartilhe pelo WhatsApp e deixe o Tirei Você! guardar o
          segredo.
        </p>
        <Link
          to="/register"
          className="inline-flex min-h-12 items-center justify-center rounded-full bg-(--accent) px-7 text-lg font-extrabold text-white shadow-md hover:brightness-110"
        >
          Criar meu amigo secreto
        </Link>
        <p className="text-sm text-gray-600">
          Já tem conta?{" "}
          <Link
            to="/login"
            className="font-bold text-(--accent-text) underline-offset-2 hover:underline"
          >
            Entrar
          </Link>
        </p>
      </section>

      <section aria-labelledby="temas" className="space-y-3">
        <h2 id="temas" className="text-center text-xl font-extrabold">
          Escolha a brincadeira
        </h2>
        <ul className="grid gap-3 sm:grid-cols-3">
          {THEMES.map((theme) => (
            <li
              key={theme.name}
              className="rounded-3xl bg-white p-5 text-center shadow-sm ring-1 ring-black/5"
            >
              <div className="text-4xl" aria-hidden>
                {theme.emoji}
              </div>
              <p className="mt-2 font-extrabold">{theme.name}</p>
              <p className="text-sm text-gray-600">{theme.text}</p>
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="como" className="space-y-3">
        <h2 id="como" className="text-center text-xl font-extrabold">
          Como funciona
        </h2>
        <ol className="space-y-2">
          {STEPS.map((step, index) => (
            <li
              key={step}
              className="flex items-center gap-3 rounded-2xl bg-white p-4 ring-1 ring-black/5"
            >
              <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-(--accent) font-black text-white">
                {index + 1}
              </span>
              <span className="font-semibold">{step}</span>
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}
