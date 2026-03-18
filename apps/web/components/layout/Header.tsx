import Link from "next/link";

type HeaderProps = {
  siteName?: string;
  whatsappNumber?: string;
};

export function Header({ siteName = "Revenda", whatsappNumber }: HeaderProps) {
  const whatsappUrl = whatsappNumber
    ? `https://wa.me/${whatsappNumber.replace(/\D/g, "")}`
    : "#";

  return (
    <header className="border-b bg-white shadow-sm">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4">
        <Link href="/" className="text-lg font-semibold">
          {siteName}
        </Link>
        <nav className="flex gap-6 text-sm">
          <Link href="/estoque" className="hover:underline">
            Estoque
          </Link>
          <Link href="/financiamento" className="hover:underline">
            Financiamento
          </Link>
          <Link href="/vender-seu-veiculo" className="hover:underline">
            Vender veículo
          </Link>
          <Link href="/contato" className="hover:underline">
            Contato
          </Link>
          <Link href="/quem-somos" className="hover:underline">
            Quem somos
          </Link>
          <Link href="/blog" className="hover:underline">
            Blog
          </Link>
          {whatsappNumber && (
            <a
              href={whatsappUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="font-medium text-green-600 hover:underline"
            >
              WhatsApp
            </a>
          )}
        </nav>
      </div>
    </header>
  );
}
