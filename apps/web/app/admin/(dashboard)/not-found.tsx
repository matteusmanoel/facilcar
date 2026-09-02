import Link from "next/link";

export default function AdminNotFound() {
  return (
    <main className="admin-page admin-section">
      <h1 className="admin-page-title">Página não encontrada</h1>
      <p className="admin-page-subtitle">
        Esse endereço não existe no painel ou o registro foi removido.
      </p>
      <Link
        href="/admin"
        className="mt-4 inline-flex text-sm font-medium text-facil-orange hover:underline"
      >
        Voltar ao dashboard
      </Link>
    </main>
  );
}
