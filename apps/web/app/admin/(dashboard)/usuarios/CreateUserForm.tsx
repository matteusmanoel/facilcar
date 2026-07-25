"use client";

import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { Save } from "lucide-react";
import { createUserAction } from "@/features/admin/server/users";
import { createUserSchema, type CreateUserInput } from "@/schemas/user";
import { AdminFieldError, AdminFieldLabel } from "@/components/admin/AdminField";
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
import { USER_ROLE_OPTIONS } from "./user-role-labels";

type Props = {
  variant?: "page" | "dialog";
  onCancel?: () => void;
  onCreated?: () => void;
};

export function CreateUserForm({ variant = "page", onCancel, onCreated }: Props) {
  const router = useRouter();

  const {
    register,
    handleSubmit,
    setValue,
    watch,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<CreateUserInput>({
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    resolver: zodResolver(createUserSchema) as any,
    defaultValues: {
      name: "",
      email: "",
      password: "",
      role: "LEAD_MANAGER",
    },
  });

  const role = watch("role");

  const onSubmit = async (data: CreateUserInput) => {
    const result = await createUserAction(data);

    if (result.ok) {
      toast.success("Usuário criado com sucesso!");
      reset();
      if (onCreated) {
        onCreated();
        return;
      }
      router.push(`/admin/usuarios/${result.id}`);
      return;
    }

    if (typeof result.error === "string") {
      toast.error(result.error);
      return;
    }

    const firstError = Object.values(result.error).flat()[0];
    toast.error(typeof firstError === "string" ? firstError : "Dados inválidos");
  };

  return (
    <form
      onSubmit={handleSubmit(onSubmit)}
      className={cn(
        "space-y-5",
        variant === "page" ? "admin-card max-w-2xl p-6" : "p-1",
      )}
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1 sm:col-span-2">
          <AdminFieldLabel required>Nome</AdminFieldLabel>
          <Input
            {...register("name")}
            placeholder="Nome completo"
            className={cn(errors.name && "border-red-400")}
          />
          <AdminFieldError message={errors.name?.message} />
        </div>

        <div className="space-y-1">
          <AdminFieldLabel required>E-mail</AdminFieldLabel>
          <Input
            type="email"
            {...register("email")}
            placeholder="vendedor@facilcar.demo"
            className={cn(errors.email && "border-red-400")}
          />
          <AdminFieldError message={errors.email?.message} />
        </div>

        <div className="space-y-1">
          <AdminFieldLabel required>Senha</AdminFieldLabel>
          <Input
            type="password"
            {...register("password")}
            placeholder="Mínimo 8 caracteres"
            className={cn(errors.password && "border-red-400")}
          />
          <AdminFieldError message={errors.password?.message} />
        </div>

        <div className="space-y-1 sm:col-span-2">
          <AdminFieldLabel required>Perfil</AdminFieldLabel>
          <Select
            value={role}
            onValueChange={(v) =>
              setValue("role", v as CreateUserInput["role"], { shouldValidate: true })
            }
          >
            <SelectTrigger className={cn("w-full", errors.role && "border-red-400")}>
              <SelectValue placeholder="Selecionar perfil" />
            </SelectTrigger>
            <SelectContent>
              {USER_ROLE_OPTIONS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <AdminFieldError message={errors.role?.message} />
          <p className="mt-1 text-xs text-facil-muted">
            Para vendedores, use o perfil &quot;Vendedor&quot; (LEAD_MANAGER).
          </p>
        </div>
      </div>

      <div className="flex justify-end gap-2 border-t border-facil-border pt-4">
        <Button
          type="button"
          variant="outline"
          onClick={() => (onCancel ? onCancel() : router.push("/admin/usuarios"))}
          disabled={isSubmitting}
        >
          Cancelar
        </Button>
        <Button type="submit" variant="primary" disabled={isSubmitting}>
          <Save className="h-4 w-4" />
          {isSubmitting ? "Salvando…" : "Criar usuário"}
        </Button>
      </div>
    </form>
  );
}
