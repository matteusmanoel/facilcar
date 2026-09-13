/** First customer bubble for "Mensagem original" — never a copy of juliaSummary. */

function isDebugDump(text: string): boolean {
  return /\bIntent:\s/i.test(text) && (/\bFacts:\s/i.test(text) || /\bBusiness:\s/i.test(text));
}

export function originalCustomerMessage(input: {
  message?: string | null;
  juliaSummary?: string | null;
  firstInbound?: string | null;
}): string | null {
  const summary = (input.juliaSummary ?? "").trim();
  const candidates = [input.firstInbound, input.message];
  for (const raw of candidates) {
    const text = (raw ?? "").trim();
    if (!text) continue;
    if (summary && text === summary) continue;
    if (isDebugDump(text)) continue;
    if (/^intent:/i.test(text)) continue;
    return text;
  }
  return null;
}
