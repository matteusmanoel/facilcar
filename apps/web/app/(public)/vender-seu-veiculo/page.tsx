import Link from "next/link";
import { SellVehicleForm } from "@/features/lead/ui/SellVehicleForm";
import { getSiteSettings } from "@/features/settings/server/queries";

export const metadata = {
  title: "Vender ou consignar seu veículo",
  description:
    "Venda com segurança ou consigne seu carro na FácilCar. Avaliação sem compromisso — consignação ou compra direta pela loja.",
};

export default async function VenderVeiculoPage() {
  const settings = await getSiteSettings();
  const wa = settings?.defaultWhatsappNumber?.replace(/\D/g, "") ?? "";

  return (
    <main className="min-h-screen">
      <section className="bg-gradient-to-br from-facil-black to-zinc-900 px-4 py-16 text-white">
        <div className="mx-auto max-w-6xl">
          <h1 className="text-4xl font-extrabold md:text-5xl">
            Venda ou consigne seu carro com a FácilCar
          </h1>
          <p className="mt-6 max-w-2xl text-lg text-zinc-300">
            Duas formas de negociar: <strong className="text-white">consignação</strong> (a loja
            anuncia e cuida da venda) ou <strong className="text-white">compra direta</strong> pela
            loja. Preencha o formulário — um especialista entra em contato com a avaliação.
          </p>
          {wa && (
            <a
              href={`https://wa.me/${wa}?text=${encodeURIComponent("Quero avaliar meu carro para venda/consignação.")}`}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-8 inline-flex rounded-xl bg-facil-orange px-8 py-3.5 font-bold hover:bg-facil-orange-hover"
            >
              Falar no WhatsApp
            </a>
          )}
        </div>
      </section>

      <section className="px-4 py-14">
        <div className="mx-auto max-w-6xl">
          <h2 className="text-2xl font-bold text-foreground">Por que vender conosco?</h2>
          <div className="mt-10 grid gap-8 md:grid-cols-2 lg:grid-cols-3">
            {[
              {
                t: "Avaliação com especialista",
                d: "Você envia os dados e fotos. Um da equipe retorna com a avaliação — sem compromisso.",
              },
              {
                t: "Consignação",
                d: "Seu carro é anunciado pela loja, com alcance profissional, contrato e segurança na negociação.",
              },
              {
                t: "Compra direta",
                d: "Prefere vender agora? A FácilCar pode comprar o veículo após a avaliação, sem você anunciar sozinho.",
              },
              {
                t: "Segurança",
                d: "Sem encontros arriscados com desconhecidos. A conversa passa pela loja, com transparência.",
              },
              {
                t: "Documentação",
                d: "Apoio na transferência, comunicação de venda e burocracia.",
              },
              {
                t: "Mais alcance",
                d: "Na consignação, divulgamos no site, redes e canais parceiros — audiência qualificada.",
              },
            ].map((x) => (
              <div key={x.t} className="rounded-2xl border border-facil-border bg-facil-card p-6 shadow-sm">
                <div className="h-1 w-10 rounded-full bg-facil-orange" />
                <h3 className="mt-4 font-bold text-foreground">{x.t}</h3>
                <p className="mt-2 text-sm text-facil-muted leading-relaxed">{x.d}</p>
              </div>
            ))}
          </div>

          <div className="mt-16 grid gap-12 lg:grid-cols-2">
            <div>
              <h2 className="text-2xl font-bold text-foreground">Solicite sua avaliação</h2>
              <p className="mt-2 text-facil-muted">
                Preencha e envie. Um dos especialistas entra em contato com a avaliação do seu
                veículo.
              </p>
              <div className="mt-8">
                <SellVehicleForm />
              </div>
            </div>
            <div className="rounded-2xl border border-facil-border bg-facil-surface p-8">
              <h3 className="font-bold text-foreground">Como funciona na prática</h3>
              <ol className="mt-4 list-decimal space-y-3 pl-5 text-sm text-facil-muted">
                <li>Você preenche o formulário com os dados do carro e, se quiser, envia fotos.</li>
                <li>Um especialista entra em contato com a avaliação.</li>
                <li>
                  Vocês escolhem o caminho: consignação (a loja anuncia) ou compra direta pela
                  FácilCar.
                </li>
                <li>Seguimos com contrato, divulgação ou pagamento — com segurança jurídica.</li>
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
