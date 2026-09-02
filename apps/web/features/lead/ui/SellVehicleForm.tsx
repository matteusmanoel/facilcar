"use client";

import { useRef, useState } from "react";
import { createSellVehicleLead } from "../server/actions";
import { publicFormInputClass, publicFormLabelClass } from "@/lib/theme";
import { formatPhoneBR } from "@/lib/input-masks";

const inputClass = publicFormInputClass;
const labelClass = publicFormLabelClass;
const MAX_PHOTOS = 5;

export function SellVehicleForm() {
  const [status, setStatus] = useState<"idle" | "submitting" | "success" | "error">("idle");
  const [errorMessage, setErrorMessage] = useState("");
  const [phoneValue, setPhoneValue] = useState("");
  const [photoCount, setPhotoCount] = useState(0);
  const formRef = useRef<HTMLFormElement>(null);

  async function handleSubmit(formData: FormData) {
    setStatus("submitting");
    setErrorMessage("");
    const result = await createSellVehicleLead(formData);
    if (result.success) {
      setStatus("success");
      formRef.current?.reset();
      setPhoneValue("");
      setPhotoCount(0);
    } else {
      setStatus("error");
      setErrorMessage(result.error);
    }
  }

  if (status === "success") {
    return (
      <div className="flex flex-col items-center gap-4 rounded-xl bg-green-50 px-6 py-8 text-center">
        <div className="flex h-14 w-14 items-center justify-center rounded-full bg-green-100">
          <svg
            width="28"
            height="28"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
            className="text-green-600"
            aria-hidden
          >
            <path d="M20 6 9 17l-5-5" />
          </svg>
        </div>
        <p className="text-base font-semibold text-green-900">Pedido enviado!</p>
        <p className="text-sm text-green-700">
          Um dos nossos especialistas vai entrar em contato com a avaliação.
        </p>
        <button
          type="button"
          onClick={() => setStatus("idle")}
          className="mt-2 text-sm text-facil-muted underline hover:text-foreground"
        >
          Enviar outro veículo
        </button>
      </div>
    );
  }

  return (
    <form ref={formRef} action={handleSubmit} className="flex flex-col gap-4" noValidate>
      <label className={labelClass}>
        Nome completo *
        <input
          name="name"
          required
          autoComplete="name"
          className={inputClass}
          placeholder="Seu nome completo"
          disabled={status === "submitting"}
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
          />
        </label>
        <label className={labelClass}>
          Modelo
          <input
            name="model"
            className={inputClass}
            placeholder="Ex: Corolla"
            disabled={status === "submitting"}
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
          disabled={status === "submitting"}
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
