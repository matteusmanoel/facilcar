"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { updateLeadFinancingAction } from "@/features/lead/server/mutations";
import {
  updateLeadFinancingSchema,
  type UpdateLeadFinancingInput,
} from "@/schemas/lead";
import { AdminFieldLabel, AdminTextarea } from "@/components/admin/AdminField";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/cn";
import { LeadDetailField } from "./LeadDetailField";
import { LeadEditToolbar } from "./LeadEditToolbar";

const INSTALLMENTS = [12, 24, 36, 48, 60, 72, 84];
const LICENSE_NONE = "__none__";
const INSTALLMENTS_NONE = "__none__";

function formatMoney(value: unknown): string | null {
  if (value == null || value === "") return null;
  const n = Number(value);
  if (Number.isNaN(n)) return null;
  return `R$ ${n.toLocaleString("pt-BR")}`;
}

function creditRatioColor(ratio: number) {
  if (ratio >= 20) return "text-green-600 bg-green-50 dark:text-green-400 dark:bg-green-950/30";
  if (ratio >= 10) return "text-yellow-600 bg-yellow-50 dark:text-yellow-400 dark:bg-yellow-950/30";
  return "text-red-600 bg-red-50 dark:text-red-400 dark:bg-red-950/30";
}

function creditRatioLabel(ratio: number) {
  if (ratio >= 20) return "Entrada forte";
  if (ratio >= 10) return "Entrada regular";
  return "Entrada baixa";
}

type Props = {
  leadId: string;
  monthlyIncome: string;
  downPayment: string;
  desiredInstallments: string;
  hasDriverLicense: boolean | null;
  occupation: string | null;
  notes: string | null;
};

export function LeadFinancingEditor({
  leadId,
  monthlyIncome,
  downPayment,
  desiredInstallments,
  hasDriverLicense,
  occupation,
  notes,
}: Props) {
  const router = useRouter();
  const [editing, setEditing] = useState(false);

  const defaults: UpdateLeadFinancingInput = {
    leadId,
    monthlyIncome,
    downPayment,
    desiredInstallments,
    hasDriverLicense: hasDriverLicense == null ? "" : hasDriverLicense ? "true" : "false",
    occupation: occupation ?? "",
    notes: notes ?? "",
  };

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    watch,
    formState: { isSubmitting },
  } = useForm<UpdateLeadFinancingInput>({
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    resolver: zodResolver(updateLeadFinancingSchema) as any,
    defaultValues: defaults,
  });

  const entradaRenda =
    monthlyIncome && downPayment && Number(monthlyIncome) > 0
      ? Math.round((Number(downPayment) / Number(monthlyIncome)) * 100)
      : null;

  async function onSubmit(data: UpdateLeadFinancingInput) {
    const result = await updateLeadFinancingAction(data);
    if (result.ok) {
      toast.success("Perfil de crédito atualizado");
      setEditing(false);
      router.refresh();
      return;
    }
    toast.error(result.error ?? "Não foi possível salvar");
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="admin-card">
      <div className="mb-4 flex items-center justify-between gap-2">
        <h2 className="text-sm font-bold uppercase tracking-wide text-facil-muted">Perfil de crédito</h2>
        <LeadEditToolbar
          editing={editing}
          pending={isSubmitting}
          onEdit={() => {
            reset(defaults);
            setEditing(true);
          }}
          onCancel={() => {
            reset(defaults);
            setEditing(false);
          }}
        />
      </div>

      {editing ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="space-y-1">
            <AdminFieldLabel>Renda mensal</AdminFieldLabel>
            <Input type="number" min={0} step={100} inputMode="decimal" {...register("monthlyIncome")} />
          </div>
          <div className="space-y-1">
            <AdminFieldLabel>Entrada</AdminFieldLabel>
            <Input type="number" min={0} step={100} inputMode="decimal" {...register("downPayment")} />
          </div>
          <div className="space-y-1">
            <AdminFieldLabel>Prazo desejado</AdminFieldLabel>
            <Select
              value={watch("desiredInstallments") || INSTALLMENTS_NONE}
              onValueChange={(v) =>
                setValue("desiredInstallments", v === INSTALLMENTS_NONE ? "" : v, { shouldDirty: true })
              }
            >
              <SelectTrigger>
                <SelectValue placeholder="Selecione" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={INSTALLMENTS_NONE}>—</SelectItem>
                {desiredInstallments && !INSTALLMENTS.includes(Number(desiredInstallments)) ? (
                  <SelectItem value={desiredInstallments}>{desiredInstallments} meses</SelectItem>
                ) : null}
                {INSTALLMENTS.map((n) => (
                  <SelectItem key={n} value={String(n)}>
                    {n} meses
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <AdminFieldLabel>CNH</AdminFieldLabel>
            <Select
              value={watch("hasDriverLicense") || LICENSE_NONE}
              onValueChange={(v) =>
                setValue("hasDriverLicense", v === LICENSE_NONE ? "" : (v as "true" | "false"), {
                  shouldDirty: true,
                })
              }
            >
              <SelectTrigger>
                <SelectValue placeholder="Não informado" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={LICENSE_NONE}>Não informado</SelectItem>
                <SelectItem value="true">Sim</SelectItem>
                <SelectItem value="false">Não</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1 sm:col-span-2">
            <AdminFieldLabel>Ocupação</AdminFieldLabel>
            <Input {...register("occupation")} />
          </div>
          <div className="space-y-1 sm:col-span-2">
            <AdminFieldLabel>Notas da ficha</AdminFieldLabel>
            <AdminTextarea rows={3} {...register("notes")} />
          </div>
        </div>
      ) : (
        <>
          <dl className="grid grid-cols-1 gap-x-6 gap-y-4 sm:grid-cols-2">
            <LeadDetailField label="Renda mensal">
              <span className="text-base font-bold">{formatMoney(monthlyIncome) ?? "—"}</span>
            </LeadDetailField>
            <LeadDetailField label="Entrada">
              <span className="text-base font-bold">{formatMoney(downPayment) ?? "—"}</span>
            </LeadDetailField>
            <LeadDetailField label="Prazo desejado">
              {desiredInstallments ? `${desiredInstallments} meses` : "—"}
            </LeadDetailField>
            <LeadDetailField label="CNH">
              {hasDriverLicense == null ? "—" : hasDriverLicense ? "Sim" : "Não"}
            </LeadDetailField>
            <LeadDetailField label="Ocupação">{occupation ?? "—"}</LeadDetailField>
          </dl>
          {entradaRenda !== null ? (
            <div className="mt-4 border-t border-facil-border pt-3">
              <p className="mb-1.5 text-xs font-medium text-facil-muted">Razão entrada / renda</p>
              <div className="flex items-center gap-3">
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-facil-surface">
                  <div
                    className={cn(
                      "h-full rounded-full",
                      entradaRenda >= 20 ? "bg-green-500" : entradaRenda >= 10 ? "bg-yellow-400" : "bg-red-400",
                    )}
                    style={{ width: `${Math.min(entradaRenda * 2, 100)}%` }}
                  />
                </div>
                <span
                  className={`shrink-0 rounded-full px-2.5 py-0.5 text-xs font-bold ${creditRatioColor(entradaRenda)}`}
                >
                  {entradaRenda}% — {creditRatioLabel(entradaRenda)}
                </span>
              </div>
            </div>
          ) : null}
          {notes ? (
            <p className="mt-4 whitespace-pre-wrap text-sm text-facil-muted">{notes}</p>
          ) : null}
        </>
      )}
    </form>
  );
}
