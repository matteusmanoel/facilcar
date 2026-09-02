import { leadVehicleLabel } from "./vehicle-label";

function isPlaceholderDisplayName(name: string | null | undefined): boolean {
  const value = (name ?? "").trim();
  return !value || value.toLowerCase().startsWith("whatsapp ");
}

export function isDebugJuliaSummary(text: string | null | undefined): boolean {
  if (!text) return false;
  return /\bIntent:\s/i.test(text) && (/\bFacts:\s/i.test(text) || /\bBusiness:\s/i.test(text));
}

const INTENT_FORMA: Record<string, string> = {
  purchase: "Compra",
  purchase_financing: "Compra financiada",
  trade: "Troca",
  sale: "Venda",
  consignment: "Consignação",
  refinancing: "Refinanciamento",
};

/** Seller-facing brief. Never show the Intent/Facts debug dump in the CRM. */
export function vendorSummaryFromLead(lead: {
  name: string;
  juliaSummary: string | null;
  metadataJson?: unknown;
}): string | null {
  const stored = lead.juliaSummary?.trim() ?? "";
  if (stored && !isDebugJuliaSummary(stored)) return stored;

  const parts: string[] = [];
  if (!isPlaceholderDisplayName(lead.name)) {
    parts.push(`Cliente: ${lead.name.trim()}`);
  }

  const interest = leadVehicleLabel({
    vehicle: null,
    metadataJson: lead.metadataJson,
  });
  if (interest) parts.push(`Interesse: ${interest}`);

  const meta =
    lead.metadataJson && typeof lead.metadataJson === "object" && !Array.isArray(lead.metadataJson)
      ? (lead.metadataJson as { intent?: unknown })
      : null;
  const intent = typeof meta?.intent === "string" ? meta.intent : "";
  const forma = INTENT_FORMA[intent];
  if (forma) parts.push(`Forma: ${forma}`);

  if (parts.length) return parts.join(" · ");
  return stored || null;
}
