import { NextRequest, NextResponse } from "next/server";
import {
  ForbiddenError,
  UnauthorizedError,
} from "@/features/auth/server/require-admin-session";
import {
  countUnreadNotifications,
  listUnreadNotifications,
  markNotificationsSeen,
} from "@/features/sdr/server/notifications";

function authErrorResponse(e: unknown) {
  if (e instanceof UnauthorizedError) {
    return NextResponse.json({ error: e.message }, { status: 401 });
  }
  if (e instanceof ForbiddenError) {
    return NextResponse.json({ error: e.message }, { status: 403 });
  }
  throw e;
}

/** Poll unread SDR notifications (LEAD_ROLES). */
export async function GET() {
  try {
    const [notifications, unreadCount] = await Promise.all([
      listUnreadNotifications(50),
      countUnreadNotifications(),
    ]);

    return NextResponse.json({
      unreadCount,
      notifications: notifications.map((n) => ({
        ...n,
        createdAt: n.createdAt.toISOString(),
        seenAt: n.seenAt?.toISOString() ?? null,
      })),
    });
  } catch (e) {
    return authErrorResponse(e);
  }
}

/** Mark notifications as seen. Body: `{ ids: string[] }` */
export async function POST(req: NextRequest) {
  try {
    const body = (await req.json().catch(() => null)) as { ids?: unknown } | null;
    const ids = Array.isArray(body?.ids)
      ? body!.ids.filter((id): id is string => typeof id === "string")
      : [];

    const result = await markNotificationsSeen(ids);
    return NextResponse.json(result);
  } catch (e) {
    return authErrorResponse(e);
  }
}
