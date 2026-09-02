import type { ReactNode } from "react";
import Link from "next/link";
import { notFound } from "next/navigation";
import { prisma } from "@/lib/db";
import { guardAdminSection } from "@/features/auth/server/rbac";
import { StatusBadge } from "@/components/admin/StatusBadge";
import { UpdateLeadStatusForm } from "./UpdateLeadStatusForm";
import { InternalNoteForm } from "./InternalNoteForm";
import { AssignLeadForm } from "./AssignLeadForm";
import { LeadDangerZone } from "./LeadDangerZone";
import { LeadVehicleInterestForm } from "./LeadVehicleInterestForm";
import { LeadContactEditor } from "./LeadContactEditor";
import { LeadFinancingEditor } from "./LeadFinancingEditor";
import { LeadSellEditor } from "./LeadSellEditor";
import { LeadDetailField as Field } from "./LeadDetailField";
import { toDateInputValue } from "@/features/lead/lib/edit-values";
import { leadVehicleLabel } from "@/features/lead/lib/vehicle-label";
import { vendorSummaryFromLead } from "@/features/lead/lib/julia-summary";

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

const CHANNEL_LABELS: Record<string, string> = {
  FORM: "Formulário",
  WHATSAPP: "WhatsApp",
  MANUAL: "Manual",
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

const TEMPERATURE_LABELS: Record<string, string> = {
  HOT: "Quente",
  WARM: "Morno",
  COLD: "Frio",
};

const TEMPERATURE_CLASSES: Record<string, string> = {
  HOT: "bg-red-100 text-red-800 dark:bg-red-950/40 dark:text-red-300",
  WARM: "bg-amber-100 text-amber-800 dark:bg-amber-950/40 dark:text-amber-300",
  COLD: "bg-sky-100 text-sky-800 dark:bg-sky-950/40 dark:text-sky-300",
};

function formatMoney(value: unknown): string | null {
  if (value == null || value === "") return null;
  const n = Number(value);
  if (Number.isNaN(n)) return null;
  return `R$ ${n.toLocaleString("pt-BR")}`;
}

function Card({
  title,
  children,
  className = "",
}: {
  title: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`admin-card ${className}`}>
      <h2 className="mb-4 text-sm font-bold uppercase tracking-wide text-facil-muted">{title}</h2>
      {children}
    </section>
  );
}

