import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Política de cookies",
  description:
    "Como a FácilCar usa cookies essenciais e, com o seu consentimento, cookies de analytics.",
};

export default function PoliticaDeCookiesPage() {
  return (
    <main className="min-h-screen py-12 px-4">
      <div className="mx-auto max-w-3xl">
        <h1 className="text-2xl font-semibold">Política de cookies</h1>
        <div className="public-prose mt-6 space-y-4 text-sm leading-relaxed text-facil-muted">
          <p>
            Esta página explica, de forma simples, quais cookies o site da FácilCar Multimarcas
            utiliza e como você escolhe o que aceitar.
          </p>
          <h2 className="text-base font-semibold text-foreground">Cookies essenciais</h2>
          <p>
            Necessários para o site funcionar — por exemplo, manter a sessão de quem acessa o
            painel administrativo. Esses cookies não dependem de consentimento de marketing.
          </p>
          <h2 className="text-base font-semibold text-foreground">Cookies de analytics</h2>
          <p>
            Usamos o PostHog apenas se você clicar em <strong>Aceitar</strong>. Eles ajudam a
            entender quais páginas são visitadas, sem vender seus dados. Se escolher{" "}
            <strong>Só essenciais</strong>, o PostHog não é iniciado.
          </p>
          <h2 className="text-base font-semibold text-foreground">Sua escolha</h2>
          <p>
            A escolha fica salva neste navegador. Você pode limpar os dados do site nas
            configurações do navegador para ver o aviso de novo.
          </p>
          <p>
            Para o tratamento de dados pessoais em geral, veja a{" "}
            <Link href="/politica-de-privacidade" className="text-facil-orange hover:underline">
              política de privacidade
            </Link>
            .
          </p>
        </div>
      </div>
    </main>
  );
}
