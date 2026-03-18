"use client";

import { useState } from "react";
import { createVehicleInterestLead } from "../server/actions";

type Props = { vehicleId: string };

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
      className="flex flex-col gap-3"
    >
      <input type="hidden" name="vehicleId" value={vehicleId} />
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
      <label className="text-sm font-medium">
        Mensagem
        <textarea name="message" rows={3} className="mt-1 w-full rounded border border-zinc-300 px-3 py-2" />
      </label>
      {status === "success" && <p className="text-sm text-green-600">Enviado! Entraremos em contato em breve.</p>}
      {status === "error" && <p className="text-sm text-red-600">{errorMessage}</p>}
      <button type="submit" className="rounded bg-zinc-900 py-2 text-white hover:bg-zinc-800">
        Tenho interesse
      </button>
    </form>
  );
}
