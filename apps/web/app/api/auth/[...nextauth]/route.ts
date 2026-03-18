import { handlers } from "@/features/auth/server/auth";

export const runtime = "nodejs";

export const { GET, POST } = handlers;
