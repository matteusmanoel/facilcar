export function shouldShowInspectionSeal(
  result: string | null | undefined,
): boolean {
  return result === "APPROVED";
}
