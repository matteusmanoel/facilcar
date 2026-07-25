"use client";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

type Props = {
  open: boolean;
  existingName: string;
  submittedName: string;
  onKeepExisting: () => void;
  onUseNew: () => void;
  onCancel: () => void;
};

export function CustomerNameConflictDialog({
  open,
  existingName,
  submittedName,
  onKeepExisting,
  onUseNew,
  onCancel,
}: Props) {
  return (
    <Dialog open={open} onOpenChange={(next) => !next && onCancel()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Nome diferente no cadastro</DialogTitle>
          <DialogDescription>
            Já existe um cliente com este telefone, mas com outro nome. Como deseja prosseguir?
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3 rounded-lg border border-facil-border bg-facil-surface p-4 text-sm">
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-facil-muted">No sistema</p>
            <p className="mt-0.5 font-medium text-foreground">{existingName}</p>
          </div>
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-facil-muted">Informado agora</p>
            <p className="mt-0.5 font-medium text-foreground">{submittedName}</p>
          </div>
        </div>

        <DialogFooter className="flex-col gap-2 sm:flex-col">
          <Button type="button" variant="primary" className="w-full" onClick={onKeepExisting}>
            Manter nome do cadastro
          </Button>
          <Button type="button" variant="outline" className="w-full" onClick={onUseNew}>
            Atualizar para o novo nome
          </Button>
          <Button type="button" variant="ghost" className="w-full" onClick={onCancel}>
            Cancelar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
