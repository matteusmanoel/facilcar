"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Bell } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/cn";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

type NotificationItem = {
  id: string;
  leadId: string;
  type: string;
  createdAt: string;
  lead: { id: string; name: string; temperature: string | null };
};

type PollResponse = {
  unreadCount: number;
  notifications: NotificationItem[];
};

const POLL_MS = 15_000;

const TYPE_LABELS: Record<string, string> = {
  NEW_QUALIFIED: "Lead qualificado",
  NEW_HOT_LEAD: "Lead quente",
};

export function SdrNotificationBadge({
  className,
  placement = "sidebar",
}: {
  className?: string;
  placement?: "sidebar" | "header";
}) {
  const [unreadCount, setUnreadCount] = useState(0);
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [open, setOpen] = useState(false);
  const knownIdsRef = useRef<Set<string> | null>(null);
  const mountedRef = useRef(true);

  const poll = useCallback(async () => {
    try {
      const res = await fetch("/api/admin/sdr/notifications", {
        method: "GET",
        credentials: "same-origin",
        cache: "no-store",
      });
      if (!res.ok) return;
      const data = (await res.json()) as PollResponse;
      if (!mountedRef.current) return;

      const nextIds = new Set(data.notifications.map((n) => n.id));
      const known = knownIdsRef.current;
      if (known) {
        for (const n of data.notifications) {
          if (!known.has(n.id)) {
            const label = TYPE_LABELS[n.type] ?? "Nova oportunidade";
            toast.info(`${label}: ${n.lead.name}`, {
              action: {
                label: "Abrir",
                onClick: () => {
                  window.location.href = `/admin/leads/${n.leadId}`;
                },
              },
            });
          }
        }
      }
      knownIdsRef.current = nextIds;
      setUnreadCount(data.unreadCount);
      setItems(data.notifications);
    } catch {
      // silent — polling should not spam the UI
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    void poll();
    const id = window.setInterval(() => void poll(), POLL_MS);
    return () => {
      mountedRef.current = false;
      window.clearInterval(id);
    };
  }, [poll]);

  const markAllSeen = useCallback(async () => {
    const ids = items.map((n) => n.id);
    if (ids.length === 0) return;
    try {
      await fetch("/api/admin/sdr/notifications", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ids }),
      });
      setUnreadCount(0);
      setItems([]);
      knownIdsRef.current = new Set();
    } catch {
      toast.error("Não foi possível marcar notificações como vistas.");
    }
  }, [items]);

  const sidebar = placement === "sidebar";

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          className={cn(
            "relative rounded-md p-1.5 text-zinc-500 hover:bg-zinc-50 hover:text-zinc-950 dark:hover:bg-zinc-800 dark:hover:text-white",
            className,
          )}
          title="Notificações SDR"
          aria-label={`Notificações SDR${unreadCount > 0 ? ` (${unreadCount})` : ""}`}
        >
          <Bell className="h-4 w-4" />
          {unreadCount > 0 ? (
            <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-facil-orange px-1 text-[10px] font-bold text-white">
              {unreadCount > 99 ? "99+" : unreadCount}
            </span>
          ) : null}
        </button>
      </PopoverTrigger>
      <PopoverContent
        side={sidebar ? "top" : "bottom"}
        align={sidebar ? "start" : "end"}
        sideOffset={8}
        collisionPadding={12}
        className="w-72 p-0"
      >
        <div className="flex items-center justify-between border-b border-facil-border px-3 py-2">
          <p className="text-xs font-semibold uppercase tracking-wide text-facil-muted">
            Oportunidades
          </p>
          {items.length > 0 ? (
            <button
              type="button"
              onClick={() => void markAllSeen()}
              className="text-xs font-medium text-facil-orange hover:underline"
            >
              Marcar vistas
            </button>
          ) : null}
        </div>
        <ul className="max-h-64 overflow-y-auto py-1">
          {items.length === 0 ? (
            <li className="px-3 py-6 text-center text-xs text-facil-muted">
              Nenhuma notificação nova
            </li>
          ) : (
            items.map((n) => (
              <li key={n.id}>
                <Link
                  href={`/admin/leads/${n.leadId}`}
                  onClick={() => setOpen(false)}
                  className="block px-3 py-2 hover:bg-facil-surface"
                >
                  <p className="text-sm font-medium text-foreground">{n.lead.name}</p>
                  <p className="text-xs text-facil-muted">
                    {TYPE_LABELS[n.type] ?? n.type} ·{" "}
                    {new Date(n.createdAt).toLocaleString("pt-BR")}
                  </p>
                </Link>
              </li>
            ))
          )}
        </ul>
      </PopoverContent>
    </Popover>
  );
}
