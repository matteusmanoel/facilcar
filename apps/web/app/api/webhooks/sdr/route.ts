import { NextRequest, NextResponse } from "next/server";
import { ingestSdrWebhook } from "@/features/sdr/server/ingest";

export const runtime = "nodejs";

const MAX_BODY = 2_000_000;

function assertSdrSecret(req: NextRequest): boolean {
  const expected = process.env.SDR_WEBHOOK_SECRET;
  if (!expected) return false;
  const header = req.headers.get("x-sdr-secret")?.trim() ?? "";
  return header.length > 0 && header === expected;
}

export async function POST(req: NextRequest) {
  if (!assertSdrSecret(req)) {
    return NextResponse.json({ ok: false, error: "unauthorized" }, { status: 401 });
  }

  const raw = await req.text();
  if (raw.length > MAX_BODY) {
    return NextResponse.json({ ok: false, error: "payload_too_large" }, { status: 413 });
  }

  let payload: unknown;
  try {
    payload = raw ? JSON.parse(raw) : {};
  } catch {
    return NextResponse.json({ ok: false, error: "invalid_json" }, { status: 400 });
  }

  try {
    const result = await ingestSdrWebhook(payload);
    return NextResponse.json(result);
  } catch (e) {
    console.error("[sdr] ingest error", e);
    return NextResponse.json({ ok: false, error: "ingest_failed" }, { status: 503 });
  }
}

export async function GET() {
  return NextResponse.json({
    ok: true,
    service: "facilcar-sdr-webhook",
  });
}
