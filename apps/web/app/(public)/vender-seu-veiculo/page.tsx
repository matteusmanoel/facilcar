import { SellVehicleForm } from "@/features/lead/ui/SellVehicleForm";

export default function VenderVeiculoPage() {
  return (
    <main className="min-h-screen py-12 px-4">
      <div className="mx-auto max-w-6xl">
        <h1 className="text-2xl font-semibold">Vender seu veículo</h1>
        <p className="mt-2 text-zinc-600">
          Informe seus dados e as características do veículo. Entraremos em contato para uma avaliação.
        </p>
        <div className="mt-8">
          <SellVehicleForm />
        </div>
      </div>
    </main>
  );
}
