"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { createVehicle, updateVehicle } from "@/features/vehicle/server/mutations";
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
  priceCash: unknown;
  shortDescription: string | null;
  description: string | null;
  featured: boolean;
  images: { url: string }[];
  features: { label: string }[];
};

type Props = {
  brands: BrandOption[];
  vehicle?: VehicleForForm | null;
};

const STATUSES = ["DRAFT", "PUBLISHED", "RESERVED", "SOLD", "ARCHIVED"] as const;
const TYPES = ["CAR", "MOTORCYCLE", "UTILITY", "OTHER"] as const;
const FUEL = ["GASOLINE", "ETHANOL", "FLEX", "DIESEL", "ELECTRIC", "HYBRID", "OTHER"] as const;
const TRANSMISSION = ["MANUAL", "AUTOMATIC", "AUTOMATED", "CVT", "OTHER"] as const;

export function VehicleForm({ brands, vehicle }: Props) {
  const router = useRouter();
  const [message, setMessage] = useState<{ type: "ok" | "error"; text: string } | null>(null);
  const isEdit = !!vehicle;

  return (
    <form
      action={async (formData: FormData) => {
        setMessage(null);
        const result = isEdit ? await updateVehicle(formData) : await createVehicle(formData);
        if (result.ok) {
          setMessage({ type: "ok", text: isEdit ? "Salvo." : "Veículo criado." });
          if (!isEdit) router.push(`/admin/veiculos/${result.id}`);
          else router.refresh();
        } else {
          setMessage({ type: "error", text: JSON.stringify(result.error) });
        }
      }}
      className="mt-6 max-w-2xl space-y-4"
    >
      {isEdit && <input type="hidden" name="id" value={vehicle.id} />}

      <label className="block text-sm font-medium">
        Slug *
        <input name="slug" required defaultValue={vehicle?.slug} className="mt-1 w-full rounded border px-3 py-2" placeholder="ex: toyota-corolla-2022" />
      </label>
      <label className="block text-sm font-medium">
        Status
        <select name="status" defaultValue={vehicle?.status ?? "DRAFT"} className="mt-1 w-full rounded border px-3 py-2">
          {STATUSES.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </label>
      <label className="block text-sm font-medium">
        Tipo
        <select name="type" defaultValue={vehicle?.type ?? "CAR"} className="mt-1 w-full rounded border px-3 py-2">
          {TYPES.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
      </label>
      <label className="block text-sm font-medium">
        Título *
        <input name="title" required defaultValue={vehicle?.title} className="mt-1 w-full rounded border px-3 py-2" />
      </label>
      <label className="block text-sm font-medium">
        Marca *
        <select name="brandId" required defaultValue={vehicle?.brandId} className="mt-1 w-full rounded border px-3 py-2">
          {brands.map((b) => (
            <option key={b.id} value={b.id}>{b.name}</option>
          ))}
        </select>
      </label>
      <label className="block text-sm font-medium">
        Modelo *
        <input name="model" required defaultValue={vehicle?.model} className="mt-1 w-full rounded border px-3 py-2" />
      </label>
      <label className="block text-sm font-medium">
        Versão
        <input name="version" defaultValue={vehicle?.version ?? ""} className="mt-1 w-full rounded border px-3 py-2" />
      </label>
      <div className="grid grid-cols-2 gap-4">
        <label className="block text-sm font-medium">
          Ano fabricação
          <input name="yearManufacture" type="number" defaultValue={vehicle?.yearManufacture ?? ""} className="mt-1 w-full rounded border px-3 py-2" />
        </label>
        <label className="block text-sm font-medium">
          Ano modelo
          <input name="yearModel" type="number" defaultValue={vehicle?.yearModel ?? ""} className="mt-1 w-full rounded border px-3 py-2" />
        </label>
      </div>
      <label className="block text-sm font-medium">
        Quilometragem
        <input name="mileage" type="number" defaultValue={vehicle?.mileage ?? ""} className="mt-1 w-full rounded border px-3 py-2" />
      </label>
      <div className="grid grid-cols-2 gap-4">
        <label className="block text-sm font-medium">
          Combustível
          <select name="fuelType" defaultValue={vehicle?.fuelType ?? ""} className="mt-1 w-full rounded border px-3 py-2">
            <option value="">—</option>
            {FUEL.map((f) => (
              <option key={f} value={f}>{f}</option>
            ))}
          </select>
        </label>
        <label className="block text-sm font-medium">
          Câmbio
          <select name="transmission" defaultValue={vehicle?.transmission ?? ""} className="mt-1 w-full rounded border px-3 py-2">
            <option value="">—</option>
            {TRANSMISSION.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        </label>
      </div>
      <label className="block text-sm font-medium">
        Cor
        <input name="color" defaultValue={vehicle?.color ?? ""} className="mt-1 w-full rounded border px-3 py-2" />
      </label>
      <label className="block text-sm font-medium">
        Preço à vista (R$)
        <input name="priceCash" type="number" step="0.01" defaultValue={vehicle?.priceCash != null ? Number(vehicle.priceCash) : ""} className="mt-1 w-full rounded border px-3 py-2" />
      </label>
      <label className="flex items-center gap-2">
        <input name="featured" type="checkbox" defaultChecked={vehicle?.featured} className="rounded" />
        <span className="text-sm">Destaque (home)</span>
      </label>
      <label className="block text-sm font-medium">
        Descrição curta
        <input name="shortDescription" defaultValue={vehicle?.shortDescription ?? ""} className="mt-1 w-full rounded border px-3 py-2" />
      </label>
      <label className="block text-sm font-medium">
        Descrição
        <textarea name="description" rows={4} defaultValue={vehicle?.description ?? ""} className="mt-1 w-full rounded border px-3 py-2" />
      </label>
      <label className="block text-sm font-medium">
        Imagens (uma URL por linha)
        <textarea name="imageUrls" rows={3} defaultValue={vehicle?.images?.map((i) => i.url).join("\n") ?? ""} className="mt-1 w-full rounded border px-3 py-2 font-mono text-sm" placeholder="https://..." />
      </label>
      <label className="block text-sm font-medium">
        Opcionais (um por linha)
        <textarea name="features" rows={3} defaultValue={vehicle?.features?.map((f) => f.label).join("\n") ?? ""} className="mt-1 w-full rounded border px-3 py-2" />
      </label>

      {message && (
        <p className={message.type === "ok" ? "text-green-600" : "text-red-600"}>{message.text}</p>
      )}
      <button type="submit" className="rounded bg-zinc-900 px-4 py-2 text-white hover:bg-zinc-800">
        {isEdit ? "Salvar" : "Criar veículo"}
      </button>
    </form>
  );
}
