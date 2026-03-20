"use client";

import { useState } from "react";
import { updateSettingsAction } from "./action";
import type { SiteSettings } from "@prisma/client";

type Props = { settings: SiteSettings };

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
      className="mt-6 max-w-3xl space-y-8"
    >
      <input type="hidden" name="id" value={settings.id} />

      <section className="space-y-4 rounded-lg border bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-zinc-900">Identidade</h2>
        <label className="block text-sm font-medium">
          Nome do site
          <input
            name="siteName"
            defaultValue={settings.siteName}
            className="mt-1 w-full rounded border px-3 py-2"
          />
        </label>
        <label className="block text-sm font-medium">
          Título do hero (home)
          <input
            name="heroTitle"
            defaultValue={settings.heroTitle ?? ""}
            className="mt-1 w-full rounded border px-3 py-2"
          />
        </label>
        <label className="block text-sm font-medium">
          Subtítulo do hero
          <textarea
            name="heroSubtitle"
            rows={2}
            defaultValue={settings.heroSubtitle ?? ""}
            className="mt-1 w-full rounded border px-3 py-2"
          />
        </label>
        <label className="block text-sm font-medium">
          Texto do rodapé (resumo da loja)
          <textarea
            name="footerText"
            rows={3}
            defaultValue={settings.footerText ?? ""}
            className="mt-1 w-full rounded border px-3 py-2"
          />
        </label>
      </section>

      <section className="space-y-4 rounded-lg border bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-zinc-900">Contato</h2>
        <label className="block text-sm font-medium">
          WhatsApp (E.164, ex: 5545999123456)
          <input
            name="defaultWhatsappNumber"
            defaultValue={settings.defaultWhatsappNumber}
            className="mt-1 w-full rounded border px-3 py-2 font-mono text-sm"
          />
        </label>
        <label className="block text-sm font-medium">
          E-mail padrão
          <input
            name="defaultEmail"
            type="email"
            defaultValue={settings.defaultEmail}
            className="mt-1 w-full rounded border px-3 py-2"
          />
        </label>
        <label className="block text-sm font-medium">
          Telefone (exibição)
          <input
            name="phoneNumber"
            defaultValue={settings.phoneNumber ?? ""}
            className="mt-1 w-full rounded border px-3 py-2"
          />
        </label>
      </section>

      <section className="space-y-4 rounded-lg border bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-zinc-900">Endereço</h2>
        <label className="block text-sm font-medium">
          Logradouro
          <input
            name="addressLine"
            defaultValue={settings.addressLine ?? ""}
            className="mt-1 w-full rounded border px-3 py-2"
          />
        </label>
        <div className="grid gap-4 sm:grid-cols-3">
          <label className="block text-sm font-medium">
            Cidade
            <input
              name="city"
              defaultValue={settings.city ?? ""}
              className="mt-1 w-full rounded border px-3 py-2"
            />
          </label>
          <label className="block text-sm font-medium">
            UF
            <input
              name="state"
              maxLength={2}
              defaultValue={settings.state ?? ""}
              className="mt-1 w-full rounded border px-3 py-2 uppercase"
            />
          </label>
          <label className="block text-sm font-medium">
            CEP
            <input
              name="zipCode"
              defaultValue={settings.zipCode ?? ""}
              className="mt-1 w-full rounded border px-3 py-2"
            />
          </label>
        </div>
      </section>

      <section className="space-y-4 rounded-lg border bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-zinc-900">Redes sociais</h2>
        <label className="block text-sm font-medium">
          Instagram (URL)
          <input
            name="instagramUrl"
            type="url"
            placeholder="https://instagram.com/..."
            defaultValue={settings.instagramUrl ?? ""}
            className="mt-1 w-full rounded border px-3 py-2"
          />
        </label>
        <label className="block text-sm font-medium">
          Facebook (URL)
          <input
            name="facebookUrl"
            type="url"
            defaultValue={settings.facebookUrl ?? ""}
            className="mt-1 w-full rounded border px-3 py-2"
          />
        </label>
        <label className="block text-sm font-medium">
          YouTube (URL)
          <input
            name="youtubeUrl"
            type="url"
            defaultValue={settings.youtubeUrl ?? ""}
            className="mt-1 w-full rounded border px-3 py-2"
          />
        </label>
      </section>

      <section className="space-y-4 rounded-lg border bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-zinc-900">SEO padrão</h2>
        <label className="block text-sm font-medium">
          Título padrão (meta)
          <input
            name="seoDefaultTitle"
            defaultValue={settings.seoDefaultTitle ?? ""}
            className="mt-1 w-full rounded border px-3 py-2"
          />
        </label>
        <label className="block text-sm font-medium">
          Descrição padrão
          <textarea
            name="seoDefaultDescription"
            rows={2}
            defaultValue={settings.seoDefaultDescription ?? ""}
            className="mt-1 w-full rounded border px-3 py-2"
          />
        </label>
      </section>

      {status === "success" && <p className="text-sm text-green-600">Salvo.</p>}
      {status === "error" && <p className="text-sm text-red-600">Erro ao salvar.</p>}
      <button
        type="submit"
        className="rounded-lg bg-orange-600 px-6 py-2.5 font-semibold text-white hover:bg-orange-700"
      >
        Salvar tudo
      </button>
    </form>
  );
}
