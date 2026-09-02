"use client";

import { useRouter } from "next/navigation";
import { useTransition } from "react";
import { toast } from "sonner";
import { updateLeadNoteAction } from "@/features/lead/server/mutations";
import { Button } from "@/components/ui/button";

type Props = { leadId: string; currentNote: string | null };

export function InternalNoteForm({ leadId, currentNote }: Props) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();

  function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const note = (e.currentTarget.elements.namedItem("note") as HTMLTextAreaElement).value;
    startTransition(async () => {
      try {
        await updateLeadNoteAction(leadId, note);
        router.refresh();
        toast.success("Anotação salva com sucesso!");
      } catch {
        toast.error("Erro ao salvar anotação.");
      }
    });
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-2">
      <textarea
        name="note"
        rows={3}
        defaultValue={currentNote ?? ""}
        placeholder="Anotações internas sobre este lead…"
        disabled={isPending}
        className="box-border w-full resize-y rounded-lg border border-facil-border bg-facil-card px-3 py-2 text-sm text-foreground placeholder:text-facil-muted focus:border-facil-orange focus:outline-none focus:ring-2 focus:ring-inset focus:ring-facil-orange/30 disabled:opacity-50"
      />
      <Button type="submit" variant="primary" size="sm" disabled={isPending} className="self-start">
        {isPending ? "Salvando…" : "Salvar nota"}
      </Button>
    </form>
  );
}
