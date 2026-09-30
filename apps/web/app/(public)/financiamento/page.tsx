import Link from "next/link";
import { FinancingSimulationForm } from "@/features/lead/ui/FinancingSimulationForm";
import { getSiteSettings } from "@/features/settings/server/queries";

export const metadata = {
  title: "Financiamento e refinanciamento | FácilCar",
  description:
    "Precisa de crédito para comprar um carro ou usar o seu como garantia? Fale com a equipe da FácilCar pelo WhatsApp — sem CPF e sem burocracia agora.",
};

export default async function FinanciamentoPage() {
  const settings = await getSiteSettings();
  const wa = settings?.defaultWhatsappNumber?.replace(/\D/g, "") ?? "";

  return (
    <main className="min-h-screen">
      <section className="bg-facil-black px-4 py-16 text-white">
        <div className="mx-auto max-w-6xl">
          <p className="text-sm font-semibold uppercase tracking-widest text-facil-orange">
            Crédito veicular
          </p>
          <h1 className="mt-4 text-4xl font-extrabold md:text-5xl">
            Financiamento ou refinanciamento?
          </h1>
          <p className="mt-6 max-w-2xl text-lg text-zinc-300">
            A FácilCar orienta os dois caminhos. Conta o que você precisa — o encaminhamento é
            feito pelo WhatsApp, sem CPF nem burocracia agora.
          </p>
          <div className="mt-8 flex flex-wrap gap-4">
            <div className="flex items-center gap-2 rounded-full bg-facil-card/10 px-4 py-2 text-sm">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden>
                <path d="M20 6 9 17l-5-5" />
              </svg>
              Sem CPF agora
            </div>
            <div className="flex items-center gap-2 rounded-full bg-facil-card/10 px-4 py-2 text-sm">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden>
                <path d="M20 6 9 17l-5-5" />
              </svg>
              Resposta via WhatsApp
            </div>
          </div>
        </div>
      </section>

      <section className="px-4 py-14">
        <div className="mx-auto grid max-w-6xl gap-12 lg:grid-cols-[1fr_min(100%,440px)]">
          <div>
            <h2 className="text-2xl font-bold text-foreground">Como funciona</h2>
            <div className="mt-8 grid gap-6 sm:grid-cols-2">
              <div className="rounded-2xl border border-facil-border bg-facil-surface p-6">
                <h3 className="font-bold text-foreground">Financiar</h3>
                <p className="mt-2 text-sm text-facil-muted leading-relaxed">
                  Crédito para adquirir um veículo — com ou sem um em mente. A equipe orienta as
                  condições com as financeiras parceiras, sujeitas à análise de crédito.
                </p>
              </div>
              <div className="rounded-2xl border border-facil-border bg-facil-surface p-6">
                <h3 className="font-bold text-foreground">Refinanciar</h3>
                <p className="mt-2 text-sm text-facil-muted leading-relaxed">
                  Usar o seu próprio carro como garantia para obter crédito. O veículo fica alienado
                  enquanto o crédito está em aberto. Sujeito à avaliação e à análise da financeira.
                </p>
              </div>
            </div>

            <div className="mt-10 rounded-2xl border border-facil-border bg-facil-surface p-6">
              <h3 className="font-semibold text-foreground">O que é preciso para o fechamento</h3>
              <ul className="mt-3 space-y-1.5 text-sm text-facil-muted">
                <li className="flex items-start gap-2">
                  <span className="mt-0.5 h-1.5 w-1.5 shrink-0 rounded-full bg-facil-orange" />
                  RG, CPF e comprovante de residência
                </li>
                <li className="flex items-start gap-2">
                  <span className="mt-0.5 h-1.5 w-1.5 shrink-0 rounded-full bg-facil-orange" />
                  Comprovante de renda (holerite, extrato ou declaração)
                </li>
                <li className="flex items-start gap-2">
                  <span className="mt-0.5 h-1.5 w-1.5 shrink-0 rounded-full bg-facil-orange" />
                  CNH (desejável, não obrigatório para análise inicial)
                </li>
              </ul>
              <p className="mt-3 text-xs text-facil-muted">
                Esses documentos só são necessários na hora de formalizar — não agora.
              </p>
            </div>
          </div>

          <aside className="h-fit">
            <div className="rounded-2xl border border-facil-border bg-facil-card p-6 shadow-lg shadow-zinc-900/5">
              <h2 className="text-xl font-bold text-foreground">Fale com a equipe</h2>
              <p className="mt-1.5 text-sm text-facil-muted">
                Escolha o que precisa e conta o que quiser. Um especialista entra em contato pelo
                WhatsApp.
              </p>
              <div className="mt-5">
                <FinancingSimulationForm
                  whatsappNumber={settings?.defaultWhatsappNumber ?? ""}
                  hideFinanceMode={false}
                />
              </div>
            </div>
            {wa && (
              <div className="mt-4 rounded-2xl border border-facil-border bg-facil-card p-5">
                <h3 className="text-sm font-semibold text-foreground">Prefere falar antes?</h3>
                <a
                  href={`https://wa.me/${wa}?text=${encodeURIComponent("Olá, tenho interesse em crédito veicular!")}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-3 flex w-full items-center justify-center gap-2 rounded-xl bg-green-600 py-3 font-bold text-white hover:bg-green-700"
                >
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
                    <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" />
                  </svg>
                  Falar com quem entende
                </a>
              </div>
            )}
            <Link
              href="/estoque"
              className="mt-3 flex w-full items-center justify-center rounded-xl border-2 border-facil-orange py-3 text-center font-bold text-facil-orange hover:bg-facil-orange hover:text-white transition"
            >
              Ver estoque disponível
            </Link>
          </aside>
        </div>
      </section>
    </main>
  );
}
