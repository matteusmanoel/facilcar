# VERCEL_IMPACT — SDR Impact on Existing Vercel Deployment

## Current Vercel Configuration

| Parameter | Value | Evidence |
|-----------|-------|----------|
| Project ID | `prj_wsZpNsGxuV81etDVFSzBu4S1ZNvM` | `.vercel/project.json` |
| Org ID | `team_U7JOfalB4XvfDKBwsMVT6Wa3` | `.vercel/project.json` |
| Root Directory | `apps/web` (inferred) | No root `vercel.json`; root has no `next.config.*`; deploys successfully per HANDOFF.md |
| Framework | Next.js 16 | `apps/web/package.json` |
| Build command | `next build` (default) | Standard Vercel Next.js |
| Install command | `npm install` (default) | `postinstall: prisma generate` in apps/web |
| Runtime | Node.js | `export const runtime = "nodejs"` in admin layout |

**INFERRED WITH HIGH CONFIDENCE**: Vercel rootDirectory is set to `apps/web`. The monorepo root has no Next.js configuration (`next.config.*` absent). The current deploy works. This can only work if Vercel is configured to use `apps/web` as root. Confirmed by: no `vercel.json` ignore rules needed since Vercel never sees the root-level files.

---

## Will Adding `apps/sdr` Affect Vercel?

### ✅ SAFE — No Impact

**Adding `apps/sdr/` (Python FastAPI service) to the repository WILL NOT affect the Vercel deployment** because:

1. **Vercel rootDirectory = `apps/web`**: Vercel only processes the `apps/web` subtree. Files outside `apps/web` are completely ignored during build.

2. **No workspace coupling**: The monorepo is NOT a pnpm/Turborepo workspace. There is no shared build pipeline that could accidentally pull in `apps/sdr`.

3. **No root `vercel.json`**: No ignore rules or build settings that span the whole repo.

4. **Python is not a Vercel buildable target** in this project configuration: Even if `apps/sdr` contained a `pyproject.toml`, Vercel would not try to build it.

5. **`package-lock.json` at root is minimal**: Only has root-level scripts. Adding a Python directory does not affect npm installs.

### Conditions That WOULD Cause Issues (and must be avoided)

| Action | Risk | Status |
|--------|------|--------|
| Moving `vercel.json` to root with wrong build settings | Would change Vercel behavior | ❌ Must not do |
| Adding a root `next.config.*` | Vercel might try to build from root | ❌ Must not do |
| Adding `apps/sdr` to root `package.json` scripts in a way that runs during `postinstall` | Could break Vercel install step | ❌ Must not do |
| Installing npm packages at root that have native bindings | Could affect Vercel node_modules | ⚠️ Avoid |

---

## SDR Python Service Deployment (NOT on Vercel)

The SDR Python service (`apps/sdr`) will NOT be deployed to Vercel. It runs on:
- **Local**: Docker Compose (Colima)
- **Staging**: Docker Compose on Supabase staging environment
- **Production**: Docker Compose on Hostinger VPS (D-014)

Vercel remains exclusively for the Next.js web app (`apps/web`).

---

## Webhook Route in Web App

The existing `apps/web/app/api/webhooks/evolution/route.ts` is for catalog import. The SDR needs a separate webhook. Two options:

### Option A: Add new webhook route in Next.js (Recommended for MVP)
Create `apps/web/app/api/webhooks/sdr/route.ts` that:
1. Validates `SDR_WEBHOOK_SECRET`
2. Stores raw payload in DB (idempotent)
3. Enqueues for Python worker via DB polling OR direct HTTP call to SDR API

This keeps the webhook receiver close to the database and avoids VPS public exposure during local dev.

### Option B: Evolution webhook points directly to Python FastAPI on VPS
Production-ready but requires the VPS to be publicly accessible with TLS from day one.

**Recommendation**: Use Option A for MVP dev. Migrate to Option B for production when VPS is provisioned.

---

## Environment Variables for SDR (New, Not in `apps/web/.env`)

The following will be needed in `apps/web/.env` for the webhook relay:
```
SDR_WEBHOOK_SECRET=<random>
SDR_API_URL=http://localhost:8000  # local SDR FastAPI
```

These are ADDITIVE and do not affect existing Vercel env vars.

---

## Conclusion

**SAFE TO PROCEED with `apps/sdr` in monorepo. Zero Vercel deployment risk.**
