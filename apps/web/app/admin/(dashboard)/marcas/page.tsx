import { guardAdminSection } from "@/features/auth/server/rbac";
import { canWriteBrands } from "@/features/auth/rbac-config";
import { listBrands } from "@/features/admin/server/brands";
import { BrandsClient } from "./BrandsClient";

export default async function AdminMarcasPage() {
  const user = await guardAdminSection("marcas");
  const canManage = canWriteBrands(user.role);
  const brands = await listBrands();

  return (
    <div className="admin-page admin-section">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Marcas</h1>
        <p className="mt-0.5 text-sm text-facil-muted">
          Gerencie as marcas do catálogo de veículos
        </p>
      </div>

      <BrandsClient brands={brands} canManage={canManage} />
    </div>
  );
}
