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
import { BlogPostForm } from "./BlogPostForm";

type PostRow = {
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
  posts: PostRow[];
};

export function BlogClient({ posts }: Props) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [editPost, setEditPost] = useState<PostRow | null>(null);

  useEffect(() => {
    const editId = searchParams.get("edit");
    if (editId) {
      const post = posts.find((p) => p.id === editId);
      if (post) setEditPost(post);
    }
  }, [searchParams, posts]);

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
              {posts.length === 0 ? (
                <tr>
                  <td colSpan={4} className="py-10 text-center text-sm text-facil-muted">
                    Nenhum post. Rode o seed para criar posts iniciais.
                  </td>
                </tr>
              ) : (
                posts.map((p) => (
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
                        {p.status === "PUBLISHED" ? "Publicado" : "Rascunho"}
                      </span>
                    </td>
                    <td className="admin-table-cell">
                      <div className="flex gap-3">
                        <button
                          type="button"
                          onClick={() => setEditPost(p)}
                          className="inline-flex items-center gap-1 font-medium text-facil-orange hover:underline"
                        >
                          <Pencil className="h-3.5 w-3.5" />
                          Editar
                        </button>
                        {p.status === "PUBLISHED" && (
                          <Link
                            href={`/blog/${p.slug}`}
                            target="_blank"
                            className="text-facil-muted hover:text-foreground"
                          >
                            Ver
                          </Link>
                        )}
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
        open={!!editPost}
        onOpenChange={(open) => {
          if (!open) {
            setEditPost(null);
            if (searchParams.get("edit")) router.replace("/admin/blog");
          }
        }}
      >
        <DialogContent className="max-h-[90vh] max-w-2xl overflow-y-auto">
          {editPost ? (
            <>
              <DialogHeader>
                <DialogTitle>Editar post</DialogTitle>
                <DialogDescription>{editPost.title}</DialogDescription>
              </DialogHeader>
              <BlogPostForm
                key={editPost.id}
                post={editPost}
                variant="dialog"
                onCancel={() => setEditPost(null)}
                onSaved={() => {
                  setEditPost(null);
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
