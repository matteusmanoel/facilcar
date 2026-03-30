import { cn } from "@/lib/cn";

const STATUS_CONFIG: Record<
  string,
  { label: string; className: string }
> = {
  // Lead statuses
  NEW: { label: "Novo", className: "bg-blue-100 text-blue-800" },
  IN_PROGRESS: { label: "Em progresso", className: "bg-yellow-100 text-yellow-800" },
  CONTACTED: { label: "Contactado", className: "bg-purple-100 text-purple-800" },
  QUALIFIED: { label: "Qualificado", className: "bg-indigo-100 text-indigo-800" },
  WON: { label: "Ganho", className: "bg-green-100 text-green-800" },
  LOST: { label: "Perdido", className: "bg-zinc-100 text-zinc-600" },
  SPAM: { label: "Spam", className: "bg-red-100 text-red-700" },
  // Vehicle statuses
  DRAFT: { label: "Rascunho", className: "bg-zinc-100 text-zinc-600" },
  PUBLISHED: { label: "Publicado", className: "bg-green-100 text-green-800" },
  RESERVED: { label: "Reservado", className: "bg-yellow-100 text-yellow-800" },
  SOLD: { label: "Vendido", className: "bg-blue-100 text-blue-800" },
  ARCHIVED: { label: "Arquivado", className: "bg-zinc-100 text-zinc-500" },
};

const TYPE_CONFIG: Record<string, { label: string; className: string }> = {
  CONTACT: { label: "Contato", className: "bg-zinc-100 text-zinc-700" },
  VEHICLE_INTEREST: { label: "Interesse", className: "bg-facil-orange-light text-facil-orange" },
  FINANCING: { label: "Financiamento", className: "bg-blue-50 text-blue-700" },
  SELL_VEHICLE: { label: "Vender veículo", className: "bg-purple-50 text-purple-700" },
};

interface StatusBadgeProps {
  status: string;
  type?: "status" | "type";
  className?: string;
}

export function StatusBadge({ status, type = "status", className }: StatusBadgeProps) {
  const config =
    type === "type"
      ? TYPE_CONFIG[status] ?? { label: status, className: "bg-zinc-100 text-zinc-600" }
      : STATUS_CONFIG[status] ?? { label: status, className: "bg-zinc-100 text-zinc-600" };

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold",
        config.className,
        className,
      )}
    >
      {config.label}
    </span>
  );
}
