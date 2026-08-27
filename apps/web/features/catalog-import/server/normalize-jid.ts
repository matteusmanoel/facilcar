export function normalizeRemoteJid(remoteJid: string | null | undefined): string {
  if (!remoteJid) return "";
  let jid = remoteJid.trim().toLowerCase();
  // strip whatsapp server suffixes
  jid = jid.replace(/@s\.whatsapp\.net$/i, "").replace(/@g\.us$/i, "").replace(/@lid$/i, "");
  // strip device suffix e.g. 5511999:12
  const beforeColon = jid.split(":")[0] ?? jid;
  jid = beforeColon;
  // keep digits for phone JIDs
  const digits = jid.replace(/\D/g, "");
  return digits || jid;
}

export function buildSessionKey(instance: string, normalizedJid: string): string {
  return `${instance}|${normalizedJid}`;
}

export function parseAllowedJids(raw: string | undefined): Set<string> {
  const set = new Set<string>();
  if (!raw?.trim()) return set;
  for (const part of raw.split(",")) {
    const n = normalizeRemoteJid(part);
    if (n) set.add(n);
  }
  return set;
}

export function isJidAllowed(normalizedJid: string, allowed: Set<string>): boolean {
  if (!normalizedJid) return false;
  if (allowed.size === 0) return false;
  if (allowed.has(normalizedJid)) return true;
  // allow suffix match for longer/shorter country codes / missing mobile 9
  for (const a of allowed) {
    if (normalizedJid.endsWith(a) || a.endsWith(normalizedJid)) return true;
  }
  return false;
}

/** Peer identities from WA key (prefer phone alt when chat is @lid). */
export function peerIdentityCandidates(
  remoteJid: string | null | undefined,
  remoteJidAlt?: string | null | undefined,
): string[] {
  const out: string[] = [];
  for (const raw of [remoteJidAlt, remoteJid]) {
    const n = normalizeRemoteJid(raw);
    if (n && !out.includes(n)) out.push(n);
  }
  return out;
}

export function isAnyJidAllowed(candidates: string[], allowed: Set<string>): boolean {
  return candidates.some((c) => isJidAllowed(c, allowed));
}

/** Prefer E.164-ish digits over opaque LID ids for sessionKey / storage. */
export function preferredPeerJid(candidates: string[]): string {
  const phone = candidates.find((c) => /^\d{10,15}$/.test(c));
  return phone ?? candidates[0] ?? "";
}
