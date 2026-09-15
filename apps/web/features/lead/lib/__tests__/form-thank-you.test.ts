import { afterEach, beforeEach, describe, expect, it } from "vitest";
import {
  buildFormThankYouPath,
  consumeFormThankYouToast,
  firstNameFromFullName,
  FORM_THANK_YOU_REDIRECT_MS,
  FORM_THANK_YOU_TOAST_KEY,
  getFormThankYouPreset,
  parseFormThankYouKind,
  queueFormThankYouToast,
} from "../form-thank-you";

function installMemorySessionStorage() {
  const store = new Map<string, string>();
  const memory = {
    getItem: (key: string) => store.get(key) ?? null,
    setItem: (key: string, value: string) => {
      store.set(key, value);
    },
    removeItem: (key: string) => {
      store.delete(key);
    },
    clear: () => store.clear(),
  };
  Object.defineProperty(globalThis, "sessionStorage", {
    value: memory,
    configurable: true,
  });
  Object.defineProperty(globalThis, "window", {
    value: globalThis,
    configurable: true,
  });
}

describe("form thank-you helpers", () => {

  it("parses known kinds and rejects unknown values", () => {
    expect(parseFormThankYouKind("financiamento")).toBe("financiamento");
    expect(parseFormThankYouKind(["venda"])).toBe("venda");
    expect(parseFormThankYouKind("outro")).toBeNull();
    expect(parseFormThankYouKind(undefined)).toBeNull();
  });

  it("extracts a safe first name from a full name", () => {
    expect(firstNameFromFullName("joão da silva")).toBe("João");
    expect(firstNameFromFullName("  Maria  ")).toBe("Maria");
    expect(firstNameFromFullName("A")).toBeNull();
    expect(firstNameFromFullName("<script>")).toBeNull();
    expect(firstNameFromFullName(12)).toBeNull();
  });

  it("builds a thank-you path with kind and first name", () => {
    expect(buildFormThankYouPath({ kind: "venda", name: "Carlos Mendes" })).toBe(
      "/obrigado?tipo=venda&nome=Carlos",
    );
    expect(buildFormThankYouPath({ kind: "financiamento" })).toBe(
      "/obrigado?tipo=financiamento",
    );
  });

  it("keeps the thank-you redirect at ten seconds", () => {
    expect(FORM_THANK_YOU_REDIRECT_MS).toBe(10_000);
  });

  it("personalizes preset copy without inventing a name", () => {
    const preset = getFormThankYouPreset("financiamento");
    expect(preset.title("Ana")).toBe("Obrigado, Ana!");
    expect(preset.title(null)).toBe("Obrigado!");
    expect(preset.redirectHref).toBe("/");
  });
});

describe("form thank-you toast queue", () => {
  beforeEach(() => {
    installMemorySessionStorage();
  });

  afterEach(() => {
    sessionStorage.clear();
  });

  it("stores and consumes the pending toast once", () => {
    queueFormThankYouToast({
      title: "Simulação enviada",
      description: "Em breve um especialista fala com você.",
    });
    expect(sessionStorage.getItem(FORM_THANK_YOU_TOAST_KEY)).toContain("Simulação enviada");
    expect(consumeFormThankYouToast()).toEqual({
      title: "Simulação enviada",
      description: "Em breve um especialista fala com você.",
    });
    expect(consumeFormThankYouToast()).toBeNull();
  });
});
