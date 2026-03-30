"use client";

import { useState, useRef, useMemo } from "react";
import { createFinancingSimulationLead } from "../server/actions";

type Props = {
  vehicleId?: string;
  vehicleTitle?: string;
  vehicleYear?: number;
  vehicleModel?: string;
  whatsappNumber: string;
};

const inputClass =
  "mt-1.5 w-full rounded-lg border border-zinc-300 bg-white px-3 py-2.5 text-zinc-900 shadow-sm transition placeholder:text-zinc-400 focus:border-facil-orange focus:outline-none focus:ring-2 focus:ring-facil-orange/20 disabled:opacity-60";

const labelClass = "block text-sm font-medium text-zinc-800";

function formatCPF(value: string) {
  const digits = value.replace(/\D/g, "").slice(0, 11);
  return digits
    .replace(/(\d{3})(\d)/, "$1.$2")
    .replace(/(\d{3})\.(\d{3})(\d)/, "$1.$2.$3")
    .replace(/(\d{3})\.(\d{3})\.(\d{3})(\d)/, "$1.$2.$3-$4");
}

const INSTALLMENT_OPTIONS = [36, 48];

export function FinancingSimulationForm({
  vehicleId,
  vehicleTitle,
  vehicleYear,
  vehicleModel,
  whatsappNumber,
}: Props) {
  const [status, setStatus] = useState<"idle" | "submitting" | "success" | "error">("idle");
  const [errorMessage, setErrorMessage] = useState("");
  const [cpfValue, setCpfValue] = useState("");
  const [birthDay, setBirthDay] = useState("");
  const [birthMonth, setBirthMonth] = useState("");
  const [birthYear, setBirthYear] = useState("");
  const formRef = useRef<HTMLFormElement>(null);

  const birthDateValue = birthDay && birthMonth && birthYear
    ? `${birthYear}-${birthMonth.padStart(2, "0")}-${birthDay.padStart(2, "0")}`
    : "";

  const MONTHS = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
  ];

  const currentYear = new Date().getFullYear();
  const years = useMemo(
    () => Array.from({ length: 80 }, (_, i) => currentYear - 18 - i),
    [currentYear],
  );
  const daysInMonth = useMemo(() => {
    if (!birthMonth || !birthYear) return 31;
    return new Date(Number(birthYear), Number(birthMonth), 0).getDate();
  }, [birthMonth, birthYear]);

  const hasVehicle = Boolean(vehicleId);

  async function handleSubmit(formData: FormData) {
    setStatus("submitting");
    setErrorMessage("");

    const result = await createFinancingSimulationLead(formData, whatsappNumber);

    if (result.success) {
      setStatus("success");
      formRef.current?.reset();
      setCpfValue("");
      setBirthDay("");
      setBirthMonth("");
      setBirthYear("");
      if (result.whatsappUrl && result.whatsappUrl !== "#") {
        setTimeout(() => {
          window.open(result.whatsappUrl, "_blank", "noopener,noreferrer");
        }, 600);
      }
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
        <p className="text-base font-semibold text-green-900">
          Dados enviados com sucesso!
        </p>
        <p className="text-sm text-green-700">
          Abrindo WhatsApp para continuarmos o atendimento...
        </p>
        <button
          type="button"
          onClick={() => setStatus("idle")}
          className="mt-2 text-sm text-zinc-500 underline hover:text-zinc-700"
        >
          Preencher novamente
        </button>
      </div>
    );
  }

  return (
    <form
      ref={formRef}
      action={handleSubmit}
      className="flex flex-col gap-4"
      noValidate
    >
      {vehicleId && <input type="hidden" name="vehicleId" value={vehicleId} />}
      {vehicleTitle && <input type="hidden" name="vehicleTitle" value={vehicleTitle} />}

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
        CPF *
        <input
          name="cpf"
          required
          autoComplete="off"
          inputMode="numeric"
          maxLength={14}
          className={inputClass}
          placeholder="000.000.000-00"
          value={cpfValue}
          onChange={(e) => setCpfValue(formatCPF(e.target.value))}
          disabled={status === "submitting"}
        />
      </label>

      <div>
        <span className={labelClass}>Data de Nascimento *</span>
        <input type="hidden" name="birthDate" value={birthDateValue} />
        <div className="mt-1.5 grid grid-cols-3 gap-2">
          <select
            aria-label="Dia"
            value={birthDay}
            onChange={(e) => setBirthDay(e.target.value)}
            required
            className={inputClass}
            disabled={status === "submitting"}
          >
            <option value="" disabled>Dia</option>
            {Array.from({ length: daysInMonth }, (_, i) => i + 1).map((d) => (
              <option key={d} value={d}>{String(d).padStart(2, "0")}</option>
            ))}
          </select>
          <select
            aria-label="Mês"
            value={birthMonth}
            onChange={(e) => setBirthMonth(e.target.value)}
            required
            className={inputClass}
            disabled={status === "submitting"}
          >
            <option value="" disabled>Mês</option>
            {MONTHS.map((m, i) => (
              <option key={i + 1} value={i + 1}>{m}</option>
            ))}
          </select>
          <select
            aria-label="Ano"
            value={birthYear}
            onChange={(e) => setBirthYear(e.target.value)}
            required
            className={inputClass}
            disabled={status === "submitting"}
          >
            <option value="" disabled>Ano</option>
            {years.map((y) => (
              <option key={y} value={y}>{y}</option>
            ))}
          </select>
        </div>
      </div>

      <label className={labelClass}>
        DDD + Celular *
        <input
          name="phone"
          type="tel"
          required
          autoComplete="tel"
          className={inputClass}
          placeholder="(00) 00000-0000"
          disabled={status === "submitting"}
        />
      </label>

      <div className="grid grid-cols-2 gap-3">
        <label className={labelClass}>
          Renda Mensal *
          <div className="relative mt-1.5">
            <span className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-sm text-zinc-500">
              R$
            </span>
            <input
              name="monthlyIncome"
              type="number"
              min={0}
              step={100}
              required
              className={`${inputClass} !mt-0 pl-9`}
              placeholder="0"
              disabled={status === "submitting"}
            />
          </div>
        </label>

        <label className={labelClass}>
          Valor de Entrada
          <div className="relative mt-1.5">
            <span className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-sm text-zinc-500">
              R$
            </span>
            <input
              name="downPayment"
              type="number"
              min={0}
              step={100}
              className={`${inputClass} !mt-0 pl-9`}
              placeholder="0"
              disabled={status === "submitting"}
            />
          </div>
        </label>
      </div>

      <label className={labelClass}>
        Prazo Desejado *
        <select
          name="desiredInstallments"
          required
          className={inputClass}
          disabled={status === "submitting"}
          defaultValue=""
        >
          <option value="" disabled>
            Selecione o prazo
          </option>
          {INSTALLMENT_OPTIONS.map((n) => (
            <option key={n} value={n}>
              {n} meses ({n / 12} {n / 12 === 1 ? "ano" : "anos"})
            </option>
          ))}
        </select>
      </label>

      {!hasVehicle && (
        <div className="grid grid-cols-2 gap-3">
          <label className={labelClass}>
            Ano do Veículo
            <input
              name="vehicleYear"
              type="number"
              min={1990}
              max={2030}
              defaultValue={vehicleYear}
              className={inputClass}
              placeholder={String(new Date().getFullYear())}
              disabled={status === "submitting"}
            />
          </label>
          <label className={labelClass}>
            Modelo
            <input
              name="vehicleModel"
              type="text"
              defaultValue={vehicleModel}
              className={inputClass}
              placeholder="Ex: Onix, HB20..."
              disabled={status === "submitting"}
            />
          </label>
        </div>
      )}

      {hasVehicle && vehicleYear && (
        <input type="hidden" name="vehicleYear" value={vehicleYear} />
      )}
      {hasVehicle && vehicleModel && (
        <input type="hidden" name="vehicleModel" value={vehicleModel} />
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
          <>
            <svg
              className="h-5 w-5 animate-spin"
              viewBox="0 0 24 24"
              fill="none"
              aria-hidden
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8v8z"
              />
            </svg>
            Enviando...
          </>
        ) : (
          <>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
              <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" />
            </svg>
            Simular e Enviar pelo WhatsApp
          </>
        )}
      </button>

      <p className="text-center text-xs text-zinc-400">
        100% gratuito · Sem consulta ao SPC/Serasa nesta etapa · Seus dados são protegidos
      </p>
    </form>
  );
}
