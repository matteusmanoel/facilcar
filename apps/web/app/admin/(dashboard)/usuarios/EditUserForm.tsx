"use client";

import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { Save, KeyRound } from "lucide-react";
import { updateUserAction, resetPasswordAction } from "@/features/admin/server/users";
import {
  updateUserSchema,
  resetPasswordSchema,
  type UpdateUserInput,
  type ResetPasswordInput,
} from "@/schemas/user";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { AdminFieldError, AdminFieldLabel } from "@/components/admin/AdminField";
import { cn } from "@/lib/cn";
import { USER_ROLE_OPTIONS } from "./user-role-labels";

type Props = {
  userId: string;
  defaultValues: UpdateUserInput;
  email: string;
  isSelf: boolean;
  variant?: "page" | "dialog";
  onCancel?: () => void;
  onSaved?: () => void;
};

export function EditUserForm({
  userId,
  defaultValues,
  email,
  isSelf,
  variant = "page",
  onCancel,
  onSaved,
}: Props) {
  const router = useRouter();

  const {
    register,
    handleSubmit,
    setValue,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<UpdateUserInput>({
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    resolver: zodResolver(updateUserSchema) as any,
    defaultValues,
  });

  const role = watch("role");
  const isActive = watch("isActive");

  const {
    register: registerPassword,
    handleSubmit: handlePasswordSubmit,
    reset: resetPasswordForm,
    formState: { errors: passwordErrors, isSubmitting: isResetting },
  } = useForm<ResetPasswordInput>({
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    resolver: zodResolver(resetPasswordSchema) as any,
    defaultValues: { password: "" },
  });

  const onSubmit = async (data: UpdateUserInput) => {
    const result = await updateUserAction(userId, data);

    if (result.ok) {
      toast.success("Usuário atualizado!");
      if (onSaved) {
        onSaved();
      } else {
        router.refresh();
      }
      return;
    }

    toast.error(typeof result.error === "string" ? result.error : "Erro ao salvar usuário.");
  };

  const onResetPassword = async (data: ResetPasswordInput) => {
    const result = await resetPasswordAction(userId, data);

    if (result.ok) {
      toast.success("Senha redefinida com sucesso!");
      resetPasswordForm();
      return;
    }

    if (typeof result.error === "string") {
      toast.error(result.error);
      return;
    }

    const firstError = Object.values(result.error).flat()[0];
    toast.error(typeof firstError === "string" ? firstError : "Senha inválida");
  };

  return (
    <div className={cn("flex flex-col gap-6", variant === "page" && "max-w-2xl")}>
      <form
        onSubmit={handleSubmit(onSubmit)}
        className={cn("admin-card space-y-5 p-6", variant === "dialog" && "border-0 p-0 shadow-none")}
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1 sm:col-span-2">
            <AdminFieldLabel required>Nome</AdminFieldLabel>
            <Input
              {...register("name")}
              className={cn(errors.name && "border-red-400")}
            />
            <AdminFieldError message={errors.name?.message} />
          </div>

          <div className="space-y-1 sm:col-span-2">
            <AdminFieldLabel>E-mail</AdminFieldLabel>
            <Input value={email} disabled />
            <p className="mt-1 text-xs text-facil-muted">
              O e-mail não pode ser alterado.
            </p>
          </div>

          <div className="space-y-1">
            <AdminFieldLabel required>Perfil</AdminFieldLabel>
            <Select
              value={role}
              onValueChange={(v) =>
                setValue("role", v as UpdateUserInput["role"], { shouldValidate: true })
              }
            >
              <SelectTrigger className={cn("w-full", errors.role && "border-red-400")}>
                <SelectValue />
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
          </div>

          <div className="space-y-1">
            <AdminFieldLabel>Status</AdminFieldLabel>
            <Select
              value={isActive ? "active" : "inactive"}
              disabled={isSelf}
              onValueChange={(v) => setValue("isActive", v === "active", { shouldValidate: true })}
            >
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="active">Ativo</SelectItem>
                <SelectItem value="inactive">Inativo</SelectItem>
              </SelectContent>
            </Select>
            {isSelf ? (
              <p className="mt-1 text-xs text-facil-muted">
                Você não pode desativar sua própria conta.
              </p>
            ) : null}
          </div>
        </div>

        <div className="flex justify-end gap-2 border-t border-facil-border pt-4">
          <Button
            type="button"
            variant="outline"
            onClick={() => (onCancel ? onCancel() : router.push("/admin/usuarios"))}
            disabled={isSubmitting}
          >
            {variant === "dialog" ? "Cancelar" : "Voltar"}
          </Button>
          <Button type="submit" variant="primary" disabled={isSubmitting}>
            <Save className="h-4 w-4" />
            {isSubmitting ? "Salvando…" : "Salvar"}
          </Button>
        </div>
      </form>

      {variant === "page" ? (
      <form
        onSubmit={handlePasswordSubmit(onResetPassword)}
        className="admin-card space-y-4 p-6"
      >
        <div>
          <h2 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">
            Redefinir senha
          </h2>
          <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
            Defina uma nova senha para este usuário.
          </p>
        </div>

        <div className="space-y-1">
          <AdminFieldLabel required>Nova senha</AdminFieldLabel>
          <Input
            type="password"
            {...registerPassword("password")}
            placeholder="Mínimo 8 caracteres"
            className={cn("max-w-sm", passwordErrors.password && "border-red-400")}
          />
          <AdminFieldError message={passwordErrors.password?.message} />
        </div>

        <div className="flex justify-end border-t border-facil-border pt-4">
          <Button type="submit" variant="outline" disabled={isResetting}>
            <KeyRound className="h-4 w-4" />
            {isResetting ? "Redefinindo…" : "Redefinir senha"}
          </Button>
        </div>
      </form>
      ) : null}
    </div>
  );
}
