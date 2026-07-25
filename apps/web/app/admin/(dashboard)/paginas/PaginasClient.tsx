"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Pencil } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { PageForm } from "./PageForm";

type PageRow = {
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
  pages: PageRow[];
};

export function PaginasClient({ pages }: Props) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [editPage, setEditPage] = useState<PageRow | null>(null);

  useEffect(() => {
    const editId = searchParams.get("edit");
    if (editId) {
      const page = pages.find((p) => p.id === editId);
      if (page) setEditPage(page);
    }
  }, [searchParams, pages]);

  return (
    <>
      <div className="overflow-hidden rounded-xl border border-facil-border bg-facil-card shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b border-facil-border bg-facil-surface">
              <tr>
                <th className="admin-table-header">Slug</th>
                <th className="admin-table-header">Título</th>
                <th className="admin-table-header">Status</th>
                <th className="admin-table-header">Ações</th>
              </tr>
            </thead>
            <tbody>
              {pages.length === 0 ? (
                <tr>
                  <td colSpan={4} className="py-10 text-center text-sm text-facil-muted">
                    Nenhuma página. Rode o seed para criar páginas iniciais.
                  </td>
                </tr>
              ) : (
                pages.map((p) => (
                  <tr
                    key={p.id}
                    className="border-t border-facil-border hover:bg-facil-surface/60"
                  >
                    <td className="admin-table-cell font-mono text-facil-muted">{p.slug}</td>
                    <td className="admin-table-cell font-medium text-foreground">{p.title}</td>
                    <td className="admin-table-cell">
                      <span
                        className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                          p.status === "PUBLISHED"
                            ? "bg-green-100 text-green-800 dark:bg-green-950/40 dark:text-green-400"
                            : "bg-facil-surface text-facil-muted"
                        }`}
                      >
                        {p.status === "PUBLISHED" ? "Publicada" : "Rascunho"}
                      </span>
                    </td>
                    <td className="admin-table-cell">
                      <div className="flex gap-3">
                        <button
                          type="button"
                          onClick={() => setEditPage(p)}
                          className="inline-flex items-center gap-1 font-medium text-facil-orange hover:underline"
                        >
                          <Pencil className="h-3.5 w-3.5" />
                          Editar
                        </button>
                        <Link
                          href={`/${p.slug}`}
                          target="_blank"
                          className="text-facil-muted hover:text-foreground"
                        >
                          Ver
                        </Link>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      <Dialog
        open={!!editPage}
        onOpenChange={(open) => {
          if (!open) {
            setEditPage(null);
            if (searchParams.get("edit")) router.replace("/admin/paginas");
          }
        }}
      >
        <DialogContent className="max-h-[90vh] max-w-2xl overflow-y-auto">
          {editPage ? (
            <>
              <DialogHeader>
                <DialogTitle>Editar página</DialogTitle>
                <DialogDescription>{editPage.title}</DialogDescription>
              </DialogHeader>
              <PageForm
                key={editPage.id}
                page={editPage}
                variant="dialog"
                onCancel={() => setEditPage(null)}
                onSaved={() => {
                  setEditPage(null);
                  router.refresh();
                }}
              />
            </>
          ) : null}
        </DialogContent>
      </Dialog>
    </>
  );
}
