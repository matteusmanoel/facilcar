"use client";

import { useState } from "react";
import { createFinancingLead } from "../server/actions";

type Props = { vehicleId?: string; vehicleTitle?: string };

export function FinancingForm({ vehicleId, vehicleTitle }: Props) {
  const [status, setStatus] = useState<"idle" | "success" | "error">("idle");
  const [errorMessage, setErrorMessage] = useState("");

  return (
    <form
      action={async (formData) => {
        setStatus("idle");
        const result = await createFinancingLead(formData);
        if (result.success) {
          setStatus("success");
        } else {
          setStatus("error");
          setErrorMessage(result.error);
        }
      }}
      className="flex flex-col gap-3 max-w-md"
    >
      {vehicleId && <input type="hidden" name="vehicleId" value={vehicleId} />}
      {vehicleTitle && <p className="text-sm text-zinc-600">Veículo: {vehicleTitle}</p>}
      <label className="text-sm font-medium">
        Nome *
        <input name="name" required className="mt-1 w-full rounded border border-zinc-300 px-3 py-2" />
      </label>
      <label className="text-sm font-medium">
        Telefone *
        <input name="phone" type="tel" required className="mt-1 w-full rounded border border-zinc-300 px-3 py-2" />
      </label>
      <label className="text-sm font-medium">
        E-mail
        <input name="email" type="email" className="mt-1 w-full rounded border border-zinc-300 px-3 py-2" />
      </label>
      <label className="flex items-center gap-2">
        <input name="hasDriverLicense" type="checkbox" value="sim" className="rounded" />
        <span className="text-sm">Possui CNH?</span>
      </label>
      <label className="text-sm font-medium">
        Renda mensal (R$)
        <input name="monthlyIncome" type="number" min={0} className="mt-1 w-full rounded border border-zinc-300 px-3 py-2" />
      </label>
      <label className="text-sm font-medium">
        Entrada (R$)
        <input name="downPayment" type="number" min={0} className="mt-1 w-full rounded border border-zinc-300 px-3 py-2" />
      </label>
      <label className="text-sm font-medium">
        Parcelas desejadas
        <input name="desiredInstallments" type="number" min={1} max={84} className="mt-1 w-full rounded border border-zinc-300 px-3 py-2" />
      </label>
      <label className="text-sm font-medium">
        Observações
        <textarea name="notes" rows={3} className="mt-1 w-full rounded border border-zinc-300 px-3 py-2" />
      </label>
      {status === "success" && <p className="text-sm text-green-600">Solicitação enviada. Entraremos em contato em breve.</p>}
      {status === "error" && <p className="text-sm text-red-600">{errorMessage}</p>}
      <button type="submit" className="rounded bg-zinc-900 py-2 text-white hover:bg-zinc-800">
        Solicitar análise
      </button>
    </form>
  );
}
