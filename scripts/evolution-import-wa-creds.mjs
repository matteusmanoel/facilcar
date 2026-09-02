#!/usr/bin/env node
/**
 * Import WhatsApp Web companion creds into local Evolution (passkey workaround).
 *
 * Usage (from repo root):
 *   node scripts/evolution-import-wa-creds.mjs path/to/wa-session.json [--yes]
 *
 * Accepts:
 *   - Baileys creds object / { creds: {...} }
 *   - Extractor v1.2 dump (noiseCandidates + identityKey + id/lid) from
 *     whatsapp-session-extractor / Passkey Linker export
 *
 * Tries noiseCandidates until Evolution reaches state "open" (or candidates exhausted).
 * Does NOT print secrets. Requires Docker: facilcar-evolution-postgres + API :8081.
 */
import { readFileSync, existsSync } from "node:fs";
import { resolve } from "node:path";
import { execFileSync } from "node:child_process";
import { createInterface } from "node:readline/promises";
import { stdin as input, stdout as output } from "node:process";
import crypto from "node:crypto";

const INSTANCE = process.env.EVOLUTION_INSTANCE || "facilcar";
const API = (process.env.EVOLUTION_API_URL || "http://127.0.0.1:8081").replace(/\/$/, "");
const PG_CONTAINER = process.env.EVOLUTION_PG_CONTAINER || "facilcar-evolution-postgres";
const PG_USER = process.env.POSTGRES_USER || "evolution";
const PG_DB = process.env.POSTGRES_DB || "evolution";
const YES = process.argv.includes("--yes") || process.env.EVOLUTION_IMPORT_YES === "1";

function loadApiKey() {
  const envPath = resolve(process.cwd(), ".env.evolution");
  if (!existsSync(envPath)) throw new Error("Missing .env.evolution");
  for (const line of readFileSync(envPath, "utf8").split("\n")) {
    if (line.startsWith("AUTHENTICATION_API_KEY=")) {
      return line.slice("AUTHENTICATION_API_KEY=".length).trim();
    }
  }
  throw new Error("AUTHENTICATION_API_KEY not found in .env.evolution");
}

function genCurveKeyPair() {
  const { publicKey, privateKey } = crypto.generateKeyPairSync("x25519");
  const pub = publicKey.export({ type: "spki", format: "der" }).subarray(-32);
  const priv = privateKey.export({ type: "pkcs8", format: "der" }).subarray(-32);
  return { private: priv, public: pub };
}

function initAuthCredsSkeleton() {
  return {
    noiseKey: genCurveKeyPair(),
    pairingEphemeralKeyPair: genCurveKeyPair(),
    signedIdentityKey: genCurveKeyPair(),
    signedPreKey: undefined,
    registrationId: 0,
    advSecretKey: crypto.randomBytes(32).toString("base64"),
    processedHistoryMessages: [],
    nextPreKeyId: 1,
    firstUnuploadedPreKeyId: 1,
    accountSyncCounter: 0,
    accountSettings: { unarchiveChats: false },
    registered: false,
    pairingCode: undefined,
    lastPropHash: undefined,
    routingInfo: undefined,
  };
}

function dumpB64(v) {
  return v == null ? undefined : Buffer.from(v, "base64");
}
function dumpKeyPair(o) {
  return o ? { private: dumpB64(o.private), public: dumpB64(o.public) } : undefined;
}

/** Normalize extractor / Passkey Linker export → Contrato A dump. */
function normalizeToWebDump(raw) {
  if (!raw || typeof raw !== "object") throw new Error("Invalid JSON root");
  if (raw.creds && typeof raw.creds === "object") return normalizeToWebDump(raw.creds);

  // Already Contrato A / Baileys-ish
  if (raw.noiseKey && (raw.signedIdentityKey || raw.identityKey) && raw.me?.id) {
    return {
      ...raw,
      signedIdentityKey: raw.signedIdentityKey || raw.identityKey,
    };
  }

  // Extractor v1.2: noiseCandidates + identityKey + id/lid
  if (Array.isArray(raw.noiseCandidates) && raw.identityKey && raw.id) {
    const signedPreKey = raw.signedPreKey?.keyPair
      ? raw.signedPreKey
      : raw.signedPreKey
        ? {
            keyId: raw.signedPreKey.keyId,
            keyPair: {
              private: raw.signedPreKey.private,
              public: raw.signedPreKey.public,
            },
            signature: raw.signedPreKey.signature,
          }
        : undefined;

    return {
      noiseCandidates: raw.noiseCandidates,
      noiseKey: raw.noiseCandidates[0],
      signedIdentityKey: raw.identityKey,
      signedPreKey,
      registrationId: raw.registrationId,
      advSecretKey: raw.advSecretKey,
      me: { id: raw.id, lid: raw.lid || undefined, name: raw.pushName || undefined },
      account: raw.account,
      platform: raw.platform || "android",
      pairingEphemeralKeyPair: raw.pairingEphemeralKeyPair,
      routingInfo: raw.routingInfo,
    };
  }

  if (raw.noiseKey || raw.signedIdentityKey || raw.me) return raw;
  throw new Error(
    "Unrecognized session JSON. Expected Baileys creds or extractor dump (noiseCandidates+identityKey+id).",
  );
}

