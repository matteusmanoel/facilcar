import Link from "next/link";
import { notFound } from "next/navigation";
import { prisma } from "@/lib/db";
import { UpdateLeadStatusForm } from "./UpdateLeadStatusForm";
import { InternalNoteForm } from "./InternalNoteForm";
import { LeadDangerZone } from "./LeadDangerZone";

const SOURCE_LABELS: Record<string, string> = {
  HOME: "Página inicial",
  CATALOG: "Catálogo",
  VEHICLE_PAGE: "Página do veículo",
  CONTACT_PAGE: "Contato",
  FINANCING_PAGE: "Financiamento",
  SELL_PAGE: "Vender veículo",
  BLOG: "Blog",
  UNKNOWN: "Desconhecido",
};

const STATUS_LABELS: Record<string, string> = {
  NEW: "Novo",
  IN_PROGRESS: "Em progresso",
  CONTACTED: "Contactado",
  QUALIFIED: "Qualificado",
  WON: "Ganho",
  LOST: "Perdido",
  SPAM: "Spam",
};

function maskCPF(cpf: string | null | undefined): string {
  if (!cpf) return "—";
  const digits = cpf.replace(/\D/g, "");
  if (digits.length !== 11) return cpf;
  return `***.${digits.slice(3, 6)}.${digits.slice(6, 9)}-${digits.slice(9)}`;
}

function creditRatioColor(ratio: number) {
  if (ratio >= 20) return "text-green-600 bg-green-50";
  if (ratio >= 10) return "text-yellow-600 bg-yellow-50";
  return "text-red-600 bg-red-50";
}

