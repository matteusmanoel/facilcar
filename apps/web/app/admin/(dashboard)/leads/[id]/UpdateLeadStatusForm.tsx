"use client";

import { useRouter } from "next/navigation";
import { updateLeadStatusAction } from "./action";

type Props = { leadId: string; currentStatus: string };

const STATUSES = ["NEW", "IN_PROGRESS", "CONTACTED", "QUALIFIED", "WON", "LOST", "SPAM"] as const;

export function UpdateLeadStatusForm({ leadId, currentStatus }: Props) {
  const router = useRouter();

  return (
    <form
      action={async (formData) => {
        await updateLeadStatusAction(leadId, formData.get("status") as string);
        router.refresh();
      }}
      className="inline"
    >
      <select
        name="status"
        defaultValue={currentStatus}
        className="rounded border px-2 py-1 text-sm"
        onChange={(e) => e.target.form?.requestSubmit()}
      >
        {STATUSES.map((s) => (
          <option key={s} value={s}>
            {s}
          </option>
        ))}
      </select>
    </form>
  );
}
