import Link from "next/link";
import { notFound } from "next/navigation";
import { format } from "date-fns";
import { ptBR } from "date-fns/locale";
import { guardAdminSection } from "@/features/auth/server/rbac";
import { getCustomerById } from "@/features/admin/server/customers";
import { StatusBadge } from "@/components/admin/StatusBadge";

function formatPhone(phone: string): string {
  if (phone.length === 11) {
    return `(${phone.slice(0, 2)}) ${phone.slice(2, 7)}-${phone.slice(7)}`;
  }
  if (phone.length === 10) {
    return `(${phone.slice(0, 2)}) ${phone.slice(2, 6)}-${phone.slice(6)}`;
  }
  return phone;
}

export default async function AdminClienteDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  await guardAdminSection("clientes");
  const { id } = await params;
  const customer = await getCustomerById(id);
  if (!customer) notFound();

  return (
    <div className="admin-page admin-section">
      <div>
        <Link
          href="/admin/clientes"
          className="text-sm text-zinc-500 hover:text-facil-orange hover:underline dark:text-zinc-400"
        >
          ← Voltar aos clientes
        </Link>
        <h1 className="mt-3 text-2xl font-bold text-zinc-900 dark:text-zinc-50">{customer.name}</h1>
        <p className="mt-0.5 text-sm text-zinc-500 dark:text-zinc-400">
          Cliente consolidado — somente leitura
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
          <h2 className="text-base font-semibold text-zinc-900 dark:text-zinc-50">Dados de contato</h2>
          <dl className="mt-4 space-y-3 text-sm">
            <div>
              <dt className="text-zinc-500 dark:text-zinc-400">Telefone</dt>
              <dd className="mt-0.5 font-mono font-medium text-zinc-900 dark:text-zinc-100">
                {formatPhone(customer.phone)}
              </dd>
            </div>
            <div>
              <dt className="text-zinc-500 dark:text-zinc-400">E-mail</dt>
              <dd className="mt-0.5 text-zinc-900 dark:text-zinc-100">{customer.email ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-zinc-500 dark:text-zinc-400">Cadastrado em</dt>
              <dd className="mt-0.5 text-zinc-900 dark:text-zinc-100">
                {format(customer.createdAt, "dd/MM/yyyy 'às' HH:mm", { locale: ptBR })}
              </dd>
            </div>
            <div>
              <dt className="text-zinc-500 dark:text-zinc-400">Última atualização</dt>
              <dd className="mt-0.5 text-zinc-900 dark:text-zinc-100">
                {format(customer.updatedAt, "dd/MM/yyyy 'às' HH:mm", { locale: ptBR })}
              </dd>
            </div>
          </dl>
        </div>

        <div className="rounded-xl border border-zinc-200 bg-white shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
          <div className="flex items-center justify-between border-b border-zinc-100 px-5 py-4 dark:border-zinc-800">
            <h2 className="text-base font-semibold text-zinc-900 dark:text-zinc-50">
              Leads relacionados ({customer.leads.length})
            </h2>
            {customer.leads.length > 0 && (
              <Link
                href={`/admin/leads?q=${encodeURIComponent(customer.phone)}`}
                className="text-sm text-facil-orange hover:underline"
              >
                Ver na lista →
              </Link>
            )}
          </div>
          {customer.leads.length === 0 ? (
            <p className="px-5 py-8 text-center text-sm text-zinc-400">Nenhum lead vinculado.</p>
          ) : (
            <ul className="divide-y divide-zinc-100 dark:divide-zinc-800">
              {customer.leads.map((lead) => (
                <li key={lead.id} className="flex items-center justify-between gap-3 px-5 py-3">
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
                      {format(lead.createdAt, "dd/MM/yyyy", { locale: ptBR })}
                    </p>
                    <div className="mt-1 flex flex-wrap gap-2">
                      <StatusBadge status={lead.type} type="type" />
                      <StatusBadge status={lead.status} />
                    </div>
                  </div>
                  <Link
                    href={`/admin/leads/${lead.id}`}
                    className="shrink-0 text-sm font-medium text-facil-orange hover:underline"
                  >
                    Ver
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
