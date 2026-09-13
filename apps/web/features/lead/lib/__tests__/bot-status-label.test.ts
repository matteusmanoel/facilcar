import { describe, expect, it } from "vitest";
import {
  botStatusLabel,
  canAssumeConversation,
  canResumeConversation,
} from "../bot-status-label";

describe("botStatusLabel", () => {
  it("D6 labels IA-active statuses as IA atendendo", () => {
    expect(botStatusLabel("BOT_ACTIVE")).toBe("IA atendendo");
    expect(botStatusLabel("QUALIFYING")).toBe("IA atendendo");
    expect(botStatusLabel("READY_FOR_HANDOFF")).toBe("IA atendendo");
  });

  it("D7 labels HANDOFF_SENT as waiting for a human", () => {
    expect(botStatusLabel("HANDOFF_SENT")).toBe("Handoff enviado, aguardando humano");
  });

  it("D8 labels HUMAN_ACTIVE and AI_RESUMED", () => {
    expect(botStatusLabel("HUMAN_ACTIVE")).toBe("Humano ativo");
    expect(botStatusLabel("AI_RESUMED")).toBe("IA reativada");
  });
});

describe("assume/resume visibility", () => {
  it("allows assume until a human owns the thread", () => {
    expect(canAssumeConversation("HANDOFF_SENT")).toBe(true);
    expect(canAssumeConversation("AI_RESUMED")).toBe(true);
    expect(canAssumeConversation(null)).toBe(true);
    expect(canAssumeConversation(null, true)).toBe(false);
    expect(canAssumeConversation("HUMAN_ACTIVE")).toBe(false);
    expect(canAssumeConversation("HUMAN_CLOSED")).toBe(false);
    expect(canAssumeConversation("HANDOFF_SENT", true)).toBe(true);
  });

  it("allows resume only while HUMAN_ACTIVE", () => {
    expect(canResumeConversation("HUMAN_ACTIVE")).toBe(true);
    expect(canResumeConversation("AI_RESUMED")).toBe(false);
    expect(canResumeConversation("HANDOFF_SENT")).toBe(false);
  });
});
