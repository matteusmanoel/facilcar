export const dynamic = "force-dynamic";
/** Auth.js + Prisma/bcrypt exigem Node; evita bundle edge (crypto) em /admin/* */
export const runtime = "nodejs";

export default function AdminRootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
