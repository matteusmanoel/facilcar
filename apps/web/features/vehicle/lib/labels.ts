export const fuelLabels: Record<string, string> = {
  GASOLINE: "Gasolina",
  ETHANOL: "Etanol",
  FLEX: "Flex",
  DIESEL: "Diesel",
  ELECTRIC: "Elétrico",
  HYBRID: "Híbrido",
  OTHER: "Outro",
};

export const transLabels: Record<string, string> = {
  MANUAL: "Manual",
  AUTOMATIC: "Automático",
  AUTOMATED: "Automatizado",
  CVT: "CVT",
  OTHER: "Outro",
};

export const statusLabels: Record<string, string> = {
  DRAFT: "Rascunho",
  PUBLISHED: "Publicado",
  RESERVED: "Reservado",
  SOLD: "Vendido",
  ARCHIVED: "Arquivado",
};

export const stockTypeLabels: Record<string, string> = {
  OWNED: "Próprio",
  CONSIGNED: "Consignado",
};

export const commercialHistoryLabels: Record<string, string> = {
  CLEAN: "Histórico limpo",
  AUCTION: "Leilão",
  RECOVERED_CLAIM: "Recuperado de sinistro",
  AUCTION_AND_RECOVERED_CLAIM: "Leilão e recuperado de sinistro",
};

export const typeLabels: Record<string, string> = {
  CAR: "Carro",
  MOTORCYCLE: "Moto",
  UTILITY: "Utilitário",
  OTHER: "Outro",
};

export function labelFor(map: Record<string, string>, value: string | null | undefined): string {
  if (!value) return "—";
  return map[value] ?? value;
}
