"use client";

import { useRouter } from "next/navigation";
import { useTransition } from "react";
import { toast } from "sonner";
import { updateLeadStatusAction } from "./action";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

type Props = { leadId: string; currentStatus: string };

const STATUSES: { value: string; label: string }[] = [
  { value: "NEW", label: "Novo" },
  { value: "IN_PROGRESS", label: "Em progresso" },
  { value: "CONTACTED", label: "Contactado" },
  { value: "QUALIFIED", label: "Qualificado" },
  { value: "WON", label: "Ganho" },
  { value: "LOST", label: "Perdido" },
  { value: "SPAM", label: "Spam" },
];

export function UpdateLeadStatusForm({ leadId, currentStatus }: Props) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();

  return (
    <Select
      value={currentStatus}
      disabled={isPending}
      onValueChange={(newStatus) => {
        startTransition(async () => {
          try {
            await updateLeadStatusAction(leadId, newStatus);
            router.refresh();
            const label = STATUSES.find((s) => s.value === newStatus)?.label ?? newStatus;
            toast.success(`Status atualizado para "${label}"`);
          } catch {
            toast.error("Erro ao atualizar status. Tente novamente.");
          }
        });
      }}
    >
      <SelectTrigger className="w-full dark:border-zinc-700 dark:bg-zinc-900">
        <SelectValue placeholder="Status" />
      </SelectTrigger>
      <SelectContent>
        {STATUSES.map((s) => (
          <SelectItem key={s.value} value={s.value}>
            {s.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
