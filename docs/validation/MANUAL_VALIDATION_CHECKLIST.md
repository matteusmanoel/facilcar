# MANUAL_VALIDATION_CHECKLIST (~30–45 min)

## 1. Env
- [ ] `SDR_WEBHOOK_SECRET`, `JULIA_ENABLED=true`, DB URL, Redis, Evolution keys in local `.env`
- [ ] Point Evolution **dev** instance webhook to `https://<preview-or-tunnel>/api/webhooks/sdr` OR local tunnel

## 2. WhatsApp test number `5545988432998`
- [ ] Pair/QR if needed (human)
- [ ] Send “Oi” → Conversation row, **no Lead**
- [ ] Send purchase actionable (Hilux / budget) → QUALIFIED + notification + one confirmation
- [ ] Further customer messages → **no bot reply**
- [ ] Seller types on phone (`fromMe`) → HUMAN_ACTIVE if not already

## 3. CRM
- [ ] Badge/notification for new QUALIFIED
- [ ] Open lead → see `juliaSummary`
- [ ] Click **Assumir** → `assignedToUserId` set; second claim fails

## 4. Documents
- [ ] Send CNH image in financing context → storage + extracted fields (if OpenAI on)
- [ ] ADMIN can open signed URL; LEAD_MANAGER cannot

## 5. Inventory
- [ ] Ask for cars in a budget → only PUBLISHED; missing km said as unavailable

## 6. Kill switch
- [ ] `JULIA_ENABLED=false` → messages stored, no AI replies

## 7. Milton
- [ ] Complete `MILTON_PLAYBOOK_VALIDATION.md` before production traffic
