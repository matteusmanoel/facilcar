import type { VehicleImportInput } from "./classify";
import {
  normalizeEngineDisplacementLiters,
  parseEngineDisplacementFromAdText,
} from "@/features/vehicle/lib/engine-displacement";
import { isSuspiciousVehicleModel } from "@/features/vehicle/lib/suspicious-model";

export type ValidationResult = {
  valid: boolean;
  errors: string[];
  warnings: string[];
};

export function validateVehicleImportInput(
  input: VehicleImportInput,
  rawText: string | null | undefined,
): ValidationResult {
  const errors: string[] = [];
  const warnings = [...input.warnings];

  const hasTitle = !!input.title?.trim();
  const model = input.model?.trim() || "";
  const hasBrandModel = !!input.brand?.trim() && !!model;
  if (!hasTitle && !hasBrandModel) {
    errors.push("insufficient_vehicle_identity");
  }
  if (!model) {
    errors.push("missing_model");
  } else if (isSuspiciousVehicleModel(model)) {
    errors.push("suspicious_model");
  }

  const engine = normalizeEngineDisplacementLiters(input.engineDisplacementLiters);
  if (input.engineDisplacementLiters != null && engine == null) {
    warnings.push("ENGINE_AMBIGUOUS");
  }
  if (rawText?.trim()) {
    const fromText = parseEngineDisplacementFromAdText(rawText);
    if (fromText.warning === "ENGINE_AMBIGUOUS") {
      warnings.push("ENGINE_AMBIGUOUS");
    }
  }
  if (!rawText?.trim()) {
    warnings.push("missing_raw_text");
  }
  for (const f of input.missingFields) {
    warnings.push(`missing:${f}`);
  }

  return { valid: errors.length === 0, errors, warnings };
}
