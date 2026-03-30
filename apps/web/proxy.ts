import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

/**
 * Auth.js v5 (next-auth@5) uses `authjs.session-token` / `__Secure-authjs.session-token`,
 * not the v4 `next-auth.session-token` names. Chunked JWT cookies use `.0`, `.1`, etc.
 * @see @auth/core/lib/utils/cookie.js — defaultCookies()
 */
const SESSION_COOKIE_NAME_RE =
  /^(?:__Secure-)?(?:authjs|next-auth)\.session-token(?:\.\d+)?$/;

function hasSessionCookie(req: NextRequest): boolean {
  for (const { name } of req.cookies.getAll()) {
    if (SESSION_COOKIE_NAME_RE.test(name)) return true;
  }
  return false;
}

export default function proxy(req: NextRequest) {
  const path = req.nextUrl.pathname;
  const isAdmin = path.startsWith("/admin");
  const isAdminLogin = path.startsWith("/admin/login");

  if (!isAdmin) {
    return NextResponse.next();
  }

  if (isAdminLogin) {
    return NextResponse.next();
  }

  if (!hasSessionCookie(req)) {
    const login = new URL("/admin/login", req.nextUrl.origin);
    login.searchParams.set("callbackUrl", path);
    return NextResponse.redirect(login);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/admin/:path*"],
};
