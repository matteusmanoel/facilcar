import Image from "next/image";
import Link from "next/link";

type HeaderProps = {
  siteName?: string;
  whatsappNumber?: string;
};

const nav = [
  { href: "/estoque", label: "Estoque" },
  { href: "/financiamento", label: "Financiamento" },
  { href: "/vender-seu-veiculo", label: "Vender / Consignar" },
  { href: "/quem-somos", label: "Quem somos" },
  { href: "/blog", label: "Blog" },
  { href: "/contato", label: "Contato" },
];

export function Header({ siteName = "FácilCar", whatsappNumber }: HeaderProps) {
  const wa = whatsappNumber?.replace(/\D/g, "") ?? "";
  const whatsappUrl = wa ? `https://wa.me/${wa}` : "#";

  return (
    <header className="sticky top-0 z-50 border-b border-zinc-800 bg-facil-black shadow-lg">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-4">
        <Link href="/" className="flex shrink-0 items-center gap-2">
          <Image
            src="/facilcar-logo.jpg"
            alt={siteName}
            width={44}
            height={44}
            className="rounded-md border border-facil-orange/40 object-cover"
            priority
          />
          <span className="hidden font-bold tracking-tight text-white sm:block sm:text-lg">
            {siteName}
          </span>
        </Link>
        <nav className="hidden items-center gap-1 text-sm font-medium text-zinc-300 lg:flex">
          {nav.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="rounded-md px-2 py-1.5 transition hover:bg-white/10 hover:text-white"
            >
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="flex items-center gap-2">
          <Link
            href="/estoque"
            className="hidden rounded-lg bg-facil-orange px-3 py-2 text-sm font-semibold text-white shadow hover:bg-facil-orange-hover sm:inline-flex"
          >
            Ver estoque
          </Link>
          {wa && (
            <a
              href={whatsappUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 rounded-lg border border-green-500/50 bg-green-600 px-3 py-2 text-sm font-semibold text-white hover:bg-green-700"
            >
              WhatsApp
            </a>
          )}
        </div>
      </div>
      <nav className="flex gap-1 overflow-x-auto border-t border-zinc-800 px-4 py-2 lg:hidden">
        {nav.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className="shrink-0 rounded-md bg-zinc-800 px-2.5 py-1 text-xs font-medium text-zinc-200"
          >
            {item.label}
          </Link>
        ))}
      </nav>
    </header>
  );
}
