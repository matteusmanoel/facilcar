export const FORM_THANK_YOU_REDIRECT_MS = 10_000;
export const FORM_THANK_YOU_TOAST_KEY = "facilcar.formThankYouToast";

export const FORM_THANK_YOU_KINDS = ["financiamento", "venda"] as const;

export type FormThankYouKind = (typeof FORM_THANK_YOU_KINDS)[number];

export type FormThankYouIconName = "check" | "car";

export type FormThankYouPreset = {
  kind: FormThankYouKind;
  icon: FormThankYouIconName;
  redirectHref: string;
  redirectLabel: string;
  title: (firstName: string | null) => string;
  description: string;
  toastTitle: string;
  toastDescription: string;
};

export type FormThankYouToastPayload = {
  title: string;
  description: string;
};

const NAME_TOKEN = /^[\p{L}\p{M}'’-]+$/u;

export const formThankYouPresets: Record<FormThankYouKind, FormThankYouPreset> = {
  financiamento: {
    kind: "financiamento",
    icon: "check",
    redirectHref: "/",
    redirectLabel: "Ir para a página inicial",
    title: (firstName) => (firstName ? `Obrigado, ${firstName}!` : "Obrigado!"),
    description:
      "Recebemos sua simulação de financiamento. Um especialista da FácilCar entra em contato em breve pelo WhatsApp.",
    toastTitle: "Simulação enviada",
    toastDescription: "Em breve um especialista fala com você pelo WhatsApp.",
  },
  venda: {
    kind: "venda",
    icon: "car",
    redirectHref: "/",
    redirectLabel: "Ir para a página inicial",
    title: (firstName) => (firstName ? `Obrigado, ${firstName}!` : "Obrigado!"),
    description:
      "Recebemos o pedido de avaliação. Um especialista entra em contato com as próximas etapas.",
    toastTitle: "Pedido de avaliação enviado",
    toastDescription: "Nossa equipe retorna em breve com a avaliação.",
  },
};

export function isFormThankYouKind(value: unknown): value is FormThankYouKind {
  return FORM_THANK_YOU_KINDS.includes(value as FormThankYouKind);
}

export function parseFormThankYouKind(
  value: string | string[] | undefined,
): FormThankYouKind | null {
  const raw = Array.isArray(value) ? value[0] : value;
  return isFormThankYouKind(raw) ? raw : null;
}

export function firstNameFromFullName(raw: unknown): string | null {
  if (typeof raw !== "string") return null;
  const first = raw.trim().split(/\s+/).filter(Boolean)[0] ?? "";
  if (first.length < 2 || first.length > 40) return null;
  if (!NAME_TOKEN.test(first)) return null;
  return first.charAt(0).toLocaleUpperCase("pt-BR") + first.slice(1);
}

export function buildFormThankYouPath(input: {
  kind: FormThankYouKind;
  name?: unknown;
}): string {
  const params = new URLSearchParams();
  params.set("tipo", input.kind);
  const firstName = firstNameFromFullName(input.name);
  if (firstName) params.set("nome", firstName);
  return `/obrigado?${params.toString()}`;
}

export function getFormThankYouPreset(kind: FormThankYouKind): FormThankYouPreset {
  return formThankYouPresets[kind];
}

export function queueFormThankYouToast(payload: FormThankYouToastPayload): void {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.setItem(FORM_THANK_YOU_TOAST_KEY, JSON.stringify(payload));
  } catch {
    // Private mode or blocked storage should not break the thank-you flow.
  }
}

export function consumeFormThankYouToast(): FormThankYouToastPayload | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.sessionStorage.getItem(FORM_THANK_YOU_TOAST_KEY);
    if (!raw) return null;
    window.sessionStorage.removeItem(FORM_THANK_YOU_TOAST_KEY);
    const parsed = JSON.parse(raw) as Partial<FormThankYouToastPayload>;
    if (typeof parsed.title !== "string" || parsed.title.trim() === "") return null;
    return {
      title: parsed.title,
      description: typeof parsed.description === "string" ? parsed.description : "",
    };
  } catch {
    return null;
  }
}
