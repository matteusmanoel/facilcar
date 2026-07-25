"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Save } from "lucide-react";
import { createBrandAction, updateBrandAction } from "@/features/admin/server/brands";
import { AdminFieldLabel } from "@/components/admin/AdminField";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/cn";

type BrandData = {
  id: string;
  name: string;
  slug: string;
  logoUrl: string | null;
  isActive: boolean;
};

type Props = {
  brand?: BrandData;
  readOnly?: boolean;
  variant?: "page" | "dialog";
  onCancel?: () => void;
  onSaved?: () => void;
};

function slugify(text: string): string {
  return text
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9\s-]/g, "")
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-+|-+$/g, "");
}

export function BrandForm({
  brand,
  readOnly = false,
  variant = "page",
  onCancel,
  onSaved,
}: Props) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const isEdit = !!brand;

  const [name, setName] = useState(brand?.name ?? "");
  const [slug, setSlug] = useState(brand?.slug ?? "");
  const [logoUrl, setLogoUrl] = useState(brand?.logoUrl ?? "");
  const [isActive, setIsActive] = useState(brand?.isActive ?? true);
  const [slugTouched, setSlugTouched] = useState(isEdit);

  function handleNameChange(value: string) {
    setName(value);
    if (!slugTouched) {
      setSlug(slugify(value));
    }
  }

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (readOnly) return;

    startTransition(async () => {
      const payload = {
        name,
        slug,
        logoUrl: logoUrl || undefined,
        isActive,
      };

      const result = isEdit
        ? await updateBrandAction(brand!.id, payload)
        : await createBrandAction(payload);

      if (result.ok) {
        toast.success(isEdit ? "Marca atualizada." : "Marca criada.");
        if (onSaved) {
          onSaved();
          return;
        }
        router.push("/admin/marcas");
        router.refresh();
        return;
      }

      if (typeof result.error === "string") {
        toast.error(result.error);
        return;
      }

      const firstFieldError = Object.values(result.error).flat()[0];
      toast.error(firstFieldError ?? "Verifique os campos do formulário.");
    });
  }

  return (
    <form
      onSubmit={onSubmit}
      className={cn(
        "space-y-5",
        variant === "page" &&
          "max-w-xl rounded-xl border border-facil-border bg-facil-card p-6 shadow-sm",
      )}
    >
      {readOnly && (
        <p className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:bg-amber-950/30 dark:text-amber-300">
          Modo somente leitura — você não pode alterar marcas.
        </p>
      )}

      <div className="space-y-2">
        <AdminFieldLabel htmlFor="name">Nome</AdminFieldLabel>
        <Input
          id="name"
          value={name}
          onChange={(e) => handleNameChange(e.target.value)}
          disabled={readOnly || isPending}
          required
        />
      </div>

      <div className="space-y-2">
        <AdminFieldLabel htmlFor="slug">Slug</AdminFieldLabel>
        <Input
          id="slug"
          value={slug}
          onChange={(e) => {
            setSlugTouched(true);
            setSlug(e.target.value);
          }}
          disabled={readOnly || isPending}
          required
        />
      </div>

      <div className="space-y-2">
        <AdminFieldLabel htmlFor="logoUrl">URL do logo (opcional)</AdminFieldLabel>
        <Input
          id="logoUrl"
          type="url"
          value={logoUrl}
          onChange={(e) => setLogoUrl(e.target.value)}
          disabled={readOnly || isPending}
          placeholder="https://..."
        />
      </div>

      {isEdit && (
        <label className="flex items-center gap-2 text-sm text-foreground">
          <input
            type="checkbox"
            checked={isActive}
            onChange={(e) => setIsActive(e.target.checked)}
            disabled={readOnly || isPending}
            className="rounded border-facil-border accent-facil-orange"
          />
          Marca ativa
        </label>
      )}

      {!readOnly && (
        <div className={cn("flex justify-end gap-2", variant === "dialog" && "border-t border-facil-border pt-4")}>
          {variant === "dialog" && onCancel ? (
            <Button type="button" variant="outline" onClick={onCancel} disabled={isPending}>
              Cancelar
            </Button>
          ) : null}
          <Button type="submit" variant="primary" disabled={isPending}>
            <Save className="h-4 w-4" />
            {isPending ? "Salvando…" : isEdit ? "Salvar" : "Criar marca"}
          </Button>
        </div>
      )}
    </form>
  );
}
