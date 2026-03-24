import { NextResponse } from "next/server";
import { S3Client, PutObjectCommand } from "@aws-sdk/client-s3";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";
import { auth } from "@/features/auth/server/auth";

export const runtime = "nodejs";

const endpoint = process.env.STORAGE_ENDPOINT;
const bucket = process.env.STORAGE_BUCKET_NAME;
const accessKey = process.env.STORAGE_ACCESS_KEY;
const secretKey = process.env.STORAGE_SECRET_KEY;

export async function POST(req: Request) {
  const session = await auth();
  if (!session?.user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  if (!endpoint || !bucket || !accessKey || !secretKey) {
    return NextResponse.json(
      { error: "Storage not configured. Set STORAGE_* env vars (R2 ou Supabase S3)." },
      { status: 501 }
    );
  }

  try {
    const body = await req.json().catch(() => ({}));
    const prefix = "vehicles";
    const ext = (body.filename as string)?.split(".").pop() || "jpg";
    const key = `${prefix}/${Date.now()}-${Math.random().toString(36).slice(2)}.${ext}`;

    const isSupabaseS3 = endpoint.includes("supabase.co");
    const client = new S3Client({
      region: isSupabaseS3 ? (process.env.STORAGE_S3_REGION ?? "us-east-1") : "auto",
      endpoint,
      forcePathStyle: isSupabaseS3,
      credentials: { accessKeyId: accessKey, secretAccessKey: secretKey },
    });

    const url = await getSignedUrl(
      client,
      new PutObjectCommand({
        Bucket: bucket,
        Key: key,
        ContentType: body.contentType || "image/jpeg",
      }),
      { expiresIn: 3600 }
    );

    const publicBase = process.env.STORAGE_PUBLIC_URL?.replace(/\/$/, "");
    const imageUrl = publicBase ? `${publicBase}/${key}` : url.split("?")[0];

    return NextResponse.json({ url: imageUrl, key, uploadUrl: url });
  } catch (e) {
    console.error("Storage presign error:", e);
    return NextResponse.json({ error: "Failed to generate upload URL" }, { status: 500 });
  }
}
