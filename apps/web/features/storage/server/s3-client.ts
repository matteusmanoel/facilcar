import { S3Client } from "@aws-sdk/client-s3";

export function isObjectStorageConfigured(): boolean {
  return !!(
    process.env.STORAGE_ENDPOINT &&
    process.env.STORAGE_ACCESS_KEY &&
    process.env.STORAGE_SECRET_KEY
  );
}

export function getObjectStorageS3Client(): S3Client {
  if (!isObjectStorageConfigured()) {
    throw new Error(
      "Storage not configured. Set STORAGE_ENDPOINT, STORAGE_ACCESS_KEY, STORAGE_SECRET_KEY.",
    );
  }
  return new S3Client({
    region: process.env.STORAGE_S3_REGION ?? "auto",
    endpoint: process.env.STORAGE_ENDPOINT,
    credentials: {
      accessKeyId: process.env.STORAGE_ACCESS_KEY!,
      secretAccessKey: process.env.STORAGE_SECRET_KEY!,
    },
    forcePathStyle: true,
  });
}

export function isVehicleStorageConfigured(): boolean {
  return !!(isObjectStorageConfigured() && process.env.STORAGE_BUCKET_NAME);
}

export function getVehicleStorageBucket(): string {
  const bucket = process.env.STORAGE_BUCKET_NAME;
  if (!bucket) throw new Error("STORAGE_BUCKET_NAME is not set");
  return bucket;
}

export function getVehicleImagesS3Client(): S3Client {
  if (!isVehicleStorageConfigured()) {
    throw new Error(
      "Storage not configured. Set STORAGE_ENDPOINT, STORAGE_ACCESS_KEY, STORAGE_SECRET_KEY, STORAGE_BUCKET_NAME.",
    );
  }
  return new S3Client({
    region: process.env.STORAGE_S3_REGION ?? "auto",
    endpoint: process.env.STORAGE_ENDPOINT,
    credentials: {
      accessKeyId: process.env.STORAGE_ACCESS_KEY!,
      secretAccessKey: process.env.STORAGE_SECRET_KEY!,
    },
    forcePathStyle: true,
  });
}

export function publicUrlForKey(key: string): string {
  const publicBase = process.env.STORAGE_PUBLIC_URL?.replace(/\/$/, "");
  if (publicBase) return `${publicBase}/${key}`;
  const endpoint = process.env.STORAGE_ENDPOINT?.replace(/\/$/, "");
  const bucket = getVehicleStorageBucket();
  return `${endpoint}/${bucket}/${key}`;
}
