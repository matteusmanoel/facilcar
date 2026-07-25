"use client";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { EditUserForm } from "./EditUserForm";
import type { UpdateUserInput } from "@/schemas/user";

type UserRow = {
  id: string;
  name: string;
  email: string;
  role: string;
  isActive: boolean;
};

type Props = {
  user: UserRow | null;
  currentUserId: string;
  onClose: () => void;
  onSaved: () => void;
};

export function UserEditDialog({ user, currentUserId, onClose, onSaved }: Props) {
  return (
    <Dialog open={!!user} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[90vh] max-w-lg overflow-y-auto">
        {user ? (
          <>
            <DialogHeader>
              <DialogTitle>Editar usuário</DialogTitle>
              <DialogDescription>{user.email}</DialogDescription>
            </DialogHeader>
            <EditUserForm
              userId={user.id}
              email={user.email}
              isSelf={user.id === currentUserId}
              variant="dialog"
              onCancel={onClose}
              onSaved={onSaved}
              defaultValues={{
                name: user.name,
                role: user.role as UpdateUserInput["role"],
                isActive: user.isActive,
              }}
            />
          </>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
