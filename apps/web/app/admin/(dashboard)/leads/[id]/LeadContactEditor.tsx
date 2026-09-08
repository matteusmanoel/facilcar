"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { updateLeadContactAction } from "@/features/lead/server/mutations";
import { maskCPF } from "@/features/lead/lib/edit-values";
import {
  updateLeadContactSchema,
  type UpdateLeadContactInput,
} from "@/schemas/lead";
import { AdminFieldError, AdminFieldLabel } from "@/components/admin/AdminField";
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
import { formatCPF, formatPhoneBR } from "@/lib/input-masks";
import { cn } from "@/lib/cn";
import { LeadDetailField } from "./LeadDetailField";
import { LeadEditToolbar } from "./LeadEditToolbar";

const UFS = [
  "AC",
  "AL",
  "AP",
  "AM",
  "BA",
  "CE",
  "DF",
  "ES",
  "GO",
  "MA",
  "MT",
  "MS",
  "MG",
  "PA",
  "PB",
  "PR",
  "PE",
  "PI",
  "RJ",
  "RN",
  "RS",
  "RO",
  "RR",
  "SC",
  "SP",
  "SE",
  "TO",
] as const;

const STATE_NONE = "__none__";

type FinancingIdentity = {
  cpf: string | null;
  birthDate: string;
  age?: number | null;
};

type Props = {
  leadId: string;
  name: string;
  phone: string;
  email: string | null;
  city: string | null;
  state: string | null;
  customer: { id: string; name: string } | null;
  financing: FinancingIdentity | null;
};

