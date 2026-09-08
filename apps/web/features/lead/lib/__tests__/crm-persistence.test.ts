import { describe, expect, it } from "vitest";
import { originalCustomerMessage } from "../original-message";
import { desiredMonthlyPaymentLabel, isInstallmentMonthCount } from "../desired-monthly-payment";
import { ageFromBirthDate } from "../age-from-birth";
import { documentCrmView } from "../document-crm";
import { selectExplicitPrimary } from "../vehicle-label";

describe("originalCustomerMessage", () => {
  it("shows the first real inbound, not juliaSummary", () => {
    const summary = "Mateus, 32 anos, demonstrou interesse principal na Fiat Strada Working Hard 2018.";
    expect(
      originalCustomerMessage({
        message: summary,
        juliaSummary: summary,
        firstInbound: "Oi, vi as Stradas de vocês",
      }),
    ).toBe("Oi, vi as Stradas de vocês");
  });

  it("does not duplicate the summary when there is no real inbound", () => {
    const summary = "Mateus pretende comprar um Strada.";
    expect(originalCustomerMessage({ message: summary, juliaSummary: summary })).toBeNull();
  });
});

describe("desiredMonthlyPayment", () => {
  it("formats monthly amount with currency", () => {
    expect(desiredMonthlyPaymentLabel(1500)).toBe("Parcela pretendida: até R$ 1.500/mês");
  });

  it("does not treat 1500 as installment month count", () => {
    expect(isInstallmentMonthCount(1500)).toBe(false);
    expect(isInstallmentMonthCount(60)).toBe(true);
  });
});

describe("ageFromBirthDate", () => {
  const birthday = new Date("2026-09-08T13:00:00Z");
  const eve = new Date("2026-09-07T13:00:00Z");

  it("counts birthday today and eve", () => {
    expect(ageFromBirthDate("1994-09-08", birthday)).toBe(32);
    expect(ageFromBirthDate("08/09/1994", eve)).toBe(31);
  });

  it("rejects invalid and missing dates", () => {
    expect(ageFromBirthDate(null, birthday)).toBeNull();
    expect(ageFromBirthDate("31/02/1990", birthday)).toBeNull();
  });
});

describe("documentCrmView", () => {
  it("marks CNH sent but not downloadable while storage is pending", () => {
    const view = documentCrmView({ storageStatus: "PENDING", commerciallyReceived: true });
    expect(view.commerciallyReceived).toBe(true);
    expect(view.downloadable).toBe(false);
  });
});

describe("selectExplicitPrimary", () => {
  it("does not pick the first interest without isPrimary", () => {
    const rows = [
      { id: "a", isPrimary: false },
      { id: "b", isPrimary: true },
    ];
    expect(selectExplicitPrimary(rows)?.id).toBe("b");
    expect(selectExplicitPrimary([{ isPrimary: false }, { isPrimary: false }])).toBeNull();
  });
});
