"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { createSellVehicleLead } from "../server/actions";
import { publicFormInputClass, publicFormLabelClass } from "@/lib/theme";
import { formatPhoneBR } from "@/lib/input-masks";
import { scrollPublicFieldIntoView } from "@/lib/public-form";
import { buildFormThankYouPath } from "@/features/lead/lib/form-thank-you";

const inputClass = publicFormInputClass;
const labelClass = publicFormLabelClass;
const MAX_PHOTOS = 5;

export function SellVehicleForm() {
  const [status, setStatus] = useState<"idle" | "submitting" | "error">("idle");
  const [errorMessage, setErrorMessage] = useState("");
  const [phoneValue, setPhoneValue] = useState("");
  const [photoCount, setPhotoCount] = useState(0);
  const formRef = useRef<HTMLFormElement>(null);
  const router = useRouter();

  async function handleSubmit(formData: FormData) {
    const payload = new FormData();
    for (const [key, value] of formData.entries()) {
      payload.append(key, value);
    }

    setStatus("submitting");
    setErrorMessage("");
    const result = await createSellVehicleLead(payload);
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
        <legend className={labelClass}>Como prefere vender?</legend>
        <label className="flex cursor-pointer items-start gap-2 text-sm text-foreground">
          <input
            type="radio"
            name="saleMode"
            value="CONSIGNMENT"
            className="mt-1 accent-facil-orange"
            disabled={status === "submitting"}
          />
          <span>
            <span className="font-medium">Consignação</span>
            <span className="block text-facil-muted">A loja anuncia e negocia o seu carro.</span>
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
            <span className="font-medium">Compra direta pela loja</span>
            <span className="block text-facil-muted">A FácilCar avalia e pode comprar o veículo.</span>
          </span>
        </label>
      </fieldset>

      <div className="grid grid-cols-2 gap-3">
        <label className={labelClass}>
          Marca
          <input
            name="brand"
            className={inputClass}
            placeholder="Ex: Toyota"
            disabled={status === "submitting"}
            onFocus={scrollPublicFieldIntoView}
          />
        </label>
        <label className={labelClass}>
          Modelo
          <input
            name="model"
            className={inputClass}
            placeholder="Ex: Corolla"
            disabled={status === "submitting"}
            onFocus={scrollPublicFieldIntoView}
          />
        </label>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <label className={labelClass}>
          Ano
          <input
            name="yearModel"
            type="number"
            min={1990}
            max={2030}
            inputMode="numeric"
            className={inputClass}
            placeholder="2020"
            disabled={status === "submitting"}
            onFocus={scrollPublicFieldIntoView}
          />
        </label>
        <label className={labelClass}>
          Quilometragem
          <input
            name="mileage"
            type="number"
            min={0}
            inputMode="numeric"
            className={inputClass}
            placeholder="45000"
            disabled={status === "submitting"}
            onFocus={scrollPublicFieldIntoView}
          />
        </label>
      </div>

      <label className={labelClass}>
        Fotos do veículo
        <input
          name="photos"
          type="file"
          accept="image/jpeg,image/png,image/webp"
          multiple
          className={`${inputClass} file:mr-3 file:rounded-md file:border-0 file:bg-facil-orange file:px-3 file:py-1.5 file:text-sm file:font-semibold file:text-white`}
          onChange={(e) => {
            const files = Array.from(e.target.files ?? []);
            if (files.length > MAX_PHOTOS) {
              e.target.value = "";
              setPhotoCount(0);
              setStatus("error");
              setErrorMessage(`Envie no máximo ${MAX_PHOTOS} fotos.`);
              return;
            }
            setPhotoCount(files.length);
          }}
        />
        <span className="mt-1 block text-xs font-normal text-facil-muted">
          Até {MAX_PHOTOS} fotos (JPEG, PNG ou WebP, 4 MB cada)
          {photoCount > 0 ? ` · ${photoCount} selecionada(s)` : ""}
        </span>
      </label>

      <label className={labelClass}>
        Observações
        <textarea
          name="observations"
          rows={4}
          className={inputClass}
          placeholder="Opcionais, estado de conservação, documentação…"
          disabled={status === "submitting"}
          onFocus={scrollPublicFieldIntoView}
        />
      </label>

      {status === "error" && (
        <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{errorMessage}</p>
      )}

      <button
        type="submit"
        disabled={status === "submitting"}
        className="btn-facil-primary mt-1 flex w-full items-center justify-center gap-2 py-3.5 text-base font-bold shadow-md disabled:opacity-70"
      >
        {status === "submitting" ? "Enviando..." : "Solicitar avaliação"}
      </button>
    </form>
  );
}
