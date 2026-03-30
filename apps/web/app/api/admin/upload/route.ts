import { NextRequest, NextResponse } from "next/server";
import { S3Client, PutObjectCommand } from "@aws-sdk/client-s3";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";

const STORAGE_ENDPOINT = process.env.STORAGE_ENDPOINT;
const STORAGE_ACCESS_KEY = process.env.STORAGE_ACCESS_KEY;
const STORAGE_SECRET_KEY = process.env.STORAGE_SECRET_KEY;
const STORAGE_BUCKET_NAME = process.env.STORAGE_BUCKET_NAME;
const STORAGE_S3_REGION = process.env.STORAGE_S3_REGION ?? "auto";
const STORAGE_PUBLIC_URL = process.env.STORAGE_PUBLIC_URL;

function isConfigured() {
  return !!(STORAGE_ENDPOINT && STORAGE_ACCESS_KEY && STORAGE_SECRET_KEY && STORAGE_BUCKET_NAME);
}

export async function GET(req: NextRequest) {
  if (!isConfigured()) {
    return NextResponse.json(
      { error: "Storage not configured. Set STORAGE_ENDPOINT, STORAGE_ACCESS_KEY, STORAGE_SECRET_KEY, STORAGE_BUCKET_NAME." },
      { status: 503 },
    );
  }

  const { searchParams } = req.nextUrl;
  const filename = searchParams.get("filename");
  const contentType = searchParams.get("type") ?? "image/jpeg";

  if (!filename) {
    return NextResponse.json({ error: "filename is required" }, { status: 400 });
  }

  const ext = filename.split(".").pop()?.toLowerCase() ?? "jpg";
  const key = `vehicles/${Date.now()}-${Math.random().toString(36).slice(2)}.${ext}`;

  const client = new S3Client({
    region: STORAGE_S3_REGION,
    endpoint: STORAGE_ENDPOINT,
    credentials: {
      accessKeyId: STORAGE_ACCESS_KEY!,
      secretAccessKey: STORAGE_SECRET_KEY!,
    },
    forcePathStyle: true,
  });

  const command = new PutObjectCommand({
    Bucket: STORAGE_BUCKET_NAME,
    Key: key,
    ContentType: contentType,
  });

  try {
    const uploadUrl = await getSignedUrl(client, command, { expiresIn: 300 });
    const publicUrl = STORAGE_PUBLIC_URL
      ? `${STORAGE_PUBLIC_URL.replace(/\/$/, "")}/${key}`
      : `${STORAGE_ENDPOINT}/${STORAGE_BUCKET_NAME}/${key}`;

    return NextResponse.json({ uploadUrl, publicUrl, key });
  } catch (err) {
    console.error("[upload] presign error:", err);
    return NextResponse.json({ error: "Failed to generate upload URL" }, { status: 500 });
  }
}
