"use client";

import { useState } from "react";
import { updateSettingsAction } from "./action";
import type { SiteSettings } from "@prisma/client";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";

type Props = { settings: SiteSettings };

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-4 rounded-xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
      <h2 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">{title}</h2>
      {children}
    </section>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block space-y-1 text-sm font-medium text-zinc-700 dark:text-zinc-300">
      <span>{label}</span>
      {children}
    </label>
  );
}

const textareaClass = cn(
  "mt-1 w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 shadow-sm transition-colors",
  "placeholder:text-zinc-400 focus:border-facil-orange focus:outline-none focus:ring-2 focus:ring-facil-orange/30",
  "dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 dark:placeholder:text-zinc-500",
);

export function SettingsForm({ settings }: Props) {
  const [status, setStatus] = useState<"idle" | "success" | "error">("idle");

  return (
    <form
      action={async (formData) => {
        setStatus("idle");
        const result = await updateSettingsAction(formData);
        if (result.success) setStatus("success");
        else setStatus("error");
      }}
      className="max-w-3xl space-y-6"
    >
      <input type="hidden" name="id" value={settings.id} />

      <Section title="Identidade">
        <Field label="Nome do site">
          <Input name="siteName" defaultValue={settings.siteName} className="mt-1" />
        </Field>
        <Field label="Título do hero (home)">
          <Input name="heroTitle" defaultValue={settings.heroTitle ?? ""} className="mt-1" />
        </Field>
        <Field label="Subtítulo do hero">
          <textarea
            name="heroSubtitle"
            rows={2}
            defaultValue={settings.heroSubtitle ?? ""}
            className={textareaClass}
          />
        </Field>
        <Field label="Texto do rodapé (resumo da loja)">
          <textarea
            name="footerText"
            rows={3}
            defaultValue={settings.footerText ?? ""}
            className={textareaClass}
          />
        </Field>
      </Section>

      <Section title="Contato">
        <Field label="WhatsApp (E.164, ex: 5545999123456)">
          <Input
            name="defaultWhatsappNumber"
            defaultValue={settings.defaultWhatsappNumber}
            className="mt-1 font-mono"
          />
        </Field>
        <Field label="E-mail padrão">
          <Input
            name="defaultEmail"
            type="email"
            defaultValue={settings.defaultEmail}
            className="mt-1"
          />
        </Field>
        <Field label="Telefone (exibição)">
          <Input
            name="phoneNumber"
            defaultValue={settings.phoneNumber ?? ""}
            className="mt-1"
          />
        </Field>
      </Section>

      <Section title="Endereço">
        <Field label="Logradouro">
          <Input name="addressLine" defaultValue={settings.addressLine ?? ""} className="mt-1" />
        </Field>
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Cidade">
            <Input name="city" defaultValue={settings.city ?? ""} className="mt-1" />
          </Field>
          <Field label="UF">
            <Input
              name="state"
              maxLength={2}
              defaultValue={settings.state ?? ""}
              className="mt-1 uppercase"
            />
          </Field>
          <Field label="CEP">
            <Input name="zipCode" defaultValue={settings.zipCode ?? ""} className="mt-1" />
          </Field>
        </div>
      </Section>

      <Section title="Redes sociais">
        <Field label="Instagram (URL)">
          <Input
            name="instagramUrl"
            type="url"
            placeholder="https://instagram.com/..."
            defaultValue={settings.instagramUrl ?? ""}
            className="mt-1"
          />
        </Field>
        <Field label="Facebook (URL)">
          <Input
            name="facebookUrl"
            type="url"
            defaultValue={settings.facebookUrl ?? ""}
            className="mt-1"
          />
        </Field>
        <Field label="YouTube (URL)">
          <Input
            name="youtubeUrl"
            type="url"
            defaultValue={settings.youtubeUrl ?? ""}
            className="mt-1"
          />
        </Field>
      </Section>

      <Section title="SEO padrão">
        <Field label="Título padrão (meta)">
          <Input
            name="seoDefaultTitle"
            defaultValue={settings.seoDefaultTitle ?? ""}
            className="mt-1"
          />
        </Field>
        <Field label="Descrição padrão">
          <textarea
            name="seoDefaultDescription"
            rows={2}
            defaultValue={settings.seoDefaultDescription ?? ""}
            className={textareaClass}
          />
        </Field>
      </Section>

      <div className="flex items-center gap-4">
        <Button type="submit" variant="primary">
          Salvar tudo
        </Button>
        {status === "success" && (
          <p className="text-sm font-medium text-green-600 dark:text-green-400">
            Configurações salvas com sucesso.
          </p>
        )}
        {status === "error" && (
          <p className="text-sm font-medium text-red-600 dark:text-red-400">
            Erro ao salvar. Tente novamente.
          </p>
        )}
      </div>
    </form>
  );
}
