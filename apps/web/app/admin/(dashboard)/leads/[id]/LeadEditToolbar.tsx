"use client";

import { Pencil } from "lucide-react";
import { Button } from "@/components/ui/button";

export function LeadEditToolbar({
  editing,
  pending,
  onEdit,
  onCancel,
}: {
  editing: boolean;
  pending: boolean;
  onEdit: () => void;
  onCancel: () => void;
}) {
  if (!editing) {
    return (
      <Button type="button" variant="outline" size="sm" onClick={onEdit}>
        <Pencil className="h-3.5 w-3.5" />
        Editar
      </Button>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <Button type="button" variant="ghost" size="sm" disabled={pending} onClick={onCancel}>
        Cancelar
      </Button>
      <Button type="submit" variant="primary" size="sm" disabled={pending}>
        {pending ? "Salvando…" : "Salvar"}
      </Button>
    </div>
  );
}
