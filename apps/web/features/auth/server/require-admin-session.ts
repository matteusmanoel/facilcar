import "server-only";

import { prisma } from "@/lib/db";
import { auth } from "./auth";

export class UnauthorizedError extends Error {
  constructor(message = "Não autorizado") {
    super(message);
    this.name = "UnauthorizedError";
  }
}

export class ForbiddenError extends Error {
  constructor(message = "Sem permissão para esta ação") {
    super(message);
    this.name = "ForbiddenError";
  }
}

/** Validates an authenticated, active admin session. Throws UnauthorizedError otherwise. */
export async function requireAdminSession() {
  const session = await auth();
  if (!session?.user?.id) {
    throw new UnauthorizedError();
  }

  const user = await prisma.user.findUnique({
    where: { id: session.user.id },
    select: { id: true, email: true, name: true, role: true, isActive: true },
  });

  if (!user?.isActive) {
    throw new UnauthorizedError("Usuário inativo");
  }

  return { session, user };
}
