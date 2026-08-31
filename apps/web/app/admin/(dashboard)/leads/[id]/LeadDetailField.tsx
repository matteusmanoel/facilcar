import type { ReactNode } from "react";

export function LeadDetailField({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-xs font-medium text-facil-muted">{label}</dt>
      <dd className="mt-0.5 text-sm text-foreground">{children ?? "—"}</dd>
    </div>
  );
}
