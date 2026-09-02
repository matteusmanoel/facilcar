"use client";

import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { Save } from "lucide-react";
import { createManualLeadAction } from "@/features/lead/server/mutations";
import {
  createManualLeadSchema,
  type CreateManualLeadInput,
} from "@/schemas/lead";
import { AdminFieldError, AdminFieldLabel, AdminTextarea } from "@/components/admin/AdminField";
import { CustomerNameConflictDialog } from "@/components/admin/CustomerNameConflictDialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/cn";
import { formatPhoneBR } from "@/lib/input-masks";
import { useState } from "react";

type VehicleOption = { id: string; title: string };

const LEAD_TYPES: { value: CreateManualLeadInput["type"]; label: string }[] = [
  { value: "CONTACT", label: "Contato" },
  { value: "VEHICLE_INTEREST", label: "Interesse em veículo" },
  { value: "FINANCING", label: "Financiamento" },
  { value: "SELL_VEHICLE", label: "Vender veículo" },
  { value: "REFINANCING", label: "Refinanciamento" },
  { value: "TRADE_IN", label: "Troca" },
  { value: "CONSIGNMENT", label: "Consignação" },
  { value: "THIRD_PARTY_FINANCING", label: "Financiamento terceiros" },
];

const SELECT_NONE = "__none__";

type Props = {
  vehicles: VehicleOption[];
  variant?: "page" | "dialog";
  onSuccess?: (leadId: string) => void;
  onCancel?: () => void;
};

export function ManualLeadForm({
  vehicles,
  variant = "page",
  onSuccess,
  onCancel,
}: Props) {
  const router = useRouter();
  const [nameConflict, setNameConflict] = useState<{
    existingName: string;
    submittedName: string;
    customerId: string;
    pendingData: CreateManualLeadInput;
  } | null>(null);

  const {
    register,
    handleSubmit,
    setValue,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<CreateManualLeadInput>({
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    resolver: zodResolver(createManualLeadSchema) as any,
    defaultValues: {
      name: "",
      phone: "",
      email: "",
      type: "CONTACT",
      message: "",
      vehicleId: undefined,
    },
  });

  const leadType = watch("type");
  const vehicleId = watch("vehicleId");

  const submitLead = async (
    data: CreateManualLeadInput,
    nameResolution?: "keep_existing" | "use_new",
  ) => {
    const result = await createManualLeadAction({ ...data, nameResolution });

    if (result.ok) {
      toast.success("Lead criado com sucesso!");
      if (variant === "dialog" && onSuccess) {
        onSuccess(result.id);
        return;
      }
      router.push(`/admin/leads/${result.id}`);
      return;
    }

    if ("conflict" in result && result.conflict) {
      setNameConflict({
        ...result.conflict,
        pendingData: data,
      });
      return;
    }

    const firstError = Object.values(result.error ?? {}).flat()[0];
    toast.error(typeof firstError === "string" ? firstError : "Dados inválidos");
  };

  const onSubmit = async (data: CreateManualLeadInput) => {
    await submitLead(data);
  };

  return (
    <>
      <form
        onSubmit={handleSubmit(onSubmit)}
        className={cn(
          "space-y-5",
          variant === "page" ? "admin-card max-w-2xl p-6" : "p-1",
        )}
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1 sm:col-span-2">
            <AdminFieldLabel required>Nome</AdminFieldLabel>
            <Input
              {...register("name")}
              placeholder="Nome completo"
              className={cn(errors.name && "border-red-400")}
            />
            <AdminFieldError message={errors.name?.message} />
          </div>

          <div className="space-y-1">
            <AdminFieldLabel required>Telefone</AdminFieldLabel>
            <Input
              value={formatPhoneBR(watch("phone") ?? "")}
              onChange={(e) =>
                setValue("phone", formatPhoneBR(e.target.value), { shouldValidate: true, shouldDirty: true })
              }
              inputMode="numeric"
              autoComplete="tel"
              placeholder="(11) 99999-9999"
              className={cn(errors.phone && "border-red-400")}
            />
            <AdminFieldError message={errors.phone?.message} />
          </div>

          <div className="space-y-1">
            <AdminFieldLabel>E-mail</AdminFieldLabel>
            <Input
              type="email"
              {...register("email")}
              placeholder="email@exemplo.com"
              className={cn(errors.email && "border-red-400")}
            />
            <AdminFieldError message={errors.email?.message} />
          </div>

          <div className="space-y-1">
            <AdminFieldLabel required>Tipo</AdminFieldLabel>
            <Select
              value={leadType}
              onValueChange={(v) =>
                setValue("type", v as CreateManualLeadInput["type"], { shouldValidate: true })
              }
            >
              <SelectTrigger className={cn("w-full", errors.type && "border-red-400")}>
                <SelectValue placeholder="Selecionar tipo" />
              </SelectTrigger>
              <SelectContent>
                {LEAD_TYPES.map((t) => (
                  <SelectItem key={t.value} value={t.value}>
                    {t.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <AdminFieldError message={errors.type?.message} />
          </div>

          <div className="space-y-1">
            <AdminFieldLabel>Veículo (opcional)</AdminFieldLabel>
            <Select
              value={vehicleId ?? SELECT_NONE}
              onValueChange={(v) =>
                setValue("vehicleId", v === SELECT_NONE ? undefined : v, { shouldValidate: true })
              }
            >
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Nenhum" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={SELECT_NONE}>Nenhum</SelectItem>
                {vehicles.map((v) => (
                  <SelectItem key={v.id} value={v.id}>
                    {v.title}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <AdminFieldError message={errors.vehicleId?.message} />
          </div>

          <div className="space-y-1 sm:col-span-2">
            <AdminFieldLabel>Mensagem</AdminFieldLabel>
            <AdminTextarea
              rows={4}
              {...register("message")}
              placeholder="Observações ou detalhes do contato…"
              className={cn(errors.message && "border-red-400")}
            />
            <AdminFieldError message={errors.message?.message} />
          </div>
        </div>

        <div className="flex justify-end gap-2 border-t border-facil-border pt-4">
          <Button
            type="button"
            variant="outline"
            onClick={() => (onCancel ? onCancel() : router.push("/admin/leads"))}
            disabled={isSubmitting}
          >
            Cancelar
          </Button>
          <Button type="submit" variant="primary" disabled={isSubmitting}>
            <Save className="h-4 w-4" />
            {isSubmitting ? "Salvando…" : "Criar lead"}
          </Button>
        </div>
      </form>

      <CustomerNameConflictDialog
        open={!!nameConflict}
        existingName={nameConflict?.existingName ?? ""}
        submittedName={nameConflict?.submittedName ?? ""}
        onCancel={() => setNameConflict(null)}
        onKeepExisting={async () => {
          if (!nameConflict) return;
          const data = nameConflict.pendingData;
          setNameConflict(null);
          await submitLead(data, "keep_existing");
        }}
        onUseNew={async () => {
          if (!nameConflict) return;
          const data = nameConflict.pendingData;
          setNameConflict(null);
          await submitLead(data, "use_new");
        }}
      />
    </>
  );
}
