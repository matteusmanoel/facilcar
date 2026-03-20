import Link from "next/link";
import { prisma } from "@/lib/db";

export default async function AdminVeiculosPage() {
  const vehicles = await prisma.vehicle.findMany({
    orderBy: { updatedAt: "desc" },
    take: 100,
    include: {
      brand: true,
      images: { take: 1, orderBy: { sortOrder: "asc" } },
    },
  });

  return (
    <main className="p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Veículos</h1>
        <Link
          href="/admin/veiculos/novo"
          className="rounded bg-zinc-900 px-4 py-2 text-white hover:bg-zinc-800"
        >
          Novo veículo
        </Link>
      </div>
      <div className="mt-4 overflow-x-auto rounded border">
        <table className="w-full text-sm">
          <thead className="bg-zinc-50">
            <tr>
              <th className="p-2 text-left">Imagem</th>
              <th className="p-2 text-left">Título</th>
              <th className="p-2 text-left">Marca</th>
              <th className="p-2 text-left">Status</th>
              <th className="p-2 text-left">Preço</th>
              <th className="p-2 text-left">Ações</th>
            </tr>
          </thead>
          <tbody>
            {vehicles.map((v) => (
              <tr key={v.id} className="border-t">
                <td className="p-2">
                  {v.images[0] ? (
                    <img
                      src={v.images[0].url}
                      alt=""
                      className="h-12 w-16 rounded object-cover"
                    />
                  ) : (
                    <span className="text-zinc-400">—</span>
                  )}
                </td>
                <td className="p-2">{v.title}</td>
                <td className="p-2">{v.brand.name}</td>
                <td className="p-2">{v.status}</td>
                <td className="p-2">
                  {v.priceCash != null
                    ? `R$ ${Number(v.priceCash).toLocaleString("pt-BR")}`
                    : "—"}
                </td>
                <td className="p-2">
                  <Link
                    href={`/admin/veiculos/${v.id}`}
                    className="text-zinc-600 hover:underline"
                  >
                    Editar
                  </Link>
                  {" · "}
                  <Link
                    href={`/estoque/${v.slug}`}
                    target="_blank"
                    className="text-zinc-600 hover:underline"
                  >
                    Ver
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  );
}
