"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { updatePageAction } from "@/features/content/server/mutations";

type Page = { id: string; slug: string; title: string; excerpt: string | null; body: string; status: string; metaTitle: string | null; metaDescription: string | null };

export function PageForm({ page }: { page: Page }) {
  const router = useRouter();
  const [message, setMessage] = useState<{ type: "ok" | "error"; text: string } | null>(null);

  return (
    <form
      action={async (formData: FormData) => {
        setMessage(null);
        const result = await updatePageAction(formData);
        if (result.ok) {
          setMessage({ type: "ok", text: "Salvo." });
          router.refresh();
        } else {
          setMessage({ type: "error", text: result.error ?? "Erro" });
        }
      }}
      className="mt-6 max-w-2xl space-y-4"
    >
      <input type="hidden" name="id" value={page.id} />
      <label className="block text-sm font-medium">
        Slug *
        <input name="slug" required defaultValue={page.slug} className="mt-1 w-full rounded border px-3 py-2 font-mono" />
      </label>
      <label className="block text-sm font-medium">
        Título *
        <input name="title" required defaultValue={page.title} className="mt-1 w-full rounded border px-3 py-2" />
      </label>
      <label className="block text-sm font-medium">
        Status
        <select name="status" defaultValue={page.status} className="mt-1 w-full rounded border px-3 py-2">
          <option value="DRAFT">DRAFT</option>
          <option value="PUBLISHED">PUBLISHED</option>
        </select>
      </label>
      <label className="block text-sm font-medium">
        Resumo
        <input name="excerpt" defaultValue={page.excerpt ?? ""} className="mt-1 w-full rounded border px-3 py-2" />
      </label>
      <label className="block text-sm font-medium">
        Conteúdo *
        <textarea name="body" rows={12} defaultValue={page.body} className="mt-1 w-full rounded border px-3 py-2 font-mono text-sm" />
      </label>
      <label className="block text-sm font-medium">
        Meta título
        <input name="metaTitle" defaultValue={page.metaTitle ?? ""} className="mt-1 w-full rounded border px-3 py-2" />
      </label>
      <label className="block text-sm font-medium">
        Meta descrição
        <textarea name="metaDescription" rows={2} defaultValue={page.metaDescription ?? ""} className="mt-1 w-full rounded border px-3 py-2" />
      </label>
      {message && <p className={message.type === "ok" ? "text-green-600" : "text-red-600"}>{message.text}</p>}
      <button type="submit" className="rounded bg-zinc-900 px-4 py-2 text-white hover:bg-zinc-800">
        Salvar
      </button>
    </form>
  );
}
