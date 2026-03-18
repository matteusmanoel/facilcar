import Link from "next/link";
import { notFound } from "next/navigation";
import { prisma } from "@/lib/db";
import { UpdateLeadStatusForm } from "./UpdateLeadStatusForm";

export default async function AdminLeadDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const lead = await prisma.lead.findUnique({
    where: { id },
    include: {
      vehicle: true,
      financingRequest: true,
      sellRequest: true,
    },
  });

  if (!lead) notFound();

  return (
    <main className="p-6">
      <Link href="/admin/leads" className="text-sm text-zinc-600 hover:underline">
        ← Voltar aos leads
      </Link>
      <h1 className="mt-4 text-2xl font-semibold">Lead: {lead.name}</h1>
      <div className="mt-6 grid gap-6 md:grid-cols-2">
        <div className="rounded border bg-white p-4">
          <h2 className="font-medium">Dados</h2>
          <dl className="mt-2 space-y-1 text-sm">
            <dt className="text-zinc-500">Tipo</dt>
            <dd>{lead.type}</dd>
            <dt className="text-zinc-500">Status</dt>
            <dd>
              <UpdateLeadStatusForm leadId={lead.id} currentStatus={lead.status} />
            </dd>
            <dt className="text-zinc-500">Nome</dt>
            <dd>{lead.name}</dd>
            <dt className="text-zinc-500">Telefone</dt>
            <dd>{lead.phone}</dd>
            <dt className="text-zinc-500">E-mail</dt>
            <dd>{lead.email ?? "—"}</dd>
            <dt className="text-zinc-500">Mensagem</dt>
            <dd className="whitespace-pre-wrap">{lead.message ?? "—"}</dd>
            <dt className="text-zinc-500">Origem</dt>
            <dd>{lead.source}</dd>
            <dt className="text-zinc-500">Criado em</dt>
            <dd>{new Date(lead.createdAt).toLocaleString("pt-BR")}</dd>
          </dl>
        </div>
        <div className="rounded border bg-white p-4">
          {lead.vehicle && (
            <>
              <h2 className="font-medium">Veículo</h2>
              <Link href={`/estoque/${lead.vehicle.slug}`} className="mt-2 block text-zinc-600 hover:underline">
                {lead.vehicle.title}
              </Link>
            </>
          )}
          {lead.financingRequest && (
            <div className="mt-4">
              <h2 className="font-medium">Financiamento</h2>
              <p className="mt-1 text-sm">CNH: {lead.financingRequest.hasDriverLicense ? "Sim" : "Não"}</p>
              {lead.financingRequest.monthlyIncome != null && (
                <p className="text-sm">Renda: R$ {Number(lead.financingRequest.monthlyIncome).toLocaleString("pt-BR")}</p>
              )}
              {lead.financingRequest.notes && (
                <p className="mt-1 text-sm">{lead.financingRequest.notes}</p>
              )}
            </div>
          )}
          {lead.sellRequest && (
            <div className="mt-4">
              <h2 className="font-medium">Venda</h2>
              <p className="text-sm">{lead.sellRequest.brand} {lead.sellRequest.model} {lead.sellRequest.yearModel}</p>
              {lead.sellRequest.observations && (
                <p className="mt-1 text-sm">{lead.sellRequest.observations}</p>
              )}
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
