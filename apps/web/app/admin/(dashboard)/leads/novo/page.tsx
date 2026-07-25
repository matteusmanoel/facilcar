import Link from "next/link";
import { ChevronLeft } from "lucide-react";
import { prisma } from "@/lib/db";
import { guardAdminSection } from "@/features/auth/server/rbac";
import { ManualLeadForm } from "./ManualLeadForm";

export default async function AdminNovoLeadPage() {
  await guardAdminSection("leads");
  const vehicles = await prisma.vehicle.findMany({
    where: { status: { in: ["PUBLISHED", "RESERVED", "DRAFT"] } },
    orderBy: { updatedAt: "desc" },
    take: 200,
    select: { id: true, title: true },
  });

  return (
    <div className="admin-page flex flex-col gap-4">
      <div>
        <Link
          href="/admin/leads"
          className="inline-flex items-center gap-1 text-sm text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200"
        >
          <ChevronLeft className="h-3.5 w-3.5" />
          Voltar para leads
        </Link>
        <h1 className="mt-2 text-2xl font-bold text-zinc-900 dark:text-zinc-50">Novo lead</h1>
        <p className="mt-0.5 text-sm text-zinc-500 dark:text-zinc-400">
          Cadastre manualmente um contato recebido por telefone, WhatsApp ou balcão
        </p>
      </div>

      <ManualLeadForm vehicles={vehicles} />
    </div>
  );
}
