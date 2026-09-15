export type PhoneAccessDecision = {
  allowed: boolean;
  reason: string;
  detail?: string;
};

export type PhoneAccessInput = {
  environment: string;
  policy: string;
  allowlist: string[];
};

const VALID_ENVIRONMENTS = new Set(["sandbox", "staging", "production"]);
const VALID_POLICIES = new Set(["deny_all", "allowlist", "unrestricted"]);

export function normalizePhoneDigits(raw: string | null | undefined): string {
  if (!raw) return "";
  const local = String(raw).trim().split("@")[0] ?? "";
  return local.replace(/\D+/g, "");
}

export function parseAllowlist(raw: string | null | undefined): string[] {
  if (!raw) return [];
  const seen = new Set<string>();
  const out: string[] = [];
  for (const part of String(raw).replace(/\n/g, ",").split(",")) {
    const digits = normalizePhoneDigits(part);
    if (digits && !seen.has(digits)) {
      seen.add(digits);
      out.push(digits);
    }
  }
  return out;
}

export function maskPhone(raw: string | null | undefined): string {
  const digits = normalizePhoneDigits(raw);
  if (!digits) return "****";
  if (digits.length <= 4) return "*".repeat(digits.length);
  return "*".repeat(digits.length - 4) + digits.slice(-4);
}

export function evaluatePhoneAccess(
  phone: string,
  input: PhoneAccessInput,
): PhoneAccessDecision {
  const env = (input.environment || "").trim().toLowerCase();
  const policy = (input.policy || "").trim().toLowerCase();
  const listed = input.allowlist.map(normalizePhoneDigits).filter(Boolean);
  const target = normalizePhoneDigits(phone);
  if (!VALID_ENVIRONMENTS.has(env)) {
    return { allowed: false, reason: "invalid_environment" };
  }
  if (!VALID_POLICIES.has(policy)) {
    return { allowed: false, reason: "invalid_policy" };
  }
  if (!target) {
    return { allowed: false, reason: "missing_phone" };
  }
  if (policy === "deny_all") {
    return { allowed: false, reason: "deny_all" };
  }
  if (policy === "unrestricted") {
    if (env !== "production") {
      return { allowed: false, reason: "unrestricted_requires_production" };
    }
    return { allowed: true, reason: "unrestricted" };
  }
  if (listed.includes(target)) {
    return { allowed: true, reason: "allowlisted" };
  }
  return { allowed: false, reason: "not_in_allowlist" };
}

export function evaluatePhoneAccessFromEnv(phone: string): PhoneAccessDecision {
  return evaluatePhoneAccess(phone, {
    environment: process.env.SDR_ENVIRONMENT ?? "sandbox",
    policy: process.env.SDR_OUTBOUND_POLICY ?? "deny_all",
    allowlist: parseAllowlist(process.env.SDR_OUTBOUND_ALLOWLIST ?? ""),
  });
}
