# STORAGE_SECURITY — Document Storage Strategy

## Existing Storage Infrastructure

| Bucket | Provider | Public | Purpose |
|--------|----------|--------|---------|
| `vehicle-images` | Supabase Storage (S3 API) | ✅ Yes | Vehicle photos — publicly accessible |

The app also supports Cloudflare R2 via S3 SDK (see `features/storage/server/s3-client.ts`). Currently vehicle images use R2 or Supabase Storage depending on env vars.

---

## Required: Private Document Bucket

Create bucket `sdr-documents` with:
- **Public: false** — no anonymous access
- **File size limit**: 20MB per file (PDF, image)
- **Allowed MIME types**: image/jpeg, image/png, image/pdf, image/webp, application/pdf
- **Access**: service_role only (server-side reads), signed URLs for authorized access

### Storage Path Convention

```
sdr-documents/
  {leadId}/
    {documentType}_{timestamp}_{random}.{ext}
```

Example:
```
sdr-documents/clxyz123/cnh_1724628000_a3b2c1.jpg
sdr-documents/clxyz123/comprovante_renda_1724628001_d4e5f6.pdf
```

### Document Types
| Type | Internal enum | Notes |
|------|--------------|-------|
| CNH | `CNH` | Driver license — front/back |
| CRLV | `CRLV` | Vehicle registration |
| Income proof | `INCOME_PROOF` | Holerite, MEI, etc. |
| Residence proof | `RESIDENCE_PROOF` | Comprovante de endereço |
| Other | `OTHER` | Anything else |

---

## Access Control Model

### Worker (SDR service — `service_role`)
- May upload originals to `sdr-documents`
- May read originals during processing (extraction)
- Must NOT log file contents, base64 payloads, or extracted PII

### Admin role (`SUPER_ADMIN`, `ADMIN`)
- May generate signed read URL for original document
- Signed URL expiry: 15 minutes (configurable via `SDR_DOCUMENT_URL_TTL_SECONDS`)

### Lead Manager / Seller (`LEAD_MANAGER`)
- May access extracted structured data (stored in `SdrDocument.extractedJson`)
- **May NOT** generate signed URL for original file
- Web panel shows: "Documento recebido — tipo: CNH | dados extraídos disponíveis"

### Public / Anonymous
- No access to `sdr-documents` bucket or any document metadata

---

## Signed URL Generation Pattern

```typescript
// apps/web / admin API
async function getDocumentSignedUrl(documentId: string, session: Session): Promise<string> {
  if (!isAdminRole(session.user.role)) throw new ForbiddenError();
  const doc = await prisma.sdrDocument.findUnique({ where: { id: documentId } });
  if (!doc) throw new NotFoundError();
  return supabaseAdmin.storage
    .from('sdr-documents')
    .createSignedUrl(doc.storageKey, 900); // 15 min
}
```

---

## Retention Policy Implementation

| Scenario | Retention Rule | Implementation |
|----------|----------------|---------------|
| Lead status = WON | Documents permanent | No expiry, separate lifecycle flag |
| Lead status = LOST / SPAM / expired | 180-day from upload | Scheduled cleanup job |
| Conversation messages | 180-day for PII content | Message.deletedAt or cron job |

**MVP approach**: Tag documents with `retentionPolicy: "permanent" | "180_days"` in `SdrDocument`. Implement actual cleanup as a background cron job (Wave 8+). Do NOT implement automatic deletion before go-live — data must be preserved during initial operation.

---

## Supabase Storage vs R2

**Recommendation for SDR documents**: Use Supabase Storage for `sdr-documents`.

Rationale:
- Already integrated (S3-compatible API via `@aws-sdk/client-s3`)
- Private bucket with RLS-via-service-role is the standard Supabase pattern
- Avoids introducing a second storage provider for a different use case
- Signed URLs available natively

The existing `s3-client.ts` can be extended with a second client pointing to the same Supabase Storage endpoint but a different bucket.

---

## Security Checklist

- [ ] `sdr-documents` bucket created with `public: false`
- [ ] No public RLS policy on `sdr-documents`
- [ ] service_role key only on server side (never in browser)
- [ ] CPF/renda masked in UI (digits 4-6 only visible: `***.456.789-**`)
- [ ] Document base64 NOT logged (log only hash + storage key)
- [ ] Signed URL expiry ≤ 15 minutes
- [ ] `LEAD_MANAGER` role cannot generate signed URLs
- [ ] OpenAI API calls with document content: check org-level data retention policy
- [ ] Original documents NOT included in LLM context after extraction
