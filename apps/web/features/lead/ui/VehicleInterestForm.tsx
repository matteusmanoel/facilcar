"use client";

import { useState } from "react";
import { createVehicleInterestLead } from "../server/actions";
import { publicFormInputClass, publicFormLabelClass } from "@/lib/theme";
import { scrollPublicFieldIntoView } from "@/lib/public-form";

type Props = { vehicleId: string };

const fieldClass = publicFormInputClass;

export function VehicleInterestForm({ vehicleId }: Props) {
  const [status, setStatus] = useState<"idle" | "success" | "error">("idle");
  const [errorMessage, setErrorMessage] = useState("");

  return (
    <form
      action={async (formData) => {
        setStatus("idle");
        const result = await createVehicleInterestLead(formData, vehicleId);
        if (result.success) {
          setStatus("success");
        } else {
          setStatus("error");
          setErrorMessage(result.error);
        }
      }}
      className="flex flex-col gap-4"
    >
      <input type="hidden" name="vehicleId" value={vehicleId} />
      <p className={publicFormLabelClass}>Preencha os campos com seus dados</p>
      <label className={publicFormLabelClass}>
        Nome completo *
        <input name="name" required autoComplete="name" className={fieldClass} placeholder="Seu nome" onFocus={scrollPublicFieldIntoView} />
      </label>
      <label className={publicFormLabelClass}>
        DDD + Celular *
        <input
          name="phone"
          type="tel"
          required
          autoComplete="tel"
          className={fieldClass}
          placeholder="(00) 00000-0000"
          onFocus={scrollPublicFieldIntoView}
        />
      </label>
      <label className={publicFormLabelClass}>
        E-mail
        <input name="email" type="email" autoComplete="email" className={fieldClass} placeholder="seu@email.com" onFocus={scrollPublicFieldIntoView} />
      </label>
      <label className={publicFormLabelClass}>
        Mensagem <span className="font-normal text-facil-muted">(opcional)</span>
        <textarea
          name="message"
          rows={3}
          className={`${fieldClass} resize-y min-h-[5rem]`}
          placeholder="Dúvidas ou melhor horário para contato"
          onFocus={scrollPublicFieldIntoView}
        />
      </label>
      {status === "success" && (
        <p className="rounded-lg bg-green-50 px-3 py-2 text-sm text-green-800 dark:bg-green-950/40 dark:text-green-400">
          Mensagem enviada! Entraremos em contato em breve.
        </p>
      )}
      {status === "error" && (
        <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950/40 dark:text-red-400">
          {errorMessage}
        </p>
      )}
      <button
        type="submit"
        className="btn-facil-primary w-full"
        disabled={status === "success"}
      >
        Enviar interesse
      </button>
    </form>
  );
}
