import { SellVehicleForm } from "@/features/lead/ui/SellVehicleForm";
import { getSiteSettings } from "@/features/settings/server/queries";

export const metadata = {
  title: "Vender ou consignar seu veículo | FácilCar",
  description:
    "Escolha entre consignação ou venda direta. Conta o que quiser — um especialista da FácilCar entra em contato pelo WhatsApp.",
};

export default async function VenderVeiculoPage() {
  const settings = await getSiteSettings();
  const wa = settings?.defaultWhatsappNumber?.replace(/\D/g, "") ?? "";

  return (
    <main className="min-h-screen">
      <section className="bg-gradient-to-br from-facil-black to-zinc-900 px-4 py-16 text-white">
        <div className="mx-auto max-w-6xl">
          <h1 className="text-4xl font-extrabold md:text-5xl">
            Venda ou consigne seu carro
          </h1>
          <p className="mt-6 max-w-2xl text-lg text-zinc-300">
            Dois caminhos, você escolhe. Conta o que quiser — um especialista entra em contato para
            combinar os detalhes.
          </p>
          {wa && (
            <a
              href={`https://wa.me/${wa}?text=${encodeURIComponent("Quero saber mais sobre vender meu carro.")}`}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-8 inline-flex rounded-xl bg-facil-orange px-8 py-3.5 font-bold hover:bg-facil-orange-hover"
            >
              Falar pelo WhatsApp
            </a>
          )}
        </div>
      </section>

      <section className="px-4 py-14">
        <div className="mx-auto max-w-6xl">
          <h2 className="text-2xl font-bold text-foreground">Entenda os modos</h2>
          <div className="mt-10 grid gap-8 md:grid-cols-2">
            <div className="rounded-2xl border border-facil-border bg-facil-card p-6 shadow-sm">
              <div className="h-1 w-10 rounded-full bg-facil-orange" />
              <h3 className="mt-4 font-bold text-foreground">Consignação</h3>
              <p className="mt-2 text-sm text-facil-muted leading-relaxed">
                Seu carro é anunciado pela loja, com alcance profissional e segurança na
                negociação. A FácilCar cuida da divulgação, da conversa com compradores e da
                papelada — você aprova a proposta antes de qualquer passo.
              </p>
            </div>
            <div className="rounded-2xl border border-facil-border bg-facil-card p-6 shadow-sm">
              <div className="h-1 w-10 rounded-full bg-facil-orange" />
              <h3 className="mt-4 font-bold text-foreground">Venda direta</h3>
              <p className="mt-2 text-sm text-facil-muted leading-relaxed">
                A FácilCar avalia o veículo e, se tiver interesse, apresenta uma proposta de
                compra. Rápido e sem você precisar anunciar sozinho. A compra depende da avaliação
                e do interesse da loja naquele momento.
              </p>
            </div>
            <div className="rounded-2xl border border-facil-border bg-facil-card p-6 shadow-sm">
              <div className="h-1 w-10 rounded-full bg-facil-orange" />
              <h3 className="mt-4 font-bold text-foreground">Segurança</h3>
              <p className="mt-2 text-sm text-facil-muted leading-relaxed">
                Sem encontros com desconhecidos. A conversa passa pela equipe da loja, com
                transparência em cada etapa.
              </p>
            </div>
            <div className="rounded-2xl border border-facil-border bg-facil-card p-6 shadow-sm">
              <div className="h-1 w-10 rounded-full bg-facil-orange" />
              <h3 className="mt-4 font-bold text-foreground">Documentação</h3>
              <p className="mt-2 text-sm text-facil-muted leading-relaxed">
                Apoio na transferência, comunicação de venda e burocracia — quando chegar a hora.
                Não precisa enviar nenhum documento agora.
              </p>
            </div>
          </div>

          <div className="mt-16 grid gap-12 lg:grid-cols-2">
            <div>
              <h2 className="text-2xl font-bold text-foreground">Quero negociar meu carro</h2>
              <p className="mt-3 text-facil-muted">
                Escolha o modo e conte o que quiser sobre o veículo. Sem fotos nem documentos
                agora — esses detalhes vêm depois.
              </p>
              <div className="mt-6">
                <SellVehicleForm />
              </div>
            </div>

            {wa && (
              <aside className="h-fit rounded-2xl border border-facil-border bg-facil-card p-6 shadow-sm lg:sticky lg:top-24">
                <h3 className="font-bold text-foreground">Prefere falar direto?</h3>
                <p className="mt-2 text-sm text-facil-muted">
                  Chame no WhatsApp e conta o que precisar — um especialista responde.
                </p>
                <a
                  href={`https://wa.me/${wa}?text=${encodeURIComponent("Quero saber mais sobre vender meu carro.")}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-4 flex items-center justify-center gap-2 rounded-xl bg-green-600 py-3 font-bold text-white hover:bg-green-700"
                >
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
                    <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" />
                  </svg>
                  Chamar no WhatsApp
                </a>
              </aside>
            )}
          </div>
        </div>
      </section>
    </main>
  );
}
