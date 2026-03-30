"use client";

import { cn } from "@/lib/cn";
import { Skeleton } from "@/components/ui/skeleton";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";

export interface ColumnDef<T> {
  key: string;
  header: string;
  cell: (row: T) => React.ReactNode;
  className?: string;
  hideOnMobile?: boolean;
}

interface AdminTableProps<T> {
  columns: ColumnDef<T>[];
  data: T[];
  isLoading?: boolean;
  emptyMessage?: string;
  emptyIcon?: React.ReactNode;
  keyExtractor: (row: T) => string;
  skeletonRows?: number;
  onRowClick?: (row: T) => void;
  // Pagination
  currentPage?: number;
  totalPages?: number;
  onPageChange?: (page: number) => void;
}

export function AdminTable<T>({
  columns,
  data,
  isLoading = false,
  emptyMessage = "Nenhum item encontrado.",
  emptyIcon,
  keyExtractor,
  skeletonRows = 5,
  onRowClick,
  currentPage,
  totalPages,
  onPageChange,
}: AdminTableProps<T>) {
  const visibleColumns = columns;

  return (
    <div className="overflow-hidden rounded-xl border border-zinc-200 bg-white shadow-sm">
      {/* Desktop table */}
      <div className="hidden overflow-x-auto md:block">
        <table className="w-full text-sm">
          <thead className="border-b border-zinc-100 bg-zinc-50">
            <tr>
              {visibleColumns.map((col) => (
                <th
                  key={col.key}
                  className={cn(
                    "admin-table-header",
                    col.className,
                  )}
                >
                  {col.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              Array.from({ length: skeletonRows }).map((_, i) => (
                <tr key={i} className="border-t border-zinc-100">
                  {visibleColumns.map((col) => (
                    <td key={col.key} className="px-4 py-3">
                      <Skeleton className="h-4 w-full max-w-[160px]" />
                    </td>
                  ))}
                </tr>
              ))
            ) : data.length === 0 ? (
              <tr>
                <td colSpan={visibleColumns.length} className="py-12 text-center">
                  <div className="flex flex-col items-center gap-2 text-zinc-400">
                    {emptyIcon ?? (
                      <svg
                        className="h-10 w-10 text-zinc-300"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={1.5}
                          d="M9 5H7a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"
                        />
                      </svg>
                    )}
                    <p className="text-sm">{emptyMessage}</p>
                  </div>
                </td>
              </tr>
            ) : (
              data.map((row) => (
                <tr
                  key={keyExtractor(row)}
                  className={cn(
                    "border-t border-zinc-100 transition-colors",
                    onRowClick && "cursor-pointer hover:bg-zinc-50",
                  )}
                  onClick={() => onRowClick?.(row)}
                >
                  {visibleColumns.map((col) => (
                    <td key={col.key} className={cn("admin-table-cell", col.className)}>
                      {col.cell(row)}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Mobile cards */}
      <div className="divide-y divide-zinc-100 md:hidden">
        {isLoading ? (
          Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="p-4 space-y-2">
              <Skeleton className="h-4 w-3/4" />
              <Skeleton className="h-3 w-1/2" />
              <Skeleton className="h-3 w-1/3" />
            </div>
          ))
        ) : data.length === 0 ? (
          <div className="py-12 text-center text-sm text-zinc-400">{emptyMessage}</div>
        ) : (
          data.map((row) => (
            <div
              key={keyExtractor(row)}
              className={cn("p-4", onRowClick && "cursor-pointer active:bg-zinc-50")}
              onClick={() => onRowClick?.(row)}
            >
              {visibleColumns
                .filter((c) => !c.hideOnMobile)
                .map((col) => (
                  <div key={col.key} className="flex items-start justify-between py-0.5">
                    <span className="text-xs font-medium text-zinc-400 shrink-0 mr-2">
                      {col.header}
                    </span>
                    <span className="text-xs text-zinc-700 text-right">{col.cell(row)}</span>
                  </div>
                ))}
            </div>
          ))
        )}
      </div>

      {/* Pagination */}
      {totalPages && totalPages > 1 && onPageChange && (
        <div className="flex items-center justify-between border-t border-zinc-100 px-4 py-3">
          <p className="text-xs text-zinc-500">
            Página {currentPage} de {totalPages}
          </p>
          <div className="flex items-center gap-1">
            <Button
              variant="outline"
              size="icon-sm"
              onClick={() => onPageChange((currentPage ?? 1) - 1)}
              disabled={currentPage === 1}
            >
              <ChevronLeft className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant="outline"
              size="icon-sm"
              onClick={() => onPageChange((currentPage ?? 1) + 1)}
              disabled={currentPage === totalPages}
            >
              <ChevronRight className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
