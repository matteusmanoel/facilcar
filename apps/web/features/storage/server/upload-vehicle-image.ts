import { PutObjectCommand } from "@aws-sdk/client-s3";
import {
  getVehicleImagesS3Client,
  getVehicleStorageBucket,
  publicUrlForKey,
} from "./s3-client";

export async function uploadVehicleImageBuffer(opts: {
  bytes: Buffer;
  contentType: string;
  ext?: string;
  keyPrefix?: string;
}): Promise<{ key: string; publicUrl: string }> {
  const ext = (opts.ext ?? "jpg").replace(/^\./, "");
  const key = `${opts.keyPrefix ?? "vehicles"}/${Date.now()}-${Math.random().toString(36).slice(2)}.${ext}`;
  const client = getVehicleImagesS3Client();
  await client.send(
    new PutObjectCommand({
      Bucket: getVehicleStorageBucket(),
      Key: key,
      Body: opts.bytes,
      ContentType: opts.contentType,
    }),
  );
  return { key, publicUrl: publicUrlForKey(key) };
}
