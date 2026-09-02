import { NextRequest, NextResponse } from "next/server";
import { assertCatalogImportSecret } from "@/features/catalog-import/server/auth";
import { ingestEvolutionWebhook } from "@/features/catalog-import/server/ingest-event";

export const runtime = "nodejs";

const MAX_BODY = 2_000_000;

export async function POST(req: NextRequest) {
  if (!assertCatalogImportSecret(req)) {
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
    const result = await ingestEvolutionWebhook(payload);
    return NextResponse.json(result);
  } catch (e) {
    console.error("[catalog-import] ingest error", e);
    return NextResponse.json({ ok: false, error: "ingest_failed" }, { status: 503 });
  }
}

export async function GET() {
  return NextResponse.json({
    ok: true,
    service: "facilcar-catalog-import-webhook",
  });
}
