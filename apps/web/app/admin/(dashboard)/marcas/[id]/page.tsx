import { redirect } from "next/navigation";

export default async function AdminMarcaEditRedirect({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  redirect(`/admin/marcas?edit=${id}`);
}
