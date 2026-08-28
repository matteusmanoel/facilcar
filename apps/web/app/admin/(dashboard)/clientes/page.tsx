import { guardAdminSection } from "@/features/auth/server/rbac";
import { CUSTOMER_WRITE_ROLES } from "@/features/auth/rbac-config";
import type { UserRole } from "@prisma/client";
import { listCustomers } from "@/features/admin/server/customers";
import { CustomersClient } from "./CustomersClient";

type SearchParams = { [key: string]: string | string[] | undefined };

export default async function AdminClientesPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const user = await guardAdminSection("clientes");

  const params = await searchParams;
  const page = Math.max(1, parseInt(String(params.page ?? "1"), 10) || 1);
  const pageSize = 20;
  const q = typeof params.q === "string" ? params.q : undefined;

  const { customers, totalCount } = await listCustomers({ page, pageSize, search: q });

  const serializable = customers.map((c) => ({
    ...c,
    createdAt: c.createdAt.toISOString(),
  }));

  return (
    <div className="admin-page admin-section">
      <div>
        <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-50">Clientes</h1>
        <p className="mt-0.5 text-sm text-zinc-500 dark:text-zinc-400">
          Contatos consolidados por telefone
        </p>
      </div>

      <CustomersClient
        customers={serializable}
        totalCount={totalCount}
        page={page}
        pageSize={pageSize}
        initialSearch={q ?? ""}
        canWrite={CUSTOMER_WRITE_ROLES.includes(user.role as UserRole)}
      />
    </div>
  );
}
