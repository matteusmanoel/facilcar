"use client";

import Link from "next/link";
import { CheckCircle2, ExternalLink, Plus, List } from "lucide-react";
import { Button } from "@/components/ui/button";

type Props = {
  slug: string;
  title: string;
  priceCash: number | null;
  thumbnailUrl: string | null;
  status: string;
  onCreateAnother: () => void;
};

function formatPrice(value: number | null): string {
  if (value == null) return "Preço não informado";
  return value.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

export function VehicleSuccessPanel({
  slug,
  title,
  priceCash,
  thumbnailUrl,
  status,
  onCreateAnother,
}: Props) {
  const publicUrl = `/estoque/${slug}`;
  const isPublished = status === "PUBLISHED";

  return (
    <div className="mx-auto max-w-lg space-y-6 py-8 text-center">
      <div className="flex flex-col items-center gap-2">
        <CheckCircle2 className="h-12 w-12 text-green-500" />
        <h2 className="text-xl font-bold text-foreground">Veículo cadastrado!</h2>
        <p className="text-sm text-facil-muted">
          {isPublished
            ? "O veículo já está disponível no catálogo público."
            : "Salvo como rascunho — publique quando estiver pronto."}
        </p>
      </div>

      <div className="overflow-hidden rounded-xl border border-facil-border bg-facil-card text-left shadow-sm">
        {thumbnailUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={thumbnailUrl} alt={title} className="aspect-video w-full object-cover" />
        ) : (
          <div className="flex aspect-video items-center justify-center bg-facil-surface text-sm text-facil-muted">
            Sem imagem
          </div>
        )}
        <div className="space-y-1 p-4">
          <p className="font-semibold text-foreground">{title}</p>
          <p className="text-lg font-bold text-facil-orange">{formatPrice(priceCash)}</p>
        </div>
      </div>

      <div className="flex flex-col gap-2 sm:flex-row sm:justify-center">
        {isPublished ? (
          <Link
            href={publicUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-facil-orange px-4 py-2 text-sm font-semibold text-white hover:bg-facil-orange-hover"
          >
            <ExternalLink className="h-4 w-4" />
            Ver no catálogo
          </Link>
        ) : null}
        <Button variant="outline" onClick={onCreateAnother}>
          <Plus className="h-4 w-4" />
          Cadastrar outro
        </Button>
        <Link
          href="/admin/veiculos"
          className="inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold text-foreground hover:bg-facil-surface"
        >
          <List className="h-4 w-4" />
          Ir para lista
        </Link>
      </div>
    </div>
  );
}
