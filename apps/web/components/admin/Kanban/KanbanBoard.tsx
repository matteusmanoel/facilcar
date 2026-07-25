"use client";

import { useState, useCallback, useMemo, useTransition } from "react";
import {
  DndContext,
  DragEndEvent,
  DragOverEvent,
  DragStartEvent,
  DragOverlay,
  PointerSensor,
  TouchSensor,
  useSensor,
  useSensors,
  closestCenter,
} from "@dnd-kit/core";
import { useDroppable } from "@dnd-kit/core";
import { toast } from "sonner";
import { cn } from "@/lib/cn";
import { KanbanCard, type KanbanLead } from "./KanbanCard";
import { batchUpdateLeadStatusAction, updateLeadStatusAction } from "@/features/lead/server/mutations";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

const COLUMNS: { id: string; label: string; color: string }[] = [
  { id: "NEW", label: "Novos", color: "bg-blue-500" },
  { id: "IN_PROGRESS", label: "Em progresso", color: "bg-yellow-500" },
  { id: "CONTACTED", label: "Contactado", color: "bg-purple-500" },
  { id: "QUALIFIED", label: "Qualificado", color: "bg-indigo-500" },
  { id: "WON", label: "Ganho", color: "bg-green-500" },
  { id: "LOST", label: "Perdido", color: "bg-zinc-400" },
];

function DroppableColumn({
  column,
  leads,
  isOver,
  selectable,
  selectedIds,
  onToggleSelect,
}: {
  column: (typeof COLUMNS)[number];
  leads: KanbanLead[];
  isOver: boolean;
  selectable: boolean;
  selectedIds: Set<string>;
  onToggleSelect: (id: string) => void;
}) {
  const { setNodeRef } = useDroppable({ id: column.id });

  return (
    <div className="flex w-64 shrink-0 flex-col rounded-xl border border-facil-border bg-facil-surface/80">
      <div className="flex items-center justify-between rounded-t-xl px-3 py-2.5">
        <div className="flex items-center gap-2">
          <div className={cn("h-2 w-2 rounded-full", column.color)} />
          <span className="text-sm font-semibold text-foreground">{column.label}</span>
        </div>
        <span className="rounded-full bg-facil-card px-2 py-0.5 text-xs font-semibold text-facil-muted">
          {leads.length}
        </span>
      </div>

      <div
        ref={setNodeRef}
        className={cn(
          "flex min-h-[120px] flex-1 flex-col gap-2 rounded-b-xl p-2 transition-colors",
          isOver && "bg-facil-orange-light/80 ring-2 ring-inset ring-facil-orange/40",
        )}
      >
        {leads.map((lead) => (
          <KanbanCard
            key={lead.id}
            lead={lead}
            selectable={selectable}
            selected={selectedIds.has(lead.id)}
            onToggleSelect={onToggleSelect}
          />
        ))}
        {leads.length === 0 && (
          <div className="flex h-16 items-center justify-center rounded-lg border-2 border-dashed border-facil-border text-xs text-facil-muted">
            Solte aqui
          </div>
        )}
      </div>
    </div>
  );
}

interface KanbanBoardProps {
  initialLeads: KanbanLead[];
}

