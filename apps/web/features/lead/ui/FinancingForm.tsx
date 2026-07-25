"use client";

import { useState } from "react";
import { createFinancingLead } from "../server/actions";
import {
  publicFormInputSimpleClass,
  publicFormLabelClass,
} from "@/lib/theme";

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
      {vehicleTitle && <p className="text-sm text-facil-muted">Veículo: {vehicleTitle}</p>}
      <label className={publicFormLabelClass}>
        Nome *
        <input name="name" required className={publicFormInputSimpleClass} />
      </label>
      <label className={publicFormLabelClass}>
        Telefone *
        <input name="phone" type="tel" required className={publicFormInputSimpleClass} />
      </label>
      <label className={publicFormLabelClass}>
        E-mail
        <input name="email" type="email" className={publicFormInputSimpleClass} />
      </label>
      <label className="flex items-center gap-2 text-sm text-foreground">
        <input name="hasDriverLicense" type="checkbox" value="sim" className="rounded" />
        <span>Possui CNH?</span>
      </label>
      <label className={publicFormLabelClass}>
        Renda mensal (R$)
        <input name="monthlyIncome" type="number" min={0} className={publicFormInputSimpleClass} />
      </label>
      <label className={publicFormLabelClass}>
        Entrada (R$)
        <input name="downPayment" type="number" min={0} className={publicFormInputSimpleClass} />
      </label>
      <label className={publicFormLabelClass}>
        Parcelas desejadas
        <input
          name="desiredInstallments"
          type="number"
          min={1}
          max={84}
          className={publicFormInputSimpleClass}
        />
      </label>
      <label className={publicFormLabelClass}>
        Observações
        <textarea name="notes" rows={3} className={publicFormInputSimpleClass} />
      </label>
      {status === "success" && (
        <p className="text-sm text-green-600 dark:text-green-400">
          Solicitação enviada. Entraremos em contato em breve.
        </p>
      )}
      {status === "error" && (
        <p className="text-sm text-red-600 dark:text-red-400">{errorMessage}</p>
      )}
      <button
        type="submit"
        className="rounded bg-zinc-900 py-2 text-white hover:bg-zinc-800 dark:bg-facil-orange dark:hover:bg-facil-orange-hover"
      >
        Solicitar análise
      </button>
    </form>
  );
}
