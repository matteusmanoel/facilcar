"use client";

import { useRouter } from "next/navigation";
import { useTransition } from "react";
import { toast } from "sonner";
import { updateLeadNoteAction } from "./action";

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
        className="w-full resize-y rounded-lg border border-zinc-300 px-3 py-2 text-sm text-zinc-800 focus:border-facil-orange focus:outline-none focus:ring-2 focus:ring-facil-orange/20 disabled:opacity-50"
      />
      <button
        type="submit"
        disabled={isPending}
        className="self-start rounded-lg bg-zinc-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-zinc-800 disabled:opacity-50"
      >
        {isPending ? "Salvando…" : "Salvar nota"}
      </button>
    </form>
  );
}
