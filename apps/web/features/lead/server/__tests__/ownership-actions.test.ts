import { beforeEach, describe, expect, it, vi } from "vitest";

const { requireAdminRole, ForbiddenError } = vi.hoisted(() => {
  class ForbiddenError extends Error {
    constructor(message = "Sem permissão para esta ação") {
      super(message);
      this.name = "ForbiddenError";
    }
  }
  return { requireAdminRole: vi.fn(), ForbiddenError };
});

const prisma = vi.hoisted(() => {
  const client = {
    lead: {
      findFirst: vi.fn(),
      update: vi.fn(),
      updateMany: vi.fn(),
    },
    conversation: {
      updateMany: vi.fn(),
      findUnique: vi.fn(),
    },
    $transaction: vi.fn(),
  };
  client.$transaction.mockImplementation(async (fn: (tx: typeof client) => unknown) => fn(client));
  return client;
});

vi.mock("@/lib/db", () => ({ prisma }));

vi.mock("next/cache", () => ({
  revalidatePath: vi.fn(),
}));

vi.mock("@/features/auth/server/rbac", () => ({
  ForbiddenError,
  UnauthorizedError: class UnauthorizedError extends Error {
    constructor(message = "Não autorizado") {
      super(message);
      this.name = "UnauthorizedError";
    }
  },
  LEAD_ROLES: ["SUPER_ADMIN", "ADMIN", "LEAD_MANAGER"],
  requireAdminRole,
}));

import {
  claimLeadAction,
  resumeConversationAction,
} from "../conversation-ownership";

const SESSION_USER = { id: "user-alice", role: "LEAD_MANAGER" };
const LEAD_ID = "lead-1";
const CONV_ID = "conv-1";

function handedOffLead(overrides?: {
  assignedToUserId?: string | null;
  conversation?: Record<string, unknown> | null;
}) {
  return {
    id: LEAD_ID,
    assignedToUserId: overrides?.assignedToUserId ?? null,
    conversation:
      overrides && "conversation" in overrides
        ? overrides.conversation
        : {
            id: CONV_ID,
            botStatus: "HANDOFF_SENT",
            ownershipRevision: 0,
            assumedByUserId: null,
            resumedByUserId: null,
          },
  };
}

