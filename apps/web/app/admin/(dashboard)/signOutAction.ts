"use server";

import { signOut } from "@/features/auth/server/auth";

export async function adminSignOutAction() {
  await signOut({ redirectTo: "/admin/login" });
}
