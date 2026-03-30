"use client";

import { format } from "date-fns";
import { useRouter } from "next/navigation";
import { DateRangePicker } from "@/components/ui/date-picker";

export function DashboardPeriodFilter({
  from,
  to,
}: {
  from: Date;
  to: Date;
}) {
  const router = useRouter();

  return (
    <DateRangePicker
      from={from}
      to={to}
      onApply={({ from: f, to: t }) => {
        const sp = new URLSearchParams();
        if (f) sp.set("from", format(f, "yyyy-MM-dd"));
        if (t) sp.set("to", format(t, "yyyy-MM-dd"));
        router.push(`/admin?${sp.toString()}`);
      }}
      className="min-w-[200px]"
    />
  );
}
