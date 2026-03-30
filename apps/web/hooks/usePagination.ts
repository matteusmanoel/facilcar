import { useState, useMemo } from "react";

interface UsePaginationProps {
  totalItems: number;
  itemsPerPage?: number;
  initialPage?: number;
}

export function usePagination({
  totalItems,
  itemsPerPage = 20,
  initialPage = 1,
}: UsePaginationProps) {
  const [currentPage, setCurrentPage] = useState(initialPage);

  const totalPages = Math.max(1, Math.ceil(totalItems / itemsPerPage));
  const safeCurrentPage = Math.min(Math.max(1, currentPage), totalPages);

  const startIndex = (safeCurrentPage - 1) * itemsPerPage;
  const endIndex = Math.min(startIndex + itemsPerPage, totalItems);

  const pageNumbers = useMemo(() => {
    const delta = 2;
    const range: number[] = [];
    for (
      let i = Math.max(2, safeCurrentPage - delta);
      i <= Math.min(totalPages - 1, safeCurrentPage + delta);
      i++
    ) {
      range.push(i);
    }
    if (safeCurrentPage - delta > 2) range.unshift(-1);
    if (safeCurrentPage + delta < totalPages - 1) range.push(-1);
    if (totalPages > 1) {
      range.unshift(1);
      if (totalPages > 1) range.push(totalPages);
    }
    return [...new Set(range)];
  }, [safeCurrentPage, totalPages]);

  function goToPage(page: number) {
    setCurrentPage(Math.min(Math.max(1, page), totalPages));
  }

  function nextPage() {
    goToPage(safeCurrentPage + 1);
  }

  function prevPage() {
    goToPage(safeCurrentPage - 1);
  }

  function paginateArray<T>(arr: T[]): T[] {
    return arr.slice(startIndex, endIndex);
  }

  return {
    currentPage: safeCurrentPage,
    totalPages,
    startIndex,
    endIndex,
    pageNumbers,
    goToPage,
    nextPage,
    prevPage,
    paginateArray,
    hasPrev: safeCurrentPage > 1,
    hasNext: safeCurrentPage < totalPages,
  };
}
