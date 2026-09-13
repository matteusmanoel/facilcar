"use client";

import { useState, useTransition } from "react";
import { toast } from "sonner";
import { MultiSelect } from "@/components/ui/multi-select";
import { Button } from "@/components/ui/button";
import { updateLeadVehicleInterestsAction } from "@/features/lead/server/mutations";

type VehicleOption = { id: string; title: string };

export function LeadVehicleInterestForm({
  leadId,
  vehicles,
  selectedIds,
}: {
  leadId: string;
  vehicles: VehicleOption[];
  selectedIds: string[];
}) {
  const [value, setValue] = useState<string[]>(selectedIds);
  const [isPending, startTransition] = useTransition();

  return (
    <div className="space-y-2">
      <p className="text-xs font-medium text-facil-muted">
        Veículos de interesse. O primário é o escolhido pelo cliente; a ordem da lista não define o primário.
      </p>
      <MultiSelect
        options={vehicles.map((v) => ({ value: v.id, label: v.title }))}
        value={value}
        onChange={setValue}
        placeholder="Vincular veículos…"
        searchPlaceholder="Buscar veículo…"
        emptyMessage="Nenhum veículo encontrado."
      />
      <Button
        type="button"
        variant="primary"
        size="sm"
        disabled={isPending}
        onClick={() => {
          startTransition(async () => {
            const result = await updateLeadVehicleInterestsAction(leadId, value);
            if (result.ok) toast.success("Veículos de interesse atualizados");
            else toast.error(result.error ?? "Não foi possível salvar");
          });
        }}
      >
        {isPending ? "Salvando…" : "Salvar interesses"}
      </Button>
    </div>
  );
}
