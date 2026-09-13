import { GetObjectCommand } from "@aws-sdk/client-s3";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";
import { NextResponse } from "next/server";
import {
  ForbiddenError,
  UnauthorizedError,
  requireAdminSession,
} from "@/features/auth/server/require-admin-session";
import { canAccessSdrDocuments } from "@/features/sdr/server/document-access";
import {
  isSdrDocumentSigningConfigured,
  resolveSdrDocumentDownload,
} from "@/features/sdr/server/document-download";
import { getObjectStorageS3Client } from "@/features/storage/server/s3-client";
import { prisma } from "@/lib/db";

type RouteContext = { params: Promise<{ id: string }> };

function fileNameFromStorageKey(storageKey: string): string {
  const base = storageKey.split("/").pop()?.trim() || "documento";
  return base.replace(/["\\\r\n]/g, "_").slice(0, 180);
}

function attachmentDisposition(fileName: string): string {
  const encoded = encodeURIComponent(fileName);
  return `attachment; filename="${fileName}"; filename*=UTF-8''${encoded}`;
}

/**
 * Signed GET URL for an SdrDocument storage object.
 * CRM operators (LEAD_ROLES, including LEAD_MANAGER) may open signed URLs.
 * Bucket and key come from persisted document rows — never from the request.
 */
export async function GET(_req: Request, context: RouteContext) {
  try {
    const { user } = await requireAdminSession();
    if (!canAccessSdrDocuments(user.role)) {
      throw new ForbiddenError();
    }

    const { id } = await context.params;
    if (!id) {
      return NextResponse.json({ error: "Document id is required" }, { status: 400 });
    }

    const doc = await prisma.sdrDocument.findUnique({
      where: { id },
      select: {
        id: true,
        leadId: true,
        storageKey: true,
        storageBucket: true,
        storageStatus: true,
        mimeType: true,
      },
    });

    if (!doc) {
      return NextResponse.json({ error: "Documento não encontrado" }, { status: 404 });
    }

    const resolved = resolveSdrDocumentDownload({
      storageKey: doc.storageKey,
      storageBucket: doc.storageBucket,
      storageStatus: doc.storageStatus,
      legacyReadBucket: process.env.STORAGE_BUCKET_NAME,
    });

    if (!resolved.ok) {
      return NextResponse.json(
        {
          code: resolved.code,
          error: "Arquivo ainda não está disponível internamente.",
        },
        { status: 409 },
      );
    }

    if (!isSdrDocumentSigningConfigured()) {
      return NextResponse.json(
        {
          error:
            "Private document storage is not configured. Set STORAGE_ENDPOINT, STORAGE_ACCESS_KEY, STORAGE_SECRET_KEY.",
        },
        { status: 501 },
      );
    }

    try {
      const client = getObjectStorageS3Client();
      const fileName = fileNameFromStorageKey(resolved.key);
      const command = new GetObjectCommand({
        Bucket: resolved.bucket,
        Key: resolved.key,
        ResponseContentType: doc.mimeType ?? undefined,
        ResponseContentDisposition: attachmentDisposition(fileName),
      });
      const url = await getSignedUrl(client, command, { expiresIn: 300 });
      return NextResponse.json({
        url,
        expiresIn: 300,
        documentId: doc.id,
        mimeType: doc.mimeType,
        fileName,
      });
    } catch (err) {
      console.error("[sdr/documents/signed-url] presign error:", err);
      return NextResponse.json(
        {
          error:
            "Failed to generate signed URL for private bucket document. Verify storage credentials and that the object key exists.",
        },
        { status: 501 },
      );
    }
  } catch (e) {
    if (e instanceof UnauthorizedError) {
      return NextResponse.json({ error: e.message }, { status: 401 });
    }
    if (e instanceof ForbiddenError) {
      return NextResponse.json({ error: e.message }, { status: 403 });
    }
    throw e;
  }
}
