/** Shared multi-select helpers for kanban columns and list pages. */

export function rangeIds(
  orderedIds: string[],
  fromId: string | null | undefined,
  toId: string,
): string[] {
  if (!fromId) return [toId];
  const from = orderedIds.indexOf(fromId);
  const to = orderedIds.indexOf(toId);
  if (from < 0 || to < 0) return [toId];
  const start = Math.min(from, to);
  const end = Math.max(from, to);
  return orderedIds.slice(start, end + 1);
}

export function toggleId(prev: Set<string>, id: string): Set<string> {
  const next = new Set(prev);
  if (next.has(id)) next.delete(id);
  else next.add(id);
  return next;
}

export function unionIds(prev: Set<string>, ids: Iterable<string>): Set<string> {
  const next = new Set(prev);
  for (const id of ids) next.add(id);
  return next;
}
