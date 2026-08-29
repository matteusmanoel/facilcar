import { formatBRL } from "@/lib/input-masks";
import { fuelLabels, labelFor, statusLabels, transLabels, typeLabels } from "./labels";

export const CUSTOMER_SHEET_MAX_FEATURES = 12;
export const CUSTOMER_SHEET_MAX_THUMBS = 4;

export type StockListVehicleInput = {
  id: string;
  title: string;
  status: string;
  type: string;
  model: string;
  version: string | null;
  yearManufacture: number | null;
  yearModel: number | null;
  mileage: number | null;
  fuelType: string | null;
  transmission: string | null;
  engineDisplacementLiters: number | string | { toString(): string } | null;
  color: string | null;
  doors: number | null;
  plateFinal: string | null;
  priceCash: number | string | { toString(): string } | null;
  pricePromotional: number | string | { toString(): string } | null;
  priceTradeIn: number | string | { toString(): string } | null;
  aceitaTroca: boolean;
  aceitaSemEntrada: boolean;
  featured: boolean;
  parcelaBase: number | string | { toString(): string } | null;
  entradaMinima: number | string | { toString(): string } | null;
  rendaMinimaSugerida: number | string | { toString(): string } | null;
  prioridade: number;
  city: string | null;
  state: string | null;
  brand: { name: string };
};

export type StockListRow = {
  id: string;
  identity: string;
  brand: string;
  model: string;
  version: string;
  typeLabel: string;
  yearLabel: string;
  mileageLabel: string;
  fuelLabel: string;
  transmissionLabel: string;
  engineLabel: string;
  color: string;
  doorsLabel: string;
  plateFinal: string;
  priceCashLabel: string;
  pricePromotionalLabel: string;
  priceTradeInLabel: string;
  aceitaTroca: boolean;
  aceitaSemEntrada: boolean;
  featured: boolean;
  parcelaBaseLabel: string;
  entradaMinimaLabel: string;
  rendaMinimaLabel: string;
  prioridade: number;
  location: string;
  status: string;
  statusLabel: string;
};

export type CustomerSheetVehicleInput = {
  status: string;
  slug: string;
  title: string;
  shortDescription: string | null;
  model: string;
  version: string | null;
  yearManufacture: number | null;
  yearModel: number | null;
  mileage: number | null;
  fuelType: string | null;
  transmission: string | null;
  engineDisplacementLiters: number | string | { toString(): string } | null;
  color: string | null;
  doors: number | null;
  plateFinal: string | null;
  priceCash: number | string | { toString(): string } | null;
  pricePromotional: number | string | { toString(): string } | null;
  priceTradeIn: number | string | { toString(): string } | null;
  aceitaTroca: boolean;
  aceitaSemEntrada: boolean;
  city: string | null;
  state: string | null;
  brand: { name: string };
  images: { url: string; sortOrder: number }[];
  features: { label: string; sortOrder: number }[];
};

export type CustomerSheetSpec = { label: string; value: string };

export type CustomerSheetModel = {
  title: string;
  subtitle: string | null;
  yearLabel: string;
  priceCashLabel: string;
  pricePromotionalLabel: string | null;
  priceTradeInLabel: string | null;
  specs: CustomerSheetSpec[];
  plateFinal: string | null;
  shortDescription: string | null;
  features: { visible: string[]; remaining: number };
  aceitaTroca: boolean;
  aceitaSemEntrada: boolean;
  coverUrl: string | null;
  thumbUrls: string[];
  listingUrl: string;
  cityState: string | null;
};

export type PrintSiteContext = {
  siteName: string;
  listingBaseUrl: string;
  whatsapp?: string | null;
  phoneNumber?: string | null;
  addressLine?: string | null;
  city?: string | null;
  state?: string | null;
};

export function toNumber(
  value: number | string | { toString(): string } | null | undefined,
): number | null {
  if (value == null || value === "") return null;
  const n = typeof value === "number" ? value : Number(value.toString());
  return Number.isFinite(n) ? n : null;
}

export function formatPrintPrice(
  value: number | string | { toString(): string } | null | undefined,
): string {
  const n = toNumber(value);
  if (n == null) return "—";
  return `R$ ${formatBRL(n)}`;
}

export function formatMileage(km: number | null | undefined): string {
  if (km == null) return "—";
  return `${km.toLocaleString("pt-BR")} km`;
}

export function formatYearPair(
  manufacture: number | null | undefined,
  model: number | null | undefined,
): string {
  if (manufacture == null && model == null) return "—";
  return `${manufacture ?? "—"} / ${model ?? "—"}`;
}

export function truncateFeatureLabels(
  labels: string[],
  max = CUSTOMER_SHEET_MAX_FEATURES,
): { visible: string[]; remaining: number } {
  const cleaned = labels.map((l) => l.trim()).filter(Boolean);
  if (cleaned.length <= max) return { visible: cleaned, remaining: 0 };
  return { visible: cleaned.slice(0, max), remaining: cleaned.length - max };
}

