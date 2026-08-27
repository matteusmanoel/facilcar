import { AdminPageReveal } from "@/components/motion/AdminPageReveal";

export default function AdminDashboardLayoutClient({
  children,
}: {
  children: React.ReactNode;
}) {
  return <AdminPageReveal className="min-h-full">{children}</AdminPageReveal>;
}
