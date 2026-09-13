/** FinancingRequest.desiredMonthlyPayment is R$/mês — never month count. */

export function formatDesiredMonthlyPayment(value: unknown): string | null {
  if (value == null || value === "") return null;
  const n = Number(value);
  if (!Number.isFinite(n)) return null;
  const formatted = n.toLocaleString("pt-BR", {
    minimumFractionDigits: n % 1 === 0 ? 0 : 2,
    maximumFractionDigits: 2,
  });
  return `até R$ ${formatted}/mês`;
}

export function desiredMonthlyPaymentLabel(value: unknown): string | null {
  const amount = formatDesiredMonthlyPayment(value);
  if (!amount) return null;
  return `Parcela pretendida: ${amount}`;
}

/** Prazo (1–84 months). A monthly amount like 1500 must not be treated as count. */
export function isInstallmentMonthCount(value: unknown): boolean {
  const n = Number(value);
  return Number.isInteger(n) && n >= 1 && n <= 84;
}
