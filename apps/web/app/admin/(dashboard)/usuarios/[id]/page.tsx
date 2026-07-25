import Link from "next/link";
import { notFound } from "next/navigation";
import { format } from "date-fns";
import { ptBR } from "date-fns/locale";
import { ChevronLeft } from "lucide-react";
import { getUserById } from "@/features/admin/server/users";
import { guardAdminSection } from "@/features/auth/server/rbac";
import { EditUserForm } from "../EditUserForm";
import { formatUserRole } from "../user-role-labels";

export default async function AdminUsuarioEditPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const currentUser = await guardAdminSection("usuarios");
  const { id } = await params;
  const targetUser = await getUserById(id);

  if (!targetUser) notFound();

  return (
    <div className="admin-page admin-section">
      <div>
        <Link
          href="/admin/usuarios"
          className="inline-flex items-center gap-1 text-sm text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200"
        >
          <ChevronLeft className="h-3.5 w-3.5" />
          Voltar para usuários
        </Link>
        <h1 className="mt-2 text-2xl font-bold text-zinc-900 dark:text-zinc-50">
          Editar: {targetUser.name}
        </h1>
        <p className="mt-0.5 text-sm text-zinc-500 dark:text-zinc-400">
          {formatUserRole(targetUser.role)} ·{" "}
          {targetUser.lastLoginAt
            ? `Último acesso em ${format(targetUser.lastLoginAt, "dd/MM/yyyy HH:mm", { locale: ptBR })}`
            : "Nunca acessou"}
        </p>
      </div>

      <EditUserForm
        userId={targetUser.id}
        email={targetUser.email}
        isSelf={targetUser.id === currentUser.id}
        defaultValues={{
          name: targetUser.name,
          role: targetUser.role,
          isActive: targetUser.isActive,
        }}
      />
    </div>
  );
}
