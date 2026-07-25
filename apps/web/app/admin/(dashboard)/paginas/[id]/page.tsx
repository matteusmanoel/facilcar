import { redirect } from "next/navigation";

export default async function AdminPaginaEditRedirect({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  redirect(`/admin/paginas?edit=${id}`);
}
