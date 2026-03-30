import { Toaster } from "sonner";
import { AdminShell } from "@/components/admin/AdminShell";
import { adminSignOutAction } from "./signOutAction";

export default function AdminDashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <>
      <AdminShell signOutAction={adminSignOutAction}>{children}</AdminShell>
      <Toaster position="top-right" richColors closeButton />
    </>
  );
}
