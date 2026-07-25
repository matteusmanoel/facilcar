"use client";

import { useEffect, useState, useTransition } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Pencil, Plus, Tag } from "lucide-react";
import { toast } from "sonner";
import { deactivateBrandAction } from "@/features/admin/server/brands";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { BrandFormDialog } from "./BrandFormDialog";

type BrandRow = {
  id: string;
  name: string;
  slug: string;
  logoUrl: string | null;
  isActive: boolean;
  _count: { vehicles: number };
};

type Props = {
  brands: BrandRow[];
  canManage: boolean;
};

export function BrandsClient({ brands, canManage }: Props) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [isPending, startTransition] = useTransition();
  const [deactivateTarget, setDeactivateTarget] = useState<BrandRow | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [editBrand, setEditBrand] = useState<BrandRow | null>(null);

  useEffect(() => {
    const editId = searchParams.get("edit");
    if (editId) {
      const brand = brands.find((b) => b.id === editId);
      if (brand) {
        setEditBrand(brand);
        setFormOpen(true);
      }
    }
  }, [searchParams, brands]);

  function openCreate() {
    setEditBrand(null);
    setFormOpen(true);
  }

  function openEdit(brand: BrandRow) {
    setEditBrand(brand);
    setFormOpen(true);
  }

  function confirmDeactivate() {
    if (!deactivateTarget) return;
    startTransition(async () => {
      const result = await deactivateBrandAction(deactivateTarget.id);
      if (result.ok) {
        toast.success(`${deactivateTarget.name} foi desativada.`);
        setDeactivateTarget(null);
        router.refresh();
        return;
      }
      toast.error(typeof result.error === "string" ? result.error : "Erro ao desativar marca.");
    });
  }

  return (
    <>
      {canManage ? (
        <div className="flex justify-end">
          <Button variant="primary" size="sm" onClick={openCreate}>
            <Plus className="mr-1 h-4 w-4" />
            Nova marca
          </Button>
        </div>
      ) : null}

      <div className="overflow-hidden rounded-xl border border-facil-border bg-facil-card shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b border-facil-border bg-facil-surface">
              <tr>
                <th className="admin-table-header">Marca</th>
                <th className="admin-table-header">Slug</th>
                <th className="admin-table-header">Veículos</th>
                <th className="admin-table-header">Status</th>
                <th className="admin-table-header">Ações</th>
              </tr>
            </thead>
            <tbody>
              {brands.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-10 text-center text-sm text-facil-muted">
                    Nenhuma marca cadastrada.
                  </td>
                </tr>
              ) : (
                brands.map((brand) => (
                  <tr
                    key={brand.id}
                    className="border-t border-facil-border hover:bg-facil-surface/60"
                  >
                    <td className="admin-table-cell">
                      <div className="flex items-center gap-2 font-medium text-foreground">
                        <Tag className="h-4 w-4 text-facil-muted" />
                        {brand.name}
                      </div>
                    </td>
                    <td className="admin-table-cell font-mono text-facil-muted">{brand.slug}</td>
                    <td className="admin-table-cell text-foreground">{brand._count.vehicles}</td>
                    <td className="admin-table-cell">
                      <Badge variant={brand.isActive ? "green" : "default"}>
                        {brand.isActive ? "Ativa" : "Inativa"}
                      </Badge>
                    </td>
                    <td className="admin-table-cell">
                      <div className="flex gap-2">
                        <button
                          type="button"
                          onClick={() => openEdit(brand)}
                          className="inline-flex items-center gap-1 font-medium text-facil-orange hover:underline"
                        >
                          <Pencil className="h-3.5 w-3.5" />
                          {canManage ? "Editar" : "Ver"}
                        </button>
                        {canManage && brand.isActive && (
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            className="h-auto px-2 py-1 text-red-600 hover:text-red-700"
                            onClick={() => setDeactivateTarget(brand)}
                          >
                            Desativar
                          </Button>
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

      <BrandFormDialog
        open={formOpen}
        onOpenChange={(open) => {
          setFormOpen(open);
          if (!open) {
            setEditBrand(null);
            if (searchParams.get("edit")) {
              router.replace("/admin/marcas");
            }
          }
        }}
        brand={editBrand ?? undefined}
        readOnly={!canManage}
        onSaved={() => router.refresh()}
      />

      <Dialog open={!!deactivateTarget} onOpenChange={(o) => !o && setDeactivateTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Desativar marca?</DialogTitle>
            <DialogDescription>
              {deactivateTarget?.name} deixará de aparecer nos filtros e formulários de veículos.
              Veículos existentes não serão alterados.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button type="button" variant="outline" onClick={() => setDeactivateTarget(null)}>
              Cancelar
            </Button>
            <Button type="button" variant="destructive" disabled={isPending} onClick={confirmDeactivate}>
              {isPending ? "Desativando…" : "Desativar"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
