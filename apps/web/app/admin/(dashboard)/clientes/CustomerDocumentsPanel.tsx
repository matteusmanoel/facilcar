"use client";

import { useRef, useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";

type ManualDoc = {
  id: string;
  fileName: string;
  documentType: string;
  createdAt: string;
};

type SdrDoc = {
  id: string;
  documentType: string;
  extractionStatus: string;
  createdAt: string;
  leadId: string;
  storageKey?: string | null;
};

function sdrDocNeedsManualUpload(doc: SdrDoc): boolean {
  const key = (doc.storageKey || "").trim();
  return !key || key.startsWith("stub/") || doc.extractionStatus === "FAILED";
}

export function CustomerDocumentsPanel({
  customerId,
  manualDocs,
  sdrDocs,
  canWrite,
}: {
  customerId: string;
  manualDocs: ManualDoc[];
  sdrDocs: SdrDoc[];
  canWrite: boolean;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isPending, startTransition] = useTransition();
  const [docType, setDocType] = useState("CONTRACT");

  async function downloadSigned(kind: "customer" | "sdr", id: string) {
    const path =
      kind === "customer"
        ? `/api/admin/customers/documents/${id}/signed-url`
        : `/api/admin/sdr/documents/${id}/signed-url`;
    const res = await fetch(path);
    if (!res.ok) {
      toast.error("Não foi possível gerar o link de download");
      return;
    }
    const data = (await res.json()) as { url?: string; fileName?: string };
    if (!data.url) {
      toast.error("Não foi possível gerar o link de download");
      return;
    }
    const anchor = document.createElement("a");
    anchor.href = data.url;
    anchor.download = data.fileName?.trim() || "documento";
    anchor.rel = "noopener noreferrer";
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
  }

  function upload(file: File) {
    startTransition(async () => {
      const form = new FormData();
      form.set("file", file);
      form.set("documentType", docType);
      const res = await fetch(`/api/admin/customers/${customerId}/documents`, {
        method: "POST",
        body: form,
      });
      if (!res.ok) {
        toast.error("Falha no upload");
        return;
      }
      toast.success("Documento anexado");
      window.location.reload();
    });
  }

  return (
    <div className="space-y-4">
      {canWrite ? (
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={docType}
            onChange={(e) => setDocType(e.target.value)}
            className="h-9 rounded-lg border border-facil-border bg-facil-card px-2 text-sm text-foreground"
          >
            <option value="CONTRACT">Contrato</option>
            <option value="OTHER">Outro</option>
          </select>
          <input
            ref={inputRef}
            type="file"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) upload(file);
              e.target.value = "";
            }}
          />
          <Button
            type="button"
            size="sm"
            variant="primary"
            disabled={isPending}
            onClick={() => inputRef.current?.click()}
          >
            {isPending ? "Enviando…" : "Anexar documento"}
          </Button>
        </div>
      ) : null}

      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-facil-muted">
          Anexos do painel
        </p>
        {manualDocs.length === 0 ? (
          <p className="mt-2 text-sm text-facil-muted">Nenhum anexo manual.</p>
        ) : (
          <ul className="mt-2 divide-y divide-facil-border">
            {manualDocs.map((doc) => (
              <li key={doc.id} className="flex items-center justify-between gap-2 py-2 text-sm">
                <span className="truncate text-foreground">
                  {doc.fileName} · {doc.documentType}
                </span>
                <button
                  type="button"
                  className="text-xs font-medium text-facil-orange hover:underline"
                  onClick={() => void downloadSigned("customer", doc.id)}
                >
                  Baixar
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-facil-muted">
          Documentos enviados no WhatsApp
        </p>
        {sdrDocs.length === 0 ? (
          <p className="mt-2 text-sm text-facil-muted">Nenhum documento da Júlia ainda.</p>
        ) : (
          <ul className="mt-2 divide-y divide-facil-border">
            {sdrDocs.map((doc) => (
              <li key={doc.id} className="flex items-center justify-between gap-2 py-2 text-sm">
                <span className="truncate text-foreground">
                  {doc.documentType} · {doc.extractionStatus}
                  {sdrDocNeedsManualUpload(doc) ? (
                    <span className="ml-2 text-xs font-medium text-facil-orange">
                      Falha no upload — anexe manualmente
                    </span>
                  ) : null}
                </span>
                {sdrDocNeedsManualUpload(doc) ? null : (
                <button
                  type="button"
                  className="text-xs font-medium text-facil-orange hover:underline"
                  onClick={() => void downloadSigned("sdr", doc.id)}
                >
                  Baixar
                </button>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
