import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/features/auth/server/auth";
import { isVehicleStorageConfigured } from "@/features/storage/server/s3-client";
import { presignVehicleImage } from "@/features/storage/server/presign-vehicle-image";

export async function GET(req: NextRequest) {
  const session = await auth();
  if (!session?.user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  if (!isVehicleStorageConfigured()) {
    return NextResponse.json(
      {
        error:
          "Storage not configured. Set STORAGE_ENDPOINT, STORAGE_ACCESS_KEY, STORAGE_SECRET_KEY, STORAGE_BUCKET_NAME.",
      },
      { status: 503 },
    );
  }

  const { searchParams } = req.nextUrl;
  const filename = searchParams.get("filename");
  const contentType = searchParams.get("type") ?? "image/jpeg";

  if (!filename) {
    return NextResponse.json({ error: "filename is required" }, { status: 400 });
  }

  try {
    const result = await presignVehicleImage({ filename, contentType });
    return NextResponse.json(result);
  } catch (err) {
    console.error("[upload] presign error:", err);
    return NextResponse.json({ error: "Failed to generate upload URL" }, { status: 500 });
  }
}
