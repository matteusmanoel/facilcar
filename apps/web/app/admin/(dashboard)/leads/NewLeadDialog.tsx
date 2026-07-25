"use client";

import { useRouter } from "next/navigation";
import { Plus } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ManualLeadForm } from "./novo/ManualLeadForm";

type VehicleOption = { id: string; title: string };

type Props = {
  vehicles: VehicleOption[];
};

export function NewLeadDialog({ vehicles }: Props) {
  const router = useRouter();
  const [open, setOpen] = useState(false);

  return (
    <>
      <Button variant="primary" size="sm" onClick={() => setOpen(true)}>
        <Plus className="mr-1 h-4 w-4" />
        Novo lead
      </Button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[90vh] max-w-lg overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Novo lead</DialogTitle>
            <DialogDescription>
              Cadastre manualmente um contato recebido por telefone, WhatsApp ou balcão.
            </DialogDescription>
          </DialogHeader>
          <ManualLeadForm
            vehicles={vehicles}
            variant="dialog"
            onCancel={() => setOpen(false)}
            onSuccess={(leadId) => {
              setOpen(false);
              router.refresh();
              router.push(`/admin/leads/${leadId}`);
            }}
          />
        </DialogContent>
      </Dialog>
    </>
  );
}
