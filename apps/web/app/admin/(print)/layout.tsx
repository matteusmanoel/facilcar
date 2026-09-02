import { requireAdminSession } from "@/features/auth/server/require-admin-session";

export default async function AdminPrintLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  await requireAdminSession();

  return <div className="print-root min-h-screen bg-white text-zinc-900">{children}</div>;
}
