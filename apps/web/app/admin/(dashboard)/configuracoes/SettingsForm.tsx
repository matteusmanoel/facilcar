"use client";

import { useState } from "react";
import { updateSettingsAction } from "./action";
import type { SiteSettings } from "@prisma/client";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/cn";
import { normalizePublicTheme } from "@/lib/theme";
import { formatPhoneBR } from "@/lib/input-masks";

function extractCoordsFromMapsUrl(url: string): { lat: number; lng: number } | null {
  if (!url) return null;
  // Pattern 1: @lat,lng (share links)
  let m = url.match(/@(-?\d+\.\d+),(-?\d+\.\d+)/);
  if (m) return { lat: parseFloat(m[1]), lng: parseFloat(m[2]) };
  // Pattern 2: !3dlat!4dlng (embedded data parameter)
  m = url.match(/!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)/);
  if (m) return { lat: parseFloat(m[1]), lng: parseFloat(m[2]) };
  return null;
}

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
  const [themeValue, setThemeValue] = useState(publicTheme);
  const [phoneNumber, setPhoneNumber] = useState(() =>
    formatPhoneBR(settings.phoneNumber ?? ""),
  );
  const [mapsUrl, setMapsUrl] = useState(settings.googleMapsUrl ?? "");
  const [coords, setCoords] = useState<{ lat: number; lng: number } | null>(
    settings.latitude != null && settings.longitude != null
      ? { lat: settings.latitude, lng: settings.longitude }
      : null,
  );

  function handleMapsUrlChange(url: string) {
    setMapsUrl(url);
    const extracted = extractCoordsFromMapsUrl(url);
    setCoords(extracted);
  }

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
            <input type="hidden" name="publicTheme" value={themeValue} />
            <Select
              value={themeValue}
              onValueChange={(value) => {
                if (value === "light" || value === "dark") setThemeValue(value);
              }}
            >
              <SelectTrigger className="mt-1 w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="dark">Escuro (padrão)</SelectItem>
                <SelectItem value="light">Claro</SelectItem>
              </SelectContent>
            </Select>
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
              value={phoneNumber}
              onChange={(e) => setPhoneNumber(formatPhoneBR(e.target.value))}
              inputMode="numeric"
              autoComplete="tel"
              placeholder="(45) 98823-0845"
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
          <Field label="Link do Google Maps (para pin de localização via WhatsApp)">
            <input type="hidden" name="googleMapsUrl" value={mapsUrl} />
            <input type="hidden" name="latitude" value={coords?.lat ?? ""} />
            <input type="hidden" name="longitude" value={coords?.lng ?? ""} />
            <Input
              value={mapsUrl}
              onChange={(e) => handleMapsUrlChange(e.target.value)}
              placeholder="https://www.google.com/maps/place/..."
              className="mt-1 font-mono text-xs"
            />
            {coords ? (
              <p className="mt-1 text-xs text-facil-orange">
                ✓ Coordenadas extraídas: {coords.lat.toFixed(6)}, {coords.lng.toFixed(6)}
              </p>
            ) : mapsUrl ? (
              <p className="mt-1 text-xs text-red-400">
                Não foi possível extrair coordenadas. Verifique o link.
              </p>
            ) : null}
          </Field>
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
