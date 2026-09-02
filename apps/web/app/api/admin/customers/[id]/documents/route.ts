import { PutObjectCommand } from "@aws-sdk/client-s3";
import { NextResponse } from "next/server";
import {
  ForbiddenError,
  UnauthorizedError,
  requireAdminRole,
} from "@/features/auth/server/rbac";
import { CUSTOMER_WRITE_ROLES } from "@/features/auth/rbac-config";
import { createCustomerDocumentRecord } from "@/features/admin/server/customers";
import { canAccessCustomerDocuments } from "@/features/sdr/server/document-access";
import {
  getVehicleImagesS3Client,
  getVehicleStorageBucket,
  isVehicleStorageConfigured,
} from "@/features/storage/server/s3-client";
import { prisma } from "@/lib/db";

export const runtime = "nodejs";

const MAX_BYTES = 15 * 1024 * 1024;
const ALLOWED_TYPES = new Set(["CONTRACT", "OTHER"]);

type RouteContext = { params: Promise<{ id: string }> };

function safeFileName(name: string): string {
  const base = name.replace(/[/\\]/g, "_").trim() || "documento";
  return base.slice(0, 180);
}

export async function POST(req: Request, context: RouteContext) {
  try {
    const ctx = await requireAdminRole(CUSTOMER_WRITE_ROLES);
    if (!canAccessCustomerDocuments(ctx.user.role)) {
      throw new ForbiddenError();
    }

    const { id: customerId } = await context.params;
    if (!customerId) {
      return NextResponse.json({ error: "Customer id is required" }, { status: 400 });
    }

    const customer = await prisma.customer.findUnique({
      where: { id: customerId },
      select: { id: true },
    });
    if (!customer) {
      return NextResponse.json({ error: "Cliente não encontrado" }, { status: 404 });
    }

    if (!isVehicleStorageConfigured()) {
      return NextResponse.json(
        { error: "Storage privado não configurado." },
        { status: 501 },
      );
    }

    const form = await req.formData();
    const file = form.get("file");
    if (!(file instanceof File) || file.size === 0) {
      return NextResponse.json({ error: "Arquivo obrigatório" }, { status: 400 });
    }
    if (file.size > MAX_BYTES) {
      return NextResponse.json({ error: "Arquivo maior que 15 MB" }, { status: 413 });
    }

    const documentTypeRaw = String(form.get("documentType") ?? "CONTRACT").toUpperCase();
    const documentType = ALLOWED_TYPES.has(documentTypeRaw) ? documentTypeRaw : "OTHER";
    const fileName = safeFileName(file.name);
    const mimeType = file.type || "application/octet-stream";
    const body = Buffer.from(await file.arrayBuffer());
    const key = `customer-documents/${customerId}/${Date.now()}_${fileName}`;

    const client = getVehicleImagesS3Client();
    await client.send(
      new PutObjectCommand({
        Bucket: getVehicleStorageBucket(),
        Key: key,
        Body: body,
        ContentType: mimeType,
      }),
    );

    const created = await createCustomerDocumentRecord({
      customerId,
      fileName,
      storageKey: key,
      mimeType,
      byteSize: body.length,
      documentType,
      uploadedByUserId: ctx.user.id,
    });

    return NextResponse.json({ ok: true, id: created.id });
  } catch (e) {
    if (e instanceof UnauthorizedError) {
      return NextResponse.json({ error: e.message }, { status: 401 });
    }
    if (e instanceof ForbiddenError) {
      return NextResponse.json({ error: e.message }, { status: 403 });
    }
    console.error("[customers/documents] upload error:", e);
    return NextResponse.json({ error: "Falha no upload" }, { status: 500 });
  }
}
