import { createHash } from "node:crypto";
import { prisma } from "@/lib/db";
import { uploadVehicleImageBuffer } from "@/features/storage/server/upload-vehicle-image";
import { isVehicleStorageConfigured } from "@/features/storage/server/s3-client";

const MAX_BYTES = 15 * 1024 * 1024;
const ALLOWED_MIME = new Set(["image/jpeg", "image/jpg", "image/png", "image/webp", "image/gif"]);

function extFromMime(mime: string): string {
  if (mime.includes("png")) return "png";
  if (mime.includes("webp")) return "webp";
  if (mime.includes("gif")) return "gif";
  return "jpg";
}

async function downloadFromEvolution(mediaRef: unknown): Promise<{
  bytes: Buffer;
  mimeType: string;
}> {
  const base = process.env.EVOLUTION_API_URL?.replace(/\/$/, "");
  const key = process.env.EVOLUTION_API_KEY;
  const instance = process.env.EVOLUTION_INSTANCE ?? "facilcar";
  if (!base || !key) throw new Error("EVOLUTION_API_URL/EVOLUTION_API_KEY not configured");

  const ref = mediaRef as { type?: string; message?: Record<string, unknown> } | null;
  const body = {
    message: {
      key: {},
      message: ref?.message ? { [ref.type ?? "imageMessage"]: ref.message } : {},
    },
    convertToMp4: false,
  };

  const res = await fetch(`${base}/chat/getBase64FromMediaMessage/${instance}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      apikey: key,
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const t = await res.text();
    throw new Error(`Evolution media download failed: ${res.status} ${t.slice(0, 200)}`);
  }
  const json = (await res.json()) as { base64?: string; mimetype?: string };
  if (!json.base64) throw new Error("Evolution media response missing base64");
  const bytes = Buffer.from(json.base64, "base64");
  const mimeType = json.mimetype ?? "image/jpeg";
  return { bytes, mimeType };
}

export async function processItemMedia(itemId: string): Promise<{ warnings: string[] }> {
  const warnings: string[] = [];
  const assets = await prisma.catalogMediaAsset.findMany({
    where: { importItemId: itemId, status: { in: ["PENDING", "FAILED"] } },
    orderBy: { sortOrder: "asc" },
  });

  if (!isVehicleStorageConfigured() && assets.length) {
    warnings.push("storage_not_configured");
  }

  for (const asset of assets) {
    try {
      if (!asset.eventId) {
        await prisma.catalogMediaAsset.update({
          where: { id: asset.id },
          data: { status: "FAILED", error: "missing_event" },
        });
        warnings.push(`media_failed:${asset.id}`);
        continue;
      }
      const event = await prisma.catalogImportEvent.findUnique({ where: { id: asset.eventId } });
      if (!event?.mediaRef) {
        await prisma.catalogMediaAsset.update({
          where: { id: asset.id },
          data: { status: "FAILED", error: "missing_media_ref" },
        });
        warnings.push(`media_failed:${asset.id}`);
        continue;
      }

      const { bytes, mimeType } = await downloadFromEvolution(event.mediaRef);
      if (bytes.byteLength > MAX_BYTES) throw new Error("media_too_large");
      if (!ALLOWED_MIME.has(mimeType.toLowerCase())) throw new Error(`unsupported_mime:${mimeType}`);

      const sha256 = createHash("sha256").update(bytes).digest("hex");
      let blob = await prisma.catalogMediaBlob.findUnique({ where: { sha256 } });
      if (blob) {
        await prisma.catalogMediaAsset.update({
          where: { id: asset.id },
          data: { blobId: blob.id, status: "SKIPPED_DEDUPED", error: null },
        });
        continue;
      }

      if (!isVehicleStorageConfigured()) {
        throw new Error("storage_not_configured");
      }
      const uploaded = await uploadVehicleImageBuffer({
        bytes,
        contentType: mimeType,
        ext: extFromMime(mimeType),
      });
      blob = await prisma.catalogMediaBlob.create({
        data: {
          sha256,
          storageKey: uploaded.key,
          publicUrl: uploaded.publicUrl,
          mimeType,
          byteSize: bytes.byteLength,
        },
      });
      await prisma.catalogMediaAsset.update({
        where: { id: asset.id },
        data: { blobId: blob.id, status: "UPLOADED", error: null },
      });
      await prisma.catalogImportEvent.update({
        where: { id: event.id },
        data: { mediaStatus: "UPLOADED" },
      });
    } catch (e) {
      const msg = e instanceof Error ? e.message : "media_error";
      await prisma.catalogMediaAsset.update({
        where: { id: asset.id },
        data: { status: "FAILED", error: msg.slice(0, 500) },
      });
      warnings.push(`media_failed:${asset.id}:${msg}`);
    }
  }

  return { warnings };
}
