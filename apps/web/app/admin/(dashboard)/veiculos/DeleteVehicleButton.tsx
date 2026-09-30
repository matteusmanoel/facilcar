"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { Trash2 } from "lucide-react";
import { toast } from "sonner";
import { deleteVehicleAction } from "@/features/vehicle/server/mutations";
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
  variant?: "list" | "edit";
};

export function DeleteVehicleButton({ vehicleId, vehicleTitle, variant = "list" }: Props) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [isPending, startTransition] = useTransition();

  function confirmDelete() {
    startTransition(async () => {
      try {
        await deleteVehicleAction(vehicleId);
        toast.success("Veículo excluído.");
        setOpen(false);
        router.push("/admin/veiculos");
      } catch {
        toast.error("Erro ao excluir veículo. Tente novamente.");
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
          className="h-7 gap-1 px-2 text-xs text-red-500 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300"
          onClick={() => setOpen(true)}
        >
          <Trash2 className="h-3.5 w-3.5" />
          Excluir
        </Button>
      ) : (
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="border-red-200 text-red-700 hover:bg-red-50 dark:border-red-900/50 dark:text-red-400 dark:hover:bg-red-950/30"
          onClick={() => setOpen(true)}
        >
          <Trash2 className="h-4 w-4" />
          Excluir permanentemente
        </Button>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="dark:border-zinc-700 dark:bg-zinc-900">
          <DialogHeader>
            <DialogTitle className="dark:text-zinc-100">Excluir veículo permanentemente?</DialogTitle>
            <DialogDescription className="dark:text-zinc-400">
              <strong>{vehicleTitle}</strong> será removido junto com as fotos, a ficha
              técnica e os vínculos de proprietários. Leads e conversas permanecem, sem o
              vínculo com esse anúncio. Essa ação não pode ser desfeita.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              Cancelar
            </Button>
            <Button type="button" variant="destructive" disabled={isPending} onClick={confirmDelete}>
              {isPending ? "Excluindo…" : "Excluir permanentemente"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
