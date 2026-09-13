"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { updateLeadSellAction } from "@/features/lead/server/mutations";
import { updateLeadSellSchema, type UpdateLeadSellInput } from "@/schemas/lead";
import { AdminFieldLabel, AdminTextarea } from "@/components/admin/AdminField";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { visibleSellPhotoUrls } from "@/features/lead/lib/sell-photos";
import { fuelLabels, transLabels } from "@/features/vehicle/lib/labels";
import { LeadDetailField } from "./LeadDetailField";
import { LeadEditToolbar } from "./LeadEditToolbar";

const NONE = "__none__";
const FUEL_OPTIONS = Object.entries(fuelLabels);
const TRANS_OPTIONS = Object.entries(transLabels);

type Photo = { url: string };

type Props = {
  leadId: string;
  brand: string | null;
  model: string | null;
  version: string | null;
  yearManufacture: string;
  yearModel: string;
  mileage: string;
  fuelType: string | null;
  transmission: string | null;
  saleMode: string | null;
  observations: string | null;
  photoUrls: Photo["url"][];
};

function saleModeLabel(value: string | null) {
  if (value === "CONSIGNMENT") return "Consignação";
  if (value === "DIRECT_PURCHASE") return "Compra direta pela loja";
  return "—";
}

export function LeadSellEditor({
  leadId,
  brand,
  model,
  version,
  yearManufacture,
  yearModel,
  mileage,
  fuelType,
  transmission,
  saleMode,
  observations,
  photoUrls,
}: Props) {
  const router = useRouter();
  const [editing, setEditing] = useState(false);

  const defaults: UpdateLeadSellInput = {
    leadId,
    brand: brand ?? "",
    model: model ?? "",
    version: version ?? "",
    yearManufacture,
    yearModel,
    mileage,
    fuelType: fuelType ?? "",
    transmission: transmission ?? "",
    saleMode: saleMode === "CONSIGNMENT" || saleMode === "DIRECT_PURCHASE" ? saleMode : "",
    observations: observations ?? "",
  };

  const photos = visibleSellPhotoUrls(photoUrls);

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    watch,
    formState: { isSubmitting },
  } = useForm<UpdateLeadSellInput>({
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    resolver: zodResolver(updateLeadSellSchema) as any,
    defaultValues: defaults,
  });

  async function onSubmit(data: UpdateLeadSellInput) {
    const result = await updateLeadSellAction(data);
    if (result.ok) {
      toast.success("Ficha de venda atualizada");
      setEditing(false);
      router.refresh();
      return;
    }
    toast.error(result.error ?? "Não foi possível salvar");
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="admin-card">
      <div className="mb-4 flex items-center justify-between gap-2">
        <h2 className="text-sm font-bold uppercase tracking-wide text-facil-muted">Veículo para venda</h2>
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

      <div className="mb-6 border-b border-facil-border pb-4">
        <h3 className="text-xs font-medium text-facil-muted">
          Fotos enviadas{photos.length > 0 ? ` · ${photos.length}` : ""}
        </h3>
        {photos.length > 0 ? (
          <ul className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
            {photos.map((url, index) => (
              <li key={`${url}-${index}`}>
                <a
                  href={url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block overflow-hidden rounded-lg border border-facil-border bg-facil-surface"
                >
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={url}
                    alt={`Foto ${index + 1} do veículo enviado pelo cliente`}
                    className="aspect-[4/3] w-full object-cover"
                  />
                </a>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-2 text-sm text-facil-muted">Nenhuma foto enviada neste pedido.</p>
        )}
      </div>

      {editing ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="space-y-1">
            <AdminFieldLabel>Marca</AdminFieldLabel>
            <Input {...register("brand")} />
          </div>
          <div className="space-y-1">
            <AdminFieldLabel>Modelo</AdminFieldLabel>
            <Input {...register("model")} />
          </div>
          <div className="space-y-1">
            <AdminFieldLabel>Versão</AdminFieldLabel>
            <Input {...register("version")} />
          </div>
          <div className="space-y-1">
            <AdminFieldLabel>Modalidade</AdminFieldLabel>
            <Select
              value={watch("saleMode") || NONE}
              onValueChange={(v) =>
                setValue("saleMode", v === NONE ? "" : (v as "CONSIGNMENT" | "DIRECT_PURCHASE"), {
                  shouldDirty: true,
                })
              }
            >
              <SelectTrigger>
                <SelectValue placeholder="—" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={NONE}>—</SelectItem>
                <SelectItem value="CONSIGNMENT">Consignação</SelectItem>
                <SelectItem value="DIRECT_PURCHASE">Compra direta pela loja</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <AdminFieldLabel>Ano fabricação</AdminFieldLabel>
            <Input type="number" min={1900} max={2100} inputMode="numeric" {...register("yearManufacture")} />
          </div>
          <div className="space-y-1">
            <AdminFieldLabel>Ano modelo</AdminFieldLabel>
            <Input type="number" min={1900} max={2100} inputMode="numeric" {...register("yearModel")} />
          </div>
          <div className="space-y-1">
            <AdminFieldLabel>KM</AdminFieldLabel>
            <Input type="number" min={0} inputMode="numeric" {...register("mileage")} />
          </div>
          <div className="space-y-1">
            <AdminFieldLabel>Combustível</AdminFieldLabel>
            <Select
              value={watch("fuelType") || NONE}
              onValueChange={(v) => setValue("fuelType", v === NONE ? "" : v, { shouldDirty: true })}
            >
              <SelectTrigger>
                <SelectValue placeholder="—" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={NONE}>—</SelectItem>
                {fuelType && !fuelLabels[fuelType] ? (
                  <SelectItem value={fuelType}>{fuelType}</SelectItem>
                ) : null}
                {FUEL_OPTIONS.map(([value, label]) => (
                  <SelectItem key={value} value={value}>
                    {label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <AdminFieldLabel>Câmbio</AdminFieldLabel>
            <Select
              value={watch("transmission") || NONE}
              onValueChange={(v) =>
                setValue("transmission", v === NONE ? "" : v, { shouldDirty: true })
              }
            >
              <SelectTrigger>
                <SelectValue placeholder="—" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={NONE}>—</SelectItem>
                {transmission && !transLabels[transmission] ? (
                  <SelectItem value={transmission}>{transmission}</SelectItem>
                ) : null}
                {TRANS_OPTIONS.map(([value, label]) => (
                  <SelectItem key={value} value={value}>
                    {label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1 sm:col-span-2">
            <AdminFieldLabel>Observações</AdminFieldLabel>
            <AdminTextarea rows={3} {...register("observations")} />
          </div>
        </div>
      ) : (
        <dl className="grid grid-cols-1 gap-x-6 gap-y-4 sm:grid-cols-2">
          <LeadDetailField label="Marca">{brand ?? "—"}</LeadDetailField>
          <LeadDetailField label="Modelo">{model ?? "—"}</LeadDetailField>
          <LeadDetailField label="Versão">{version ?? "—"}</LeadDetailField>
          <LeadDetailField label="Ano fabricação">{yearManufacture || "—"}</LeadDetailField>
          <LeadDetailField label="Ano modelo">{yearModel || "—"}</LeadDetailField>
          <LeadDetailField label="KM">
            {mileage ? Number(mileage).toLocaleString("pt-BR") : "—"}
          </LeadDetailField>
          <LeadDetailField label="Combustível">
            {fuelType ? (fuelLabels[fuelType] ?? fuelType) : "—"}
          </LeadDetailField>
          <LeadDetailField label="Câmbio">
            {transmission ? (transLabels[transmission] ?? transmission) : "—"}
          </LeadDetailField>
          <LeadDetailField label="Modalidade">{saleModeLabel(saleMode)}</LeadDetailField>
        </dl>
      )}

      {!editing && observations ? (
        <p className="mt-4 whitespace-pre-wrap text-sm text-facil-muted">{observations}</p>
      ) : null}
    </form>
  );
}
