import Link from "next/link";
import { FinancingSimulationForm } from "@/features/lead/ui/FinancingSimulationForm";
import { getSiteSettings } from "@/features/settings/server/queries";

export const metadata = {
  title: "Simule seu Financiamento 100% Online",
  description:
    "Simule o financiamento do seu próximo carro em 2 minutos. Análise de crédito pelo WhatsApp com mais de 10 financeiras parceiras. Gratuito, sem compromisso.",
};

export default async function FinanciamentoPage() {
  const settings = await getSiteSettings();
  const wa = settings?.defaultWhatsappNumber?.replace(/\D/g, "") ?? "";

  return (
    <main className="min-h-screen">
      <section className="bg-facil-black px-4 py-16 text-white">
        <div className="mx-auto max-w-6xl">
          <p className="text-sm font-semibold uppercase tracking-widest text-facil-orange">
            Financiamento 100% Online
          </p>
          <h1 className="mt-4 text-4xl font-extrabold md:text-5xl">
            Simule seu Financiamento em 2 Minutos
          </h1>
          <p className="mt-6 max-w-2xl text-lg text-zinc-300">
            Preencha seus dados e receba a análise de crédito pelo WhatsApp. Trabalhamos com mais de
            10 financeiras para encontrar a melhor condição para o seu perfil.
          </p>
          <div className="mt-8 flex flex-wrap gap-4">
            <div className="flex items-center gap-2 rounded-full bg-white/10 px-4 py-2 text-sm">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden>
                <path d="M20 6 9 17l-5-5" />
              </svg>
              100% gratuito
            </div>
            <div className="flex items-center gap-2 rounded-full bg-white/10 px-4 py-2 text-sm">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden>
                <path d="M20 6 9 17l-5-5" />
              </svg>
              Resposta via WhatsApp
            </div>
            <div className="flex items-center gap-2 rounded-full bg-white/10 px-4 py-2 text-sm">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden>
                <path d="M20 6 9 17l-5-5" />
              </svg>
              Sem consulta ao SPC nesta etapa
            </div>
          </div>
        </div>
      </section>

      <section className="px-4 py-14">
        <div className="mx-auto grid max-w-6xl gap-12 lg:grid-cols-[1fr_min(100%,440px)]">
          <div>
            <h2 className="text-2xl font-bold text-zinc-900">Como funciona</h2>
            <div className="mt-8 grid gap-6 sm:grid-cols-3">
              {[
                {
                  step: "1",
                  t: "Simulação Online",
                  d: "Preencha nome, CPF, renda e a entrada desejada. Leva menos de 2 minutos.",
                },
                {
                  step: "2",
                  t: "Análise Rápida",
                  d: "Nossa equipe recebe seus dados pelo WhatsApp e inicia a análise com as financeiras parceiras.",
                },
                {
                  step: "3",
                  t: "Proposta e Fechamento",
                  d: "Você recebe as melhores condições e fecha o negócio sem burocracia.",
                },
              ].map((x) => (
                <div key={x.step} className="rounded-2xl border border-zinc-200 bg-zinc-50 p-6">
                  <span className="text-3xl font-black text-facil-orange">{x.step}</span>
                  <h3 className="mt-2 font-bold text-zinc-900">{x.t}</h3>
                  <p className="mt-2 text-sm text-facil-muted leading-relaxed">{x.d}</p>
                </div>
              ))}
            </div>
            <div className="mt-10 rounded-2xl border border-facil-orange/20 bg-orange-50/50 p-6">
              <h3 className="font-bold text-zinc-900">Refinanciamento</h3>
              <p className="mt-2 text-sm text-facil-muted leading-relaxed">
                Quer usar seu carro como garantia para obter crédito? Podemos orientar sobre
                refinanciamento com prazos e taxas competitivas, conforme análise da instituição.
              </p>
            </div>
            <div className="mt-10 rounded-2xl border border-zinc-200 bg-zinc-50 p-6">
              <h3 className="font-semibold text-zinc-900">Documentos necessários (na hora do fechamento)</h3>
              <ul className="mt-3 space-y-1.5 text-sm text-zinc-600">
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
            </div>
          </div>

          <aside className="h-fit">
            <div className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-lg shadow-zinc-900/5">
              <h2 className="text-xl font-bold text-zinc-900">Simule Agora</h2>
              <p className="mt-1.5 text-sm text-facil-muted">
                Preencha abaixo. Após o envio, abrimos o WhatsApp automaticamente.
              </p>
              <div className="mt-5">
                <FinancingSimulationForm
                  whatsappNumber={settings?.defaultWhatsappNumber ?? ""}
                />
              </div>
            </div>
            {wa && (
              <div className="mt-4 rounded-2xl border border-zinc-200 bg-white p-5">
                <h3 className="text-sm font-semibold text-zinc-900">Prefere falar antes?</h3>
                <a
                  href={`https://wa.me/${wa}?text=${encodeURIComponent("Olá, tenho interesse em simular um financiamento!")}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-3 flex w-full items-center justify-center gap-2 rounded-xl bg-green-600 py-3 font-bold text-white hover:bg-green-700"
                >
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
                    <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" />
                  </svg>
                  Falar no WhatsApp
                </a>
                {settings?.phoneNumber && (
                  <p className="mt-3 text-center text-sm text-zinc-500">
                    ou ligue: <span className="font-semibold text-zinc-700">{settings.phoneNumber}</span>
                  </p>
                )}
              </div>
            )}
            <Link
              href="/estoque"
              className="mt-3 flex w-full items-center justify-center rounded-xl border-2 border-facil-orange py-3 text-center font-bold text-facil-orange hover:bg-facil-orange hover:text-white transition"
            >
              Escolher um veículo primeiro
            </Link>
          </aside>
        </div>
      </section>
    </main>
  );
}
