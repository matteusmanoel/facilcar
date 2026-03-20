"use client";

import { useState } from "react";
import { createVehicleInterestLead } from "../server/actions";

type Props = { vehicleId: string };

const fieldClass =
  "mt-1.5 w-full rounded-lg border border-zinc-300 bg-white px-3 py-2.5 text-zinc-900 shadow-sm transition placeholder:text-zinc-400 focus:border-facil-orange focus:outline-none focus:ring-2 focus:ring-facil-orange/20";

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
      <p className="text-sm font-medium text-zinc-800">Preencha os campos com seus dados</p>
      <label className="text-sm font-medium text-zinc-800">
        Nome completo *
        <input name="name" required autoComplete="name" className={fieldClass} placeholder="Seu nome" />
      </label>
      <label className="text-sm font-medium text-zinc-800">
        DDD + Celular *
        <input
          name="phone"
          type="tel"
          required
          autoComplete="tel"
          className={fieldClass}
          placeholder="(00) 00000-0000"
        />
      </label>
      <label className="text-sm font-medium text-zinc-800">
        E-mail
        <input name="email" type="email" autoComplete="email" className={fieldClass} placeholder="seu@email.com" />
      </label>
      <label className="text-sm font-medium text-zinc-800">
        Mensagem <span className="font-normal text-facil-muted">(opcional)</span>
        <textarea
          name="message"
          rows={3}
          className={`${fieldClass} resize-y min-h-[5rem]`}
          placeholder="Dúvidas ou melhor horário para contato"
        />
      </label>
      {status === "success" && (
        <p className="rounded-lg bg-green-50 px-3 py-2 text-sm text-green-800">
          Enviado! Entraremos em contato em breve.
        </p>
      )}
      {status === "error" && (
        <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{errorMessage}</p>
      )}
      <button type="submit" className="btn-facil-primary w-full py-3.5 text-base font-bold shadow-md">
        Enviar interesse
      </button>
    </form>
  );
}
