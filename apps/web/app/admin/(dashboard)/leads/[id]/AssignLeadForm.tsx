"use client";

import { useRouter } from "next/navigation";
import { useTransition } from "react";
import { toast } from "sonner";
import { updateLeadAssignmentAction } from "@/features/lead/server/mutations";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

type Seller = { id: string; name: string };

type Props = {
  leadId: string;
  currentAssignedToUserId: string | null;
  sellers: Seller[];
};

export function AssignLeadForm({ leadId, currentAssignedToUserId, sellers }: Props) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();

  return (
    <Select
      value={currentAssignedToUserId ?? "none"}
      disabled={isPending}
      onValueChange={(value) => {
        const assignedToUserId = value === "none" ? null : value;
        startTransition(async () => {
          try {
            await updateLeadAssignmentAction(leadId, assignedToUserId);
            router.refresh();
            const label =
              assignedToUserId == null
                ? "Sem responsável"
                : sellers.find((s) => s.id === assignedToUserId)?.name ?? "Vendedor";
            toast.success(`Responsável atualizado: ${label}`);
          } catch {
            toast.error("Erro ao atribuir vendedor. Tente novamente.");
          }
        });
      }}
    >
      <SelectTrigger className="w-full dark:border-zinc-700 dark:bg-zinc-900">
        <SelectValue placeholder="Selecionar vendedor" />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="none">Sem responsável</SelectItem>
        {sellers.map((seller) => (
          <SelectItem key={seller.id} value={seller.id}>
            {seller.name}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
