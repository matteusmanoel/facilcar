"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { ChevronLeft, ChevronRight, Save } from "lucide-react";
import { createVehicle, updateVehicle } from "@/features/vehicle/server/mutations";
import { createVehicleSchema, type CreateVehicleInput } from "@/schemas/vehicle";
import { Stepper } from "@/components/ui/stepper";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ImageUploader } from "@/features/admin/ui/ImageUploader";
import { VehicleBrandCombobox } from "@/components/admin/VehicleBrandCombobox";
import { cn } from "@/lib/cn";

type BrandOption = { id: string; name: string; slug: string };

type VehicleForForm = {
  id: string;
  slug: string;
  status: string;
  type: string;
  title: string;
  brandId: string;
  model: string;
  version: string | null;
  yearManufacture: number | null;
  yearModel: number | null;
  mileage: number | null;
  fuelType: string | null;
  transmission: string | null;
  color: string | null;
  doors: number | null;
  priceCash: unknown;
  priceTradeIn: unknown;
  pricePromotional: unknown;
  city: string | null;
  state: string | null;
  metaTitle: string | null;
  metaDescription: string | null;
  shortDescription: string | null;
  description: string | null;
  featured: boolean;
  images: { url: string }[];
  features: { label: string }[];
};

interface VehicleFormProps {
  brands: BrandOption[];
  vehicle?: VehicleForForm | null;
}

const STEPS = ["Informações", "Especificações", "Precificação", "Mídia & SEO"];

const STATUSES = ["DRAFT", "PUBLISHED", "RESERVED", "SOLD", "ARCHIVED"] as const;
const STATUS_LABELS: Record<string, string> = {
  DRAFT: "Rascunho",
  PUBLISHED: "Publicado",
  RESERVED: "Reservado",
  SOLD: "Vendido",
  ARCHIVED: "Arquivado",
};

const TYPES = ["CAR", "MOTORCYCLE", "UTILITY", "OTHER"] as const;
const TYPE_LABELS: Record<string, string> = {
  CAR: "Carro",
  MOTORCYCLE: "Moto",
  UTILITY: "Utilitário",
  OTHER: "Outro",
};

const FUEL = ["GASOLINE", "ETHANOL", "FLEX", "DIESEL", "ELECTRIC", "HYBRID", "OTHER"] as const;
const FUEL_LABELS: Record<string, string> = {
  GASOLINE: "Gasolina",
  ETHANOL: "Etanol",
  FLEX: "Flex",
  DIESEL: "Diesel",
  ELECTRIC: "Elétrico",
  HYBRID: "Híbrido",
  OTHER: "Outro",
};

const TRANSMISSION = ["MANUAL", "AUTOMATIC", "AUTOMATED", "CVT", "OTHER"] as const;
const TRANS_LABELS: Record<string, string> = {
  MANUAL: "Manual",
  AUTOMATIC: "Automático",
  AUTOMATED: "Automatizado",
  CVT: "CVT",
  OTHER: "Outro",
};

const STEP_FIELDS: Record<number, (keyof CreateVehicleInput)[]> = {
  0: ["title", "brandId", "model", "type", "status"],
  1: ["yearManufacture", "yearModel", "mileage", "fuelType", "transmission", "color", "doors"],
  2: ["priceCash"],
  3: [],
};

const SELECT_NONE = "__none__";

function FieldLabel({
  children,
  required,
  htmlFor,
}: {
  children: React.ReactNode;
  required?: boolean;
  htmlFor?: string;
}) {
  return (
    <label htmlFor={htmlFor} className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
      {children}
      {required && <span className="ml-0.5 text-facil-orange">*</span>}
    </label>
  );
}

function FieldError({ message }: { message?: string }) {
  if (!message) return null;
  return <p className="mt-1 text-xs text-red-500">{message}</p>;
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="text-base font-semibold text-zinc-800 dark:text-zinc-100">{children}</h2>
  );
}

