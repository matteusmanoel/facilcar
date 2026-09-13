import { SearchX } from "lucide-react";
import { ClearFiltersButton } from "@/features/catalog/ui/ClearFiltersButton";

type Props = {
  title: string;
  description?: string;
  showClearFilters?: boolean;
};

export function EmptyState({ title, description, showClearFilters = false }: Props) {
  return (
    <div className="flex flex-col items-center rounded-2xl border border-dashed border-facil-border bg-facil-surface px-6 py-16 text-center">
      <SearchX className="h-16 w-16 text-facil-orange sm:h-20 sm:w-20" strokeWidth={1.5} aria-hidden />
      <p className="mt-5 font-semibold text-foreground">{title}</p>
      {description ? <p className="mt-1 max-w-md text-sm text-facil-muted">{description}</p> : null}
      {showClearFilters ? <ClearFiltersButton className="mt-6" /> : null}
    </div>
  );
}
