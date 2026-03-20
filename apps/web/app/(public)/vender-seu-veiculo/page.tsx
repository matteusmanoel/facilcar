import Link from "next/link";
import { SellVehicleForm } from "@/features/lead/ui/SellVehicleForm";
import { getSiteSettings } from "@/features/settings/server/queries";

export const metadata = {
  title: "Vender ou consignar seu veículo",
  description:
    "Venda com segurança ou consigne seu carro na FácilCar. Avaliação sem compromisso e divulgação profissional.",
};

export default async function VenderVeiculoPage() {
  const settings = await getSiteSettings();
  const wa = settings?.defaultWhatsappNumber?.replace(/\D/g, "") ?? "";

  return (
    <main className="min-h-screen">
      <section className="bg-gradient-to-br from-facil-black to-zinc-900 px-4 py-16 text-white">
        <div className="mx-auto max-w-6xl">
          <h1 className="text-4xl font-extrabold md:text-5xl">
            Venda seu carro com mais segurança e visibilidade
          </h1>
          <p className="mt-6 max-w-2xl text-lg text-zinc-300">
            Anunciar sozinho na internet pode gerar risco de golpe e perda de tempo. Na FácilCar você
            pode <strong className="text-white">consignar</strong> ou vender com nossa equipe —
            cuidamos da negociação, divulgação e documentação.
          </p>
          {wa && (
            <a
              href={`https://wa.me/${wa}?text=${encodeURIComponent("Quero avaliar meu carro para venda/consignação.")}`}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-8 inline-flex rounded-xl bg-facil-orange px-8 py-3.5 font-bold hover:bg-facil-orange-hover"
            >
              Agendar avaliação no WhatsApp
            </a>
          )}
        </div>
      </section>

      <section className="px-4 py-14">
        <div className="mx-auto max-w-6xl">
          <h2 className="text-2xl font-bold text-zinc-900">Por que consignar conosco?</h2>
          <div className="mt-10 grid gap-8 md:grid-cols-2 lg:grid-cols-3">
            {[
              {
                t: "Melhor preço possível",
                d: "Evitamos a corrida por venda rápida a qualquer custo. Seu carro é precificado de forma justa com o mercado.",
              },
              {
                t: "Mais alcance",
                d: "Divulgamos no site, redes sociais e canais parceiros — seu veículo ganha audiência qualificada.",
              },
              {
                t: "Segurança",
                d: "Sem encontros arriscados com desconhecidos. A negociação passa pela loja, com contrato e transparência.",
              },
              {
                t: "Documentação",
                d: "Apoio na transferência, comunicação de venda e burocracia — você foca no que importa.",
              },
              {
                t: "Financiamento para o comprador",
                d: "Compradores podem financiar — isso amplia muito as chances de venda no valor desejado.",
              },
              {
                t: "Troca integrada",
                d: "Cliente troca com a gente? Absorvemos o usado e você recebe o combinado de forma organizada.",
              },
            ].map((x) => (
              <div key={x.t} className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm">
                <div className="h-1 w-10 rounded-full bg-facil-orange" />
                <h3 className="mt-4 font-bold text-zinc-900">{x.t}</h3>
                <p className="mt-2 text-sm text-facil-muted leading-relaxed">{x.d}</p>
              </div>
            ))}
          </div>

          <div className="mt-16 grid gap-12 lg:grid-cols-2">
            <div>
              <h2 className="text-2xl font-bold text-zinc-900">Solicite sua avaliação</h2>
              <p className="mt-2 text-facil-muted">
                Preencha os dados do veículo. Retornamos com próximos passos e convite para vistoria.
              </p>
              <div className="mt-8">
                <SellVehicleForm />
              </div>
            </div>
            <div className="rounded-2xl border border-zinc-200 bg-zinc-50 p-8">
              <h3 className="font-bold text-zinc-900">Como funciona na prática</h3>
              <ol className="mt-4 list-decimal space-y-3 pl-5 text-sm text-facil-muted">
                <li>Você envia os dados ou traz o carro para avaliação.</li>
                <li>Definimos valor de anúncio e condições de consignação.</li>
                <li>Assinatura do contrato e veículo na loja para venda.</li>
                <li>Quando vender, você recebe conforme acordado — com segurança jurídica.</li>
              </ol>
              <Link
                href="/estoque"
                className="mt-8 inline-block font-bold text-facil-orange hover:underline"
              >
                Ver como anunciamos nossos carros →
              </Link>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
