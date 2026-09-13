import { describe, expect, it } from "vitest";
import { extractSdrQuotedContext } from "../quoted-context";

describe("extractSdrQuotedContext", () => {
  it("reads stanzaId from extendedTextMessage.contextInfo", () => {
    const quoted = extractSdrQuotedContext({
      extendedTextMessage: {
        text: "Gostei dessa",
        contextInfo: {
          stanzaId: "syn-stanza-card-1",
          quotedMessage: { conversation: "Honda Civic 2020 — R$ 89.900" },
        },
      },
    });
    expect(quoted?.stanzaId).toBe("syn-stanza-card-1");
    expect(quoted?.quotedType).toBe("conversation");
    expect(quoted?.quotedText).toContain("Honda Civic");
  });

  it("reads stanzaId from imageMessage.contextInfo (reply on a photo)", () => {
    const quoted = extractSdrQuotedContext({
      imageMessage: {
        caption: "essa",
        contextInfo: {
          stanzaId: "syn-stanza-image-1",
          quotedMessage: { imageMessage: { caption: "Civic 2020" } },
        },
      },
    });
    expect(quoted?.stanzaId).toBe("syn-stanza-image-1");
    expect(quoted?.quotedType).toBe("imageMessage");
  });

  it("reads stanzaId from documentMessage.contextInfo", () => {
    const quoted = extractSdrQuotedContext({
      documentMessage: {
        fileName: "comprovante.pdf",
        contextInfo: { stanzaId: "syn-stanza-doc-1" },
      },
    });
    expect(quoted?.stanzaId).toBe("syn-stanza-doc-1");
  });

  it("reads stanzaId from videoMessage.contextInfo", () => {
    const quoted = extractSdrQuotedContext({
      videoMessage: {
        caption: "olha",
        contextInfo: { stanzaId: "syn-stanza-video-1" },
      },
    });
    expect(quoted?.stanzaId).toBe("syn-stanza-video-1");
  });

  it("reads top-level message.contextInfo", () => {
    const quoted = extractSdrQuotedContext({
      conversation: "quero esse",
      contextInfo: { stanzaId: "syn-stanza-top-1" },
    });
    expect(quoted?.stanzaId).toBe("syn-stanza-top-1");
  });

  it("returns null when there is no reply context", () => {
    expect(extractSdrQuotedContext({ conversation: "oi" })).toBeNull();
    expect(extractSdrQuotedContext(null)).toBeNull();
  });

  it("does not treat quoted media URL as the customer author text field", () => {
    const quoted = extractSdrQuotedContext({
      extendedTextMessage: {
        text: "Gostei dessa",
        contextInfo: {
          stanzaId: "syn-stanza-url-1",
          quotedMessage: {
            conversation: "https://cdn.example.test/vehicle-card.jpg",
          },
        },
      },
    });
    expect(quoted?.stanzaId).toBe("syn-stanza-url-1");
    expect(quoted?.quotedText).toContain("https://cdn.example.test/");
  });
});
