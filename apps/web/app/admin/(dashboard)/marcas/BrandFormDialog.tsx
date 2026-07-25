"use client";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { BrandForm } from "./BrandForm";

type BrandData = {
  id: string;
  name: string;
  slug: string;
  logoUrl: string | null;
  isActive: boolean;
};

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  brand?: BrandData;
  readOnly?: boolean;
  onSaved: () => void;
};

export function BrandFormDialog({ open, onOpenChange, brand, readOnly, onSaved }: Props) {
  const isEdit = !!brand;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] max-w-md overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{isEdit ? (readOnly ? "Ver marca" : "Editar marca") : "Nova marca"}</DialogTitle>
          <DialogDescription>
            {isEdit ? brand?.name : "Cadastre uma marca para o catálogo de veículos."}
          </DialogDescription>
        </DialogHeader>
        <BrandForm
          key={brand?.id ?? "new"}
          brand={brand}
          readOnly={readOnly}
          variant="dialog"
          onCancel={() => onOpenChange(false)}
          onSaved={() => {
            onOpenChange(false);
            onSaved();
          }}
        />
      </DialogContent>
    </Dialog>
  );
}