function creditRatioLabel(ratio: number) {
  if (ratio >= 20) return "Entrada forte";
  if (ratio >= 10) return "Entrada regular";
  return "Entrada baixa";
}

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

  const phone = lead.phone.replace(/\D/g, "");
  const fr = lead.financingRequest;

  const vehicleLabel =
    lead.vehicle?.title ??
    [fr?.vehicleModel, fr?.vehicleYear].filter(Boolean).join(" ") ??
    null;

  const waUrl = phone
    ? `https://wa.me/${phone}?text=${encodeURIComponent(
        `Olá ${lead.name}, aqui é da FácilCar! Recebi sua simulação${vehicleLabel ? ` de financiamento do ${vehicleLabel}` : ""}. Posso te ajudar com a análise de crédito. Podemos conversar?`,
      )}`
    : null;

  const entradaRenda =
    fr?.downPayment != null && fr?.monthlyIncome != null && Number(fr.monthlyIncome) > 0
      ? Math.round((Number(fr.downPayment) / Number(fr.monthlyIncome)) * 100)
      : null;

  const estimatedMonthly =
    lead.vehicle?.priceCash != null && fr?.desiredInstallments
      ? Math.round(Number(lead.vehicle.priceCash) / fr.desiredInstallments).toLocaleString("pt-BR")
      : null;

  return (
    <main className="admin-page admin-section">
      <div className="flex items-center justify-between">
        <Link href="/admin/leads" className="inline-flex items-center gap-1 text-sm text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200">
          ← Voltar aos leads
        </Link>
        {waUrl && (
          <a
            href={waUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 rounded-xl bg-green-500 px-5 py-2.5 font-bold text-white shadow hover:bg-green-600"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
              <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" />
            </svg>
            Abrir WhatsApp
          </a>
        )}
      </div>

      <h1 className="mt-4 text-2xl font-bold text-zinc-900 dark:text-zinc-50">Lead: {lead.name}</h1>
      <p className="text-sm text-zinc-500 dark:text-zinc-400">
        Criado em {new Date(lead.createdAt).toLocaleString("pt-BR")} ·{" "}
        {SOURCE_LABELS[lead.source] ?? lead.source}
      </p>

      <div className="mt-6 grid gap-5 lg:grid-cols-2">
        {/* Card 1 — Identidade */}
        <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
          <h2 className="mb-3 text-sm font-bold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
            Dados do Lead
          </h2>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
            <div>
              <dt className="font-medium text-zinc-500 dark:text-zinc-400">Nome</dt>
              <dd className="text-zinc-900 dark:text-zinc-100">{lead.name}</dd>
            </div>
            <div>
              <dt className="font-medium text-zinc-500 dark:text-zinc-400">CPF</dt>
              <dd className="font-mono text-zinc-900 dark:text-zinc-100">{maskCPF(fr?.cpf)}</dd>
            </div>
            <div>
              <dt className="font-medium text-zinc-500 dark:text-zinc-400">Data de Nascimento</dt>
              <dd className="text-zinc-900 dark:text-zinc-100">
                {fr?.birthDate
                  ? new Date(fr.birthDate).toLocaleDateString("pt-BR")
                  : "—"}
              </dd>
            </div>
            <div>
              <dt className="font-medium text-zinc-500 dark:text-zinc-400">Telefone</dt>
              <dd className="flex items-center gap-1.5 text-zinc-900 dark:text-zinc-100">
                {lead.phone}
                {phone && (
                  <a
                    href={`tel:${phone}`}
                    className="rounded bg-zinc-100 px-1.5 py-0.5 text-xs text-zinc-600 hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-300 dark:hover:bg-zinc-700"
                  >
                    Ligar
                  </a>
                )}
              </dd>
            </div>
            <div>
              <dt className="font-medium text-zinc-500 dark:text-zinc-400">E-mail</dt>
              <dd className="text-zinc-900 dark:text-zinc-100">{lead.email ?? "—"}</dd>
            </div>
            <div>
              <dt className="font-medium text-zinc-500 dark:text-zinc-400">Cidade / Estado</dt>
              <dd className="text-zinc-900 dark:text-zinc-100">
                {[lead.city, lead.state].filter(Boolean).join(" / ") || "—"}
              </dd>
            </div>
          </dl>
          {lead.message && (
            <div className="mt-4 border-t border-zinc-100 pt-3 dark:border-zinc-800">
              <p className="text-xs font-medium text-zinc-500 dark:text-zinc-400">Mensagem</p>
              <p className="mt-1 whitespace-pre-wrap text-sm text-zinc-700 dark:text-zinc-300">{lead.message}</p>
            </div>
          )}
        </div>

        {/* Card 2 — Perfil de crédito */}
        {fr && (
          <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
            <h2 className="mb-3 text-sm font-bold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
              Perfil de Crédito
            </h2>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
              <div>
                <dt className="font-medium text-zinc-500 dark:text-zinc-400">Renda Mensal</dt>
                <dd className="text-lg font-bold text-zinc-900 dark:text-zinc-100">
                  {fr.monthlyIncome != null
                    ? `R$ ${Number(fr.monthlyIncome).toLocaleString("pt-BR")}`
                    : "—"}
                </dd>
              </div>
              <div>
                <dt className="font-medium text-zinc-500 dark:text-zinc-400">Entrada</dt>
                <dd className="text-lg font-bold text-zinc-900 dark:text-zinc-100">
                  {fr.downPayment != null
                    ? `R$ ${Number(fr.downPayment).toLocaleString("pt-BR")}`
                    : "—"}
                </dd>
              </div>
              <div>
                <dt className="font-medium text-zinc-500 dark:text-zinc-400">Prazo Desejado</dt>
                <dd className="text-zinc-900 dark:text-zinc-100">
                  {fr.desiredInstallments ? `${fr.desiredInstallments} meses` : "—"}
                </dd>
              </div>
              <div>
                <dt className="font-medium text-zinc-500 dark:text-zinc-400">CNH</dt>
                <dd className="text-zinc-900 dark:text-zinc-100">
                  {fr.hasDriverLicense == null ? "—" : fr.hasDriverLicense ? "Sim" : "Não"}
                </dd>
              </div>
            </dl>
            {entradaRenda !== null && (
              <div className="mt-4 border-t border-zinc-100 pt-3 dark:border-zinc-800">
                <p className="mb-1.5 text-xs font-medium text-zinc-500 dark:text-zinc-400">Razão Entrada / Renda</p>
                <div className="flex items-center gap-3">
                  <div className="h-2 flex-1 overflow-hidden rounded-full bg-zinc-100 dark:bg-zinc-800">
                    <div
                      className={`h-full rounded-full transition-all ${entradaRenda >= 20 ? "bg-green-500" : entradaRenda >= 10 ? "bg-yellow-400" : "bg-red-400"}`}
                      style={{ width: `${Math.min(entradaRenda * 2, 100)}%` }}
                    />
                  </div>
                  <span
                    className={`shrink-0 rounded-full px-2.5 py-0.5 text-xs font-bold ${creditRatioColor(entradaRenda)}`}
                  >
                    {entradaRenda}% — {creditRatioLabel(entradaRenda)}
                  </span>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Card 3 — Veículo de interesse */}
        {(lead.vehicle || fr?.vehicleModel || fr?.vehicleYear) && (
          <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
            <h2 className="mb-3 text-sm font-bold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
              Veículo de Interesse
            </h2>
            {lead.vehicle ? (
              <>
                <Link
                  href={`/estoque/${lead.vehicle.slug}`}
                  target="_blank"
                  className="text-base font-semibold text-facil-orange hover:underline"
                >
                  {lead.vehicle.title} ↗
                </Link>
                {lead.vehicle.priceCash != null && (
                  <p className="mt-1 text-lg font-bold text-zinc-900 dark:text-zinc-100">
                    R$ {Number(lead.vehicle.priceCash).toLocaleString("pt-BR")}
                  </p>
                )}
                {estimatedMonthly && (
                  <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
                    Estimativa: ~R$ {estimatedMonthly}/mês em{" "}
                    {fr?.desiredInstallments} meses
                  </p>
                )}
              </>
            ) : (
              <p className="text-zinc-700 dark:text-zinc-300">
                {[fr?.vehicleModel, fr?.vehicleYear].filter(Boolean).join(" — ") || "—"}
              </p>
            )}
          </div>
        )}

        {/* Card 4 — Ações e status */}
        <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
          <h2 className="mb-3 text-sm font-bold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
            Gestão do Lead
          </h2>
          <div className="flex flex-col gap-3">
            <div>
              <p className="mb-1.5 text-xs font-medium text-zinc-500 dark:text-zinc-400">Status</p>
              <UpdateLeadStatusForm leadId={lead.id} currentStatus={lead.status} />
              <p className="mt-1 text-xs text-zinc-400 dark:text-zinc-500">
                Atual: {STATUS_LABELS[lead.status] ?? lead.status}
              </p>
            </div>
            <div>
              <p className="mb-1.5 text-xs font-medium text-zinc-500 dark:text-zinc-400">Anotação interna</p>
              <InternalNoteForm leadId={lead.id} currentNote={lead.internalNote} />
            </div>
            <LeadDangerZone leadId={lead.id} currentStatus={lead.status} />
          </div>
        </div>

        {/* Venda de veículo (se existir) */}
        {lead.sellRequest && (
          <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
            <h2 className="mb-3 text-sm font-bold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
              Veículo para Venda
            </h2>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
              <div>
                <dt className="font-medium text-zinc-500 dark:text-zinc-400">Marca</dt>
                <dd className="text-zinc-900 dark:text-zinc-100">{lead.sellRequest.brand ?? "—"}</dd>
              </div>
              <div>
                <dt className="font-medium text-zinc-500 dark:text-zinc-400">Modelo</dt>
                <dd className="text-zinc-900 dark:text-zinc-100">{lead.sellRequest.model ?? "—"}</dd>
              </div>
              <div>
                <dt className="font-medium text-zinc-500 dark:text-zinc-400">Ano Modelo</dt>
                <dd className="text-zinc-900 dark:text-zinc-100">{lead.sellRequest.yearModel ?? "—"}</dd>
              </div>
              <div>
                <dt className="font-medium text-zinc-500 dark:text-zinc-400">KM</dt>
                <dd className="text-zinc-900 dark:text-zinc-100">
                  {lead.sellRequest.mileage != null
                    ? lead.sellRequest.mileage.toLocaleString("pt-BR")
                    : "—"}
                </dd>
              </div>
            </dl>
            {lead.sellRequest.observations && (
              <p className="mt-3 whitespace-pre-wrap text-sm text-zinc-600 dark:text-zinc-400">
                {lead.sellRequest.observations}
              </p>
            )}
          </div>
        )}
      </div>
    </main>
  );
}
