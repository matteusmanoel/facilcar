import Link from "next/link";
import { FinancingForm } from "@/features/lead/ui/FinancingForm";
import { getSiteSettings } from "@/features/settings/server/queries";

export const metadata = {
  title: "Financiamento",
  description:
    "Financiamento de veículos com as principais financeiras. Análise sem compromisso na FácilCar.",
};

export default async function FinanciamentoPage() {
  const settings = await getSiteSettings();
  const wa = settings?.defaultWhatsappNumber?.replace(/\D/g, "") ?? "";

  return (
    <main className="min-h-screen">
      <section className="bg-facil-black px-4 py-16 text-white">
        <div className="mx-auto max-w-6xl">
          <p className="text-sm font-semibold uppercase tracking-widest text-facil-orange">
            Financiamento
          </p>
          <h1 className="mt-4 text-4xl font-extrabold md:text-5xl">
            Realize seu sonho com parcelas que cabem no bolso
          </h1>
          <p className="mt-6 max-w-2xl text-lg text-zinc-300">
            Trabalhamos com várias financeiras para encontrar a melhor condição para o seu perfil —
            com transparência total sobre prazo, entrada e documentação.
          </p>
        </div>
      </section>

      <section className="px-4 py-14">
        <div className="mx-auto grid max-w-6xl gap-12 lg:grid-cols-3">
          <div className="lg:col-span-2">
            <h2 className="text-2xl font-bold text-zinc-900">Como funciona</h2>
            <div className="mt-8 grid gap-6 sm:grid-cols-3">
              {[
                {
                  step: "1",
                  t: "Simulação",
                  d: "Informe o veículo desejado e seus dados básicos. Nossa equipe inicia a análise.",
                },
                {
                  step: "2",
                  t: "Aprovação",
                  d: "Apresentamos as melhores propostas das financeiras parceiras, sem letras miúdas.",
                },
                {
                  step: "3",
                  t: "Fechamento",
                  d: "Assinatura do contrato e retirada do veículo com todo o suporte documental.",
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
            <div className="mt-10">
              <h2 className="text-2xl font-bold text-zinc-900">Solicitar análise</h2>
              <p className="mt-2 text-facil-muted">
                Preencha o formulário. Entraremos em contato com a proposta ou para pedir documentos
                complementares.
              </p>
              <div className="mt-6">
                <FinancingForm />
              </div>
            </div>
          </div>
          <aside className="h-fit rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm lg:sticky lg:top-24">
            <h3 className="font-bold text-zinc-900">Fale com um especialista</h3>
            <p className="mt-2 text-sm text-facil-muted">
              Dúvidas sobre entrada, prazo ou documentação? Chame no WhatsApp.
            </p>
            {wa && (
              <a
                href={`https://wa.me/${wa}`}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-4 block w-full rounded-xl bg-green-600 py-3 text-center font-bold text-white hover:bg-green-700"
              >
                WhatsApp
              </a>
            )}
            <Link
              href="/estoque"
              className="mt-3 block w-full rounded-xl border-2 border-facil-orange py-3 text-center font-bold text-facil-orange hover:bg-facil-orange hover:text-white"
            >
              Ver estoque
            </Link>
            {settings?.phoneNumber && (
              <p className="mt-6 text-sm text-facil-muted">
                Telefone: <span className="font-semibold text-zinc-800">{settings.phoneNumber}</span>
              </p>
            )}
          </aside>
        </div>
      </section>
    </main>
  );
}