function FormSelect({
  label,
  required,
  error,
  value,
  onValueChange,
  placeholder,
  items,
}: {
  label: string;
  required?: boolean;
  error?: string;
  value: string;
  onValueChange: (v: string) => void;
  placeholder?: string;
  items: { value: string; label: string }[];
}) {
  return (
    <div className="space-y-1">
      <FieldLabel required={required}>{label}</FieldLabel>
      <Select value={value} onValueChange={onValueChange}>
        <SelectTrigger className={cn("w-full", error && "border-red-400")}>
          <SelectValue placeholder={placeholder} />
        </SelectTrigger>
        <SelectContent>
          {items.map((i) => (
            <SelectItem key={i.value} value={i.value}>
              {i.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <FieldError message={error} />
    </div>
  );
}

function FormInput({
  label,
  required,
  error,
  className,
  ...props
}: {
  label: string;
  required?: boolean;
  error?: string;
  className?: string;
} & React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <div className="space-y-1">
      <FieldLabel required={required}>{label}</FieldLabel>
      <Input className={cn(error && "border-red-400", className)} {...props} />
      <FieldError message={error} />
    </div>
  );
}

function FormTextarea({
  label,
  required,
  error,
  rows = 4,
  ...props
}: {
  label: string;
  required?: boolean;
  error?: string;
  rows?: number;
} & React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <div className="space-y-1">
      <FieldLabel required={required}>{label}</FieldLabel>
      <textarea
        rows={rows}
        className={cn(
          "w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 focus:border-facil-orange focus:outline-none focus:ring-2 focus:ring-facil-orange/30",
          "dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 dark:placeholder:text-zinc-500",
          error && "border-red-400",
        )}
        {...props}
      />
      <FieldError message={error} />
    </div>
  );
}

export function VehicleForm({ brands, vehicle }: VehicleFormProps) {
  const router = useRouter();
  const isEdit = !!vehicle;
  const [step, setStep] = useState(0);

  const {
    register,
    handleSubmit,
    trigger,
    setValue,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<CreateVehicleInput>({
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    resolver: zodResolver(createVehicleSchema) as any,
    defaultValues: {
      status: (vehicle?.status as CreateVehicleInput["status"]) ?? "DRAFT",
      type: (vehicle?.type as CreateVehicleInput["type"]) ?? "CAR",
      title: vehicle?.title ?? "",
      brandId: vehicle?.brandId ?? brands[0]?.id ?? "",
      model: vehicle?.model ?? "",
      version: vehicle?.version ?? "",
      yearManufacture: vehicle?.yearManufacture ?? undefined,
      yearModel: vehicle?.yearModel ?? undefined,
      mileage: vehicle?.mileage ?? undefined,
      fuelType: (vehicle?.fuelType as CreateVehicleInput["fuelType"]) ?? undefined,
      transmission: (vehicle?.transmission as CreateVehicleInput["transmission"]) ?? undefined,
      color: vehicle?.color ?? "",
      doors: vehicle?.doors ?? undefined,
      priceCash: vehicle?.priceCash != null ? Number(vehicle.priceCash) : undefined,
      priceTradeIn: vehicle?.priceTradeIn != null ? Number(vehicle.priceTradeIn) : undefined,
      pricePromotional: vehicle?.pricePromotional != null ? Number(vehicle.pricePromotional) : undefined,
      city: vehicle?.city ?? "",
      state: vehicle?.state ?? "",
      featured: vehicle?.featured ?? false,
      metaTitle: vehicle?.metaTitle ?? "",
      metaDescription: vehicle?.metaDescription ?? "",
      shortDescription: vehicle?.shortDescription ?? "",
      description: vehicle?.description ?? "",
      imageUrls: vehicle?.images?.map((i) => i.url).join("\n") ?? "",
      features: vehicle?.features?.map((f) => f.label).join("\n") ?? "",
    },
  });

  const imageUrls = watch("imageUrls");
  const brandId = watch("brandId");
  const vehicleType = watch("type");
  const vehicleStatus = watch("status");
  const fuelType = watch("fuelType");
  const transmission = watch("transmission");

  const goNext = useCallback(async () => {
    const fields = STEP_FIELDS[step] ?? [];
    const valid = fields.length === 0 ? true : await trigger(fields);
    if (valid) setStep((s) => Math.min(s + 1, STEPS.length - 1));
  }, [step, trigger]);

  const goPrev = useCallback(() => setStep((s) => Math.max(s - 1, 0)), []);

  const handleStepClick = useCallback((index: number) => {
    if (index < step) setStep(index);
  }, [step]);

  const onSubmit = useCallback(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    async (data: any) => {
      const typed = data as CreateVehicleInput;
      const formData = new FormData();
      Object.entries(typed).forEach(([k, v]) => {
        if (v !== undefined && v !== null) formData.set(k, String(v));
      });
      if (isEdit) formData.set("id", vehicle!.id);

      const result = isEdit ? await updateVehicle(formData) : await createVehicle(formData);

      if (result.ok) {
        toast.success(isEdit ? "Veículo atualizado!" : "Veículo criado com sucesso!");
        if (!isEdit) {
          router.push(`/admin/veiculos/${result.id}`);
        } else {
          router.refresh();
        }
      } else {
        const errMsg =
          typeof result.error === "string"
            ? result.error
            : JSON.stringify(result.error);
        toast.error(`Erro ao salvar: ${errMsg}`);
      }
    },
    [isEdit, vehicle, router],
  );

  return (
    <form
      onSubmit={handleSubmit(onSubmit)}
      className="flex flex-col overflow-hidden rounded-xl border border-zinc-200 bg-white shadow-sm dark:border-zinc-800 dark:bg-zinc-900"
      style={{ height: "calc(100vh - 13rem)" }}
    >
      {/* Stepper header */}
      <div className="shrink-0 border-b border-zinc-100 px-6 pb-5 pt-5 dark:border-zinc-800">
        <Stepper
          steps={STEPS}
          currentStep={step}
          onStepClick={handleStepClick}
          className="mx-auto max-w-2xl"
        />
      </div>

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto px-6 py-5">
        {/* Step 0 — Basic Info */}
        {step === 0 && (
          <div className="space-y-5">
            <SectionTitle>Informações básicas</SectionTitle>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1 sm:col-span-2">
                <FieldLabel required>Título</FieldLabel>
                <Input
                  {...register("title")}
                  placeholder="Ex: Toyota Corolla XEi 2.0 2022"
                  className={cn(errors.title && "border-red-400")}
                />
                <FieldError message={errors.title?.message} />
              </div>
              <VehicleBrandCombobox
                brands={brands}
                value={brandId}
                onChange={(id) => setValue("brandId", id, { shouldValidate: true })}
                error={errors.brandId?.message}
                label="Marca"
                required
              />
              <FormInput
                label="Modelo"
                required
                placeholder="Corolla"
                error={errors.model?.message}
                {...register("model")}
              />
              <FormInput
                label="Versão"
                placeholder="XEi 2.0 Flex"
                {...register("version")}
              />
              <FormSelect
                label="Tipo"
                error={errors.type?.message}
                value={vehicleType}
                onValueChange={(v) => setValue("type", v as CreateVehicleInput["type"], { shouldValidate: true })}
                items={TYPES.map((t) => ({ value: t, label: TYPE_LABELS[t] }))}
              />
              <FormSelect
                label="Status"
                error={errors.status?.message}
                value={vehicleStatus}
                onValueChange={(v) =>
                  setValue("status", v as CreateVehicleInput["status"], { shouldValidate: true })
                }
                items={STATUSES.map((s) => ({ value: s, label: STATUS_LABELS[s] }))}
              />
            </div>
            <FormInput
              label="Descrição curta"
              placeholder="Resumo em uma linha"
              {...register("shortDescription")}
            />
          </div>
        )}

        {/* Step 1 — Technical Specs */}
        {step === 1 && (
          <div className="space-y-5">
            <SectionTitle>Especificações técnicas</SectionTitle>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <FormInput
                label="Ano fabricação"
                type="number"
                placeholder="2022"
                {...register("yearManufacture", { valueAsNumber: true })}
              />
              <FormInput
                label="Ano modelo"
                type="number"
                placeholder="2023"
                {...register("yearModel", { valueAsNumber: true })}
              />
              <FormInput
                label="Quilometragem"
                type="number"
                placeholder="0"
                {...register("mileage", { valueAsNumber: true })}
              />
              <FormSelect
                label="Combustível"
                value={fuelType ? String(fuelType) : SELECT_NONE}
                onValueChange={(v) =>
                  setValue(
                    "fuelType",
                    v === SELECT_NONE ? undefined : (v as CreateVehicleInput["fuelType"]),
                    { shouldValidate: true },
                  )
                }
                placeholder="—"
                items={[
                  { value: SELECT_NONE, label: "—" },
                  ...FUEL.map((f) => ({ value: f, label: FUEL_LABELS[f] })),
                ]}
              />
              <FormSelect
                label="Câmbio"
                value={transmission ? String(transmission) : SELECT_NONE}
                onValueChange={(v) =>
                  setValue(
                    "transmission",
                    v === SELECT_NONE ? undefined : (v as CreateVehicleInput["transmission"]),
                    { shouldValidate: true },
                  )
                }
                placeholder="—"
                items={[
                  { value: SELECT_NONE, label: "—" },
                  ...TRANSMISSION.map((t) => ({ value: t, label: TRANS_LABELS[t] })),
                ]}
              />
              <FormInput
                label="Cor"
                placeholder="Prata"
                {...register("color")}
              />
              <FormInput
                label="Portas"
                type="number"
                min={0}
                max={10}
                placeholder="4"
                {...register("doors", { valueAsNumber: true })}
              />
            </div>
          </div>
        )}

        {/* Step 2 — Pricing */}
        {step === 2 && (
          <div className="space-y-5">
            <SectionTitle>Precificação e localização</SectionTitle>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <FormInput
                label="Preço à vista (R$)"
                type="number"
                step="0.01"
                placeholder="0,00"
                error={errors.priceCash?.message}
                {...register("priceCash", { valueAsNumber: true })}
              />
              <FormInput
                label="Preço promocional (R$)"
                type="number"
                step="0.01"
                placeholder="0,00"
                {...register("pricePromotional", { valueAsNumber: true })}
              />
              <FormInput
                label="Troca a partir de (R$)"
                type="number"
                step="0.01"
                placeholder="0,00"
                {...register("priceTradeIn", { valueAsNumber: true })}
              />
              <FormInput
                label="Cidade"
                placeholder="São Paulo"
                {...register("city")}
              />
              <FormInput
                label="UF"
                placeholder="SP"
                maxLength={2}
                className="uppercase"
                {...register("state")}
              />
            </div>
            <label className="flex cursor-pointer items-center gap-2">
              <input
                type="checkbox"
                {...register("featured")}
                className="h-4 w-4 rounded border-zinc-300 accent-facil-orange"
              />
              <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                Destacar na home
              </span>
            </label>
          </div>
        )}

        {/* Step 3 — Media & SEO */}
        {step === 3 && (
          <div className="space-y-6">
            <div className="space-y-3">
              <SectionTitle>Imagens</SectionTitle>
              <ImageUploader
                value={imageUrls ?? ""}
                onChange={(urls) => setValue("imageUrls", urls)}
              />
            </div>

            <div className="space-y-3">
              <SectionTitle>Opcionais</SectionTitle>
              <FormTextarea
                label="Opcionais (um por linha)"
                rows={5}
                placeholder={"Ar condicionado\nDireção hidráulica\nVidros elétricos"}
                {...register("features")}
              />
            </div>

            <div className="space-y-3">
              <SectionTitle>Descrição e SEO</SectionTitle>
              <FormTextarea
                label="Descrição completa"
                rows={4}
                placeholder="Descrição detalhada do veículo…"
                {...register("description")}
              />
              <FormInput
                label="Meta título (SEO)"
                placeholder="Toyota Corolla 2022 — FácilCar"
                {...register("metaTitle")}
              />
              <FormTextarea
                label="Meta descrição (SEO)"
                rows={2}
                placeholder="Descrição para motores de busca (máx 160 caracteres)"
                maxLength={160}
                {...register("metaDescription")}
              />
            </div>
          </div>
        )}
      </div>

      {/* Footer buttons */}
      <div className="shrink-0 flex items-center justify-between border-t border-zinc-100 px-6 py-4 dark:border-zinc-800">
        <Button
          type="button"
          variant="outline"
          onClick={goPrev}
          disabled={step === 0}
          className={cn(step === 0 && "invisible")}
        >
          <ChevronLeft className="h-4 w-4" />
          Anterior
        </Button>

        <span className="text-xs text-zinc-400 dark:text-zinc-500">
          Etapa {step + 1} de {STEPS.length}
        </span>

        {step < STEPS.length - 1 ? (
          <Button type="button" variant="primary" onClick={goNext}>
            Próximo
            <ChevronRight className="h-4 w-4" />
          </Button>
        ) : (
          <Button type="submit" variant="primary" disabled={isSubmitting}>
            <Save className="h-4 w-4" />
            {isSubmitting ? "Salvando…" : isEdit ? "Salvar alterações" : "Criar veículo"}
          </Button>
        )}
      </div>
    </form>
  );
}
