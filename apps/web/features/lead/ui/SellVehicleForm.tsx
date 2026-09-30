"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { createSellVehicleLead } from "../server/actions";
import { publicFormInputClass, publicFormLabelClass } from "@/lib/theme";
import { formatPhoneBR } from "@/lib/input-masks";
import { scrollPublicFieldIntoView } from "@/lib/public-form";
import { buildFormThankYouPath } from "@/features/lead/lib/form-thank-you";
import { RelatoFields } from "./RelatoFields";

const inputClass = publicFormInputClass;
const labelClass = publicFormLabelClass;

export function SellVehicleForm() {
  const [status, setStatus] = useState<"idle" | "submitting" | "error">("idle");
  const [errorMessage, setErrorMessage] = useState("");
  const [phoneValue, setPhoneValue] = useState("");
  const formRef = useRef<HTMLFormElement>(null);
  const router = useRouter();

  async function handleSubmit(formData: FormData) {
    setStatus("submitting");
    setErrorMessage("");
    const result = await createSellVehicleLead(formData);
    if (result.success) {
      router.push(
        buildFormThankYouPath({
          kind: "venda",
          name: formData.get("name"),
        }),
      );
      return;
    }
    setStatus("error");
    setErrorMessage(result.error);
  }

  return (
    <form
      ref={formRef}
      action={handleSubmit}
      encType="multipart/form-data"
      className="flex flex-col gap-4"
      noValidate
    >
      <label className={labelClass}>
        Nome completo *
        <input
          name="name"
          required
          autoComplete="name"
          className={inputClass}
          placeholder="Seu nome completo"
          disabled={status === "submitting"}
          onFocus={scrollPublicFieldIntoView}
        />
      </label>

      <label className={labelClass}>
        DDD + Celular *
        <input
          name="phone"
          type="tel"
          inputMode="numeric"
          autoComplete="tel"
          required
          className={inputClass}
          placeholder="(00) 00000-0000"
          value={phoneValue}
          onChange={(e) => setPhoneValue(formatPhoneBR(e.target.value))}
          disabled={status === "submitting"}
          onFocus={scrollPublicFieldIntoView}
        />
      </label>

      <fieldset className="space-y-2">
        <legend className={`${labelClass} mb-1`}>Como prefere negociar? *</legend>
        <label className="flex cursor-pointer items-start gap-2 text-sm text-foreground">
          <input
            type="radio"
            name="saleMode"
            value="CONSIGNMENT"
            required
            className="mt-1 accent-facil-orange"
            disabled={status === "submitting"}
          />
          <span>
            <span className="font-medium">Consignação</span>
            <span className="block text-facil-muted">
              A loja anuncia e cuida da negociação. Seu carro fica anunciado profissionalmente até vender.
            </span>
          </span>
        </label>
        <label className="flex cursor-pointer items-start gap-2 text-sm text-foreground">
          <input
            type="radio"
            name="saleMode"
            value="DIRECT_PURCHASE"
            className="mt-1 accent-facil-orange"
            disabled={status === "submitting"}
          />
          <span>
            <span className="font-medium">Venda direta</span>
            <span className="block text-facil-muted">
              A FácilCar avalia e, se tiver interesse, compra o seu veículo diretamente.
            </span>
          </span>
        </label>
      </fieldset>

      <RelatoFields
        disabled={status === "submitting"}
        placeholder="Conte sobre o veículo: marca, modelo, ano, quilometragem, estado de conservação, o que quiser. Não precisa de fotos nem de documentos agora."
      />

      {status === "error" && (
        <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{errorMessage}</p>
      )}

      <button
        type="submit"
        disabled={status === "submitting"}
        className="btn-facil-primary mt-1 flex w-full items-center justify-center gap-2 py-3.5 text-base font-bold shadow-md disabled:opacity-70"
      >
        {status === "submitting" ? "Enviando..." : "Quero negociar meu carro"}
      </button>
    </form>
  );
}
