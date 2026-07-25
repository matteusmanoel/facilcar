"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Save } from "lucide-react";
import { toast } from "sonner";
import { updatePageAction } from "@/features/content/server/mutations";
import { AdminFieldLabel, AdminTextarea } from "@/components/admin/AdminField";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/cn";

const SLUGS_FIXOS = new Set([
  "quem-somos",
  "politica-de-privacidade",
  "termos-de-uso",
  "nosso-estoque",
  "trabalhe-conosco",
]);

type Page = {
  id: string;
  slug: string;
  title: string;
  excerpt: string | null;
  body: string;
  status: string;
  metaTitle: string | null;
  metaDescription: string | null;
};

type Props = {
  page: Page;
  variant?: "page" | "dialog";
  onCancel?: () => void;
  onSaved?: () => void;
};

export function PageForm({ page, variant = "page", onCancel, onSaved }: Props) {
  const router = useRouter();
  const [status, setStatus] = useState(page.status);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const slugLocked = SLUGS_FIXOS.has(page.slug);

  return (
    <form
      action={async (formData) => {
        setIsSubmitting(true);
        const result = await updatePageAction(formData);
        setIsSubmitting(false);
        if (result.ok) {
          toast.success("Página salva.");
          if (onSaved) {
            onSaved();
          } else {
            router.refresh();
          }
        } else {
          toast.error("error" in result && result.error ? String(result.error) : "Erro ao salvar");
        }
      }}
      className={cn("space-y-4", variant === "page" && "mt-6 max-w-2xl")}
    >
      <input type="hidden" name="id" value={page.id} />
      <input type="hidden" name="status" value={status} />
      {slugLocked ? <input type="hidden" name="slug" value={page.slug} /> : null}

      <div className="space-y-1">
        <AdminFieldLabel>Slug</AdminFieldLabel>
        {slugLocked ? (
          <>
            <p className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 font-mono text-sm dark:border-amber-900/50 dark:bg-amber-950/30">
              {page.slug}
            </p>
            <p className="text-xs text-amber-800 dark:text-amber-300">
              Slug fixo: alterar quebraria a rota pública desta página.
            </p>
          </>
        ) : (
          <Input name="slug" required defaultValue={page.slug} className="font-mono" />
        )}
      </div>

      <div className="space-y-1">
        <AdminFieldLabel required>Título</AdminFieldLabel>
        <Input name="title" required defaultValue={page.title} />
      </div>

      <div className="space-y-1">
        <AdminFieldLabel>Status</AdminFieldLabel>
        <Select value={status} onValueChange={setStatus}>
          <SelectTrigger className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="DRAFT">Rascunho</SelectItem>
            <SelectItem value="PUBLISHED">Publicada</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-1">
        <AdminFieldLabel>Resumo</AdminFieldLabel>
        <Input name="excerpt" defaultValue={page.excerpt ?? ""} />
      </div>

      <div className="space-y-1">
        <AdminFieldLabel required>Conteúdo</AdminFieldLabel>
        <AdminTextarea name="body" rows={10} defaultValue={page.body} className="font-mono text-sm" />
      </div>

      <div className="space-y-1">
        <AdminFieldLabel>Meta título</AdminFieldLabel>
        <Input name="metaTitle" defaultValue={page.metaTitle ?? ""} />
      </div>

      <div className="space-y-1">
        <AdminFieldLabel>Meta descrição</AdminFieldLabel>
        <AdminTextarea name="metaDescription" rows={2} defaultValue={page.metaDescription ?? ""} />
      </div>

      <div className={cn("flex justify-end gap-2", variant === "dialog" && "border-t border-facil-border pt-4")}>
        {variant === "dialog" && onCancel ? (
          <Button type="button" variant="outline" onClick={onCancel} disabled={isSubmitting}>
            Cancelar
          </Button>
        ) : null}
        <Button type="submit" variant="primary" disabled={isSubmitting}>
          <Save className="h-4 w-4" />
          {isSubmitting ? "Salvando…" : "Salvar"}
        </Button>
      </div>
    </form>
  );
}
