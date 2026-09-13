"use client";

import { useEffect } from "react";
import posthog from "posthog-js";
import { readCookieConsent } from "@/lib/cookie-consent";

let posthogStarted = false;

function initPostHog() {
  const key = process.env.NEXT_PUBLIC_POSTHOG_KEY;
  const host = process.env.NEXT_PUBLIC_POSTHOG_HOST ?? "https://us.i.posthog.com";
  if (!key || posthogStarted || readCookieConsent() !== "accepted") return;
  posthog.init(key, {
    api_host: host,
    person_profiles: "identified_only",
  });
  posthogStarted = true;
}

export function PostHogInit() {
  useEffect(() => {
    initPostHog();
    const onConsent = () => initPostHog();
    window.addEventListener("facilcar-cookie-consent", onConsent);
    return () => window.removeEventListener("facilcar-cookie-consent", onConsent);
  }, []);
  return null;
}
