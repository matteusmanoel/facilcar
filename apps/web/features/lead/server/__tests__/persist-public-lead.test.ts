import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("server-only", () => ({}));

const prisma = vi.hoisted(() => {
  const tx = {
    vehicle: { findUnique: vi.fn() },
    customer: { upsert: vi.fn() },
    lead: { create: vi.fn() },
    leadVehicleInterest: { create: vi.fn() },
    financingRequest: { create: vi.fn() },
    sellRequest: { create: vi.fn() },
    sdrNotification: { create: vi.fn() },
  };
  return {
    ...tx,
    $transaction: vi.fn(async (fn: (client: typeof tx) => unknown) => fn(tx)),
    _tx: tx,
  };
});

vi.mock("@/lib/db", () => ({ prisma }));
vi.mock("next/cache", () => ({ revalidatePath: vi.fn() }));

import { revalidatePath } from "next/cache";
import { persistPublicFormLead } from "../persist-public-lead";

describe("persistPublicFormLead", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    prisma.$transaction.mockImplementation(async (fn: (client: typeof prisma._tx) => unknown) =>
      fn(prisma._tx),
    );
    prisma._tx.vehicle.findUnique.mockResolvedValue({ id: "veh-1" });
    prisma._tx.customer.upsert.mockResolvedValue({ id: "cust-1" });
    prisma._tx.lead.create.mockResolvedValue({ id: "lead-1" });
    prisma._tx.leadVehicleInterest.create.mockResolvedValue({ id: "interest-1" });
    prisma._tx.financingRequest.create.mockResolvedValue({ id: "fin-1" });
    prisma._tx.sellRequest.create.mockResolvedValue({ id: "sell-1" });
    prisma._tx.sdrNotification.create.mockResolvedValue({ id: "notif-1" });
  });

  it("creates customer, lead, sell details and notifies the admin panel in one transaction", async () => {
    const result = await persistPublicFormLead({
      type: "SELL_VEHICLE",
      source: "SELL_PAGE",
      name: "Marina Ferreira",
      phone: "(45) 99999-8888",
      sell: {
        brand: "Toyota",
        model: "Corolla",
        saleMode: "CONSIGNMENT",
        photoUrls: ["https://cdn.example/sell-leads/corolla.jpg"],
      },
      message: "Quero consignar",
    });

    expect(result).toEqual({ leadId: "lead-1", customerId: "cust-1" });
    expect(prisma._tx.customer.upsert).toHaveBeenCalledWith(
      expect.objectContaining({
        where: { phone: "45999998888" },
      }),
    );
    expect(prisma._tx.lead.create).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({
          type: "SELL_VEHICLE",
          status: "NEW",
          channel: "FORM",
          customerId: "cust-1",
          phone: "45999998888",
        }),
      }),
    );
    expect(prisma._tx.sellRequest.create).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({
          leadId: "lead-1",
          brand: "Toyota",
          model: "Corolla",
          photoUrls: ["https://cdn.example/sell-leads/corolla.jpg"],
        }),
      }),
    );
    expect(prisma._tx.sdrNotification.create).toHaveBeenCalledWith(
      expect.objectContaining({
        data: { leadId: "lead-1", type: "NEW_QUALIFIED" },
      }),
    );
    expect(revalidatePath).toHaveBeenCalledWith("/admin/leads");
    expect(revalidatePath).toHaveBeenCalledWith("/admin/clientes");
  });

  it("creates a financing lead with request details and links the catalog vehicle", async () => {
    await persistPublicFormLead({
      type: "FINANCING",
      source: "VEHICLE_PAGE",
      name: "Rafael",
      phone: "45988230845",
      vehicleId: "veh-1",
      financing: {
        monthlyIncome: 5000,
        downPayment: 10000,
        desiredInstallments: 48,
        cpf: "123.456.789-00",
      },
      metadata: { facts: { desired_vehicle_text: "Onix 2022" } },
    });

    expect(prisma._tx.lead.create).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({
          type: "FINANCING",
          status: "NEW",
          vehicleId: "veh-1",
        }),
      }),
    );
    expect(prisma._tx.leadVehicleInterest.create).toHaveBeenCalledWith({
      data: { leadId: "lead-1", vehicleId: "veh-1", isPrimary: true },
    });
    expect(prisma._tx.financingRequest.create).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({
          leadId: "lead-1",
          monthlyIncome: 5000,
          desiredInstallments: 48,
        }),
      }),
    );
  });

  it("still creates a lead when the same phone already has a customer", async () => {
    prisma._tx.customer.upsert.mockResolvedValue({ id: "existing-cust" });

    const first = await persistPublicFormLead({
      type: "FINANCING",
      source: "FINANCING_PAGE",
      name: "Rafael",
      phone: "45988230845",
      financing: { monthlyIncome: 4000, downPayment: 0, desiredInstallments: 36 },
    });
    const second = await persistPublicFormLead({
      type: "FINANCING",
      source: "FINANCING_PAGE",
      name: "Rafael",
      phone: "45988230845",
      financing: { monthlyIncome: 4000, downPayment: 0, desiredInstallments: 48 },
    });

    expect(first.leadId).toBe("lead-1");
    expect(second.leadId).toBe("lead-1");
    expect(prisma._tx.lead.create).toHaveBeenCalledTimes(2);
    expect(prisma._tx.financingRequest.create).toHaveBeenCalledTimes(2);
  });
});
