"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { updateLeadStatusAction } from "./action";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

type Props = { leadId: string; currentStatus: string };

export function LeadDangerZone({ leadId, currentStatus }: Props) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [confirm, setConfirm] = useState<"LOST" | "SPAM" | null>(null);

  function run(status: "LOST" | "SPAM") {
    startTransition(async () => {
      try {
        await updateLeadStatusAction(leadId, status);
        router.refresh();
        toast.success(status === "SPAM" ? "Lead marcado como spam." : "Lead marcado como perdido.");
        setConfirm(null);
      } catch {
        toast.error("Não foi possível atualizar o status.");
      }
    });
  }

  if (currentStatus === "LOST" || currentStatus === "SPAM" || currentStatus === "WON") {
    return null;
  }

  return (
    <>
      <div className="mt-6 rounded-xl border border-red-200 bg-red-50/80 p-4 dark:border-red-900/50 dark:bg-red-950/30">
        <h3 className="text-sm font-semibold text-red-800 dark:text-red-300">Zona sensível</h3>
        <p className="mt-1 text-xs text-red-700/90 dark:text-red-400/90">
          Ações que fecham o atendimento deste lead.
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="border-red-300 text-red-700 hover:bg-red-100 dark:border-red-800 dark:text-red-300 dark:hover:bg-red-950/50"
            onClick={() => setConfirm("LOST")}
          >
            Marcar como perdido
          </Button>
          <Button type="button" variant="destructive" size="sm" onClick={() => setConfirm("SPAM")}>
            Marcar como spam
          </Button>
        </div>
      </div>

      <Dialog open={!!confirm} onOpenChange={(o) => !o && setConfirm(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {confirm === "SPAM" ? "Confirmar spam?" : "Confirmar lead perdido?"}
            </DialogTitle>
            <DialogDescription>
              {confirm === "SPAM"
                ? "Este lead será classificado como spam e sairá das filas principais."
                : "Indica que o negócio não foi fechado com este contato."}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button type="button" variant="outline" onClick={() => setConfirm(null)}>
              Cancelar
            </Button>
            <Button
              type="button"
              variant={confirm === "SPAM" ? "destructive" : "default"}
              disabled={isPending}
              onClick={() => confirm && run(confirm)}
            >
              {isPending ? "Salvando…" : "Confirmar"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
