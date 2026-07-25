"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Save } from "lucide-react";
import { toast } from "sonner";
import { updateBlogPostAction } from "@/features/content/server/mutations";
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

type Post = {
  id: string;
  slug: string;
  title: string;
  excerpt: string | null;
  body: string;
  status: string;
  coverImageUrl: string | null;
  metaTitle: string | null;
  metaDescription: string | null;
};

type Props = {
  post: Post;
  variant?: "page" | "dialog";
  onCancel?: () => void;
  onSaved?: () => void;
};

export function BlogPostForm({ post, variant = "page", onCancel, onSaved }: Props) {
  const router = useRouter();
  const [status, setStatus] = useState(post.status);
  const [isSubmitting, setIsSubmitting] = useState(false);

  return (
    <form
      action={async (formData: FormData) => {
        setIsSubmitting(true);
        const result = await updateBlogPostAction(formData);
        setIsSubmitting(false);
        if (result.ok) {
          toast.success("Post salvo.");
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
      <input type="hidden" name="id" value={post.id} />
      <input type="hidden" name="status" value={status} />

      <div className="space-y-1">
        <AdminFieldLabel required>Slug</AdminFieldLabel>
        <Input name="slug" required defaultValue={post.slug} className="font-mono" />
      </div>

      <div className="space-y-1">
        <AdminFieldLabel required>Título</AdminFieldLabel>
        <Input name="title" required defaultValue={post.title} />
      </div>

      <div className="space-y-1">
        <AdminFieldLabel>Status</AdminFieldLabel>
        <Select value={status} onValueChange={setStatus}>
          <SelectTrigger className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="DRAFT">Rascunho</SelectItem>
            <SelectItem value="PUBLISHED">Publicado</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-1">
        <AdminFieldLabel>Resumo</AdminFieldLabel>
        <Input name="excerpt" defaultValue={post.excerpt ?? ""} />
      </div>

      <div className="space-y-1">
        <AdminFieldLabel>URL da imagem de capa</AdminFieldLabel>
        <Input name="coverImageUrl" defaultValue={post.coverImageUrl ?? ""} />
      </div>

      <div className="space-y-1">
        <AdminFieldLabel required>Conteúdo</AdminFieldLabel>
        <AdminTextarea name="body" rows={10} defaultValue={post.body} className="font-mono text-sm" />
      </div>

      <div className="space-y-1">
        <AdminFieldLabel>Meta título</AdminFieldLabel>
        <Input name="metaTitle" defaultValue={post.metaTitle ?? ""} />
      </div>

      <div className="space-y-1">
        <AdminFieldLabel>Meta descrição</AdminFieldLabel>
        <AdminTextarea name="metaDescription" rows={2} defaultValue={post.metaDescription ?? ""} />
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