function buildBaileysCredsFromWebDump(dump) {
  const creds = initAuthCredsSkeleton();
  if (dump.noiseKey) creds.noiseKey = dumpKeyPair(dump.noiseKey);
  if (dump.signedIdentityKey) creds.signedIdentityKey = dumpKeyPair(dump.signedIdentityKey);
  if (dump.pairingEphemeralKeyPair) {
    creds.pairingEphemeralKeyPair = dumpKeyPair(dump.pairingEphemeralKeyPair);
  }
  if (dump.signedPreKey) {
    creds.signedPreKey = {
      keyId: dump.signedPreKey.keyId,
      keyPair: dumpKeyPair(dump.signedPreKey.keyPair),
      signature: dumpB64(dump.signedPreKey.signature),
    };
  }
  if (dump.registrationId != null) creds.registrationId = dump.registrationId;
  if (dump.advSecretKey) creds.advSecretKey = dump.advSecretKey;
  if (dump.me) {
    creds.me = {
      id: dump.me.id,
      lid: dump.me.lid || undefined,
      name: dump.me.name || undefined,
    };
  }
  if (dump.account) {
    creds.account = {
      details: dumpB64(dump.account.details),
      accountSignatureKey: dumpB64(dump.account.accountSignatureKey),
      accountSignature: dumpB64(dump.account.accountSignature),
      deviceSignature: dumpB64(dump.account.deviceSignature),
    };
  }
  if (dump.routingInfo) {
    creds.routingInfo = Buffer.isBuffer(dump.routingInfo)
      ? dump.routingInfo
      : dumpB64(dump.routingInfo);
  }
  creds.platform = dump.platform || "web";
  creds.registered = true;
  return creds;
}

function bufferJsonReplacer(_key, value) {
  if (Buffer.isBuffer(value) || value instanceof Uint8Array || (value && value.type === "Buffer")) {
    return { type: "Buffer", data: Buffer.from(value.data || value).toString("base64") };
  }
  return value;
}

/** Evolution Session.creds = JSON.stringify(JSON.stringify(creds, BufferJSON)). */
function encodeCredsForEvolution(creds) {
  const once = JSON.stringify(creds, bufferJsonReplacer);
  return JSON.stringify(once);
}

function validateDump(dump) {
  const missing = [];
  if (!dump.noiseKey?.private) missing.push("noiseKey");
  if (!dump.signedIdentityKey?.private) missing.push("signedIdentityKey");
  if (!dump.signedPreKey?.keyPair?.private || !dump.signedPreKey?.signature) missing.push("signedPreKey");
  if (dump.registrationId == null) missing.push("registrationId");
  if (!dump.me?.id) missing.push("me.id");
  if (!dump.account?.details || !dump.account?.accountSignature || !dump.account?.deviceSignature) {
    missing.push("account");
  }
  return missing;
}

function psql(sql) {
  return execFileSync(
    "docker",
    [
      "exec",
      "-i",
      PG_CONTAINER,
      "psql",
      "-U",
      PG_USER,
      "-d",
      PG_DB,
      "-v",
      "ON_ERROR_STOP=1",
      "-t",
      "-A",
      "-c",
      sql,
    ],
    { encoding: "utf8" },
  ).trim();
}

async function apiGet(path, key) {
  const res = await fetch(`${API}${path}`, { headers: { apikey: key } });
  const body = await res.json().catch(() => ({}));
  return { status: res.status, body };
}

async function waitState(key, timeoutMs = 20000) {
  const started = Date.now();
  let last = null;
  while (Date.now() - started < timeoutMs) {
    const { body } = await apiGet(`/instance/connectionState/${INSTANCE}`, key);
    last = body?.instance?.state || body?.state || null;
    if (last === "open") return last;
    await new Promise((r) => setTimeout(r, 1500));
  }
  return last;
}

function filterValidNoiseCandidates(candidates) {
  const pkcs8Prefix = Buffer.from("302e020100300506032b656e04220420", "hex");
  const strip = (b) => (b.length === 33 && b[0] === 0x05 ? b.subarray(1) : b);
  const out = [];
  for (const c of candidates) {
    if (!c?.private || !c?.public) continue;
    try {
      const priv = strip(Buffer.from(c.private, "base64"));
      const pub = strip(Buffer.from(c.public, "base64"));
      if (priv.length !== 32 || pub.length !== 32) continue;
      const key = crypto.createPrivateKey({
        key: Buffer.concat([pkcs8Prefix, priv]),
        format: "der",
        type: "pkcs8",
      });
      const derived = crypto
        .createPublicKey(key)
        .export({ type: "spki", format: "der" })
        .subarray(-32);
      if (derived.equals(pub)) out.push(c);
    } catch {
      /* skip invalid */
    }
  }
  return out.length ? out : candidates;
}