export function KanbanBoard({ initialLeads }: KanbanBoardProps) {
  const [leads, setLeads] = useState<KanbanLead[]>(initialLeads);
  const [activeLead, setActiveLead] = useState<KanbanLead | null>(null);
  const [overColumn, setOverColumn] = useState<string | null>(null);
  const [lostConfirm, setLostConfirm] = useState<{
    leadId: string;
    prevStatus: string;
  } | null>(null);
  const [bulkMode, setBulkMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [bulkStatus, setBulkStatus] = useState<string>("");
  const [isPending, startTransition] = useTransition();

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 250, tolerance: 12 } }),
  );

  const grouped = useMemo(() => {
    const map: Record<string, KanbanLead[]> = {};
    for (const col of COLUMNS) map[col.id] = [];
    for (const lead of leads) {
      if (lead.status in map) map[lead.status].push(lead);
    }
    return map;
  }, [leads]);

  const toggleSelect = useCallback((id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const handleDragStart = useCallback(
    (event: DragStartEvent) => {
      if (bulkMode) return;
      const lead = leads.find((l) => l.id === event.active.id);
      setActiveLead(lead ?? null);
    },
    [leads, bulkMode],
  );

  const handleDragOver = useCallback((event: DragOverEvent) => {
    const overId = event.over?.id as string | undefined;
    const isColumn = COLUMNS.some((c) => c.id === overId);
    setOverColumn(isColumn ? (overId ?? null) : null);
  }, []);

  const applyStatusMove = useCallback(
    (leadId: string, newStatus: string, prevStatus: string) => {
      setLeads((prev) => prev.map((l) => (l.id === leadId ? { ...l, status: newStatus } : l)));
      startTransition(async () => {
        try {
          await updateLeadStatusAction(leadId, newStatus);
          toast.success(`Lead movido para "${COLUMNS.find((c) => c.id === newStatus)?.label}"`);
        } catch {
          setLeads((prev) =>
            prev.map((l) => (l.id === leadId ? { ...l, status: prevStatus } : l)),
          );
          toast.error("Erro ao atualizar status. Tente novamente.");
        }
      });
    },
    [],
  );

  const handleDragEnd = useCallback(
    (event: DragEndEvent) => {
      setActiveLead(null);
      setOverColumn(null);
      if (bulkMode) return;

      const { active, over } = event;
      if (!over) return;

      const leadId = active.id as string;
      const newStatus = over.id as string;
      const isValidColumn = COLUMNS.some((c) => c.id === newStatus);
      if (!isValidColumn) return;

      const lead = leads.find((l) => l.id === leadId);
      if (!lead || lead.status === newStatus) return;

      if (newStatus === "LOST") {
        setLostConfirm({ leadId, prevStatus: lead.status });
        return;
      }

      applyStatusMove(leadId, newStatus, lead.status);
    },
    [leads, applyStatusMove, bulkMode],
  );

  function applyBulkMove() {
    if (!bulkStatus || selectedIds.size === 0) return;
    const ids = Array.from(selectedIds);
    const prevById = new Map(leads.filter((l) => selectedIds.has(l.id)).map((l) => [l.id, l.status]));

    setLeads((prev) =>
      prev.map((l) => (selectedIds.has(l.id) ? { ...l, status: bulkStatus } : l)),
    );

    startTransition(async () => {
      try {
        await batchUpdateLeadStatusAction(ids, bulkStatus);
        toast.success(`${ids.length} lead(s) movido(s) para "${COLUMNS.find((c) => c.id === bulkStatus)?.label}"`);
        setSelectedIds(new Set());
        setBulkMode(false);
        setBulkStatus("");
      } catch {
        setLeads((prev) =>
          prev.map((l) => {
            const prevStatus = prevById.get(l.id);
            return prevStatus ? { ...l, status: prevStatus } : l;
          }),
        );
        toast.error("Erro ao mover leads em lote.");
      }
    });
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <Button
          type="button"
          variant={bulkMode ? "primary" : "outline"}
          size="sm"
          onClick={() => {
            setBulkMode((v) => !v);
            setSelectedIds(new Set());
          }}
        >
          {bulkMode ? "Sair da seleção" : "Selecionar vários"}
        </Button>

        {bulkMode && selectedIds.size > 0 ? (
          <>
            <span className="text-sm text-facil-muted">{selectedIds.size} selecionado(s)</span>
            <Select value={bulkStatus} onValueChange={setBulkStatus}>
              <SelectTrigger className="h-8 w-[180px]">
                <SelectValue placeholder="Mover para…" />
              </SelectTrigger>
              <SelectContent>
                {COLUMNS.map((col) => (
                  <SelectItem key={col.id} value={col.id}>
                    {col.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button
              type="button"
              size="sm"
              variant="primary"
              disabled={!bulkStatus || isPending}
              onClick={applyBulkMove}
            >
              Aplicar
            </Button>
          </>
        ) : null}
      </div>

      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragStart={handleDragStart}
        onDragOver={handleDragOver}
        onDragEnd={handleDragEnd}
      >
        <div className="flex gap-3 overflow-x-auto pb-4">
          {COLUMNS.map((col) => (
            <DroppableColumn
              key={col.id}
              column={col}
              leads={grouped[col.id] ?? []}
              isOver={overColumn === col.id}
              selectable={bulkMode}
              selectedIds={selectedIds}
              onToggleSelect={toggleSelect}
            />
          ))}
        </div>

        <DragOverlay>
          {activeLead ? <KanbanCard lead={activeLead} isDragOverlay /> : null}
        </DragOverlay>

        <Dialog open={!!lostConfirm} onOpenChange={(o) => !o && setLostConfirm(null)}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Marcar como perdido?</DialogTitle>
              <DialogDescription>
                Confirme que este lead não seguirá no funil como oportunidade ativa.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter className="gap-2 sm:gap-0">
              <Button type="button" variant="outline" onClick={() => setLostConfirm(null)}>
                Cancelar
              </Button>
              <Button
                type="button"
                disabled={isPending}
                onClick={() => {
                  if (!lostConfirm) return;
                  const { leadId, prevStatus } = lostConfirm;
                  setLostConfirm(null);
                  applyStatusMove(leadId, "LOST", prevStatus);
                }}
              >
                Confirmar
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </DndContext>
    </div>
  );
}
