/** Display label for the lead list / kanban — published vehicle first, then interest text. */

type InterestFacts = {
  desired_vehicle_text?: unknown;
  desired_model?: unknown;
  vehicle_interest?: unknown;
};

function factsInterestText(metadataJson: unknown): string | null {
  if (!metadataJson || typeof metadataJson !== "object" || Array.isArray(metadataJson)) {
    return null;
  }
  const facts = (metadataJson as { facts?: unknown }).facts;
  if (!facts || typeof facts !== "object" || Array.isArray(facts)) return null;
  const record = facts as InterestFacts;
  for (const value of [record.desired_vehicle_text, record.desired_model, record.vehicle_interest]) {
    if (typeof value === "string" && value.trim()) return value.trim();
  }
  return null;
}

/** Explicit isPrimary only — never the first row of an unordered list. */
export function selectExplicitPrimary<T extends { isPrimary?: boolean }>(rows: T[]): T | null {
  return rows.find((item) => item.isPrimary === true) ?? null;
}

export function nextPrimaryVehicleId(
  selectedIds: string[],
  currentPrimaryId: string | null | undefined,
): string | null {
  const ids = selectedIds.filter(Boolean);
  const current = (currentPrimaryId ?? "").trim();
  if (current && ids.includes(current)) return current;
  return null;
}

export function leadVehicleLabel(lead: {
  vehicle?: { title: string } | null;
  vehicleInterests?: Array<{ isPrimary: boolean; vehicle: { title: string } }>;
  metadataJson?: unknown;
}): string | null {
  const linked = lead.vehicle?.title?.trim();
  if (linked) return linked;

  const interests = lead.vehicleInterests ?? [];
  const primary = selectExplicitPrimary(interests);
  const interestTitle = primary?.vehicle?.title?.trim();
  if (interestTitle) return interestTitle;

  return factsInterestText(lead.metadataJson);
}
