import Link from "next/link";
import { adminSignOutAction } from "./signOutAction";

export default function AdminDashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-zinc-100">
      <header className="border-b bg-white p-4">
        <nav className="flex flex-wrap items-center gap-4">
          <Link href="/admin" className="font-medium hover:underline">
            Dashboard
          </Link>
          <Link href="/admin/veiculos" className="hover:underline">
            Veículos
          </Link>
          <Link href="/admin/leads" className="hover:underline">
            Leads
          </Link>
          <Link href="/admin/paginas" className="hover:underline">
            Páginas
          </Link>
          <Link href="/admin/blog" className="hover:underline">
            Blog
          </Link>
          <Link href="/admin/configuracoes" className="hover:underline">
            Configurações
          </Link>
          <Link href="/" className="text-zinc-500 hover:underline">
            Site
          </Link>
          <form action={adminSignOutAction} className="ml-auto inline">
            <button
              type="submit"
              className="text-sm text-red-600 hover:underline"
            >
              Sair
            </button>
          </form>
        </nav>
      </header>
      {children}
    </div>
  );
}
