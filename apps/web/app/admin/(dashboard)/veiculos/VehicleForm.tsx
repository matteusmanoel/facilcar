"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { ChevronLeft, ChevronRight, Save } from "lucide-react";
import { createVehicle, updateVehicle } from "@/features/vehicle/server/mutations";
import { vehicleFormFooterAction } from "@/features/vehicle/lib/form-navigation";
import { createVehicleSchema, type CreateVehicleInput } from "@/schemas/vehicle";
import { Stepper } from "@/components/ui/stepper";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ImageUploader } from "@/features/admin/ui/ImageUploader";
import { VehicleBrandCombobox, type BrandOption } from "@/components/admin/VehicleBrandCombobox";
import { cn } from "@/lib/cn";
import { formatBRL, parseBRL } from "@/lib/input-masks";

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
  engineDisplacementLiters: unknown;
  color: string | null;
  doors: number | null;
  plateFinal: string | null;
  plate: string | null;
  stockType: string | null;
  commercialHistory: string | null;
  priceCash: unknown;
  priceTradeIn: unknown;
  pricePromotional: unknown;
  priceFipe: unknown;
  priceRetailWithWarranty: unknown;
  priceRetailAsIs: unknown;
  priceOwnerAsking: unknown;
  aceitaTroca: boolean;
  aceitaSemEntrada: boolean;
  parcelaBase: unknown;
  entradaMinima: unknown;
  rendaMinimaSugerida: unknown;
  prioridade: number;
  city: string | null;
  state: string | null;
  metaTitle: string | null;
  metaDescription: string | null;
  shortDescription: string | null;
  description: string | null;
  featured: boolean;
  images: { url: string }[];
  features: { label: string }[];
  owners?: { partnerId: string }[];
};

type PartnerOption = { id: string; name: string };

interface VehicleFormProps {
  brands: BrandOption[];
  partners?: PartnerOption[];
  vehicle?: VehicleForForm | null;
  readOnly?: boolean;
  canManageBrands?: boolean;
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
  1: ["engineDisplacementLiters"],
  2: [],
  3: [],
};

const STOCK_TYPES = ["OWNED", "CONSIGNED"] as const;
const STOCK_LABELS: Record<string, string> = {
  OWNED: "Próprio",
  CONSIGNED: "Consignado",
};
const HISTORY_TYPES = ["CLEAN", "AUCTION", "RECOVERED_CLAIM", "AUCTION_AND_RECOVERED_CLAIM"] as const;
const HISTORY_LABELS: Record<string, string> = {
  CLEAN: "Histórico limpo",
  AUCTION: "Leilão",
  RECOVERED_CLAIM: "Recuperado de sinistro",
  AUCTION_AND_RECOVERED_CLAIM: "Leilão e recuperado de sinistro",
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
    <label htmlFor={htmlFor} className="block text-sm font-medium text-foreground">
      {children}
      {required && <span className="ml-1 text-facil-orange">*</span>}
    </label>
  );
}

function FieldError({ message }: { message?: string }) {
  if (!message) return null;
  return <p className="mt-1 text-xs text-red-500">{message}</p>;
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return <h2 className="text-base font-semibold text-zinc-950 dark:text-zinc-50">{children}</h2>;
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

function FormCurrencyInput({
  label,
  required,
  error,
  value,
  onValueChange,
}: {
  label: string;
  required?: boolean;
  error?: string;
  value: number | undefined;
  onValueChange: (value: number | undefined) => void;
}) {
  return (
    <div className="space-y-1">
      <FieldLabel required={required}>{label}</FieldLabel>
      <Input
        inputMode="decimal"
        placeholder="0,00"
        value={formatBRL(value)}
        onChange={(e) => onValueChange(parseBRL(e.target.value))}
        className={cn(error && "border-red-400")}
      />
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
          "box-border w-full rounded-lg border border-facil-border bg-facil-card px-3 py-2 text-sm text-foreground placeholder:text-facil-muted",
          "focus:border-facil-orange focus:outline-none focus:ring-2 focus:ring-inset focus:ring-facil-orange/30",
          error && "border-red-400",
        )}
        {...props}
      />
      <FieldError message={error} />
    </div>
  );
}

