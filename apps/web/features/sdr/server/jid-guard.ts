import {
  normalizeRemoteJid,
  peerIdentityCandidates,
  preferredPeerJid,
} from "@/features/catalog-import/server/normalize-jid";

/** WhatsApp group chats use the `@g.us` server suffix. */
export function isGroupJid(remoteJid: string | null | undefined): boolean {
  if (!remoteJid) return false;
  return remoteJid.toLowerCase().includes("@g.us");
}

export function normalizeSdrJid(remoteJid: string | null | undefined): string {
  return normalizeRemoteJid(remoteJid);
}

export function sdrPeerCandidates(
  remoteJid: string | null | undefined,
  remoteJidAlt?: string | null | undefined,
): string[] {
  return peerIdentityCandidates(remoteJid, remoteJidAlt);
}

/** Prefer phone digits (E.164-ish) over opaque LID ids. */
export function sdrPreferredPhone(
  remoteJid: string | null | undefined,
  remoteJidAlt?: string | null | undefined,
): string {
  return preferredPeerJid(peerIdentityCandidates(remoteJid, remoteJidAlt));
}
