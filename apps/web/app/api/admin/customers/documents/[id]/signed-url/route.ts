import { GetObjectCommand } from "@aws-sdk/client-s3";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";
import { NextResponse } from "next/server";
import {
  ForbiddenError,
  UnauthorizedError,
  requireAdminSession,
} from "@/features/auth/server/require-admin-session";
import { canAccessCustomerDocuments } from "@/features/sdr/server/document-access";
import {
  getVehicleImagesS3Client,
  getVehicleStorageBucket,
  isVehicleStorageConfigured,
} from "@/features/storage/server/s3-client";
import { prisma } from "@/lib/db";

type RouteContext = { params: Promise<{ id: string }> };

export async function GET(_req: Request, context: RouteContext) {
  try {
    const { user } = await requireAdminSession();
    if (!canAccessCustomerDocuments(user.role)) {
      throw new ForbiddenError();
    }

    const { id } = await context.params;
    if (!id) {
      return NextResponse.json({ error: "Document id is required" }, { status: 400 });
    }

    const doc = await prisma.customerDocument.findUnique({
      where: { id },
      select: { id: true, storageKey: true, mimeType: true, fileName: true },
    });

    if (!doc) {
      return NextResponse.json({ error: "Documento não encontrado" }, { status: 404 });
    }

    if (!isVehicleStorageConfigured()) {
      return NextResponse.json(
        { error: "Private document storage is not configured." },
        { status: 501 },
      );
    }

    try {
      const client = getVehicleImagesS3Client();
      const command = new GetObjectCommand({
        Bucket: getVehicleStorageBucket(),
        Key: doc.storageKey,
        ResponseContentType: doc.mimeType ?? undefined,
        ResponseContentDisposition: `attachment; filename="${doc.fileName.replace(/"/g, "")}"`,
      });
      const url = await getSignedUrl(client, command, { expiresIn: 300 });
      return NextResponse.json({
        url,
        expiresIn: 300,
        documentId: doc.id,
        mimeType: doc.mimeType,
        fileName: doc.fileName,
      });
    } catch (err) {
      console.error("[customers/documents/signed-url] presign error:", err);
      return NextResponse.json(
        { error: "Failed to generate signed URL for private bucket document." },
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
