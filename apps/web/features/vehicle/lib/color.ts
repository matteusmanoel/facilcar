const COLOR_LABELS: Record<string, string> = {
  WHITE: "Branco",
  SILVER: "Prata",
  BLACK: "Preto",
  RED: "Vermelho",
  BLUE: "Azul",
  GRAY: "Cinza",
  GREY: "Cinza",
  GREEN: "Verde",
  YELLOW: "Amarelo",
  ORANGE: "Laranja",
  BROWN: "Marrom",
  BEIGE: "Bege",
};

export function displayColorFromSnapshot(raw: string | null | undefined): string | null {
  if (raw == null || !String(raw).trim()) return null;
  const key = String(raw).trim().toUpperCase();
  return COLOR_LABELS[key] ?? String(raw).trim();
}
