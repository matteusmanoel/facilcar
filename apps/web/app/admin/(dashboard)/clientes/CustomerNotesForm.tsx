"use client";

import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { updateCustomerNotesAction } from "@/features/admin/server/customers";

export function CustomerNotesForm({
  customerId,
  currentNotes,
  canWrite,
}: {
  customerId: string;
  currentNotes: string | null;
  canWrite: boolean;
}) {
  const [notes, setNotes] = useState(currentNotes ?? "");
  const [isPending, startTransition] = useTransition();

  return (
    <div className="space-y-2">
      <textarea
        rows={5}
        value={notes}
        disabled={!canWrite || isPending}
        onChange={(e) => setNotes(e.target.value)}
        placeholder="Observações gerais sobre o cliente…"
        className="box-border w-full resize-y rounded-lg border border-facil-border bg-facil-card px-3 py-2 text-sm text-foreground placeholder:text-facil-muted focus:border-facil-orange focus:outline-none focus:ring-2 focus:ring-facil-orange/30"
      />
      {canWrite ? (
        <Button
          type="button"
          variant="primary"
          size="sm"
          disabled={isPending}
          onClick={() => {
            startTransition(async () => {
              const result = await updateCustomerNotesAction(customerId, notes);
              if (result.ok) toast.success("Descrição salva");
              else toast.error("Não foi possível salvar");
            });
          }}
        >
          {isPending ? "Salvando…" : "Salvar descrição"}
        </Button>
      ) : null}
    </div>
  );
}
