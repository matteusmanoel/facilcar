export const COOKIE_CONSENT_STORAGE_KEY = "facilcar-cookie-consent";

export type CookieConsentChoice = "accepted" | "essential";

export const COOKIE_BANNER_OFFSET_CLASS =
  "bottom-[calc(1.25rem+var(--cookie-banner-offset,0px))]";

export function readCookieConsent(): CookieConsentChoice | null {
  if (typeof window === "undefined") return null;
  const value = window.localStorage.getItem(COOKIE_CONSENT_STORAGE_KEY);
  if (value === "accepted" || value === "essential") return value;
  return null;
}

export function writeCookieConsent(choice: CookieConsentChoice) {
  window.localStorage.setItem(COOKIE_CONSENT_STORAGE_KEY, choice);
  window.dispatchEvent(new Event("facilcar-cookie-consent"));
}
