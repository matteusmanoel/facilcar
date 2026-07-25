"use client";

import { useState, useTransition } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { format, parseISO } from "date-fns";
import { ptBR } from "date-fns/locale";
import { Pencil, Plus, UserX } from "lucide-react";
import { toast } from "sonner";
import { updateUserAction } from "@/features/admin/server/users";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { CreateUserDialog } from "./CreateUserDialog";
import { UserEditDialog } from "./UserEditDialog";
import { formatUserRole } from "./user-role-labels";

type UserRow = {
  id: string;
  name: string;
  email: string;
  role: string;
  isActive: boolean;
  lastLoginAt: string | null;
};

type Props = {
  users: UserRow[];
  currentUserId: string;
};

function formatLastLogin(iso: string | null): string {
  if (!iso) return "Nunca";
  return format(parseISO(iso), "dd/MM/yyyy HH:mm", { locale: ptBR });
}

export function UsersClient({ users, currentUserId }: Props) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [isPending, startTransition] = useTransition();
  const [deactivateTarget, setDeactivateTarget] = useState<UserRow | null>(null);
  const [editTarget, setEditTarget] = useState<UserRow | null>(null);
  const [createOpen, setCreateOpen] = useState(searchParams.get("novo") === "1");

  function handleDeactivate(user: UserRow) {
    if (user.id === currentUserId) {
      toast.error("Você não pode desativar sua própria conta.");
      return;
    }
    setDeactivateTarget(user);
  }

  function confirmDeactivate() {
    if (!deactivateTarget) return;
    startTransition(async () => {
      const result = await updateUserAction(deactivateTarget.id, {
        name: deactivateTarget.name,
        role: deactivateTarget.role,
        isActive: false,
      });

      if (result.ok) {
        toast.success(`${deactivateTarget.name} foi desativado.`);
        setDeactivateTarget(null);
        router.refresh();
        return;
      }

      toast.error(typeof result.error === "string" ? result.error : "Erro ao desativar usuário.");
    });
  }

  return (
    <>
      <div className="flex justify-end">
        <Button variant="primary" size="sm" onClick={() => setCreateOpen(true)}>
          <Plus className="mr-1 h-4 w-4" />
          Novo usuário
        </Button>
      </div>

      <div className="hidden overflow-hidden rounded-xl border border-facil-border bg-facil-card shadow-sm md:block">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b border-facil-border bg-facil-surface">
              <tr>
                <th className="admin-table-header">Nome</th>
                <th className="admin-table-header">E-mail</th>
                <th className="admin-table-header">Perfil</th>
                <th className="admin-table-header">Status</th>
                <th className="admin-table-header">Último acesso</th>
                <th className="admin-table-header">Ações</th>
              </tr>
            </thead>
            <tbody>
              {users.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-12 text-center text-sm text-facil-muted">
                    Nenhum usuário encontrado.
                  </td>
                </tr>
              ) : (
                users.map((user) => (
                  <tr
                    key={user.id}
                    className="border-t border-facil-border hover:bg-facil-surface/60"
                  >
                    <td className="admin-table-cell font-medium text-foreground">
                      {user.name}
                      {user.id === currentUserId ? (
                        <span className="ml-2 text-xs font-normal text-facil-muted">(você)</span>
                      ) : null}
                    </td>
                    <td className="admin-table-cell text-facil-muted">{user.email}</td>
                    <td className="admin-table-cell">
                      <Badge variant="default">{formatUserRole(user.role)}</Badge>
                    </td>
                    <td className="admin-table-cell">
                      {user.isActive ? (
                        <Badge variant="green">Ativo</Badge>
                      ) : (
                        <Badge variant="outline">Inativo</Badge>
                      )}
                    </td>
                    <td className="admin-table-cell text-facil-muted">
                      {formatLastLogin(user.lastLoginAt)}
                    </td>
                    <td className="admin-table-cell">
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          onClick={() => setEditTarget(user)}
                          className="inline-flex items-center gap-1 font-medium text-facil-orange hover:underline"
                        >
                          <Pencil className="h-3.5 w-3.5" />
                          Editar
                        </button>
                        {user.isActive && user.id !== currentUserId ? (
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            className="h-7 gap-1 px-2 text-xs text-red-600 hover:bg-red-50 hover:text-red-700 dark:text-red-400 dark:hover:bg-red-950/30"
                            onClick={() => handleDeactivate(user)}
                          >
                            <UserX className="h-3.5 w-3.5" />
                            Desativar
                          </Button>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="grid gap-3 md:hidden">
        {users.length === 0 ? (
          <p className="py-8 text-center text-sm text-facil-muted">Nenhum usuário encontrado.</p>
        ) : (
          users.map((user) => (
            <div
              key={user.id}
              className="rounded-xl border border-facil-border bg-facil-card p-4 shadow-sm"
            >
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="font-medium text-foreground">
                    {user.name}
                    {user.id === currentUserId ? (
                      <span className="ml-1 text-xs font-normal text-facil-muted">(você)</span>
                    ) : null}
                  </p>
                  <p className="text-xs text-facil-muted">{user.email}</p>
                </div>
                {user.isActive ? (
                  <Badge variant="green">Ativo</Badge>
                ) : (
                  <Badge variant="outline">Inativo</Badge>
                )}
              </div>
              <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-facil-muted">
                <Badge variant="default">{formatUserRole(user.role)}</Badge>
                <span>·</span>
                <span>Último acesso: {formatLastLogin(user.lastLoginAt)}</span>
              </div>
              <div className="mt-3 flex gap-2">
                <Button variant="outline" size="sm" onClick={() => setEditTarget(user)}>
                  Editar
                </Button>
                {user.isActive && user.id !== currentUserId ? (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="text-red-600 dark:text-red-400"
                    onClick={() => handleDeactivate(user)}
                  >
                    Desativar
                  </Button>
                ) : null}
              </div>
            </div>
          ))
        )}
      </div>

      <Dialog open={!!deactivateTarget} onOpenChange={(open) => !open && setDeactivateTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Desativar usuário?</DialogTitle>
            <DialogDescription>
              {deactivateTarget
                ? `${deactivateTarget.name} não poderá mais acessar o painel. Você pode reativá-lo depois na edição.`
                : ""}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button type="button" variant="outline" onClick={() => setDeactivateTarget(null)}>
              Cancelar
            </Button>
            <Button
              type="button"
              variant="destructive"
              disabled={isPending}
              onClick={confirmDeactivate}
            >
              {isPending ? "Desativando…" : "Desativar"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <CreateUserDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onCreated={() => router.refresh()}
      />

      <UserEditDialog
        user={editTarget}
        currentUserId={currentUserId}
        onClose={() => setEditTarget(null)}
        onSaved={() => {
          setEditTarget(null);
          router.refresh();
        }}
      />
    </>
  );
}
