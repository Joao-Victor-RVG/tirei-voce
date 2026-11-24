import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { EmptyState } from "@/components/ui";

function StaticPage({ title, children }: { title: string; children: ReactNode }) {
  return (
    <article className="space-y-4 leading-relaxed">
      <h1 className="text-3xl font-black">{title}</h1>
      {children}
    </article>
  );
}

export function PrivacyPage() {
  return (
    <StaticPage title="Política de privacidade">
      <p className="rounded-2xl bg-amber-50 p-4 text-sm font-semibold text-amber-900">
        Versão provisória: este texto será revisado antes do lançamento.
      </p>
      <p>
        Coletamos apenas o necessário para o amigo secreto funcionar: nome, e-mail, foto (se você
        entrar com o Google), tamanhos que você informar e suas listas de desejos.
      </p>
      <p>
        O resultado do sorteio fica cifrado. Nem o organizador nem nossa equipe conseguem ver quem
        tirou quem pela aplicação.
      </p>
      <p>Não vendemos seus dados e não usamos suas informações para publicidade.</p>
      <h2 className="text-xl font-extrabold">Por quanto tempo guardamos</h2>
      <p>
        Dados de grupos sem atividade (incluindo listas, conversas e o resultado cifrado do sorteio)
        são apagados automaticamente 12 meses depois do evento. Contas que nunca confirmaram o
        e-mail são apagadas depois de 30 dias.
      </p>
      <h2 className="text-xl font-extrabold">Seus direitos (LGPD)</h2>
      <p>
        No seu perfil você pode baixar uma cópia dos seus dados e excluir sua conta a qualquer
        momento. Se você estiver em um grupo já sorteado, seu nome vira “Participante removido” e
        seus dados pessoais, listas e mensagens são apagados; assim o sorteio das outras pessoas
        continua funcionando.
      </p>
    </StaticPage>
  );
}

export function TermsPage() {
  return (
    <StaticPage title="Termos de uso">
      <p className="rounded-2xl bg-amber-50 p-4 text-sm font-semibold text-amber-900">
        Versão provisória: este texto será revisado antes do lançamento.
      </p>
      <p>
        O Tirei Você! é uma ferramenta para organizar brincadeiras de troca de presentes entre
        amigos. Use com respeito: conteúdos ofensivos nos grupos e listas podem levar à remoção da
        conta.
      </p>
      <p>
        O organizador é responsável pelas regras do grupo e pelo evento. A plataforma não intermedia
        compras nem pagamentos.
      </p>
    </StaticPage>
  );
}

export function NotFoundPage() {
  return (
    <EmptyState emoji="🧐" title="Página não encontrada">
      <p>
        O link pode estar errado ou ter expirado.{" "}
        <Link to="/" className="font-bold text-(--accent-text) underline">
          Voltar ao início
        </Link>
      </p>
    </EmptyState>
  );
}
