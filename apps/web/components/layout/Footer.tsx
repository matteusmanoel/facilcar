import Link from "next/link";

type FooterProps = {
  siteName?: string;
  footerText?: string;
  whatsappNumber?: string;
};

export function Footer({
  siteName = "Revenda",
  footerText,
  whatsappNumber,
}: FooterProps) {
  const whatsappUrl = whatsappNumber
    ? `https://wa.me/${whatsappNumber.replace(/\D/g, "")}`
    : "#";

  return (
    <footer className="border-t bg-zinc-100 py-8">
      <div className="mx-auto max-w-6xl px-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <span className="font-semibold">{siteName}</span>
          <nav className="flex gap-4 text-sm">
            <Link href="/estoque" className="hover:underline">
              Estoque
            </Link>
            <Link href="/contato" className="hover:underline">
              Contato
            </Link>
            <Link href="/quem-somos" className="hover:underline">
              Quem somos
            </Link>
            <Link href="/politica-de-privacidade" className="hover:underline">
              Privacidade
            </Link>
            <Link href="/termos-de-uso" className="hover:underline">
              Termos
            </Link>
            {whatsappNumber && (
              <a
                href={whatsappUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="text-green-600 hover:underline"
              >
                WhatsApp
              </a>
            )}
          </nav>
        </div>
        {footerText && (
          <p className="mt-4 text-sm text-zinc-600">{footerText}</p>
        )}
      </div>
    </footer>
  );
}
