import { Suspense } from "react";
import type { UserRole } from "@prisma/client";
import { ThemedToaster } from "@/components/admin/themed-toaster";
import { AdminShell } from "@/components/admin/AdminShell";
import { ForbiddenToast } from "@/components/admin/ForbiddenToast";
import { requireAdminSession } from "@/features/auth/server/require-admin-session";
import { adminSignOutAction } from "./signOutAction";

export default async function AdminDashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user } = await requireAdminSession();

  return (
    <>
      <AdminShell signOutAction={adminSignOutAction} role={user.role as UserRole}>
        {children}
      </AdminShell>
      <ThemedToaster />
      <Suspense fallback={null}>
        <ForbiddenToast />
      </Suspense>
    </>
  );
}
