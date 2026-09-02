"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { Save, Trash2 } from "lucide-react";
import {
  createCustomerAction,
  deleteCustomerAction,
  updateCustomerAction,
} from "@/features/admin/server/customers";
import { customerFormSchema, type CustomerFormInput } from "@/schemas/customer";
import { AdminFieldError, AdminFieldLabel } from "@/components/admin/AdminField";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/cn";
import { formatPhoneBR } from "@/lib/input-masks";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  mode: "create" | "edit";
  customer?: {
    id: string;
    name: string;
    phone: string;
    email: string | null;
    leadCount: number;
  };
  onSaved: () => void;
  onOpenExisting?: (customer: {
    id: string;
    name: string;
    phone: string;
    email: string | null;
    leadCount: number;
  }) => void;
};

export function CustomerFormDialog({
  open,
  onOpenChange,
  mode,
  customer,
  onSaved,
  onOpenExisting,
}: Props) {
  const {
    register,
    handleSubmit,
    reset,
    setValue,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<CustomerFormInput>({
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    resolver: zodResolver(customerFormSchema) as any,
    values: {
      name: customer?.name ?? "",
      phone: customer?.phone ?? "",
      email: customer?.email ?? "",
    },
  });

  const close = () => {
    onOpenChange(false);
    reset();
  };

  const onSubmit = async (data: CustomerFormInput) => {
    const result =
      mode === "create"
        ? await createCustomerAction(data)
        : await updateCustomerAction(customer!.id, data);

    if (result.ok) {
      toast.success(mode === "create" ? "Cliente criado!" : "Cliente atualizado!");
      close();
      onSaved();
      return;
    }

    if ("existingCustomer" in result && result.existingCustomer && onOpenExisting) {
      close();
      onOpenExisting(result.existingCustomer);
      toast.info("Cliente já cadastrado — abrindo edição.");
      return;
    }

    if (typeof result.error === "string") {
      toast.error(result.error);
      return;
    }

    const firstError = Object.values(result.error).flat()[0];
    toast.error(typeof firstError === "string" ? firstError : "Dados inválidos");
  };

  const handleDelete = async () => {
    if (!customer) return;
    if (!window.confirm(`Excluir ${customer.name}? Esta ação não pode ser desfeita.`)) return;

    const result = await deleteCustomerAction(customer.id);
    if (result.ok) {
      toast.success("Cliente excluído.");
      close();
      onSaved();
      return;
    }

    toast.error(typeof result.error === "string" ? result.error : "Erro ao excluir.");
  };

  return (
    <Dialog open={open} onOpenChange={(next) => (next ? onOpenChange(true) : close())}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{mode === "create" ? "Novo cliente" : "Editar cliente"}</DialogTitle>
          <DialogDescription>
            {mode === "create"
              ? "Cadastre um contato consolidado por telefone."
              : "Atualize os dados do cliente."}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-1">
            <AdminFieldLabel required>Nome</AdminFieldLabel>
            <Input {...register("name")} className={cn(errors.name && "border-red-400")} />
            <AdminFieldError message={errors.name?.message} />
          </div>

          <div className="space-y-1">
            <AdminFieldLabel required>Telefone</AdminFieldLabel>
            <Input
              value={formatPhoneBR(watch("phone") ?? "")}
              onChange={(e) =>
                setValue("phone", formatPhoneBR(e.target.value), { shouldValidate: true, shouldDirty: true })
              }
              inputMode="numeric"
              autoComplete="tel"
              placeholder="(11) 99999-9999"
              className={cn(errors.phone && "border-red-400")}
            />
            <AdminFieldError message={errors.phone?.message} />
          </div>

          <div className="space-y-1">
            <AdminFieldLabel>E-mail</AdminFieldLabel>
            <Input
              type="email"
              {...register("email")}
              className={cn(errors.email && "border-red-400")}
            />
            <AdminFieldError message={errors.email?.message} />
          </div>

          <DialogFooter className="gap-2 sm:justify-between">
            {mode === "edit" && customer && customer.leadCount === 0 ? (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="text-red-600 hover:text-red-700 dark:text-red-400"
                onClick={handleDelete}
              >
                <Trash2 className="h-4 w-4" />
                Excluir
              </Button>
            ) : (
              <span />
            )}
            <div className="flex gap-2">
              <Button type="button" variant="outline" onClick={close}>
                Cancelar
              </Button>
              <Button type="submit" variant="primary" disabled={isSubmitting}>
                <Save className="h-4 w-4" />
                {isSubmitting ? "Salvando…" : "Salvar"}
              </Button>
            </div>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
