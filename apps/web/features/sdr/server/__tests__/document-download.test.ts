import { describe, expect, it } from "vitest";
import {
  resolveSdrDocumentDownload,
  sdrDocumentsBucketFromEnv,
} from "../document-download";

describe("sdrDocumentsBucketFromEnv", () => {
  it("uses SDR_DOCUMENTS_BUCKET and never vehicle-images as upload fallback", () => {
    expect(
      sdrDocumentsBucketFromEnv({
        SDR_DOCUMENTS_BUCKET: "sdr-documents",
        STORAGE_BUCKET_NAME: "vehicle-images",
      }),
    ).toBe("sdr-documents");
    expect(
      sdrDocumentsBucketFromEnv({
        STORAGE_BUCKET_NAME: "vehicle-images",
      }),
    ).toBeNull();
  });
});

describe("resolveSdrDocumentDownload", () => {
  it("uses the persisted private bucket for a stored document", () => {
    const resolved = resolveSdrDocumentDownload({
      storageKey: "sdr-documents/syn-conv/syn-prov_cnh_abc.pdf",
      storageBucket: "sdr-documents",
      storageStatus: "STORED",
    });
    expect(resolved).toEqual({
      ok: true,
      bucket: "sdr-documents",
      key: "sdr-documents/syn-conv/syn-prov_cnh_abc.pdf",
    });
  });

  it("returns internal unavailability when storage is pending", () => {
    const resolved = resolveSdrDocumentDownload({
      storageKey: null,
      storageBucket: "sdr-documents",
      storageStatus: "RETRYABLE_FAILURE",
    });
    expect(resolved.ok).toBe(false);
    if (!resolved.ok) {
      expect(resolved.code).toBe("NOT_STORED");
    }
  });

  it("does not accept an arbitrary bucket from the caller", () => {
    const resolved = resolveSdrDocumentDownload({
      storageKey: "sdr-documents/syn-conv/key.pdf",
      storageBucket: "sdr-documents",
      storageStatus: "STORED",
      requestedBucket: "vehicle-images",
    });
    expect(resolved.ok).toBe(true);
    if (resolved.ok) {
      expect(resolved.bucket).toBe("sdr-documents");
      expect(resolved.bucket).not.toBe("vehicle-images");
    }
  });

  it("reads legacy rows without storageBucket from the historical catalog bucket", () => {
    const resolved = resolveSdrDocumentDownload({
      storageKey: "customer-documents/cust1/cnh_1.pdf",
      storageBucket: null,
      storageStatus: null,
      legacyReadBucket: "vehicle-images",
    });
    expect(resolved).toEqual({
      ok: true,
      bucket: "vehicle-images",
      key: "customer-documents/cust1/cnh_1.pdf",
      legacy: true,
    });
  });

  it("rejects stub keys", () => {
    const resolved = resolveSdrDocumentDownload({
      storageKey: "stub/customer-documents/x",
      storageBucket: "sdr-documents",
      storageStatus: "STORED",
    });
    expect(resolved.ok).toBe(false);
    if (!resolved.ok) {
      expect(resolved.code).toBe("STUB");
    }
  });
});
