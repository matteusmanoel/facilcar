import { listAdminPages } from "@/features/content/server/queries";
import { guardAdminSection } from "@/features/auth/server/rbac";
import { PaginasClient } from "./PaginasClient";

export default async function AdminPaginasPage() {
  await guardAdminSection("paginas");
  const pages = await listAdminPages();

  return (
    <div className="admin-page admin-section">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Páginas</h1>
        <p className="mt-0.5 text-sm text-facil-muted">
          Gerencie páginas institucionais do site
        </p>
      </div>

      <PaginasClient pages={pages} />
    </div>
  );
}
