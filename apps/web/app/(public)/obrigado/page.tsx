import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { FormThankYouScreen } from "@/features/lead/ui/FormThankYouScreen";
import {
  firstNameFromFullName,
  getFormThankYouPreset,
  parseFormThankYouKind,
} from "@/features/lead/lib/form-thank-you";

export const metadata: Metadata = {
  title: "Pedido enviado",
  robots: { index: false, follow: false },
};

type SearchParams = {
  tipo?: string | string[];
  nome?: string | string[];
};

export default async function ObrigadoPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const params = await searchParams;
  const kind = parseFormThankYouKind(params.tipo);
  if (!kind) redirect("/");

  const preset = getFormThankYouPreset(kind);
  const nome = Array.isArray(params.nome) ? params.nome[0] : params.nome;
  const firstName = firstNameFromFullName(nome);

  return (
    <FormThankYouScreen
      title={preset.title(firstName)}
      description={preset.description}
      icon={preset.icon}
      redirectHref={preset.redirectHref}
      redirectLabel={preset.redirectLabel}
      toastTitle={preset.toastTitle}
      toastDescription={preset.toastDescription}
    />
  );
}
