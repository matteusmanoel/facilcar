import type { Brand, Vehicle, VehicleFeature } from "@prisma/client";
import { fuelLabels, transLabels } from "@/features/vehicle/lib/labels";
import { VehicleAccordionItem } from "@/features/vehicle/ui/VehicleAccordionItem";

type VehicleWith = Vehicle & {
  brand: Brand;
  features: VehicleFeature[];
};

type Props = {
  vehicle: VehicleWith;
  siteName: string;
};

export function VehicleDetailAccordion({ vehicle, siteName }: Props) {
  const hasFeatures = vehicle.features.length > 0;
  const hasDescription = Boolean(vehicle.description?.trim());

  return (
    <section className="rounded-2xl border border-zinc-200 bg-white shadow-sm">
      <div className="border-b border-zinc-100 px-4 py-4 md:px-5">
        <h2 className="text-lg font-bold text-zinc-900">Sobre o veículo</h2>
        <p className="mt-1 text-sm text-facil-muted">
          Ficha completa, equipamentos e descrição — expanda cada seção.
        </p>
      </div>
      <div className="px-4 pb-2 md:px-5">
        <VehicleAccordionItem title="Ficha técnica" defaultOpen>
          <div className="grid grid-cols-2 gap-x-4 gap-y-3 rounded-xl bg-zinc-50 p-4 text-sm">
            <span className="text-facil-muted">Marca</span>
            <span className="font-semibold text-zinc-900">{vehicle.brand.name}</span>
            <span className="text-facil-muted">Ano / Modelo</span>
            <span className="font-semibold text-zinc-900">
              {vehicle.yearManufacture ?? "—"} / {vehicle.yearModel ?? "—"}
            </span>
            <span className="text-facil-muted">Câmbio</span>
            <span className="font-semibold text-zinc-900">
              {vehicle.transmission
                ? transLabels[vehicle.transmission] ?? vehicle.transmission
                : "—"}
            </span>
            <span className="text-facil-muted">Combustível</span>
            <span className="font-semibold text-zinc-900">
              {vehicle.fuelType ? fuelLabels[vehicle.fuelType] ?? vehicle.fuelType : "—"}
            </span>
            <span className="text-facil-muted">Cor</span>
            <span className="font-semibold text-zinc-900">{vehicle.color ?? "—"}</span>
            <span className="text-facil-muted">Quilometragem</span>
            <span className="font-semibold text-zinc-900">
              {vehicle.mileage != null ? `${vehicle.mileage.toLocaleString("pt-BR")} km` : "—"}
            </span>
            {vehicle.doors != null && (
              <>
                <span className="text-facil-muted">Portas</span>
                <span className="font-semibold text-zinc-900">{vehicle.doors}</span>
              </>
            )}
            {(vehicle.city || vehicle.state) && (
              <>
                <span className="text-facil-muted">Localização</span>
                <span className="font-semibold text-zinc-900">
                  {[vehicle.city, vehicle.state].filter(Boolean).join(" / ")}
                </span>
              </>
            )}
          </div>
        </VehicleAccordionItem>

        {hasFeatures && (
          <VehicleAccordionItem title="Opcionais e equipamentos">
            <ul className="flex flex-wrap gap-2">
              {vehicle.features.map((f) => (
                <li
                  key={f.id}
                  className="rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-1.5 text-sm text-zinc-800"
                >
                  {f.label}
                </li>
              ))}
            </ul>
          </VehicleAccordionItem>
        )}

        {hasDescription && (
          <VehicleAccordionItem title="Descrição">
            <p className="whitespace-pre-wrap leading-relaxed text-facil-muted">{vehicle.description}</p>
          </VehicleAccordionItem>
        )}

        <VehicleAccordionItem title="Compre com segurança">
          <ul className="space-y-2 text-sm text-facil-muted">
            <li>Veículo conferido pela equipe {siteName}.</li>
            <li>Apoio para financiamento e avaliação do seu usado na troca.</li>
            <li>Atendimento direto — sem intermediários desconhecidos.</li>
          </ul>
        </VehicleAccordionItem>
      </div>
    </section>
  );
}
