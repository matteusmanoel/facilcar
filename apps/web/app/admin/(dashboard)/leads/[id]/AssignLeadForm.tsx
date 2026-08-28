"use client";

import { useRouter } from "next/navigation";
import { useTransition } from "react";
import { toast } from "sonner";
import {
  claimLeadAction,
  updateLeadAssignmentAction,
} from "@/features/lead/server/mutations";
import { Button } from "@/components/ui/button";
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
  currentUserId: string;
  sellers: Seller[];
};

export function AssignLeadForm({
  leadId,
  currentAssignedToUserId,
  currentUserId,
  sellers,
}: Props) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const canClaim = currentAssignedToUserId == null;

  return (
    <div className="flex flex-col gap-2">
      {canClaim ? (
        <Button
          type="button"
          disabled={isPending}
          className="w-full bg-facil-orange hover:bg-facil-orange/90"
          onClick={() => {
            startTransition(async () => {
              try {
                const result = await claimLeadAction(leadId);
                if (!result.ok) {
                  if (result.error === "already_claimed") {
                    toast.error("Este lead já foi assumido por outro vendedor.");
                  } else {
                    toast.error(result.error ?? "Não foi possível assumir o lead.");
                  }
                  router.refresh();
                  return;
                }
                router.refresh();
                toast.success("Lead assumido com sucesso.");
              } catch {
                toast.error("Erro ao assumir lead. Tente novamente.");
              }
            });
          }}
        >
          Assumir
        </Button>
      ) : null}

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
                  : assignedToUserId === currentUserId
                    ? "Você"
                    : sellers.find((s) => s.id === assignedToUserId)?.name ?? "Vendedor";
              toast.success(`Responsável atualizado: ${label}`);
            } catch {
              toast.error("Erro ao atribuir vendedor. Tente novamente.");
            }
          });
        }}
      >
        <SelectTrigger className="w-full">
          <SelectValue placeholder="Selecionar vendedor" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="none">Sem responsável</SelectItem>
          {sellers.map((seller) => (
            <SelectItem key={seller.id} value={seller.id}>
              {seller.id === currentUserId ? `${seller.name} (você)` : seller.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
