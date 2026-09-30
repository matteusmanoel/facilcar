"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Pencil, Trash2, Plus, Eye, EyeOff } from "lucide-react";
import type { Testimonial } from "@prisma/client";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  createTestimonialAction,
  updateTestimonialAction,
  deleteTestimonialAction,
} from "@/features/testimonials/server/actions";

type FormData = {
  name: string;
  comment: string;
  imageUrl: string;
  sortOrder: number;
  published: boolean;
};

const EMPTY: FormData = { name: "", comment: "", imageUrl: "", sortOrder: 0, published: false };

function TestimonialForm({
  initial,
  onSave,
  onCancel,
}: {
  initial: FormData;
  onSave: (data: FormData) => void;
  onCancel: () => void;
}) {
  const [form, setForm] = useState<FormData>(initial);

  function set<K extends keyof FormData>(key: K, value: FormData[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  return (
    <div className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-zinc-200 mb-1">Nome</label>
        <input
          className="w-full rounded-lg border border-facil-border bg-facil-surface px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-facil-orange"
          value={form.name}
          onChange={(e) => set("name", e.target.value)}
          placeholder="Ex.: João Silva"
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-zinc-200 mb-1">Depoimento</label>
        <textarea
          rows={4}
          className="w-full rounded-lg border border-facil-border bg-facil-surface px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-facil-orange resize-none"
          value={form.comment}
          onChange={(e) => set("comment", e.target.value)}
          placeholder="O depoimento do cliente..."
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-zinc-200 mb-1">URL da foto</label>
        <input
          className="w-full rounded-lg border border-facil-border bg-facil-surface px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-facil-orange"
          value={form.imageUrl}
          onChange={(e) => set("imageUrl", e.target.value)}
          placeholder="https://..."
        />
        {form.imageUrl && (
          <img
            src={form.imageUrl}
            alt="Prévia"
            className="mt-2 h-16 w-16 rounded-full object-cover border border-facil-border"
            onError={(e) => ((e.currentTarget as HTMLImageElement).style.display = "none")}
          />
        )}
      </div>
      <div className="flex gap-4 items-center">
        <div className="flex-1">
          <label className="block text-sm font-medium text-zinc-200 mb-1">Ordem</label>
          <input
            type="number"
            className="w-full rounded-lg border border-facil-border bg-facil-surface px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-facil-orange"
            value={form.sortOrder}
            onChange={(e) => set("sortOrder", Number(e.target.value))}
          />
        </div>
        <div className="flex items-center gap-2 pt-6">
          <input
            id="published"
            type="checkbox"
            className="h-4 w-4 accent-facil-orange"
            checked={form.published}
            onChange={(e) => set("published", e.target.checked)}
          />
          <label htmlFor="published" className="text-sm text-zinc-300">
            Publicado
          </label>
        </div>
      </div>
      <DialogFooter className="gap-2">
        <Button type="button" variant="outline" onClick={onCancel}>
          Cancelar
        </Button>
        <Button
          type="button"
          onClick={() => {
            if (!form.name.trim() || !form.comment.trim() || !form.imageUrl.trim()) {
              toast.error("Preencha nome, depoimento e URL da foto.");
              return;
            }
            onSave(form);
          }}
        >
          Salvar
        </Button>
      </DialogFooter>
    </div>
  );
}

export function TestimonialsClient({ testimonials }: { testimonials: Testimonial[] }) {
  const router = useRouter();
  const [list, setList] = useState<Testimonial[]>(testimonials);
  const [editTarget, setEditTarget] = useState<Testimonial | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [isPending, startTransition] = useTransition();

  function refresh() {
    router.refresh();
  }

  function handleCreate(data: FormData) {
    startTransition(async () => {
      try {
        await createTestimonialAction(data);
        toast.success("Depoimento criado.");
        setShowCreate(false);
        refresh();
      } catch {
        toast.error("Erro ao criar depoimento.");
      }
    });
  }

  function handleEdit(data: FormData) {
    if (!editTarget) return;
    startTransition(async () => {
      try {
        await updateTestimonialAction(editTarget.id, data);
        toast.success("Depoimento atualizado.");
        setEditTarget(null);
        refresh();
      } catch {
        toast.error("Erro ao atualizar depoimento.");
      }
    });
  }

  function handleTogglePublished(t: Testimonial) {
    startTransition(async () => {
      try {
        await updateTestimonialAction(t.id, { published: !t.published });
        toast.success(t.published ? "Depoimento ocultado." : "Depoimento publicado.");
        refresh();
      } catch {
        toast.error("Erro ao atualizar depoimento.");
      }
    });
  }

  function handleDelete(t: Testimonial) {
    if (!confirm(`Excluir depoimento de ${t.name}?`)) return;
    startTransition(async () => {
      try {
        await deleteTestimonialAction(t.id);
        setList((prev) => prev.filter((x) => x.id !== t.id));
        toast.success("Depoimento excluído.");
        refresh();
      } catch {
        toast.error("Erro ao excluir depoimento.");
      }
    });
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button onClick={() => setShowCreate(true)} className="gap-2">
          <Plus className="h-4 w-4" />
          Novo depoimento
        </Button>
      </div>

      {list.length === 0 ? (
        <p className="text-sm text-facil-muted py-8 text-center">
          Nenhum depoimento cadastrado ainda.
        </p>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {list.map((t) => (
            <div
              key={t.id}
              className="flex flex-col gap-3 rounded-xl border border-facil-border bg-facil-surface p-4"
            >
              <div className="flex items-center gap-3">
                <img
                  src={t.imageUrl}
                  alt={t.name}
                  className="h-12 w-12 rounded-full object-cover border border-facil-border shrink-0"
                  onError={(e) => {
                    (e.currentTarget as HTMLImageElement).src =
                      "https://ui-avatars.com/api/?name=" + encodeURIComponent(t.name);
                  }}
                />
                <div className="min-w-0">
                  <p className="font-semibold text-sm text-foreground truncate">{t.name}</p>
                  <p className="text-xs text-facil-muted">Ordem: {t.sortOrder}</p>
                </div>
                <span
                  className={`ml-auto text-xs px-2 py-0.5 rounded-full ${
                    t.published
                      ? "bg-green-500/10 text-green-400"
                      : "bg-zinc-700/40 text-zinc-400"
                  }`}
                >
                  {t.published ? "Publicado" : "Oculto"}
                </span>
              </div>
              <p className="text-sm text-zinc-300 line-clamp-3">{t.comment}</p>
              <div className="flex gap-2 mt-auto">
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-7 gap-1 px-2 text-xs"
                  onClick={() => handleTogglePublished(t)}
                  disabled={isPending}
                >
                  {t.published ? (
                    <>
                      <EyeOff className="h-3.5 w-3.5" /> Ocultar
                    </>
                  ) : (
                    <>
                      <Eye className="h-3.5 w-3.5" /> Publicar
                    </>
                  )}
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-7 gap-1 px-2 text-xs"
                  onClick={() => setEditTarget(t)}
                >
                  <Pencil className="h-3.5 w-3.5" /> Editar
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-7 gap-1 px-2 text-xs text-red-400 hover:text-red-300"
                  onClick={() => handleDelete(t)}
                  disabled={isPending}
                >
                  <Trash2 className="h-3.5 w-3.5" /> Excluir
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create dialog */}
      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent className="dark:border-zinc-700 dark:bg-zinc-900 max-w-lg">
          <DialogHeader>
            <DialogTitle>Novo depoimento</DialogTitle>
          </DialogHeader>
          <TestimonialForm
            initial={EMPTY}
            onSave={handleCreate}
            onCancel={() => setShowCreate(false)}
          />
        </DialogContent>
      </Dialog>

      {/* Edit dialog */}
      <Dialog open={!!editTarget} onOpenChange={(o) => !o && setEditTarget(null)}>
        <DialogContent className="dark:border-zinc-700 dark:bg-zinc-900 max-w-lg">
          <DialogHeader>
            <DialogTitle>Editar depoimento</DialogTitle>
          </DialogHeader>
          {editTarget && (
            <TestimonialForm
              initial={{
                name: editTarget.name,
                comment: editTarget.comment,
                imageUrl: editTarget.imageUrl,
                sortOrder: editTarget.sortOrder,
                published: editTarget.published,
              }}
              onSave={handleEdit}
              onCancel={() => setEditTarget(null)}
            />
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
