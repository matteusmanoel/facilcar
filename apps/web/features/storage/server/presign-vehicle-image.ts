import { PutObjectCommand } from "@aws-sdk/client-s3";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";
import {
  getVehicleImagesS3Client,
  getVehicleStorageBucket,
  publicUrlForKey,
} from "./s3-client";

export async function presignVehicleImage(opts: {
  filename: string;
  contentType?: string;
}): Promise<{ uploadUrl: string; publicUrl: string; key: string }> {
  const contentType = opts.contentType ?? "image/jpeg";
  const ext = opts.filename.split(".").pop()?.toLowerCase() ?? "jpg";
  const key = `vehicles/${Date.now()}-${Math.random().toString(36).slice(2)}.${ext}`;
  const client = getVehicleImagesS3Client();
  const command = new PutObjectCommand({
    Bucket: getVehicleStorageBucket(),
    Key: key,
    ContentType: contentType,
  });
  const uploadUrl = await getSignedUrl(client, command, { expiresIn: 300 });
  return { uploadUrl, publicUrl: publicUrlForKey(key), key };
}