export function VehicleForm({ brands, partners = [], vehicle, readOnly = false, canManageBrands = false }: VehicleFormProps) {
  const router = useRouter();
  const isEdit = !!vehicle;
  const [step, setStep] = useState(0);
  const [maxValidatedStep, setMaxValidatedStep] = useState(0);
  const [stepErrors, setStepErrors] = useState<Record<number, boolean>>({});
  const [discardOpen, setDiscardOpen] = useState(false);
  const [pendingNavigation, setPendingNavigation] = useState<string | null>(null);
  const allowNavigationRef = useRef(false);

  const {
    register,
    handleSubmit,
    trigger,
    setValue,
    watch,
    formState: { errors, isSubmitting, isDirty },
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
      engineDisplacementLiters:
        vehicle?.engineDisplacementLiters != null ? Number(vehicle.engineDisplacementLiters) : undefined,
      color: vehicle?.color ?? "",
      doors: vehicle?.doors ?? undefined,
      plate: vehicle?.plate ?? "",
      plateFinal: vehicle?.plateFinal ?? "",
      stockType: (vehicle?.stockType as CreateVehicleInput["stockType"]) ?? undefined,
      commercialHistory: (vehicle?.commercialHistory as CreateVehicleInput["commercialHistory"]) ?? undefined,
      partnerIds: vehicle?.owners?.map((o) => o.partnerId) ?? [],
      priceCash: vehicle?.priceCash != null ? Number(vehicle.priceCash) : undefined,
      priceTradeIn: vehicle?.priceTradeIn != null ? Number(vehicle.priceTradeIn) : undefined,
      pricePromotional: vehicle?.pricePromotional != null ? Number(vehicle.pricePromotional) : undefined,
      priceFipe: vehicle?.priceFipe != null ? Number(vehicle.priceFipe) : undefined,
      priceRetailWithWarranty:
        vehicle?.priceRetailWithWarranty != null ? Number(vehicle.priceRetailWithWarranty) : undefined,
      priceRetailAsIs: vehicle?.priceRetailAsIs != null ? Number(vehicle.priceRetailAsIs) : undefined,
      priceOwnerAsking: vehicle?.priceOwnerAsking != null ? Number(vehicle.priceOwnerAsking) : undefined,
      aceitaTroca: vehicle?.aceitaTroca ?? false,
      aceitaSemEntrada: vehicle?.aceitaSemEntrada ?? false,
      parcelaBase: vehicle?.parcelaBase != null ? Number(vehicle.parcelaBase) : undefined,
      entradaMinima: vehicle?.entradaMinima != null ? Number(vehicle.entradaMinima) : undefined,
      rendaMinimaSugerida: vehicle?.rendaMinimaSugerida != null ? Number(vehicle.rendaMinimaSugerida) : undefined,
      prioridade: vehicle?.prioridade ?? 0,
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
  const stockType = watch("stockType");
  const commercialHistory = watch("commercialHistory");
  const partnerIds = watch("partnerIds") ?? [];
  const priceCash = watch("priceCash");
  const pricePromotional = watch("pricePromotional");
  const priceTradeIn = watch("priceTradeIn");
  const priceFipe = watch("priceFipe");
  const priceRetailAsIs = watch("priceRetailAsIs");
  const priceOwnerAsking = watch("priceOwnerAsking");
  const parcelaBase = watch("parcelaBase");
  const entradaMinima = watch("entradaMinima");
  const rendaMinimaSugerida = watch("rendaMinimaSugerida");

  useEffect(() => {
    if (readOnly || !isDirty) return;
    const onBeforeUnload = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => window.removeEventListener("beforeunload", onBeforeUnload);
  }, [isDirty, readOnly]);

  useEffect(() => {
    if (readOnly || !isDirty) return;
    const onClick = (e: MouseEvent) => {
      if (allowNavigationRef.current) return;
      const anchor = (e.target as HTMLElement).closest("a");
      if (!anchor || anchor.target === "_blank") return;
      const href = anchor.getAttribute("href");
      if (!href || href.startsWith("#") || href.startsWith("mailto:") || href.startsWith("tel:")) {
        return;
      }
      e.preventDefault();
      e.stopPropagation();
      setPendingNavigation(href);
      setDiscardOpen(true);
    };
    document.addEventListener("click", onClick, true);
    return () => document.removeEventListener("click", onClick, true);
  }, [isDirty, readOnly]);

  useEffect(() => {
    if (readOnly || !isDirty) return;
    window.history.pushState(null, "", window.location.href);
    const onPopState = () => {
      window.history.pushState(null, "", window.location.href);
      setPendingNavigation("__back__");
      setDiscardOpen(true);
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, [isDirty, readOnly]);

  const confirmDiscard = useCallback(() => {
    allowNavigationRef.current = true;
    setDiscardOpen(false);
    if (pendingNavigation === "__back__") {
      router.back();
    } else if (pendingNavigation) {
      router.push(pendingNavigation);
    }
    setPendingNavigation(null);
  }, [pendingNavigation, router]);

  const requestLeave = useCallback(
    (href: string) => {
      if (!isDirty) {
        router.push(href);
        return;
      }
      setPendingNavigation(href);
      setDiscardOpen(true);
    },
    [isDirty, router],
  );

  const goNext = useCallback(async () => {
    const fields = STEP_FIELDS[step] ?? [];
    const valid = fields.length === 0 ? true : await trigger(fields);
    if (valid) {
      setStepErrors((prev) => ({ ...prev, [step]: false }));
      setMaxValidatedStep((prev) => Math.max(prev, step + 1));
      setStep((s) => Math.min(s + 1, STEPS.length - 1));
    } else {
      setStepErrors((prev) => ({ ...prev, [step]: true }));
      toast.error("Corrija os campos obrigatórios desta etapa.");
    }
  }, [step, trigger]);

  const goPrev = useCallback(() => setStep((s) => Math.max(s - 1, 0)), []);

  const handleStepClick = useCallback(
    async (index: number) => {
      if (index === step) return;
      if (index < step) {
        setStep(index);
        return;
      }
      for (let i = step; i < index; i++) {
        const fields = STEP_FIELDS[i] ?? [];
        if (fields.length > 0) {
          const valid = await trigger(fields);
          if (!valid) {
            setStepErrors((prev) => ({ ...prev, [i]: true }));
            setStep(i);
            toast.error("Complete os campos obrigatórios desta etapa.");
            return;
          }
          setStepErrors((prev) => ({ ...prev, [i]: false }));
        }
      }
      setMaxValidatedStep((prev) => Math.max(prev, index));
      setStep(index);
    },
    [step, trigger],
  );

  const fieldStep = useCallback((field: string): number => {
    for (const [stepKey, fields] of Object.entries(STEP_FIELDS)) {
      if (fields.includes(field as keyof CreateVehicleInput)) return Number(stepKey);
    }
    // SEO / media extras live on the last step
    if (["imageUrls", "features", "description", "metaTitle", "metaDescription", "shortDescription"].includes(field)) {
      return 3;
    }
    if (
      [
        "priceRetailWithWarranty",
        "priceRetailAsIs",
        "priceOwnerAsking",
        "priceFipe",
        "priceTradeIn",
        "pricePromotional",
        "parcelaBase",
        "entradaMinima",
        "rendaMinimaSugerida",
        "aceitaTroca",
        "aceitaSemEntrada",
        "featured",
        "prioridade",
      ].includes(field)
    ) {
      return 2;
    }
    if (
      ["yearManufacture", "yearModel", "mileage", "fuelType", "color", "doors", "plate", "plateFinal", "city", "state"].includes(
        field,
      )
    ) {
      return 1;
    }
    return 0;
  }, []);

  const onInvalid = useCallback(
    (formErrors: Record<string, unknown>) => {
      const keys = Object.keys(formErrors);
      if (!keys.length) {
        toast.error("Não foi possível validar o formulário.");
        return;
      }
      const targetStep = Math.min(...keys.map(fieldStep));
      setStepErrors((prev) => ({ ...prev, [targetStep]: true }));
      setStep(targetStep);
      const first = formErrors[keys[0]!] as { message?: string } | undefined;
      toast.error(first?.message || "Corrija os campos obrigatórios para salvar.");
    },
    [fieldStep],
  );

  const onSubmit = useCallback(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    async (data: any) => {
      const typed = data as CreateVehicleInput;
      const formData = new FormData();
      Object.entries(typed).forEach(([k, v]) => {
        if (typeof v === "boolean") {
          formData.set(k, v ? "true" : "false");
        } else if (typeof v === "number" && Number.isNaN(v)) {
          // skip — empty number inputs become NaN with valueAsNumber
        } else if (v !== undefined && v !== null) {
          formData.set(k, String(v));
        }
      });
      // Ensure booleans are always sent (unchecked checkboxes may be omitted)
      formData.set("featured", typed.featured ? "true" : "false");
      formData.set("aceitaTroca", typed.aceitaTroca ? "true" : "false");
      formData.set("aceitaSemEntrada", typed.aceitaSemEntrada ? "true" : "false");
      formData.set("partnerIds", (typed.partnerIds ?? []).join(","));
      if (typed.fuelType === undefined) formData.set("fuelType", "");
      if (isEdit) formData.set("id", vehicle!.id);

      const result = isEdit ? await updateVehicle(formData) : await createVehicle(formData);

      if (result.ok) {
        allowNavigationRef.current = true;
        toast.success(isEdit ? "Veículo atualizado!" : "Veículo criado com sucesso!");
        router.push("/admin/veiculos");
        router.refresh();
      } else {
        const errMsg = typeof result.error === "string" ? result.error : JSON.stringify(result.error);
        toast.error(`Erro ao salvar: ${errMsg}`);
      }
    },
    [isEdit, vehicle, router],
  );

  return (
    <>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (readOnly) return;
          if (vehicleFormFooterAction(step, STEPS.length) === "next") {
            void goNext();
            return;
          }
          void handleSubmit(onSubmit, onInvalid)(e);
        }}
        className="flex min-h-[70vh] flex-col overflow-hidden rounded-xl border border-facil-border bg-facil-card shadow-sm md:min-h-0 md:h-[calc(100vh-13rem)]">
        {readOnly && (
          <div className="shrink-0 border-b border-amber-200 bg-amber-50 px-6 py-2 text-sm text-amber-800 dark:border-amber-900/50 dark:bg-amber-950/30 dark:text-amber-300">
            Modo somente leitura — você pode consultar os dados do veículo, mas não alterá-los.
          </div>
        )}
        <fieldset disabled={readOnly} className="flex min-h-0 flex-1 flex-col">
          {/* Stepper header */}
          <div className="shrink-0 border-b border-facil-border px-4 pb-4 pt-4 sm:px-6 sm:pb-5 sm:pt-5">
            <p className="mb-3 text-center text-xs font-medium text-facil-orange sm:hidden">{STEPS[step]}</p>
            <Stepper
              steps={STEPS}
              currentStep={step}
              maxValidatedStep={maxValidatedStep}
              stepErrors={stepErrors}
              onStepClick={handleStepClick}
              className="mx-auto max-w-2xl"
            />
          </div>

          {/* Scrollable content */}
          <div className="flex-1 overflow-y-auto px-4 py-4 sm:px-6 sm:py-5">
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
                    canManage={canManageBrands && !readOnly}
                  />
                  <FormInput
                    label="Modelo"
                    required
                    placeholder="Corolla"
                    error={errors.model?.message}
                    {...register("model")}
                  />
                  <FormInput label="Versão" placeholder="GLI" {...register("version")} />
                  <FormSelect
                    label="Tipo"
                    required
                    error={errors.type?.message}
                    value={vehicleType}
                    onValueChange={(v) => setValue("type", v as CreateVehicleInput["type"], { shouldValidate: true })}
                    items={TYPES.map((t) => ({ value: t, label: TYPE_LABELS[t] }))}
                  />
                  <FormSelect
                    label="Status"
                    required
                    error={errors.status?.message}
                    value={vehicleStatus}
                    onValueChange={(v) =>
                      setValue("status", v as CreateVehicleInput["status"], { shouldValidate: true })
                    }
                    items={STATUSES.map((s) => ({ value: s, label: STATUS_LABELS[s] }))}
                  />
                  <FormSelect
                    label="Tipo de estoque"
                    error={errors.stockType?.message}
                    value={stockType ? String(stockType) : SELECT_NONE}
                    onValueChange={(v) =>
                      setValue("stockType", (v === SELECT_NONE ? undefined : v) as CreateVehicleInput["stockType"], {
                        shouldValidate: true,
                      })
                    }
                    items={[
                      { value: SELECT_NONE, label: "Não informado" },
                      ...STOCK_TYPES.map((s) => ({ value: s, label: STOCK_LABELS[s] })),
                    ]}
                  />
                  <FormSelect
                    label="Histórico comercial"
                    error={errors.commercialHistory?.message}
                    value={commercialHistory ? String(commercialHistory) : SELECT_NONE}
                    onValueChange={(v) =>
                      setValue(
                        "commercialHistory",
                        (v === SELECT_NONE ? undefined : v) as CreateVehicleInput["commercialHistory"],
                        { shouldValidate: true },
                      )
                    }
                    items={[
                      { value: SELECT_NONE, label: "Não informado" },
                      ...HISTORY_TYPES.map((s) => ({ value: s, label: HISTORY_LABELS[s] })),
                    ]}
                  />
                </div>
                {stockType === "OWNED" && partners.length > 0 ? (
                  <div className="space-y-2">
                    <FieldLabel>Sócios proprietários</FieldLabel>
                    <p className="text-xs text-facil-muted">
                      Participação societária fica em branco até ser informada. Não assume divisão igual.
                    </p>
                    <div className="flex flex-wrap gap-3">
                      {partners.map((partner) => {
                        const checked = partnerIds.includes(partner.id);
                        return (
                          <label key={partner.id} className="flex cursor-pointer items-center gap-2 text-sm">
                            <input
                              type="checkbox"
                              checked={checked}
                              onChange={() => {
                                const next = checked
                                  ? partnerIds.filter((id) => id !== partner.id)
                                  : [...partnerIds, partner.id];
                                setValue("partnerIds", next, { shouldDirty: true });
                              }}
                              className="h-4 w-4 rounded border-zinc-300 accent-facil-orange"
                            />
                            {partner.name}
                          </label>
                        );
                      })}
                    </div>
                  </div>
                ) : null}
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
                <p className="text-sm text-facil-muted">Motorização</p>
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  <FormInput
                    label="Cilindrada"
                    type="number"
                    step="0.1"
                    min={0.6}
                    max={8}
                    placeholder="1.4"
                    error={errors.engineDisplacementLiters?.message}
                    {...register("engineDisplacementLiters", { valueAsNumber: true })}
                  />
                  <FormSelect
                    label="Combustível"
                    error={errors.fuelType?.message}
                    value={fuelType ? String(fuelType) : SELECT_NONE}
                    onValueChange={(v) =>
                      setValue("fuelType", (v === SELECT_NONE ? undefined : v) as CreateVehicleInput["fuelType"], {
                        shouldValidate: true,
                      })
                    }
                    placeholder="Não informado"
                    items={[
                      { value: SELECT_NONE, label: "Não informado" },
                      ...FUEL.map((f) => ({ value: f, label: FUEL_LABELS[f] })),
                    ]}
                  />
                  <FormSelect
                    label="Câmbio"
                    error={errors.transmission?.message}
                    value={transmission ? String(transmission) : SELECT_NONE}
                    onValueChange={(v) =>
                      setValue(
                        "transmission",
                        (v === SELECT_NONE ? undefined : v) as CreateVehicleInput["transmission"],
                        { shouldValidate: true },
                      )
                    }
                    placeholder="—"
                    items={[
                      { value: SELECT_NONE, label: "—" },
                      ...TRANSMISSION.map((t) => ({ value: t, label: TRANS_LABELS[t] })),
                    ]}
                  />
                </div>
                <p className="text-xs text-facil-muted">
                  Cilindrada só com o número comercial (ex.: 1.0, 1.4, 1.8, 2.0). Combustível e câmbio são opcionais.
                </p>
                <p className="text-sm text-facil-muted">Demais dados</p>
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
                  <FormInput label="Cor" placeholder="Prata" {...register("color")} />
                  <FormInput
                    label="Portas"
                    type="number"
                    min={0}
                    max={10}
                    placeholder="4"
                    {...register("doors", { valueAsNumber: true })}
                  />
                  <FormInput label="Placa" placeholder="QIV-0G93" {...register("plate")} error={errors.plate?.message} />
                  <FormInput label="Final da placa" placeholder="7" maxLength={1} {...register("plateFinal")} />
                </div>
              </div>
            )}

            {/* Step 2 — Pricing */}
            {step === 2 && (
              <div className="space-y-5">
                <SectionTitle>Precificação e localização</SectionTitle>
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  <FormCurrencyInput
                    label={stockType === "CONSIGNED" ? "Preço anunciado com garantia (R$)" : "Preço à vista (R$)"}
                    error={errors.priceCash?.message}
                    value={typeof priceCash === "number" ? priceCash : undefined}
                    onValueChange={(n) => {
                      setValue("priceCash", n as CreateVehicleInput["priceCash"], {
                        shouldValidate: true,
                        shouldDirty: true,
                      });
                      if (stockType === "CONSIGNED") {
                        setValue("priceRetailWithWarranty", n, { shouldDirty: true });
                      }
                    }}
                  />
                  <FormCurrencyInput
                    label="FIPE (R$)"
                    error={errors.priceFipe?.message}
                    value={typeof priceFipe === "number" ? priceFipe : undefined}
                    onValueChange={(n) => setValue("priceFipe", n, { shouldValidate: true, shouldDirty: true })}
                  />
                  {stockType === "CONSIGNED" ? (
                    <>
                      <FormCurrencyInput
                        label="Repasse sem garantia (R$)"
                        error={errors.priceRetailAsIs?.message}
                        value={typeof priceRetailAsIs === "number" ? priceRetailAsIs : undefined}
                        onValueChange={(n) =>
                          setValue("priceRetailAsIs", n, { shouldValidate: true, shouldDirty: true })
                        }
                      />
                      <FormCurrencyInput
                        label="Pedido do proprietário (interno, R$)"
                        error={errors.priceOwnerAsking?.message}
                        value={typeof priceOwnerAsking === "number" ? priceOwnerAsking : undefined}
                        onValueChange={(n) =>
                          setValue("priceOwnerAsking", n, { shouldValidate: true, shouldDirty: true })
                        }
                      />
                    </>
                  ) : null}
                  <FormCurrencyInput
                    label="Preço promocional (R$)"
                    error={errors.pricePromotional?.message}
                    value={typeof pricePromotional === "number" ? pricePromotional : undefined}
                    onValueChange={(n) => setValue("pricePromotional", n, { shouldValidate: true, shouldDirty: true })}
                  />
                  <FormCurrencyInput
                    label="Troca a partir de (R$)"
                    error={errors.priceTradeIn?.message}
                    value={typeof priceTradeIn === "number" ? priceTradeIn : undefined}
                    onValueChange={(n) => setValue("priceTradeIn", n, { shouldValidate: true, shouldDirty: true })}
                  />
                  <FormInput label="Cidade" placeholder="São Paulo" {...register("city")} />
                  <FormInput label="UF" placeholder="SP" maxLength={2} className="uppercase" {...register("state")} />
                </div>
                <label className="flex cursor-pointer items-center gap-2">
                  <input
                    type="checkbox"
                    {...register("featured")}
                    className="h-4 w-4 rounded border-zinc-300 accent-facil-orange"
                  />
                  <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Destacar na home</span>
                </label>

                <div className="space-y-4 rounded-lg border border-zinc-100 bg-zinc-50/50 p-4 dark:border-zinc-800 dark:bg-zinc-800/30">
                  <h3 className="text-sm font-semibold text-zinc-800 dark:text-zinc-100">Financiamento e comercial</h3>
                  <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                    <FormCurrencyInput
                      label="Parcela base (R$)"
                      error={errors.parcelaBase?.message}
                      value={typeof parcelaBase === "number" ? parcelaBase : undefined}
                      onValueChange={(n) => setValue("parcelaBase", n, { shouldValidate: true, shouldDirty: true })}
                    />
                    <FormCurrencyInput
                      label="Entrada mínima (R$)"
                      error={errors.entradaMinima?.message}
                      value={typeof entradaMinima === "number" ? entradaMinima : undefined}
                      onValueChange={(n) => setValue("entradaMinima", n, { shouldValidate: true, shouldDirty: true })}
                    />
                    <FormCurrencyInput
                      label="Renda mínima sugerida (R$)"
                      error={errors.rendaMinimaSugerida?.message}
                      value={typeof rendaMinimaSugerida === "number" ? rendaMinimaSugerida : undefined}
                      onValueChange={(n) =>
                        setValue("rendaMinimaSugerida", n, { shouldValidate: true, shouldDirty: true })
                      }
                    />
                    <FormInput
                      label="Prioridade (0 = normal)"
                      type="number"
                      min={0}
                      placeholder="0"
                      {...register("prioridade", { valueAsNumber: true })}
                    />
                  </div>
                  <div className="flex flex-wrap gap-6">
                    <label className="flex cursor-pointer items-center gap-2">
                      <input
                        type="checkbox"
                        {...register("aceitaTroca")}
                        className="h-4 w-4 rounded border-zinc-300 accent-facil-orange"
                      />
                      <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Aceita troca</span>
                    </label>
                    <label className="flex cursor-pointer items-center gap-2">
                      <input
                        type="checkbox"
                        {...register("aceitaSemEntrada")}
                        className="h-4 w-4 rounded border-zinc-300 accent-facil-orange"
                      />
                      <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Aceita sem entrada</span>
                    </label>
                  </div>
                </div>
              </div>
            )}

            {/* Step 3 — Media & SEO */}
            {step === 3 && (
              <div className="space-y-6">
                <div className="space-y-3">
                  <SectionTitle>Imagens</SectionTitle>
                  <ImageUploader
                    value={imageUrls ?? ""}
                    onChange={(urls) => setValue("imageUrls", urls, { shouldDirty: true })}
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
          {!readOnly && (
            <div className="shrink-0 flex flex-col gap-3 border-t border-facil-border px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:px-6 sm:py-4">
              <div className="flex flex-wrap items-center gap-2">
                <Button
                  type="button"
                  variant="outline"
                  className="flex-1 sm:flex-none"
                  onClick={() => requestLeave("/admin/veiculos")}>
                  Cancelar
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  className="flex-1 sm:flex-none"
                  onClick={goPrev}
                  disabled={step === 0}>
                  <ChevronLeft className="h-4 w-4" />
                  Anterior
                </Button>
              </div>

              <span className="text-center text-xs text-zinc-400 dark:text-zinc-500 sm:text-left">
                Etapa {step + 1} de {STEPS.length}
              </span>

              {vehicleFormFooterAction(step, STEPS.length) === "next" ? (
                <Button type="button" variant="primary" className="w-full sm:w-auto" onClick={() => void goNext()}>
                  Próximo
                  <ChevronRight className="h-4 w-4" />
                </Button>
              ) : (
                <Button
                  type="button"
                  variant="primary"
                  className="w-full sm:w-auto"
                  disabled={isSubmitting}
                  onClick={() => void handleSubmit(onSubmit, onInvalid)()}>
                  <Save className="h-4 w-4" />
                  {isSubmitting ? "Salvando…" : isEdit ? "Salvar" : "Criar veículo"}
                </Button>
              )}
            </div>
          )}
        </fieldset>
      </form>

      <Dialog
        open={discardOpen}
        onOpenChange={(open) => {
          setDiscardOpen(open);
          if (!open) setPendingNavigation(null);
        }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="dark:text-zinc-100">
              {isEdit ? "Descartar alterações?" : "Descartar cadastro?"}
            </DialogTitle>
            <DialogDescription className="dark:text-zinc-400">
              As alterações não salvas serão perdidas.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button type="button" variant="outline" onClick={() => setDiscardOpen(false)}>
              Continuar editando
            </Button>
            <Button type="button" variant="destructive" onClick={confirmDiscard}>
              Descartar
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