export function LeadContactEditor({
  leadId,
  name,
  phone,
  email,
  city,
  state,
  customer,
  financing,
}: Props) {
  const router = useRouter();
  const [editing, setEditing] = useState(false);
  const [cpfTouched, setCpfTouched] = useState(false);
  const [nameConflict, setNameConflict] = useState<{
    existingName: string;
    submittedName: string;
    pendingData: UpdateLeadContactInput;
  } | null>(null);

  const defaults: UpdateLeadContactInput = {
    leadId,
    name,
    phone,
    email: email ?? "",
    city: city ?? "",
    state: state ?? "",
    cpf: financing?.cpf ?? "",
    cpfTouched: false,
    birthDate: financing?.birthDate ?? "",
  };

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<UpdateLeadContactInput>({
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    resolver: zodResolver(updateLeadContactSchema) as any,
    defaultValues: defaults,
  });

  function startEdit() {
    reset(defaults);
    setCpfTouched(false);
    setEditing(true);
  }

  function cancel() {
    reset(defaults);
    setCpfTouched(false);
    setEditing(false);
  }

  async function submit(data: UpdateLeadContactInput, nameResolution?: "keep_existing" | "use_new") {
    const result = await updateLeadContactAction({
      ...data,
      cpfTouched,
      nameResolution,
    });

    if (result.ok) {
      toast.success("Contato atualizado");
      setEditing(false);
      setCpfTouched(false);
      router.refresh();
      return;
    }

    if ("conflict" in result && result.conflict) {
      setNameConflict({
        existingName: result.conflict.existingName,
        submittedName: result.conflict.submittedName,
        pendingData: data,
      });
      return;
    }

    toast.error("error" in result && result.error ? result.error : "Não foi possível salvar");
  }

  const phoneDigits = phone.replace(/\D/g, "");

  return (
    <>
      <form
        onSubmit={handleSubmit((data) => submit(data))}
        className="admin-card"
      >
        <div className="mb-4 flex items-center justify-between gap-2">
          <h2 className="text-sm font-bold uppercase tracking-wide text-facil-muted">Contato</h2>
          <LeadEditToolbar
            editing={editing}
            pending={isSubmitting}
            onEdit={startEdit}
            onCancel={cancel}
          />
        </div>

        {editing ? (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="space-y-1 sm:col-span-2">
              <AdminFieldLabel required>Nome</AdminFieldLabel>
              <Input {...register("name")} className={cn(errors.name && "border-red-400")} />
              <AdminFieldError message={errors.name?.message} />
            </div>
            <div className="space-y-1">
              <AdminFieldLabel required>Telefone</AdminFieldLabel>
              <Input
                value={formatPhoneBR(watch("phone") ?? "")}
                onChange={(e) =>
                  setValue("phone", formatPhoneBR(e.target.value), {
                    shouldValidate: true,
                    shouldDirty: true,
                  })
                }
                inputMode="numeric"
                autoComplete="tel"
                className={cn(errors.phone && "border-red-400")}
              />
              <AdminFieldError message={errors.phone?.message} />
            </div>
            <div className="space-y-1">
              <AdminFieldLabel>E-mail</AdminFieldLabel>
              <Input type="email" {...register("email")} className={cn(errors.email && "border-red-400")} />
              <AdminFieldError message={errors.email?.message} />
            </div>
            <div className="space-y-1">
              <AdminFieldLabel>Cidade</AdminFieldLabel>
              <Input {...register("city")} />
            </div>
            <div className="space-y-1">
              <AdminFieldLabel>Estado</AdminFieldLabel>
              <Select
                value={watch("state") || STATE_NONE}
                onValueChange={(v) => setValue("state", v === STATE_NONE ? "" : v, { shouldDirty: true })}
              >
                <SelectTrigger>
                  <SelectValue placeholder="UF" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={STATE_NONE}>—</SelectItem>
                  {UFS.map((uf) => (
                    <SelectItem key={uf} value={uf}>
                      {uf}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {financing ? (
              <>
                <div className="space-y-1">
                  <AdminFieldLabel>CPF</AdminFieldLabel>
                  {cpfTouched ? (
                    <Input
                      value={formatCPF(watch("cpf") ?? "")}
                      onChange={(e) =>
                        setValue("cpf", formatCPF(e.target.value), { shouldDirty: true })
                      }
                      inputMode="numeric"
                      autoComplete="off"
                    />
                  ) : (
                    <div className="flex h-9 items-center justify-between gap-2 rounded-lg border border-facil-border bg-facil-surface px-3 text-sm">
                      <span>{maskCPF(financing.cpf)}</span>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="h-7 px-2 text-xs"
                        onClick={() => {
                          setCpfTouched(true);
                          setValue("cpf", financing.cpf ?? "", { shouldDirty: true });
                        }}
                      >
                        Alterar CPF
                      </Button>
                    </div>
                  )}
                </div>
                <div className="space-y-1">
                  <AdminFieldLabel>Data de nascimento</AdminFieldLabel>
                  <Input type="date" {...register("birthDate")} />
                  <AdminFieldError message={errors.birthDate?.message} />
                </div>
              </>
            ) : null}
          </div>
        ) : (
          <dl className="grid grid-cols-1 gap-x-6 gap-y-4 sm:grid-cols-2">
            <LeadDetailField label="Nome">{name}</LeadDetailField>
            <LeadDetailField label="Telefone">
              <span className="inline-flex items-center gap-1.5">
                {phone}
                {phoneDigits ? (
                  <a
                    href={`tel:${phoneDigits}`}
                    className="rounded bg-facil-surface px-1.5 py-0.5 text-xs text-facil-muted hover:bg-facil-border hover:text-foreground"
                  >
                    Ligar
                  </a>
                ) : null}
              </span>
            </LeadDetailField>
            <LeadDetailField label="E-mail">{email ?? "—"}</LeadDetailField>
            <LeadDetailField label="Cidade / Estado">
              {[city, state].filter(Boolean).join(" / ") || "—"}
            </LeadDetailField>
            <LeadDetailField label="Cliente no CRM">
              {customer ? (
                <Link
                  href={`/admin/clientes/${customer.id}`}
                  className="font-medium text-facil-orange hover:underline"
                >
                  {customer.name}
                </Link>
              ) : (
                "Não vinculado"
              )}
            </LeadDetailField>
            {financing ? (
              <>
                <LeadDetailField label="CPF">{maskCPF(financing.cpf)}</LeadDetailField>
                <LeadDetailField label="Data de nascimento">
                  {financing.birthDate
                    ? new Date(`${financing.birthDate}T12:00:00`).toLocaleDateString("pt-BR")
                    : "—"}
                </LeadDetailField>
                {financing.age != null ? (
                  <LeadDetailField label="Idade">{financing.age} anos</LeadDetailField>
                ) : null}
              </>
            ) : null}
          </dl>
        )}
      </form>

      <CustomerNameConflictDialog
        open={!!nameConflict}
        existingName={nameConflict?.existingName ?? ""}
        submittedName={nameConflict?.submittedName ?? ""}
        onCancel={() => setNameConflict(null)}
        onKeepExisting={async () => {
          if (!nameConflict) return;
          const pending = nameConflict.pendingData;
          setNameConflict(null);
          await submit(pending, "keep_existing");
        }}
        onUseNew={async () => {
          if (!nameConflict) return;
          const pending = nameConflict.pendingData;
          setNameConflict(null);
          await submit(pending, "use_new");
        }}
      />
    </>
  );
}
