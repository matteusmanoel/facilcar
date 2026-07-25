"use client";

import { useState } from "react";
import { updateSettingsAction } from "./action";
import type { SiteSettings } from "@prisma/client";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";
import { normalizePublicTheme } from "@/lib/theme";

type Props = { settings: SiteSettings };

function Section({
  title,
  children,
  className,
}: {
  title: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={cn("admin-card flex flex-col space-y-4", className)}>
      <h2 className="admin-section-title">{title}</h2>
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
    <label className="block space-y-1 text-sm font-medium text-foreground">
      <span>{label}</span>
      {children}
    </label>
  );
}

const fieldClass = cn(
  "mt-1 w-full rounded-lg border border-facil-border bg-facil-card px-3 py-2 text-sm text-foreground shadow-sm transition-colors",
  "placeholder:text-facil-muted focus:border-facil-orange focus:outline-none focus:ring-2 focus:ring-facil-orange/30",
);

export function SettingsForm({ settings }: Props) {
  const [status, setStatus] = useState<"idle" | "success" | "error">("idle");
  const publicTheme = normalizePublicTheme(settings.publicTheme);

  return (
    <form
      action={async (formData) => {
        setStatus("idle");
        const result = await updateSettingsAction(formData);
        if (result.success) setStatus("success");
        else setStatus("error");
      }}
      className="space-y-6"
    >
      <input type="hidden" name="id" value={settings.id} />

      <div className="grid gap-4 lg:grid-cols-3">
        <Section title="Identidade" className="lg:col-span-2">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Nome do site">
              <Input name="siteName" defaultValue={settings.siteName} className="mt-1" />
            </Field>
            <Field label="Título do hero (home)">
              <Input name="heroTitle" defaultValue={settings.heroTitle ?? ""} className="mt-1" />
            </Field>
          </div>
          <Field label="Subtítulo do hero">
            <textarea
              name="heroSubtitle"
              rows={2}
              defaultValue={settings.heroSubtitle ?? ""}
              className={fieldClass}
            />
          </Field>
          <Field label="Texto do rodapé (resumo da loja)">
            <textarea
              name="footerText"
              rows={3}
              defaultValue={settings.footerText ?? ""}
              className={fieldClass}
            />
          </Field>
        </Section>

        <Section title="Aparência do site público">
          <p className="text-sm text-facil-muted">
            Tema padrão do site para visitantes. A preferência do painel admin é independente.
          </p>
          <Field label="Tema do site">
            <select name="publicTheme" defaultValue={publicTheme} className={fieldClass}>
              <option value="dark">Escuro (padrão)</option>
              <option value="light">Claro</option>
            </select>
          </Field>
        </Section>

        <Section title="Contato">
          <Field label="WhatsApp (E.164)">
            <Input
              name="defaultWhatsappNumber"
              defaultValue={settings.defaultWhatsappNumber}
              className="mt-1 font-mono"
              placeholder="5545999123456"
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

        <Section title="SEO padrão" className="lg:col-span-3">
          <div className="grid gap-4 lg:grid-cols-2">
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
                className={fieldClass}
              />
            </Field>
          </div>
        </Section>
      </div>

      <div className="sticky bottom-0 flex items-center gap-4 border-t border-facil-border bg-background/95 py-4 backdrop-blur-sm">
        <Button type="submit" variant="primary">
          Salvar tudo
        </Button>
        {status === "success" && (
          <p className="text-sm font-medium text-facil-orange">Configurações salvas com sucesso.</p>
        )}
        {status === "error" && (
          <p className="text-sm font-medium text-red-500">Erro ao salvar. Tente novamente.</p>
        )}
      </div>
    </form>
  );
}
