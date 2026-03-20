import Link from "next/link";
import { ContactForm } from "@/features/lead/ui/ContactForm";
import { getSiteSettings } from "@/features/settings/server/queries";

export const metadata = {
  title: "Contato",
  description: "Entre em contato com a FácilCar Multimarcas — WhatsApp, telefone ou formulário.",
};

export default async function ContatoPage() {
  const settings = await getSiteSettings();
  const wa = settings?.defaultWhatsappNumber?.replace(/\D/g, "") ?? "";
  const address = [settings?.addressLine, [settings?.city, settings?.state].filter(Boolean).join(" / ")]
    .filter(Boolean)
    .join(" · ");

  return (
    <main className="min-h-screen py-12 px-4">
      <div className="mx-auto max-w-6xl">
        <h1 className="text-3xl font-extrabold text-zinc-900">Contato</h1>
        <p className="mt-2 text-facil-muted">
          Estamos prontos para atender você por WhatsApp, e-mail ou formulário.
        </p>

        <div className="mt-10 grid gap-10 lg:grid-cols-2">
          <div>
            <div className="rounded-2xl border border-zinc-200 bg-zinc-50 p-8">
              <h2 className="font-bold text-zinc-900">FácilCar Multimarcas</h2>
              {address && (
                <p className="mt-4 text-sm leading-relaxed text-facil-muted">{address}</p>
              )}
              {settings?.zipCode && (
                <p className="mt-1 text-sm text-facil-muted">CEP {settings.zipCode}</p>
              )}
              <ul className="mt-6 space-y-3 text-sm">
                {settings?.phoneNumber && (
                  <li>
                    <span className="text-facil-muted">Telefone: </span>
                    <span className="font-semibold">{settings.phoneNumber}</span>
                  </li>
                )}
                {settings?.defaultEmail && (
                  <li>
                    <span className="text-facil-muted">E-mail: </span>
                    <a
                      href={`mailto:${settings.defaultEmail}`}
                      className="font-semibold text-facil-orange hover:underline"
                    >
                      {settings.defaultEmail}
                    </a>
                  </li>
                )}
                {wa && (
                  <li>
                    <a
                      href={`https://wa.me/${wa}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex rounded-lg bg-green-600 px-4 py-2 font-bold text-white hover:bg-green-700"
                    >
                      WhatsApp
                    </a>
                  </li>
                )}
              </ul>
              {settings?.instagramUrl && (
                <p className="mt-6">
                  <a
                    href={settings.instagramUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm font-semibold text-facil-orange hover:underline"
                  >
                    Instagram
                  </a>
                </p>
              )}
            </div>
            <div className="mt-6 aspect-video overflow-hidden rounded-2xl border border-zinc-200 bg-zinc-200">
              <div className="flex h-full items-center justify-center p-6 text-center text-sm text-zinc-500">
                {address ? (
                  <p>
                    Mapa: configure o embed do Google Maps com o endereço da loja para a versão final.
                    <br />
                    <span className="mt-2 block text-xs">{address}</span>
                  </p>
                ) : (
                  <p>Configure endereço em Admin → Configurações para exibir localização.</p>
                )}
              </div>
            </div>
          </div>
          <div className="rounded-2xl border border-zinc-200 bg-white p-8 shadow-sm">
            <h2 className="font-bold text-zinc-900">Envie uma mensagem</h2>
            <p className="mt-2 text-sm text-facil-muted">
              Retornamos o mais rápido possível em horário comercial.
            </p>
            <div className="mt-6">
              <ContactForm />
            </div>
            <p className="mt-6 text-center text-sm text-facil-muted">
              Prefere falar agora?{" "}
              {wa ? (
                <a href={`https://wa.me/${wa}`} className="font-semibold text-facil-orange">
                  Abrir WhatsApp
                </a>
              ) : (
                <Link href="/estoque" className="font-semibold text-facil-orange">
                  Ver estoque
                </Link>
              )}
            </p>
          </div>
        </div>
      </div>
    </main>
  );
}
