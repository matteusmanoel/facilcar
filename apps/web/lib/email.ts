const RESEND_API_KEY = process.env.RESEND_API_KEY;
const RESEND_FROM = process.env.RESEND_FROM_EMAIL;
const NOTIFY_EMAIL = process.env.LEAD_NOTIFY_EMAIL ?? process.env.RESEND_FROM_EMAIL;

export type LeadNotifyPayload = {
  type: string;
  name: string;
  phone: string;
  email?: string | null;
  message?: string | null;
  vehicleTitle?: string | null;
};

export async function sendLeadNotification(payload: LeadNotifyPayload): Promise<boolean> {
  if (!RESEND_API_KEY || !RESEND_FROM || !NOTIFY_EMAIL) return false;
  try {
    const res = await fetch("https://api.resend.com/emails", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${RESEND_API_KEY}`,
      },
      body: JSON.stringify({
        from: RESEND_FROM,
        to: [NOTIFY_EMAIL],
        subject: `[Lead] ${payload.type}: ${payload.name}`,
        text: [
          `Tipo: ${payload.type}`,
          `Nome: ${payload.name}`,
          `Telefone: ${payload.phone}`,
          payload.email ? `Email: ${payload.email}` : "",
          payload.vehicleTitle ? `Veículo: ${payload.vehicleTitle}` : "",
          payload.message ? `Mensagem: ${payload.message}` : "",
        ]
          .filter(Boolean)
          .join("\n"),
      }),
    });
    return res.ok;
  } catch {
    return false;
  }
}