export default async function AdminLeadDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const currentUser = await guardAdminSection("leads");
  const [lead, sellers, catalogVehicles] = await Promise.all([
    prisma.lead.findFirst({
      where: { id, deletedAt: null },
      include: {
        vehicle: { select: { id: true, title: true, slug: true, priceCash: true, status: true } },
        customer: { select: { id: true, name: true } },
        vehicleInterests: {
          orderBy: [{ isPrimary: "desc" }, { createdAt: "asc" }],
          include: {
            vehicle: { select: { id: true, title: true, slug: true, priceCash: true, status: true } },
          },
        },
        financingRequest: true,
        sellRequest: true,
        assignedToUser: { select: { id: true, name: true } },
      },
    }),
    prisma.user.findMany({
      where: { isActive: true },
      orderBy: { name: "asc" },
      select: { id: true, name: true },
    }),
    prisma.vehicle.findMany({
      where: { status: { in: ["PUBLISHED", "RESERVED", "DRAFT"] } },
      orderBy: { updatedAt: "desc" },
      take: 200,
      select: { id: true, title: true },
    }),
  ]);

  if (!lead) notFound();

  const phone = lead.phone.replace(/\D/g, "");
  const fr = lead.financingRequest;

  const interestVehicles =
    lead.vehicleInterests.length > 0
      ? lead.vehicleInterests.map((item) => ({
          ...item.vehicle,
          isPrimary: item.isPrimary,
        }))
      : lead.vehicle
        ? [{ ...lead.vehicle, isPrimary: true }]
        : [];

  const primaryVehicle = interestVehicles.find((v) => v.isPrimary) ?? interestVehicles[0] ?? null;

  const vehicleLabel =
    primaryVehicle?.title ??
    [fr?.vehicleModel, fr?.vehicleYear].filter(Boolean).join(" ") ??
    leadVehicleLabel({ metadataJson: lead.metadataJson }) ??
    null;

  const juliaBrief = vendorSummaryFromLead(lead);

  const waUrl = phone
    ? `https://wa.me/${phone}?text=${encodeURIComponent(
        `Olá ${lead.name}, aqui é da FácilCar! Recebi sua simulação${vehicleLabel ? ` de financiamento do ${vehicleLabel}` : ""}. Posso te ajudar com a análise de crédito. Podemos conversar?`,
      )}`
    : null;

  const estimatedMonthly =
    primaryVehicle?.priceCash != null && fr?.desiredInstallments
      ? Math.round(Number(primaryVehicle.priceCash) / fr.desiredInstallments).toLocaleString("pt-BR")
      : null;

  const hasOrigin =
    Boolean(lead.originUrl) ||
    Boolean(lead.utmSource) ||
    Boolean(lead.utmMedium) ||
    Boolean(lead.utmCampaign) ||
    Boolean(lead.utmTerm) ||
    Boolean(lead.utmContent);

  return (
    <main className="admin-page admin-section">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <Link
          href="/admin/leads"
          className="inline-flex items-center gap-1 text-sm text-facil-muted hover:text-foreground"
        >
          ← Voltar aos leads
        </Link>
        {waUrl ? (
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
        ) : null}
      </div>

      <header className="space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-2xl font-bold text-foreground">{lead.name}</h1>
          <StatusBadge status={lead.type} type="type" />
          <StatusBadge status={lead.status} />
          {lead.temperature ? (
            <span
              className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${TEMPERATURE_CLASSES[lead.temperature] ?? "bg-zinc-100 text-zinc-600"}`}
            >
              {TEMPERATURE_LABELS[lead.temperature] ?? lead.temperature}
            </span>
          ) : null}
        </div>
        <p className="text-sm text-facil-muted">
          Criado em {new Date(lead.createdAt).toLocaleString("pt-BR")}
          {" · "}
          {SOURCE_LABELS[lead.source] ?? lead.source}
          {" · "}
          {CHANNEL_LABELS[lead.channel] ?? lead.channel}
          {lead.assignedToUser ? ` · ${lead.assignedToUser.name}` : ""}
        </p>
      </header>

      {juliaBrief ? (
        <div className="rounded-xl border border-facil-orange/30 bg-orange-50/60 p-5 shadow-sm dark:border-facil-orange/20 dark:bg-orange-950/20">
          <h2 className="mb-2 text-sm font-bold uppercase tracking-wide text-facil-orange">
            Resumo da Júlia
          </h2>
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-foreground">
            {juliaBrief}
          </p>
        </div>
      ) : null}

      <div className="grid items-start gap-5 lg:grid-cols-3">
        <div className="space-y-5 lg:col-span-2">
          <LeadContactEditor
            leadId={lead.id}
            name={lead.name}
            phone={lead.phone}
            email={lead.email}
            city={lead.city}
            state={lead.state}
            customer={lead.customer}
            financing={
              fr
                ? {
                    cpf: fr.cpf,
                    birthDate: toDateInputValue(fr.birthDate),
                  }
                : null
            }
          />

          <Card title="Veículos de interesse">
            {interestVehicles.length > 0 ? (
              <ul className="mb-4 space-y-3">
                {interestVehicles.map((vehicle) => (
                  <li
                    key={vehicle.id}
                    className="flex flex-wrap items-start justify-between gap-2 rounded-lg border border-facil-border bg-facil-surface/60 px-3 py-2.5"
                  >
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <Link
                          href={`/admin/veiculos/${vehicle.id}`}
                          className="text-sm font-semibold text-foreground hover:text-facil-orange"
                        >
                          {vehicle.title}
                        </Link>
                        {vehicle.isPrimary ? (
                          <span className="rounded-full bg-facil-orange/15 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-facil-orange">
                            Primário
                          </span>
                        ) : null}
                        <StatusBadge status={vehicle.status} />
                      </div>
                      {formatMoney(vehicle.priceCash) ? (
                        <p className="mt-1 text-sm font-medium text-foreground">
                          {formatMoney(vehicle.priceCash)}
                        </p>
                      ) : null}
                    </div>
                    {vehicle.status === "PUBLISHED" ? (
                      <Link
                        href={`/estoque/${vehicle.slug}`}
                        target="_blank"
                        className="text-xs text-facil-muted hover:text-foreground"
                      >
                        Ver no site ↗
                      </Link>
                    ) : null}
                  </li>
                ))}
              </ul>
            ) : fr?.vehicleModel || fr?.vehicleYear ? (
              <p className="mb-4 text-sm text-foreground">
                Informado no formulário: {[fr.vehicleModel, fr.vehicleYear].filter(Boolean).join(" — ")}
              </p>
            ) : vehicleLabel ? (
              <p className="mb-4 text-sm text-foreground">
                Interesse mencionado: {vehicleLabel}
                <span className="mt-1 block text-xs text-facil-muted">
                  Ainda não há veículo publicado vinculado a este lead.
                </span>
              </p>
            ) : (
              <p className="mb-4 text-sm text-facil-muted">Nenhum veículo vinculado ainda.</p>
            )}

            {estimatedMonthly ? (
              <p className="mb-4 text-sm text-facil-muted">
                Estimativa sobre o primário: ~R$ {estimatedMonthly}/mês em {fr?.desiredInstallments}{" "}
                meses (não é simulação de financiamento).
              </p>
            ) : null}

            <LeadVehicleInterestForm
              leadId={lead.id}
              vehicles={catalogVehicles}
              selectedIds={
                lead.vehicleInterests.length > 0
                  ? lead.vehicleInterests.map((item) => item.vehicleId)
                  : lead.vehicleId
                    ? [lead.vehicleId]
                    : []
              }
            />
          </Card>

          {fr ? (
            <LeadFinancingEditor
              leadId={lead.id}
              monthlyIncome={fr.monthlyIncome != null ? String(fr.monthlyIncome) : ""}
              downPayment={fr.downPayment != null ? String(fr.downPayment) : ""}
              desiredInstallments={fr.desiredInstallments != null ? String(fr.desiredInstallments) : ""}
              hasDriverLicense={fr.hasDriverLicense}
              occupation={fr.occupation}
              notes={fr.notes}
            />
          ) : null}

          {lead.sellRequest ? (
            <LeadSellEditor
              leadId={lead.id}
              brand={lead.sellRequest.brand}
              model={lead.sellRequest.model}
              version={lead.sellRequest.version}
              yearManufacture={
                lead.sellRequest.yearManufacture != null ? String(lead.sellRequest.yearManufacture) : ""
              }
              yearModel={lead.sellRequest.yearModel != null ? String(lead.sellRequest.yearModel) : ""}
              mileage={lead.sellRequest.mileage != null ? String(lead.sellRequest.mileage) : ""}
              fuelType={lead.sellRequest.fuelType}
              transmission={lead.sellRequest.transmission}
              saleMode={lead.sellRequest.saleMode}
              observations={lead.sellRequest.observations}
              photoUrls={lead.sellRequest.photoUrls}
            />
          ) : null}

          {lead.message ? (
            <Card title="Mensagem original">
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-foreground">{lead.message}</p>
            </Card>
          ) : null}

          {hasOrigin ? (
            <Card title="Origem">
              <dl className="grid grid-cols-1 gap-x-6 gap-y-4 sm:grid-cols-2">
                {lead.originUrl ? (
                  <Field label="URL de origem">
                    <a
                      href={lead.originUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="break-all text-facil-orange hover:underline"
                    >
                      {lead.originUrl}
                    </a>
                  </Field>
                ) : null}
                {lead.utmSource ? <Field label="utm_source">{lead.utmSource}</Field> : null}
                {lead.utmMedium ? <Field label="utm_medium">{lead.utmMedium}</Field> : null}
                {lead.utmCampaign ? <Field label="utm_campaign">{lead.utmCampaign}</Field> : null}
                {lead.utmTerm ? <Field label="utm_term">{lead.utmTerm}</Field> : null}
                {lead.utmContent ? <Field label="utm_content">{lead.utmContent}</Field> : null}
              </dl>
            </Card>
          ) : null}
        </div>

        <aside className="space-y-5 lg:sticky lg:top-20">
          <Card title="Gestão">
            <div className="flex flex-col gap-4">
              <div>
                <p className="mb-1.5 text-xs font-medium text-facil-muted">Status</p>
                <UpdateLeadStatusForm leadId={lead.id} currentStatus={lead.status} />
                <p className="mt-1 text-xs text-facil-muted">
                  Atual: {STATUS_LABELS[lead.status] ?? lead.status}
                </p>
              </div>
              <div>
                <p className="mb-1.5 text-xs font-medium text-facil-muted">Responsável</p>
                <AssignLeadForm
                  leadId={lead.id}
                  currentAssignedToUserId={lead.assignedToUserId}
                  currentUserId={currentUser.id}
                  sellers={sellers}
                />
                {lead.assignedToUser ? (
                  <p className="mt-1 text-xs text-facil-muted">Atual: {lead.assignedToUser.name}</p>
                ) : null}
              </div>
              <div>
                <p className="mb-1.5 text-xs font-medium text-facil-muted">Anotação interna</p>
                <InternalNoteForm leadId={lead.id} currentNote={lead.internalNote} />
              </div>
            </div>
          </Card>
          <LeadDangerZone leadId={lead.id} currentStatus={lead.status} />
        </aside>
      </div>
    </main>
  );
}
