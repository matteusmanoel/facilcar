"use client";

import { useDraggable } from "@dnd-kit/core";
import { CSS } from "@dnd-kit/utilities";
import { cn } from "@/lib/cn";
import { StatusBadge } from "@/components/admin/StatusBadge";
import type { MouseEvent } from "react";

const WA_ICON = (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor">
    <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" />
  </svg>
);

export type KanbanLead = {
  id: string;
  name: string;
  phone: string;
  type: string;
  status: string;
  createdAt: Date;
  vehicle: { title: string } | null;
  temperature?: string | null;
  assignedToUser?: { name: string } | null;
};

interface KanbanCardProps {
  lead: KanbanLead;
  isDragOverlay?: boolean;
  showCheckbox?: boolean;
  selected?: boolean;
  onToggleSelect?: (leadId: string, event: { shiftKey: boolean }) => void;
  onOpen?: (lead: KanbanLead) => void;
}

export function KanbanCard({
  lead,
  isDragOverlay,
  showCheckbox,
  selected,
  onToggleSelect,
  onOpen,
}: KanbanCardProps) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: lead.id,
    data: { lead },
    disabled: isDragOverlay,
  });

  const style = transform ? { transform: CSS.Translate.toString(transform) } : undefined;

  const phone = lead.phone.replace(/\D/g, "");
  const waUrl = phone
    ? `https://wa.me/${phone}?text=${encodeURIComponent(`Olá ${lead.name}, aqui é da FácilCar!`)}`
    : null;

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...listeners}
      {...attributes}
      role="button"
      tabIndex={0}
      onClick={(e) => {
        if (isDragging) return;
        if (showCheckbox) {
          onToggleSelect?.(lead.id, e);
          return;
        }
        onOpen?.(lead);
      }}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          if (showCheckbox) {
            onToggleSelect?.(lead.id, e);
            return;
          }
          onOpen?.(lead);
        }
      }}
      className={cn(
        "group cursor-grab rounded-lg border border-facil-border bg-facil-card p-3 shadow-sm transition-shadow active:cursor-grabbing",
        isDragging && "opacity-40",
        isDragOverlay && "rotate-1 cursor-grabbing opacity-100 shadow-xl",
        selected && "ring-2 ring-facil-orange ring-offset-2 ring-offset-background",
      )}
    >
      <div className="flex items-start gap-2">
        {showCheckbox ? (
          <input
            type="checkbox"
            checked={selected}
            onChange={() => undefined}
            onClick={(e) => {
              e.stopPropagation();
              onToggleSelect?.(lead.id, e);
            }}
            className="mt-1 h-4 w-4 rounded border-facil-border accent-facil-orange"
            aria-label={`Selecionar ${lead.name}`}
          />
        ) : null}
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-foreground">{lead.name}</p>
          <p className="mt-0.5 text-xs text-facil-muted">{lead.phone}</p>
          {lead.vehicle ? (
            <p className="mt-1 truncate text-xs text-facil-muted">{lead.vehicle.title}</p>
          ) : null}
          <div className="mt-2 flex items-center justify-between">
            <StatusBadge status={lead.type} type="type" />
            {waUrl ? (
              <a
                href={waUrl}
                target="_blank"
                rel="noopener noreferrer"
                onClick={(e) => e.stopPropagation()}
                onPointerDown={(e) => e.stopPropagation()}
                className="flex h-5 w-5 items-center justify-center rounded-full bg-green-500 text-white opacity-0 transition-opacity hover:bg-green-600 group-hover:opacity-100"
                aria-label="WhatsApp"
              >
                {WA_ICON}
              </a>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}
