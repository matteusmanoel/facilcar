import Link from "next/link";
import { CarFront } from "lucide-react";

export function PublicNotFound() {
  return (
    <section className="flex min-h-[60vh] flex-col items-center justify-center px-4 py-16 text-center">
      <CarFront
        className="h-24 w-24 text-facil-orange sm:h-28 sm:w-28"
        strokeWidth={1.25}
        aria-hidden
      />
      <p className="mt-6 text-sm font-semibold uppercase tracking-widest text-facil-orange">
        Erro 404
      </p>
      <h1 className="mt-2 font-display text-4xl text-foreground sm:text-5xl">
        Página não encontrada
      </h1>
      <p className="mt-4 max-w-md text-sm leading-relaxed text-facil-muted sm:text-base">
        Esse endereço não existe ou o veículo saiu do estoque. Volte ao catálogo
        para ver o que está disponível agora.
      </p>
      <Link href="/estoque" className="btn-facil-primary mt-8">
        Ver estoque
      </Link>
    </section>
  );
}
