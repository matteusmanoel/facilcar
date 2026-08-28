import Image from "next/image";
import Link from "next/link";

type FooterProps = {
  siteName?: string;
  footerText?: string;
  whatsappNumber?: string;
  phoneNumber?: string | null;
  defaultEmail?: string | null;
  addressLine?: string | null;
  city?: string | null;
  state?: string | null;
  zipCode?: string | null;
  instagramUrl?: string | null;
  facebookUrl?: string | null;
  youtubeUrl?: string | null;
};

export function Footer({
  siteName = "FácilCar Multimarcas",
  footerText,
  whatsappNumber,
  phoneNumber,
  defaultEmail,
  addressLine,
  city,
  state,
  zipCode,
  instagramUrl,
  facebookUrl,
  youtubeUrl,
}: FooterProps) {
  const wa = whatsappNumber?.replace(/\D/g, "") ?? "";
  const whatsappUrl = wa ? `https://wa.me/${wa}` : "#";
  const addressParts = [addressLine, [city, state].filter(Boolean).join(" / "), zipCode].filter(
    Boolean
  );

  return (
    <footer className="border-t border-facil-border bg-zinc-50 text-zinc-600 dark:border-zinc-800 dark:bg-facil-black dark:text-zinc-300">
      <div className="mx-auto max-w-6xl px-4 py-12">
        <div className="grid gap-10 md:grid-cols-2 lg:grid-cols-4">
          <div>
            <div className="flex items-center gap-2">
              <Image
                src="/facilcar-logo.jpg"
                alt={siteName}
                width={40}
                height={40}
                className="rounded-md border border-facil-orange/40 object-cover"
              />
              <p className="font-bold text-foreground dark:text-white">{siteName}</p>
            </div>
            <p className="mt-2 text-sm leading-relaxed text-facil-muted">
              {footerText ??
                "Seminovos multimarcas com curadoria, financiamento e avaliação do seu usado."}
            </p>
          </div>
          <div>
            <p className="text-sm font-semibold uppercase tracking-wide text-facil-orange">
              Navegação
            </p>
            <ul className="mt-3 space-y-2 text-sm">
              <li>
                <Link href="/estoque" className="hover:text-foreground dark:hover:text-white">
                  Estoque
                </Link>
              </li>
              <li>
                <Link href="/financiamento" className="hover:text-foreground dark:hover:text-white">
                  Financiamento
                </Link>
              </li>
              <li>
                <Link href="/vender-seu-veiculo" className="hover:text-foreground dark:hover:text-white">
                  Vender / Consignar
                </Link>
              </li>
              <li>
                <Link href="/quem-somos" className="hover:text-foreground dark:hover:text-white">
                  Quem somos
                </Link>
              </li>
              <li>
                <Link href="/blog" className="hover:text-foreground dark:hover:text-white">
                  Blog
                </Link>
              </li>
            </ul>
          </div>
          <div>
            <p className="text-sm font-semibold uppercase tracking-wide text-facil-orange">
              Contato
            </p>
            <ul className="mt-3 space-y-2 text-sm">
              {phoneNumber && <li>{phoneNumber}</li>}
              {defaultEmail && (
                <li>
                  <a href={`mailto:${defaultEmail}`} className="hover:text-foreground dark:hover:text-white">
                    {defaultEmail}
                  </a>
                </li>
              )}
              {wa && (
                <li>
                  <a href={whatsappUrl} className="text-green-400 hover:text-green-300">
                    WhatsApp
                  </a>
                </li>
              )}
            </ul>
            {(instagramUrl || facebookUrl || youtubeUrl) && (
              <div className="mt-4 flex flex-wrap gap-3 text-sm">
                {instagramUrl && (
                  <a href={instagramUrl} target="_blank" rel="noopener noreferrer" className="hover:text-foreground dark:hover:text-white">
                    Instagram
                  </a>
                )}
                {facebookUrl && (
                  <a href={facebookUrl} target="_blank" rel="noopener noreferrer" className="hover:text-foreground dark:hover:text-white">
                    Facebook
                  </a>
                )}
                {youtubeUrl && (
                  <a href={youtubeUrl} target="_blank" rel="noopener noreferrer" className="hover:text-foreground dark:hover:text-white">
                    YouTube
                  </a>
                )}
              </div>
            )}
          </div>
          <div>
            <p className="text-sm font-semibold uppercase tracking-wide text-facil-orange">
              Endereço
            </p>
            {addressParts.length > 0 ? (
              <p className="mt-3 text-sm leading-relaxed text-facil-muted">
                {addressParts.join("\n")}
              </p>
            ) : (
              <p className="mt-3 text-sm text-facil-muted">
                Configure endereço em Admin → Configurações.
              </p>
            )}
            <ul className="mt-4 space-y-1 text-xs text-zinc-500">
              <li>
                <Link href="/politica-de-privacidade" className="hover:text-zinc-300">
                  Política de privacidade
                </Link>
              </li>
              <li>
                <Link href="/termos-de-uso" className="hover:text-zinc-300">
                  Termos de uso
                </Link>
              </li>
            </ul>
          </div>
        </div>
        <div className="mt-10 border-t border-zinc-800 pt-6 text-center text-xs text-zinc-500">
          © {new Date().getFullYear()} {siteName}. Todos os direitos reservados.
        </div>
      </div>
    </footer>
  );
}
