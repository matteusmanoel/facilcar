"use client";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { CreateUserForm } from "./CreateUserForm";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: () => void;
};

export function CreateUserDialog({ open, onOpenChange, onCreated }: Props) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] max-w-lg overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Novo usuário</DialogTitle>
          <DialogDescription>Cadastre um vendedor ou administrador do painel.</DialogDescription>
        </DialogHeader>
        <CreateUserForm
          variant="dialog"
          onCancel={() => onOpenChange(false)}
          onCreated={() => {
            onOpenChange(false);
            onCreated();
          }}
        />
      </DialogContent>
    </Dialog>
  );
}
