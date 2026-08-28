/** Footer CTA contract: navigation never submits; save only on the last step. */

export function vehicleFormFooterAction(
  step: number,
  stepCount: number,
): "next" | "save" {
  return step < stepCount - 1 ? "next" : "save";
}
