import Image from "next/image";
import Link from "next/link";
import {
  FacebookIcon,
  InstagramIcon,
  WhatsAppIcon,
  YoutubeIcon,
} from "@/components/shared/brand-icons";

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
  const address = [addressLine, [city, state].filter(Boolean).join(" / ")].filter(Boolean).join(" · ");
  const hasSocial = Boolean(wa || instagramUrl || facebookUrl || youtubeUrl);

  return (
    <footer className="relative overflow-hidden bg-facil-black text-white">
      <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-facil-orange" />

      <div className="relative mx-auto max-w-6xl px-4 pb-[calc(6.25rem+var(--cookie-banner-offset,0px))] pt-10 sm:pt-12 lg:pb-10">
        <div className="grid items-end gap-8 lg:grid-cols-[minmax(0,1fr)_auto_minmax(16rem,22rem)] lg:gap-10">
          <div>
            <div className="flex items-center gap-3">
              <Image
                src="/facilcar-logo.jpg"
                alt={siteName}
                width={40}
                height={40}
                className="rounded-md border border-facil-orange/50 object-cover"
              />
              <p className="font-bold text-white">{siteName}</p>
            </div>
            <p className="mt-3 max-w-md text-sm leading-relaxed text-zinc-400">
              {footerText ?? "Seminovos multimarcas com financiamento e avaliação do seu usado."}
            </p>
            {address ? <p className="mt-3 text-sm text-zinc-400">{address}</p> : null}
            <div className="mt-4 flex flex-wrap gap-x-4 gap-y-1 text-sm text-zinc-300">
              {phoneNumber ? <span>{phoneNumber}</span> : null}
              {defaultEmail ? (
                <a href={`mailto:${defaultEmail}`} className="hover:text-facil-orange">
                  {defaultEmail}
                </a>
              ) : null}
            </div>
          </div>

          <div className="flex flex-col gap-8 sm:flex-row sm:items-start sm:gap-12">
            <nav aria-label="Rodapé">
              <p className="text-xs font-semibold uppercase tracking-widest text-facil-orange">Atalhos</p>
              <ul className="mt-3 space-y-2 text-sm">
                <li>
                  <Link href="/estoque" className="text-zinc-300 hover:text-white">
                    Estoque
                  </Link>
                </li>
                <li>
                  <Link href="/financiamento" className="text-zinc-300 hover:text-white">
                    Financiamento
                  </Link>
                </li>
                <li>
                  <Link href="/vender-seu-veiculo" className="text-zinc-300 hover:text-white">
                    Vender
                  </Link>
                </li>
                <li>
                  {wa ? (
                    <a href={whatsappUrl} className="text-zinc-300 hover:text-white">
                      WhatsApp
                    </a>
                  ) : (
                    <Link href="/quem-somos" className="text-zinc-300 hover:text-white">
                      Quem somos
                    </Link>
                  )}
                </li>
              </ul>
            </nav>

            {hasSocial ? (
              <div>
                <p className="text-xs font-semibold uppercase tracking-widest text-facil-orange">Redes</p>
                <div className="mt-3 flex gap-2">
                  {wa ? (
                    <a
                      href={whatsappUrl}
                      className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-white/15 text-white transition hover:border-facil-orange hover:text-facil-orange"
                      aria-label="WhatsApp"
                    >
                      <WhatsAppIcon className="h-5 w-5" />
                    </a>
                  ) : null}
                  {instagramUrl ? (
                    <a
                      href={instagramUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-white/15 text-white transition hover:border-facil-orange hover:text-facil-orange"
                      aria-label="Instagram"
                    >
                      <InstagramIcon className="h-5 w-5" />
                    </a>
                  ) : null}
                  {facebookUrl ? (
                    <a
                      href={facebookUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-white/15 text-white transition hover:border-facil-orange hover:text-facil-orange"
                      aria-label="Facebook"
                    >
                      <FacebookIcon className="h-5 w-5" />
                    </a>
                  ) : null}
                  {youtubeUrl ? (
                    <a
                      href={youtubeUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-white/15 text-white transition hover:border-facil-orange hover:text-facil-orange"
                      aria-label="YouTube"
                    >
                      <YoutubeIcon className="h-5 w-5" />
                    </a>
                  ) : null}
                </div>
              </div>
            ) : null}
          </div>

          <div className="relative hidden h-40 lg:block lg:h-52">
            <Image
              src="/porsche-laranja.png"
              alt=""
              fill
              sizes="22rem"
              className="pointer-events-none select-none object-contain object-right-bottom drop-shadow-[0_18px_28px_rgba(255,102,0,0.18)]"
            />
          </div>
        </div>

        <div className="mt-8 flex flex-col gap-3 border-t border-white/10 pt-5 text-xs text-zinc-500 sm:flex-row sm:items-center sm:justify-between">
          <p>
            © {new Date().getFullYear()} {siteName}
          </p>
          <div className="flex flex-wrap gap-x-4 gap-y-1 pr-24 sm:pr-0">
            <Link href="/politica-de-privacidade" className="hover:text-zinc-300">
              Privacidade
            </Link>
            <Link href="/politica-de-cookies" className="hover:text-zinc-300">
              Cookies
            </Link>
            <Link href="/termos-de-uso" className="hover:text-zinc-300">
              Termos
            </Link>
          </div>
        </div>
      </div>
    </footer>
  );
}