function injectEncoded(instanceId, encoded) {
  const tag = `creds_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
  const id = crypto.randomUUID();
  // Logout deletes Session — always UPSERT.
  const sql = `
INSERT INTO "Session" (id, "sessionId", creds, "createdAt")
VALUES ('${id}', '${instanceId}', $${tag}$${encoded}$${tag}$, NOW())
ON CONFLICT ("sessionId") DO UPDATE SET creds = EXCLUDED.creds;
UPDATE "Instance" SET "connectionStatus" = 'close' WHERE id = '${instanceId}';
SELECT length(creds) FROM "Session" WHERE "sessionId" = '${instanceId}';
`;
  return psql(sql);
}

async function main() {
  const file = process.argv.slice(2).find((a) => !a.startsWith("-"));
  if (!file) {
    console.error("Usage: node scripts/evolution-import-wa-creds.mjs <session.json> [--yes]");
    process.exit(1);
  }
  const abs = resolve(file);
  if (!existsSync(abs)) throw new Error(`File not found: ${abs}`);

  const raw = JSON.parse(readFileSync(abs, "utf8"));
  const baseDump = normalizeToWebDump(raw);
  const rawCandidates = Array.isArray(baseDump.noiseCandidates) && baseDump.noiseCandidates.length
    ? baseDump.noiseCandidates
    : [baseDump.noiseKey];
  const candidates = filterValidNoiseCandidates(rawCandidates);

  console.log(`Companion me=${baseDump.me?.id || "(missing)"}`);
  console.log(`noiseCandidates raw=${rawCandidates.length} valid=${candidates.length}`);
  console.log(`extractorVersion=${raw?._meta?.extractorVersion || "n/a"}`);
  console.log("IMPORTANT: close the WhatsApp Web tab for this number BEFORE continuing.");

  const missing = validateDump({ ...baseDump, noiseKey: candidates[0] });
  if (missing.length) throw new Error(`Incomplete dump: missing ${missing.join(", ")}`);

  if (!YES) {
    const rl = createInterface({ input, output });
    const answer = await rl.question(
      `Inject into Evolution instance "${INSTANCE}" and try connect? [y/N] `,
    );
    rl.close();
    if (answer.trim().toLowerCase() !== "y") {
      console.log("Aborted.");
      process.exit(0);
    }
  }

  const instanceId = psql(
    `SELECT id FROM "Instance" WHERE name = '${INSTANCE.replace(/'/g, "''")}' LIMIT 1;`,
  );
  if (!instanceId) throw new Error(`Instance not found: ${INSTANCE}`);
  console.log(`Instance id=${instanceId}`);

  const key = loadApiKey();
  let opened = false;
  let lastState = null;

  for (let i = 0; i < candidates.length; i++) {
    const dump = { ...baseDump, noiseKey: candidates[i] };
    const creds = buildBaileysCredsFromWebDump(dump);
    // Help Baileys treat this as an existing companion identity.
    if (creds.signedIdentityKey?.public && creds.me?.id) {
      const pub = Buffer.isBuffer(creds.signedIdentityKey.public)
        ? creds.signedIdentityKey.public
        : Buffer.from(creds.signedIdentityKey.public);
      const identifierKey =
        pub.length === 32 ? Buffer.concat([Buffer.from([0x05]), pub]) : pub;
      creds.signalIdentities = [
        {
          identifier: { name: String(creds.me.id).split(":")[0] + "@s.whatsapp.net", deviceId: 0 },
          identifierKey,
        },
      ];
    }
    const encoded = encodeCredsForEvolution(creds);
    const len = injectEncoded(instanceId, encoded);
    console.log(`candidate ${i + 1}/${candidates.length}: Session.creds length=${len}`);

    // Prefer restart if available; fall back to connect.
    let connect = await fetch(`${API}/instance/restart/${INSTANCE}`, {
      method: "PUT",
      headers: { apikey: key },
    }).catch(() => null);
    if (!connect || connect.status >= 400) {
      connect = await fetch(`${API}/instance/connect/${INSTANCE}`, {
        headers: { apikey: key },
      });
    }
    console.log(`start HTTP ${connect.status}`);
    lastState = await waitState(key, 35000);
    console.log(`state after candidate ${i + 1}: ${lastState}`);
    if (lastState === "open") {
      opened = true;
      break;
    }
    // Do NOT logout (it deletes Session). Just mark close for next upsert.
    psql(
      `UPDATE "Instance" SET "connectionStatus" = 'close' WHERE id = '${instanceId}';`,
    );
  }

  if (opened) {
    console.log("SUCCESS: instance is open.");
    console.log("Close the WhatsApp Web tab that donated this companion session.");
  } else {
    console.error(`FAILED: last state=${lastState}. Tried ${candidates.length} noise candidate(s).`);
    process.exit(2);
  }
}

main().catch((e) => {
  console.error(e instanceof Error ? e.message : e);
  process.exit(1);
});
