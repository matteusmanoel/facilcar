export type DocumentCrmView = {
  commerciallyReceived: boolean;
  stored: boolean;
  downloadable: boolean;
  label: string;
};

export function documentCrmView(doc: {
  storageStatus?: string | null;
  storageKey?: string | null;
  commerciallyReceived?: boolean;
}): DocumentCrmView {
  const status = (doc.storageStatus ?? "PENDING").toUpperCase();
  const stored = status === "STORED" && Boolean(doc.storageKey && !doc.storageKey.startsWith("stub/"));
  const received = doc.commerciallyReceived !== false;
  return {
    commerciallyReceived: received,
    stored,
    downloadable: received && stored,
    label: stored ? "Arquivo armazenado" : received ? "Enviado — arquivo ainda não disponível" : "Não enviado",
  };
}
