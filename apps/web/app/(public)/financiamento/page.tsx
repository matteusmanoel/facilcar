import { FinancingForm } from "@/features/lead/ui/FinancingForm";

export default function FinanciamentoPage() {
  return (
    <main className="min-h-screen py-12 px-4">
      <div className="mx-auto max-w-6xl">
        <h1 className="text-2xl font-semibold">Financiamento</h1>
        <p className="mt-2 text-zinc-600">
          Solicite uma análise de financiamento. Trabalhamos com as melhores condições.
        </p>
        <div className="mt-8">
          <FinancingForm />
        </div>
      </div>
    </main>
  );
}