describe("claimLeadAction / resumeConversationAction", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    requireAdminRole.mockResolvedValue({ user: SESSION_USER });
    prisma.$transaction.mockImplementation(async (fn: (tx: typeof prisma) => unknown) =>
      fn(prisma),
    );
  });

  it("D1 authorized assume sets HUMAN_ACTIVE and assigns the lead without changing status", async () => {
    prisma.lead.findFirst.mockResolvedValue(handedOffLead());
    prisma.conversation.updateMany.mockResolvedValue({ count: 1 });
    prisma.lead.update.mockResolvedValue({ id: LEAD_ID });

    const result = await claimLeadAction(LEAD_ID);

    expect(result).toEqual({ ok: true });
    expect(prisma.conversation.updateMany).toHaveBeenCalledWith({
      where: {
        id: CONV_ID,
        ownershipRevision: 0,
        botStatus: { notIn: ["HUMAN_ACTIVE", "HUMAN_CLOSED"] },
      },
      data: {
        botStatus: "HUMAN_ACTIVE",
        assumedByUserId: SESSION_USER.id,
        assumedAt: expect.any(Date),
        ownershipRevision: { increment: 1 },
      },
    });
    expect(prisma.lead.update).toHaveBeenCalledWith({
      where: { id: LEAD_ID },
      data: { assignedToUserId: SESSION_USER.id },
    });
    const leadData = prisma.lead.update.mock.calls[0][0].data as Record<string, unknown>;
    expect(leadData).not.toHaveProperty("status");
  });

  it("D2 unauthorized assume maps ForbiddenError", async () => {
    requireAdminRole.mockRejectedValue(new ForbiddenError());

    const result = await claimLeadAction(LEAD_ID);

    expect(result).toEqual({ ok: false, error: "Sem permissão para esta ação" });
    expect(prisma.lead.findFirst).not.toHaveBeenCalled();
  });

  it("D3 missing lead is not found", async () => {
    prisma.lead.findFirst.mockResolvedValue(null);

    const result = await claimLeadAction(LEAD_ID);

    expect(result).toEqual({ ok: false, error: "Lead não encontrado" });
    expect(prisma.conversation.updateMany).not.toHaveBeenCalled();
  });

  it("D4 repeat assume by the same user is idempotent", async () => {
    prisma.lead.findFirst.mockResolvedValue(
      handedOffLead({
        assignedToUserId: SESSION_USER.id,
        conversation: {
          id: CONV_ID,
          botStatus: "HUMAN_ACTIVE",
          ownershipRevision: 1,
          assumedByUserId: SESSION_USER.id,
          resumedByUserId: null,
        },
      }),
    );

    const first = await claimLeadAction(LEAD_ID);
    const second = await claimLeadAction(LEAD_ID);

    expect(first).toEqual({ ok: true });
    expect(second).toEqual({ ok: true });
    expect(prisma.conversation.updateMany).not.toHaveBeenCalled();
    expect(prisma.lead.update).not.toHaveBeenCalled();
    expect(prisma.lead.updateMany).not.toHaveBeenCalled();
  });

  it("D5 second distinct human does not silently overwrite", async () => {
    prisma.lead.findFirst.mockResolvedValue(
      handedOffLead({
        assignedToUserId: "user-alice",
        conversation: {
          id: CONV_ID,
          botStatus: "HUMAN_ACTIVE",
          ownershipRevision: 1,
          assumedByUserId: "user-alice",
          resumedByUserId: null,
        },
      }),
    );
    requireAdminRole.mockResolvedValue({ user: { id: "user-bob", role: "LEAD_MANAGER" } });

    const result = await claimLeadAction(LEAD_ID);

    expect(result).toEqual({ ok: false, error: "already_claimed" });
    expect(prisma.conversation.updateMany).not.toHaveBeenCalled();
    expect(prisma.lead.update).not.toHaveBeenCalled();
  });

  it("D9 authorized resume sets AI_RESUMED", async () => {
    prisma.lead.findFirst.mockResolvedValue(
      handedOffLead({
        assignedToUserId: SESSION_USER.id,
        conversation: {
          id: CONV_ID,
          botStatus: "HUMAN_ACTIVE",
          ownershipRevision: 1,
          assumedByUserId: SESSION_USER.id,
          resumedByUserId: null,
        },
      }),
    );
    prisma.conversation.updateMany.mockResolvedValue({ count: 1 });

    const result = await resumeConversationAction(LEAD_ID);

    expect(result).toEqual({ ok: true });
    expect(prisma.conversation.updateMany).toHaveBeenCalledWith({
      where: {
        id: CONV_ID,
        ownershipRevision: 1,
        botStatus: "HUMAN_ACTIVE",
      },
      data: {
        botStatus: "AI_RESUMED",
        resumedByUserId: SESSION_USER.id,
        resumedAt: expect.any(Date),
        resumeReason: "vendedor devolveu para a Júlia",
        ownershipRevision: { increment: 1 },
      },
    });
  });

  it("D10 resume does not set Lead.status to NEW", async () => {
    prisma.lead.findFirst.mockResolvedValue(
      handedOffLead({
        assignedToUserId: SESSION_USER.id,
        conversation: {
          id: CONV_ID,
          botStatus: "HUMAN_ACTIVE",
          ownershipRevision: 1,
          assumedByUserId: SESSION_USER.id,
          resumedByUserId: null,
        },
      }),
    );
    prisma.conversation.updateMany.mockResolvedValue({ count: 1 });

    await resumeConversationAction(LEAD_ID);

    expect(prisma.lead.update).not.toHaveBeenCalled();
    expect(prisma.lead.updateMany).not.toHaveBeenCalled();
  });

  it("D11 records user and timestamp on assume and resume", async () => {
    prisma.lead.findFirst.mockResolvedValue(handedOffLead());
    prisma.conversation.updateMany.mockResolvedValue({ count: 1 });
    prisma.lead.update.mockResolvedValue({ id: LEAD_ID });

    await claimLeadAction(LEAD_ID);
    const assumeData = prisma.conversation.updateMany.mock.calls[0][0].data as {
      assumedByUserId: string;
      assumedAt: Date;
    };
    expect(assumeData.assumedByUserId).toBe(SESSION_USER.id);
    expect(assumeData.assumedAt).toBeInstanceOf(Date);

    prisma.lead.findFirst.mockResolvedValue(
      handedOffLead({
        assignedToUserId: SESSION_USER.id,
        conversation: {
          id: CONV_ID,
          botStatus: "HUMAN_ACTIVE",
          ownershipRevision: 1,
          assumedByUserId: SESSION_USER.id,
          resumedByUserId: null,
        },
      }),
    );
    await resumeConversationAction(LEAD_ID, "retorno autorizado");
    const resumeData = prisma.conversation.updateMany.mock.calls[1][0].data as {
      resumedByUserId: string;
      resumedAt: Date;
      resumeReason: string;
    };
    expect(resumeData.resumedByUserId).toBe(SESSION_USER.id);
    expect(resumeData.resumedAt).toBeInstanceOf(Date);
    expect(resumeData.resumeReason).toBe("retorno autorizado");
  });

  it("D12 assume ignores client-supplied owner id", async () => {
    prisma.lead.findFirst.mockResolvedValue(handedOffLead());
    prisma.conversation.updateMany.mockResolvedValue({ count: 1 });
    prisma.lead.update.mockResolvedValue({ id: LEAD_ID });

    const result = await claimLeadAction(LEAD_ID, "attacker-id");

    expect(result).toEqual({ ok: true });
    expect(prisma.conversation.updateMany).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({ assumedByUserId: SESSION_USER.id }),
      }),
    );
    expect(prisma.lead.update).toHaveBeenCalledWith({
      where: { id: LEAD_ID },
      data: { assignedToUserId: SESSION_USER.id },
    });
    const assumeData = prisma.conversation.updateMany.mock.calls[0][0].data as {
      assumedByUserId: string;
    };
    expect(assumeData.assumedByUserId).not.toBe("attacker-id");
  });
});
