/** Pure helper for atomic claim result (unit-tested). */
export function interpretClaimCount(count: number):
  | { ok: true }
  | { ok: false; error: "already_claimed" } {
  if (count === 0) return { ok: false, error: "already_claimed" };
  return { ok: true };
}
