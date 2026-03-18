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
      className="mt-6 max-w-xl space-y-4"
    >
      <input type="hidden" name="id" value={settings.id} />
      <label className="block text-sm font-medium">
        Nome do site
        <input
          name="siteName"
          defaultValue={settings.siteName}
          className="mt-1 w-full rounded border px-3 py-2"
        />
      </label>
      <label className="block text-sm font-medium">
        WhatsApp (E.164)
        <input
          name="defaultWhatsappNumber"
          defaultValue={settings.defaultWhatsappNumber}
          className="mt-1 w-full rounded border px-3 py-2"
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
        Telefone
        <input
          name="phoneNumber"
          defaultValue={settings.phoneNumber ?? ""}
          className="mt-1 w-full rounded border px-3 py-2"
        />
      </label>
      <label className="block text-sm font-medium">
        Título do hero
        <input
          name="heroTitle"
          defaultValue={settings.heroTitle ?? ""}
          className="mt-1 w-full rounded border px-3 py-2"
        />
      </label>
      <label className="block text-sm font-medium">
        Subtítulo do hero
        <input
          name="heroSubtitle"
          defaultValue={settings.heroSubtitle ?? ""}
          className="mt-1 w-full rounded border px-3 py-2"
        />
      </label>
      {status === "success" && <p className="text-sm text-green-600">Salvo.</p>}
      {status === "error" && <p className="text-sm text-red-600">Erro ao salvar.</p>}
      <button type="submit" className="rounded bg-zinc-900 px-4 py-2 text-white hover:bg-zinc-800">
        Salvar
      </button>
    </form>
  );
}
