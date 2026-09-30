"use client";

import { useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { createFinancingSimulationLead } from "../server/actions";
import { publicFormInputClass, publicFormLabelClass } from "@/lib/theme";
import { formatPhoneBR } from "@/lib/input-masks";
import { scrollPublicFieldIntoView } from "@/lib/public-form";
import { buildFormThankYouPath } from "@/features/lead/lib/form-thank-you";
import { InfoTip, RelatoFields } from "./RelatoFields";

type Props = {
  vehicleId?: string;
  vehicleTitle?: string;
  vehicleYear?: number;
  vehicleModel?: string;
  whatsappNumber: string;
  /** "SOLD" indica que o veículo já foi vendido — lead vira VEHICLE_INTEREST */
  vehicleStatus?: string;
  /** Quando true, não exibe o radio de modo (ficha já define FINANCING) */
  hideFinanceMode?: boolean;
};

const inputClass = publicFormInputClass;
const labelClass = publicFormLabelClass;

const WA_ICON = (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
    <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" />
  </svg>
);

export function FinancingSimulationForm({
  vehicleId,
  vehicleTitle,
  whatsappNumber,
  vehicleStatus,
  hideFinanceMode = false,
}: Props) {
  const [status, setStatus] = useState<"idle" | "submitting" | "error">("idle");
  const [errorMessage, setErrorMessage] = useState("");
  const [phoneValue, setPhoneValue] = useState("");
  const formRef = useRef<HTMLFormElement>(null);
  const router = useRouter();

  const isSold = vehicleStatus === "SOLD";

  async function handleSubmit(formData: FormData) {
    setStatus("submitting");
    setErrorMessage("");

    const result = await createFinancingSimulationLead(formData, whatsappNumber);

    if (result.success) {
      if (result.whatsappUrl && result.whatsappUrl !== "#") {
        window.open(result.whatsappUrl, "_blank", "noopener,noreferrer");
      }
      router.push(
        buildFormThankYouPath({
          kind: "financiamento",
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
      {vehicleId && <input type="hidden" name="vehicleId" value={vehicleId} />}
      {vehicleTitle && <input type="hidden" name="vehicleTitle" value={vehicleTitle} />}
      {/* Sinaliza ao servidor o tipo real do lead */}
      {isSold && <input type="hidden" name="leadType" value="VEHICLE_INTEREST" />}

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

      {/* Modo: só na porta de financiamento, não na ficha nem no vendido */}
      {!hideFinanceMode && !isSold && (
        <fieldset className="space-y-2">
          <legend className={`${labelClass} mb-1`}>O que você precisa? *</legend>
          <label className="flex cursor-pointer items-start gap-2 text-sm text-foreground">
            <input
              type="radio"
              name="financeMode"
              value="FINANCING"
              required
              className="mt-1 accent-facil-orange"
              disabled={status === "submitting"}
            />
            <span>
              <span className="font-medium">Financiar</span>
              <span className="block text-facil-muted">
                Crédito para adquirir um veículo, com ou sem um em mente.
              </span>
            </span>
          </label>
          <label className="flex cursor-pointer items-start gap-2 text-sm text-foreground">
            <input
              type="radio"
              name="financeMode"
              value="REFINANCING"
              className="mt-1 accent-facil-orange"
              disabled={status === "submitting"}
            />
            <span>
              <span className="font-medium">Refinanciar</span>
              <span className="block text-facil-muted">
                Usar o seu carro como garantia para obter crédito.
              </span>
            </span>
          </label>
        </fieldset>
      )}

      <RelatoFields
        disabled={status === "submitting"}
        placeholder={
          isSold
            ? "Conte o que procura: tipo de veículo, faixa de preço, uso — qualquer detalhe ajuda a encontrar um similar."
            : "Conte o que quiser: veículo de interesse, quanto já tem de entrada, prazo preferido, dúvidas. Sem CPF ou documentos agora."
        }
        hint={
          isSold
            ? "Descreva o tipo de veículo, a faixa de preço e o uso. Isso acelera a busca por um similar. CPF e documento não são necessários agora."
            : "Conte o que acelera o encaminhamento: veículo, entrada, prazo ou a dúvida que você já tem. CPF e documento não são necessários agora."
        }
      />

      {/* Troca: só na ficha de veículo disponível */}
      {vehicleId && !isSold && (
        <div>
          <div className="flex items-center gap-1.5">
            <span className={labelClass}>Possuo veículo para troca</span>
            <InfoTip text="Opcional. Se tiver um carro para dar na troca, descreva modelo, ano e estado. Pode deixar em branco." />
          </div>
          <textarea
            name="tradeInDescription"
            rows={2}
            className={`${inputClass} resize-none`}
            placeholder="Ex.: Fiat Uno 2018, 60 mil km, bem conservado. Opcional — pode deixar em branco."
            disabled={status === "submitting"}
          />
        </div>
      )}

      {status === "error" && (
        <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{errorMessage}</p>
      )}

      <button
        type="submit"
        disabled={status === "submitting"}
        className="btn-facil-primary mt-1 flex w-full items-center justify-center gap-2 py-3.5 text-base font-bold shadow-md disabled:opacity-70"
      >
        {status === "submitting" ? (
          "Enviando..."
        ) : (
          <>
            {WA_ICON}
            {isSold ? "Quero um similar" : "Enviar pelo WhatsApp"}
          </>
        )}
      </button>
    </form>
  );
}
