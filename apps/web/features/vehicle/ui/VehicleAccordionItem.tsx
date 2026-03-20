"use client";

import { useState, type ReactNode } from "react";

function ChevronIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d="m6 9 6 6 6-6" />
    </svg>
  );
}

export function VehicleAccordionItem({
  title,
  children,
  defaultOpen = false,
}: {
  title: string;
  children: ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <details
      open={open}
      onToggle={(e) => setOpen(e.currentTarget.open)}
      className="group border-b border-zinc-200 last:border-b-0"
    >
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-1 py-4 text-left font-semibold text-zinc-900 transition hover:text-facil-orange [&::-webkit-details-marker]:hidden">
        <span>{title}</span>
        <ChevronIcon
          className={`shrink-0 text-zinc-400 transition ${open ? "rotate-180 text-facil-orange" : ""}`}
        />
      </summary>
      <div className="border-t border-zinc-100 px-1 pb-4 pt-3">{children}</div>
    </details>
  );
}
