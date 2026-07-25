"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { Archive } from "lucide-react";
import { toast } from "sonner";
import { archiveVehicleAction } from "@/features/vehicle/server/mutations";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

type Props = {
  vehicleId: string;
  vehicleTitle: string;
  currentStatus: string;
  variant?: "list" | "edit" | "menu";
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
};

export function ArchiveVehicleButton({
  vehicleId,
  vehicleTitle,
  currentStatus,
  variant = "list",
  open: controlledOpen,
  onOpenChange: controlledOnOpenChange,
}: Props) {
  const router = useRouter();
  const [internalOpen, setInternalOpen] = useState(false);
  const open = controlledOpen ?? internalOpen;
  const setOpen = controlledOnOpenChange ?? setInternalOpen;
  const [isPending, startTransition] = useTransition();

  if (currentStatus === "ARCHIVED") {
    return null;
  }

  function confirmArchive() {
    startTransition(async () => {
      try {
        await archiveVehicleAction(vehicleId);
        router.refresh();
        toast.success("Veículo arquivado.");
        setOpen(false);
        if (variant === "edit") {
          router.push("/admin/veiculos");
        }
      } catch {
        toast.error("Erro ao arquivar veículo. Tente novamente.");
      }
    });
  }

  return (
    <>
      {variant === "list" ? (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="h-7 gap-1 px-2 text-xs text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-200"
          onClick={() => setOpen(true)}
        >
          <Archive className="h-3.5 w-3.5" />
          Arquivar
        </Button>
      ) : variant === "edit" ? (
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="border-red-200 text-red-700 hover:bg-red-50 dark:border-red-900/50 dark:text-red-400 dark:hover:bg-red-950/30"
          onClick={() => setOpen(true)}
        >
          <Archive className="h-4 w-4" />
          Arquivar veículo
        </Button>
      ) : null}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="dark:border-zinc-700 dark:bg-zinc-900">
          <DialogHeader>
            <DialogTitle className="dark:text-zinc-100">Arquivar veículo?</DialogTitle>
            <DialogDescription className="dark:text-zinc-400">
              {vehicleTitle} será removido do estoque ativo e ficará com status &quot;Arquivado&quot;.
              Você pode reativá-lo alterando o status depois.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              Cancelar
            </Button>
            <Button type="button" variant="destructive" disabled={isPending} onClick={confirmArchive}>
              {isPending ? "Arquivando…" : "Arquivar"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
