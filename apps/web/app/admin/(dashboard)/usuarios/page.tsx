import { guardAdminSection } from "@/features/auth/server/rbac";
import { listUsers } from "@/features/admin/server/users";
import { UsersClient } from "./UsersClient";

export default async function AdminUsuariosPage() {
  const currentUser = await guardAdminSection("usuarios");
  const users = await listUsers();

  const serializableUsers = users.map((u) => ({
    ...u,
    lastLoginAt: u.lastLoginAt?.toISOString() ?? null,
  }));

  return (
    <div className="admin-page admin-section">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Usuários</h1>
        <p className="mt-0.5 text-sm text-facil-muted">
          Gerencie vendedores e acessos ao painel
        </p>
      </div>

      <UsersClient users={serializableUsers} currentUserId={currentUser.id} />
    </div>
  );
}
