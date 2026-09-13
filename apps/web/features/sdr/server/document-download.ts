export const FORBIDDEN_DOCUMENT_BUCKETS = new Set(["vehicle-images"]);

export type SdrDocumentDownloadInput = {
  storageKey?: string | null;
  storageBucket?: string | null;
  storageStatus?: string | null;
  requestedBucket?: string | null;
  legacyReadBucket?: string | null;
};

export type SdrDocumentDownloadResult =
  | { ok: true; bucket: string; key: string; legacy?: true }
  | { ok: false; code: "NOT_STORED" | "STUB" | "MISSING_KEY" };

export function sdrDocumentsBucketFromEnv(
  env: Record<string, string | undefined> = process.env,
): string | null {
  const bucket = (env.SDR_DOCUMENTS_BUCKET || "").trim();
  if (!bucket || FORBIDDEN_DOCUMENT_BUCKETS.has(bucket)) {
    return null;
  }
  return bucket;
}

export function isSdrDocumentSigningConfigured(
  env: Record<string, string | undefined> = process.env,
): boolean {
  return Boolean(
    env.STORAGE_ENDPOINT && env.STORAGE_ACCESS_KEY && env.STORAGE_SECRET_KEY,
  );
}

export function resolveSdrDocumentDownload(
  input: SdrDocumentDownloadInput,
): SdrDocumentDownloadResult {
  const key = (input.storageKey || "").trim();
  if (!key) {
    return { ok: false, code: "NOT_STORED" };
  }
  if (key.startsWith("stub/")) {
    return { ok: false, code: "STUB" };
  }

  const status = (input.storageStatus || "").toUpperCase();
  const persistedBucket = (input.storageBucket || "").trim();

  if (status && status !== "STORED") {
    return { ok: false, code: "NOT_STORED" };
  }

  if (persistedBucket) {
    return { ok: true, bucket: persistedBucket, key };
  }

  // Legacy rows stored before private-bucket tracking. Read-only, never used for new uploads.
  const legacy = (input.legacyReadBucket || "").trim();
  if (legacy && (!status || status === "STORED")) {
    return { ok: true, bucket: legacy, key, legacy: true };
  }

  return { ok: false, code: "NOT_STORED" };
}