export function toStockListRow(vehicle: StockListVehicleInput): StockListRow {
  const version = vehicle.version?.trim() ?? "";
  const identity = version
    ? [vehicle.brand.name, vehicle.model, version].filter(Boolean).join(" ")
    : vehicle.title;

  const engine = toNumber(vehicle.engineDisplacementLiters);

  return {
    id: vehicle.id,
    identity,
    brand: vehicle.brand.name,
    model: vehicle.model,
    version: version || "—",
    typeLabel: labelFor(typeLabels, vehicle.type),
    yearLabel: formatYearPair(vehicle.yearManufacture, vehicle.yearModel),
    mileageLabel: formatMileage(vehicle.mileage),
    fuelLabel: labelFor(fuelLabels, vehicle.fuelType),
    transmissionLabel: labelFor(transLabels, vehicle.transmission),
    engineLabel: engine != null ? `${engine.toFixed(1)} L` : "—",
    color: vehicle.color?.trim() || "—",
    doorsLabel: vehicle.doors != null ? String(vehicle.doors) : "—",
    plateFinal: vehicle.plateFinal?.trim() || "—",
    priceCashLabel: formatPrintPrice(vehicle.priceCash),
    pricePromotionalLabel: formatPrintPrice(vehicle.pricePromotional),
    priceTradeInLabel: formatPrintPrice(vehicle.priceTradeIn),
    aceitaTroca: vehicle.aceitaTroca,
    aceitaSemEntrada: vehicle.aceitaSemEntrada,
    featured: vehicle.featured,
    parcelaBaseLabel: formatPrintPrice(vehicle.parcelaBase),
    entradaMinimaLabel: formatPrintPrice(vehicle.entradaMinima),
    rendaMinimaLabel: formatPrintPrice(vehicle.rendaMinimaSugerida),
    prioridade: vehicle.prioridade,
    location: [vehicle.city, vehicle.state].filter(Boolean).join(" / ") || "—",
    status: vehicle.status,
    statusLabel: labelFor(statusLabels, vehicle.status),
  };
}

export function customerListingUrl(listingBaseUrl: string, slug: string): string {
  return `${listingBaseUrl.replace(/\/$/, "")}/estoque/${slug}`;
}

export function toCustomerSheetModel(
  vehicle: CustomerSheetVehicleInput,
  site: Pick<PrintSiteContext, "listingBaseUrl">,
): CustomerSheetModel | null {
  if (vehicle.status !== "PUBLISHED") return null;

  const sortedImages = [...vehicle.images].sort((a, b) => a.sortOrder - b.sortOrder);
  const coverUrl = sortedImages[0]?.url ?? null;
  const thumbUrls = sortedImages.slice(1, 1 + CUSTOMER_SHEET_MAX_THUMBS).map((img) => img.url);

  const subtitle =
    vehicle.shortDescription?.trim() ||
    [vehicle.model, vehicle.version].filter(Boolean).join(" ").trim() ||
    null;

  const engine = toNumber(vehicle.engineDisplacementLiters);
  const cityState = [vehicle.city, vehicle.state].filter(Boolean).join(" / ") || null;
  const cash = toNumber(vehicle.priceCash);
  const promo = toNumber(vehicle.pricePromotional);
  const tradeIn = toNumber(vehicle.priceTradeIn);

  const specs: CustomerSheetSpec[] = [
    { label: "Marca", value: vehicle.brand.name },
    { label: "Ano / Modelo", value: formatYearPair(vehicle.yearManufacture, vehicle.yearModel) },
    { label: "Câmbio", value: labelFor(transLabels, vehicle.transmission) },
    { label: "Combustível", value: labelFor(fuelLabels, vehicle.fuelType) },
    {
      label: "Motorização",
      value: engine != null ? `${engine.toFixed(1)} L` : "não informado",
    },
    { label: "Cor", value: vehicle.color?.trim() || "—" },
    { label: "Quilometragem", value: formatMileage(vehicle.mileage) },
  ];
  if (vehicle.doors != null) {
    specs.push({ label: "Portas", value: String(vehicle.doors) });
  }
  if (cityState) {
    specs.push({ label: "Localização", value: cityState });
  }

  const featureLabels = [...vehicle.features]
    .sort((a, b) => a.sortOrder - b.sortOrder)
    .map((f) => f.label);

  return {
    title: vehicle.title,
    subtitle,
    yearLabel: vehicle.yearModel != null ? String(vehicle.yearModel) : formatYearPair(
      vehicle.yearManufacture,
      vehicle.yearModel,
    ),
    priceCashLabel: cash != null ? formatPrintPrice(cash) : "Consultar valor",
    pricePromotionalLabel: promo != null ? formatPrintPrice(promo) : null,
    priceTradeInLabel: tradeIn != null ? formatPrintPrice(tradeIn) : null,
    specs,
    plateFinal: vehicle.plateFinal?.trim() || null,
    shortDescription: vehicle.shortDescription?.trim() || null,
    features: truncateFeatureLabels(featureLabels),
    aceitaTroca: vehicle.aceitaTroca,
    aceitaSemEntrada: vehicle.aceitaSemEntrada,
    coverUrl,
    thumbUrls,
    listingUrl: customerListingUrl(site.listingBaseUrl, vehicle.slug),
    cityState,
  };
}

export function formatPrintTimestamp(date = new Date()): string {
  return date.toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function printSiteFromSettings(
  settings: {
    siteName?: string | null;
    defaultWhatsappNumber?: string | null;
    phoneNumber?: string | null;
    addressLine?: string | null;
    city?: string | null;
    state?: string | null;
  } | null,
  listingBaseUrl: string,
  fallbackName: string,
): PrintSiteContext {
  return {
    siteName: settings?.siteName?.trim() || fallbackName,
    listingBaseUrl,
    whatsapp: settings?.defaultWhatsappNumber,
    phoneNumber: settings?.phoneNumber,
    addressLine: settings?.addressLine,
    city: settings?.city,
    state: settings?.state,
  };
}

export function formatPrintAddress(site: PrintSiteContext): string | null {
  const parts = [site.addressLine, [site.city, site.state].filter(Boolean).join(" / ")].filter(
    Boolean,
  );
  return parts.length ? parts.join(" · ") : null;
}
